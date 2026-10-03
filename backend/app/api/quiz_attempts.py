import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Chat, Message, Notebook, QuizAttempt, User
from app.schemas import QuizAttemptRequest, QuizAttemptResponse


router = APIRouter(prefix="/quiz-attempts", tags=["Quiz Attempts"])


def serialize_attempt(attempt: QuizAttempt) -> dict:
    return {
        "id": attempt.id,
        "notebook_id": attempt.notebook_id,
        "chat_id": attempt.chat_id,
        "message_id": attempt.message_id,
        "answers": attempt.answers,
        "results": attempt.results,
        "score": attempt.score,
        "total_questions": attempt.total_questions,
        "percentage": round(100 * attempt.score / attempt.total_questions, 1),
        "submitted_at": attempt.submitted_at,
    }


@router.post("", response_model=QuizAttemptResponse, status_code=status.HTTP_201_CREATED)
def submit_quiz_attempt(
    request: QuizAttemptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = db.scalar(
        select(Chat).where(
            Chat.id == request.chat_id,
            Chat.user_id == current_user.id,
        )
    )
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found.")

    message = db.scalar(
        select(Message).where(
            Message.id == request.message_id,
            Message.chat_id == chat.id,
            Message.user_id == current_user.id,
            Message.role == "assistant",
        )
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    try:
        serialized = json.loads(message.content)
        quiz = serialized.get("message", {}).get("quiz")
    except (json.JSONDecodeError, AttributeError):
        quiz = None
    questions = quiz.get("questions") if isinstance(quiz, dict) else None
    if not isinstance(questions, list) or not questions:
        raise HTTPException(status_code=400, detail="This message does not contain a quiz.")
    if len(request.answers) != len(questions):
        raise HTTPException(status_code=422, detail="Provide exactly one answer for each question.")

    existing = db.scalar(
        select(QuizAttempt).where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.message_id == message.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="This quiz has already been submitted.")

    results = []
    for index, (question, selected) in enumerate(zip(questions, request.answers, strict=True)):
        correct_answer = question.get("correct_answer")
        if correct_answer not in {"A", "B", "C", "D"}:
            raise HTTPException(status_code=400, detail="The stored quiz has invalid answer data.")
        results.append({
            "question_index": index,
            "selected_answer": selected,
            "correct": selected == correct_answer,
            "correct_answer": correct_answer,
            "explanation": str(question.get("explanation", ""))[:2000],
        })
    score = sum(result["correct"] for result in results)
    attempt = QuizAttempt(
        user_id=current_user.id,
        notebook_id=chat.notebook_id,
        chat_id=chat.id,
        message_id=message.id,
        answers=request.answers,
        results=results,
        score=score,
        total_questions=len(questions),
    )
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This quiz has already been submitted.") from exc
    db.refresh(attempt)
    return serialize_attempt(attempt)


@router.get("", response_model=list[QuizAttemptResponse])
def list_quiz_attempts(
    notebook_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(QuizAttempt).where(QuizAttempt.user_id == current_user.id)
    if notebook_id is not None:
        notebook = db.scalar(
            select(Notebook).where(
                Notebook.id == notebook_id,
                Notebook.user_id == current_user.id,
            )
        )
        if notebook is None:
            raise HTTPException(status_code=404, detail="Notebook not found.")
        query = query.where(QuizAttempt.notebook_id == notebook_id)
    attempts = db.scalars(query.order_by(QuizAttempt.submitted_at.desc()).limit(limit)).all()
    return [serialize_attempt(attempt) for attempt in attempts]


# FILE PURPOSE:
# Validates quiz submissions against owner-owned chat messages, scores them
# on the server, and persists notebook-scoped quiz history.
