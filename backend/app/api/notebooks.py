from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database import get_db
from app.models import Notebook, User
from app.schemas import (
    NotebookCreate,
    NotebookResponse,
    NotebookUpdate,
)

router = APIRouter(
    prefix="/notebooks",
    tags=["Notebooks"],
)


@router.post(
    "",
    response_model=NotebookResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_notebook(
    notebook_data: NotebookCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notebook = Notebook(
        user_id=current_user.id,
        name=notebook_data.name,
        description=notebook_data.description,
    )

    db.add(notebook)
    db.commit()
    db.refresh(notebook)

    return notebook


@router.get(
    "",
    response_model=list[NotebookResponse],
)
def list_notebooks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notebooks = db.scalars(
        select(Notebook)
        .where(Notebook.user_id == current_user.id)
        .order_by(Notebook.created_at.desc())
    ).all()

    return notebooks


@router.get(
    "/{notebook_id}",
    response_model=NotebookResponse,
)
def get_notebook(
    notebook_id: int,
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

    return notebook


@router.patch(
    "/{notebook_id}",
    response_model=NotebookResponse,
)
def update_notebook(
    notebook_id: int,
    notebook_data: NotebookUpdate,
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

    update_data = notebook_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(notebook, field, value)

    db.commit()
    db.refresh(notebook)

    return notebook


@router.delete(
    "/{notebook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notebook(
    notebook_id: int,
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

    db.delete(notebook)
    db.commit()


# FILE PURPOSE:
# Provides authenticated CRUD operations for user-owned notebooks with tenant isolation.