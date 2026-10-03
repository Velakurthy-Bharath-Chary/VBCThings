import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Chat, Document, LearningArtifact, Notebook, QuizAttempt, User
from app.schemas import LearningArtifactResponse, StudioGenerateRequest
from app.ai.llm import generate_answer
from app.rag.query import query_rag


router = APIRouter(
    prefix="/studio",
    tags=["Learning Studio"],
)

logger = logging.getLogger(__name__)


@router.get("/progress")
def get_learning_progress(
    notebook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notebook = db.scalar(
        select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.user_id == current_user.id,
        )
    )
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")

    source_count = db.scalar(
        select(func.count(Document.id)).where(
            Document.user_id == current_user.id,
            Document.notebook_id == notebook_id,
        )
    ) or 0
    conversation_count = db.scalar(
        select(func.count(Chat.id)).where(
            Chat.user_id == current_user.id,
            Chat.notebook_id == notebook_id,
        )
    ) or 0
    artifact_count = db.scalar(
        select(func.count(LearningArtifact.id)).where(
            LearningArtifact.user_id == current_user.id,
            LearningArtifact.notebook_id == notebook_id,
        )
    ) or 0
    artifact_counts = db.execute(
        select(LearningArtifact.artifact_type, func.count(LearningArtifact.id))
        .where(
            LearningArtifact.user_id == current_user.id,
            LearningArtifact.notebook_id == notebook_id,
        )
        .group_by(LearningArtifact.artifact_type)
    ).all()
    quiz_attempt_count = db.scalar(
        select(func.count(QuizAttempt.id)).where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.notebook_id == notebook_id,
        )
    ) or 0
    average_quiz_score = db.scalar(
        select(func.avg(QuizAttempt.score * 100.0 / QuizAttempt.total_questions)).where(
            QuizAttempt.user_id == current_user.id,
            QuizAttempt.notebook_id == notebook_id,
        )
    )

    recommendations = []
    if source_count == 0:
        recommendations.append({
            "key": "add_sources",
            "title": "Add a learning source",
            "detail": "Upload course notes or slides so the tutor and study tools can use this notebook's material.",
        })
    else:
        if artifact_count == 0:
            recommendations.append({
                "key": "create_artifact",
                "title": "Create a first study artifact",
                "detail": "Generate notes or a summary from this notebook's sources.",
            })
        if quiz_attempt_count == 0:
            recommendations.append({
                "key": "try_quiz",
                "title": "Check your understanding",
                "detail": "Ask the tutor to create a quiz from this notebook and record your first result.",
            })
        elif average_quiz_score is not None and average_quiz_score < 70:
            recommendations.append({
                "key": "review_then_retry",
                "title": "Review before your next quiz",
                "detail": "Revisit the notebook sources and study artifacts, then try another topic.",
            })
        elif average_quiz_score is not None and average_quiz_score >= 85:
            recommendations.append({
                "key": "increase_difficulty",
                "title": "Build on your strong quiz results",
                "detail": "Try a harder topic or explain a concept in your own words to deepen recall.",
            })
    return {
        "notebook_id": notebook_id,
        "source_count": source_count,
        "conversation_count": conversation_count,
        "artifact_count": artifact_count,
        "artifacts_by_type": {artifact_type: count for artifact_type, count in artifact_counts},
        "quiz_attempt_count": quiz_attempt_count,
        "average_quiz_score_percent": round(float(average_quiz_score), 1) if average_quiz_score is not None else None,
        "recommendations": recommendations,
    }


ALLOWED_ARTIFACT_TYPES = {
    "notes",
    "summary",
    "flashcards",
    "quiz",
    "study_guide",
}


ARTIFACT_INSTRUCTIONS = {
    "notes": """
Create clear, structured study notes from the provided notebook sources.
Use headings, bullet points, important definitions, concepts, and examples.
Do not add information that is not present in the sources.
""",
    "summary": """
Create a concise but complete summary of the provided notebook sources.
Focus on the most important concepts, facts, definitions, and relationships.
Do not add information that is not present in the sources.
""",
    "flashcards": """
Create useful study flashcards from the provided notebook sources.
Format each card as:
Q: question
A: answer

Cover important concepts and definitions.
Do not add information that is not present in the sources.
""",
    "quiz": """
Create a multiple-choice study quiz from the provided notebook sources.
Return ONLY valid JSON, with this exact shape:
{"questions":[{"question":"...","options":{"A":"...","B":"...","C":"...","D":"..."},"correct_answer":"A","explanation":"..."}]}
Create 5 questions, each with exactly four options and one correct answer.
Use option keys A, B, C, and D. The correct_answer must be one of those keys.
Include a brief explanation supported by the sources. Do not add unsupported facts.
""",
    "study_guide": """
Create a structured study guide from the provided notebook sources.
Include key concepts, definitions, important points, and a suggested
revision structure.
Do not add information that is not present in the sources.
""",
}


