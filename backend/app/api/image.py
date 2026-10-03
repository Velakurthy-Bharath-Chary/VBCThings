from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.vision import analyze_image, validate_image_bytes
from app.api.auth import get_current_user
from app.database import get_db
from app.models import Notebook, User


router = APIRouter(prefix="/image", tags=["Image"])

UPLOAD_DIR = Path("data/images")

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_IMAGE_SIZE = 20 * 1024 * 1024


@router.post("/analyze")
async def analyze_uploaded_image(
    notebook_id: int = Form(...),
    file: UploadFile = File(...),
    question: str = Form(
        "Explain what is shown in this image.", max_length=5000
    ),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found",
        )

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG, and WEBP images are supported.",
        )

    image_bytes = await file.read(MAX_IMAGE_SIZE + 1)

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image size must not exceed 20 MB.",
        )

    try:
        validate_image_bytes(image_bytes, file.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    user_directory = UPLOAD_DIR / str(current_user.id)
    user_directory.mkdir(parents=True, exist_ok=True)

    extension = ALLOWED_TYPES[file.content_type]
    stored_path = user_directory / f"{uuid4()}{extension}"

    stored_path.write_bytes(image_bytes)

    try:
        result = analyze_image(
            file_path=stored_path,
            question=question,
        )

        return {
            "filename": file.filename,
            "notebook_id": notebook_id,
            "question": question,
            "answer": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image analysis failed.",
        ) from exc

    finally:
        if stored_path.exists():
            stored_path.unlink()


# FILE PURPOSE:
# Provides authenticated, notebook-owned image uploads and Groq Vision analysis.


# FILE PURPOSE:
# Provides authenticated image upload and vision-analysis API endpoints.
