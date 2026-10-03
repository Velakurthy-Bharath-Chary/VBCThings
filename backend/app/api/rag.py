from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Notebook, User
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.rag.answer import (
    generate_rag_answer,
    generate_rag_answer_stream,
)

router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)


class RAGAskRequest(BaseModel):
    notebook_id: int
    question: str = Field(
        min_length=1,
        max_length=5000,
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
    )


@router.post("/ask")
def ask_rag(
    request: RAGAskRequest,
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

    return generate_rag_answer(
        question=request.question,
        user_id=current_user.id,
        notebook_id=notebook.id,
        top_k=request.top_k,
    )

@router.post("/ask/stream")
def ask_rag_stream(
    request: RAGAskRequest,
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

    return StreamingResponse(
        generate_rag_answer_stream(
            question=request.question,
            user_id=current_user.id,
            notebook_id=notebook.id,
            top_k=request.top_k,
        ),
        media_type="application/x-ndjson",
    )

# FILE PURPOSE:
# Provides an authenticated RAG question endpoint with notebook-level
# ownership validation and JWT-derived tenant identity.