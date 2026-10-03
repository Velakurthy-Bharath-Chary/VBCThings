import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.speech import SUPPORTED_AUDIO_TYPES, transcribe_audio
from app.api.auth import get_current_user
from app.database import get_db
from app.models import SpeechAssessment, User
from app.ai.speech_analysis import analyze_semantics
from app.ai.speech_tone import analyze_tone

router = APIRouter(
    prefix="/speech",
    tags=["Speech"],
)


MAX_AUDIO_SIZE = 25 * 1024 * 1024

ALLOWED_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/webm",
    "audio/x-m4a",
}


@router.post("/transcribe")
async def transcribe_speech(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    extension = os.path.splitext(file.filename or "")[1].lower()

    if extension not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio format.",
        )

    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio content type.",
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:
            temp_path = temp_file.name

            total_size = 0

            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_AUDIO_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Audio file is too large. Maximum size is 25 MB.",
                    )

                temp_file.write(chunk)

        transcript = transcribe_audio(
            file_path=temp_path,
        )

        return {
            "filename": file.filename,
            "transcript": transcript,
        }

    finally:
        await file.close()

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

@router.post("/analyze")
async def analyze_speech(
    file: UploadFile = File(...),
    reference_text: str | None = Form(default=None, max_length=20000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    extension = os.path.splitext(file.filename or "")[1].lower()

    if extension not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio format.",
        )

    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio content type.",
        )

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension,
        ) as temp_file:
            temp_path = temp_file.name

            total_size = 0

            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_AUDIO_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Audio file is too large. Maximum size is 25 MB.",
                    )

                temp_file.write(chunk)

        transcript = transcribe_audio(
            file_path=temp_path,
        )

        semantic_analysis = analyze_semantics(
            transcript=transcript,
            reference_text=reference_text,
        )

        tone_analysis = analyze_tone(
            text=transcript,
        )

        assessment = SpeechAssessment(
            user_id=current_user.id,
            filename=os.path.basename(file.filename or "speech"),
            transcript=transcript,
            reference_text=reference_text.strip() if reference_text and reference_text.strip() else None,
            semantic_analysis=semantic_analysis,
            tone_analysis=tone_analysis,
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        return {
            "id": assessment.id,
            "created_at": assessment.created_at,
            "filename": file.filename,
            "transcript": transcript,
            "semantic_analysis": semantic_analysis,
            "tone_analysis": tone_analysis,
        }

    finally:
        await file.close()

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/history")
def list_speech_history(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assessments = db.scalars(
        select(SpeechAssessment)
        .where(SpeechAssessment.user_id == current_user.id)
        .order_by(SpeechAssessment.created_at.desc())
        .limit(limit)
    ).all()
    return assessments


@router.delete("/history/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
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
# Provides an authenticated API endpoint for audio transcription
# using the Groq Whisper speech-to-text provider.
