import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Chat, Message, Notebook, SpeechAssessment, User
from app.ai.speech_history import save_assessment
from app.schemas import SpeechAssessmentResponse
from app.agents.orchestrator import run_orchestrator
from app.agents.orchestrator import classify_request
from app.agents.resource import ResourceSearchError
from app.rag.answer import generate_rag_answer_stream
from app.ai.vision import validate_image_bytes

router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])
logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_SIZE = 20 * 1024 * 1024
MAX_AUDIO_SIZE = 25 * 1024 * 1024
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".webm"}
ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3",
    "audio/mp4", "audio/webm", "audio/x-m4a",
}


class OrchestratorRequest(BaseModel):
    notebook_id: int
    chat_id: int | None = None
    question: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=3, ge=1, le=10)


@router.post("/run")
def run_agent(
    request: OrchestratorRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notebook = db.scalar(
        select(Notebook).where(
            Notebook.id == request.notebook_id,
            Notebook.user_id == current_user.id,
        )
    )

    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found",
        )

    try:
        return run_orchestrator(
            question=request.question,
            user_id=current_user.id,
            notebook_id=notebook.id,
            top_k=request.top_k,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/run/stream")
def run_agent_stream(
    request: OrchestratorRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notebook = db.scalar(
        select(Notebook).where(
            Notebook.id == request.notebook_id,
            Notebook.user_id == current_user.id,
        )
    )
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")

    conversation_history = []
    if request.chat_id is not None:
        chat = db.scalar(
            select(Chat).where(
                Chat.id == request.chat_id,
                Chat.user_id == current_user.id,
                Chat.notebook_id == notebook.id,
            )
        )
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        recent_messages = list(db.scalars(
            select(Message)
            .where(Message.chat_id == chat.id, Message.user_id == current_user.id)
            .order_by(Message.created_at.desc())
            .limit(10)
        ).all())
        conversation_history = [
            {"role": message.role, "content": message.content}
            for message in reversed(recent_messages)
        ]
        if (
            conversation_history
            and conversation_history[-1]["role"] == "user"
            and conversation_history[-1]["content"] == request.question
        ):
            conversation_history.pop()

    def events():
        agent = classify_request(request.question)
        yield json.dumps({"type": "agent", "agent": agent}) + "\n"
        if agent == "tutor":
            try:
                yield from generate_rag_answer_stream(
                    question=request.question,
                    user_id=current_user.id,
                    notebook_id=notebook.id,
                    top_k=request.top_k,
                    conversation_history=conversation_history,
                )
            except Exception:
                logger.exception("Tutor stream failed for notebook %s", notebook.id)
                yield json.dumps({"type": "error", "message": "Tutor response failed. Check backend logs for details."}) + "\n"
            return
        try:
            result = run_orchestrator(
                question=request.question,
                user_id=current_user.id,
                notebook_id=notebook.id,
                top_k=request.top_k,
            )
            yield json.dumps({"type": "result", "result": result}) + "\n"
        except ResourceSearchError as exc:
            yield json.dumps({"type": "error", "agent": "resource", "message": str(exc)}) + "\n"
        except Exception:
            yield json.dumps({"type": "error", "agent": agent, "message": "The selected agent could not process the request."}) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


@router.post("/image")
async def run_image_agent(
    notebook_id: int = Form(...),
    question: str = Form("Explain what is shown in this image.", max_length=5000),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notebook = db.scalar(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == current_user.id,
        )
    )
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, and WEBP images are supported.")

    image_bytes = await file.read(MAX_IMAGE_SIZE + 1)
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image size must not exceed 20 MB.")
    try:
        validate_image_bytes(image_bytes, file.content_type or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as image_file:
            image_file.write(image_bytes)
            temp_path = Path(image_file.name)
        return await run_in_threadpool(run_orchestrator,
            question=question,
            user_id=current_user.id,
            notebook_id=notebook.id,
            image_path=temp_path,
        )
    except Exception as exc:
        logger.exception("Image analysis failed for notebook %s", notebook.id)
        raise HTTPException(status_code=502, detail="Image analysis failed. Check backend logs for the provider error.") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@router.post("/speech")
async def run_speech_agent(
    file: UploadFile = File(...),
    reference_text: str | None = Form(default=None, max_length=20000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported audio format.")
    if file.content_type and file.content_type not in ALLOWED_AUDIO_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported audio content type.")

    audio_bytes = await file.read(MAX_AUDIO_SIZE + 1)
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="Audio file is too large. Maximum size is 25 MB.")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as audio_file:
            audio_file.write(audio_bytes)
            temp_path = Path(audio_file.name)
        result = await run_in_threadpool(
            run_orchestrator,
            question="Analyze this spoken learning response.",
            user_id=current_user.id,
            notebook_id=None,
            audio_path=temp_path,
            reference_text=reference_text,
        )
        saved = save_assessment(
            db=db,
            user_id=current_user.id,
            filename=Path(file.filename or "recording").name,
            transcript=result["transcript"],
            reference_text=reference_text.strip() if reference_text and reference_text.strip() else None,
            semantic_analysis=result["semantic_analysis"],
            tone_analysis=result["tone_analysis"],
        )
        result["assessment_id"] = saved.id
        result["created_at"] = saved.created_at
        return {"filename": Path(file.filename or "recording").name, **result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Speech analysis failed.") from exc
    finally:
        await file.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@router.get("/speech/history", response_model=list[SpeechAssessmentResponse])
def list_speech_assessments(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.scalars(
        select(SpeechAssessment)
        .where(SpeechAssessment.user_id == current_user.id)
        .order_by(SpeechAssessment.created_at.desc())
        .limit(limit)
    ).all()


@router.delete("/speech/history/{assessment_id}", status_code=204)
def delete_speech_assessment(
    assessment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assessment = db.scalar(
        select(SpeechAssessment).where(
            SpeechAssessment.id == assessment_id,
            SpeechAssessment.user_id == current_user.id,
        )
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Speech assessment not found.")
    db.delete(assessment)
    db.commit()


# FILE PURPOSE:
# Provides authenticated orchestrator routes for streamed tutor responses,
# structured agent results, and validated image and speech analysis.