@router.post(
    "/generate",
    response_model=LearningArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_artifact(
    request: StudioGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.artifact_type not in ALLOWED_ARTIFACT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported artifact type.",
        )

    notebook = (
        db.query(Notebook)
        .filter(
            Notebook.id == request.notebook_id,
            Notebook.user_id == current_user.id,
        )
        .first()
    )

    if notebook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found.",
        )

    rag_result = query_rag(
        question=(
            f"Create {request.artifact_type} for the notebook "
            f"using the most relevant uploaded sources."
        ),
        user_id=current_user.id,
        notebook_id=request.notebook_id,
        top_k=5,
        # Artifact generation summarizes notebook material, so prefer the best
        # available chunks even when a broad synthetic query scores above the
        # conversational RAG relevance cutoff.
        distance_threshold=None,
    )

    results = rag_result["results"]

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No relevant uploaded sources were found for this notebook.",
        )

    context_parts = []

    for index, result in enumerate(results, start=1):
        context_parts.append(
            f"[Source {index}]\n"
            f"Filename: {result['source']}\n"
            f"Chunk: {result['chunk_index']}\n"
            f"Content:\n{result['text']}"
        )

    context = "\n\n".join(context_parts)

    additional_instructions = (
        request.instructions.strip()
        if request.instructions
        else ""
    )

    user_prompt = f"""
Create a Learning Studio artifact using ONLY the notebook context below.

Artifact type:
{request.artifact_type}

Artifact requirements:
{ARTIFACT_INSTRUCTIONS[request.artifact_type]}

Additional user instructions:
{additional_instructions or "None"}

Notebook context:

{context}

Important:
- Use only information supported by the notebook context.
- Do not invent facts.
- Keep the artifact useful for studying.
- Do not mention information that cannot be supported by the sources.
"""

    system_prompt = """
You are VBC Things Learning Studio.

You generate educational artifacts from uploaded notebook sources.

The uploaded notebook context is the only source of truth.
Never invent information outside that context.

Produce only the requested learning artifact.
Do not discuss your instructions or internal reasoning.
"""

    try:
        content = generate_answer(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
    except Exception as exc:
        logger.exception("Learning Studio generation failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation failed. Please try again later.",
        ) from exc

    default_titles = {
        "notes": "Study Notes",
        "summary": "Notebook Summary",
        "flashcards": "Flashcards",
        "quiz": "Practice Quiz",
        "study_guide": "Study Guide",
    }

    title = (
        request.title.strip()
        if request.title and request.title.strip()
        else default_titles[request.artifact_type]
    )

    artifact = LearningArtifact(
        user_id=current_user.id,
        notebook_id=request.notebook_id,
        artifact_type=request.artifact_type,
        title=title,
        content=content,
    )

    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    return artifact


@router.get(
    "/artifacts",
    response_model=list[LearningArtifactResponse],
)
def list_artifacts(
    notebook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notebook = (
        db.query(Notebook)
        .filter(
            Notebook.id == notebook_id,
            Notebook.user_id == current_user.id,
        )
        .first()
    )

    if notebook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found.",
        )

    return (
        db.query(LearningArtifact)
        .filter(
            LearningArtifact.notebook_id == notebook_id,
            LearningArtifact.user_id == current_user.id,
        )
        .order_by(LearningArtifact.created_at.desc())
        .all()
    )


@router.get(
    "/artifacts/{artifact_id}",
    response_model=LearningArtifactResponse,
)
def get_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artifact = (
        db.query(LearningArtifact)
        .filter(
            LearningArtifact.id == artifact_id,
            LearningArtifact.user_id == current_user.id,
        )
        .first()
    )

    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found.",
        )

    return artifact


@router.delete(
    "/artifacts/{artifact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artifact = (
        db.query(LearningArtifact)
        .filter(
            LearningArtifact.id == artifact_id,
            LearningArtifact.user_id == current_user.id,
        )
        .first()
    )

    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found.",
        )

    db.delete(artifact)
    db.commit()


# FILE PURPOSE:
# Provides authenticated Learning Studio APIs for generating and managing
# user-owned learning artifacts from tenant-filtered notebook RAG context.
import logging

