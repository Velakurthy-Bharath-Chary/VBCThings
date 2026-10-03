from sqlalchemy.orm import Session

from app.models import SpeechAssessment


def save_assessment(
    db: Session,
    user_id: int,
    filename: str,
    transcript: str,
    reference_text: str | None,
    semantic_analysis: dict,
    tone_analysis: dict,
) -> SpeechAssessment:
    assessment = SpeechAssessment(
        user_id=user_id,
        filename=filename[:255],
        transcript=transcript,
        reference_text=reference_text,
        semantic_analysis=semantic_analysis,
        tone_analysis=tone_analysis,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


# FILE PURPOSE:
# Persists speech transcripts and analysis under the authenticated user owner.
