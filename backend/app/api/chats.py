from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.agents.orchestrator import run_orchestrator
from app.api.auth import get_current_user
from app.database import get_db
from app.models import Chat, Message, Notebook, User
from app.schemas import (
    ChatCreate,
    ChatResponse,
    ChatUpdate,
    MessageCreate,
    MessageResponse,
)


router = APIRouter(
    prefix="/chats",
    tags=["Chats"],
)


ALLOWED_MESSAGE_ROLES = {
    "user",
    "assistant",
}


def get_owned_chat(
    chat_id: int,
    current_user: User,
    db: Session,
) -> Chat:
    chat = db.scalar(
        select(Chat).where(
            Chat.id == chat_id,
            Chat.user_id == current_user.id,
        )
    )

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    return chat


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_chat(
    notebook_id: int,
    chat_data: ChatCreate,
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

    chat = Chat(
        user_id=current_user.id,
        notebook_id=notebook.id,
        title=chat_data.title,
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    return chat


@router.get(
    "",
    response_model=list[ChatResponse],
)
def list_chats(
    notebook_id: int | None = None,
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Chat).where(
        Chat.user_id == current_user.id,
    )

    if notebook_id is not None:
        query = query.where(
            Chat.notebook_id == notebook_id,
        )

    if not include_archived:
        query = query.where(Chat.is_archived.is_(False))

    query = query.order_by(
        Chat.is_pinned.desc(),
        Chat.updated_at.desc(),
    )

    return list(db.scalars(query).all())


@router.get(
    "/{chat_id}",
    response_model=ChatResponse,
)
def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_owned_chat(
        chat_id=chat_id,
        current_user=current_user,
        db=db,
    )


@router.patch(
    "/{chat_id}",
    response_model=ChatResponse,
)
def update_chat(
    chat_id: int,
    chat_data: ChatUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = get_owned_chat(
        chat_id=chat_id,
        current_user=current_user,
        db=db,
    )

    update_data = chat_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(chat, field, value)

    db.commit()
    db.refresh(chat)

    return chat


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = get_owned_chat(
        chat_id=chat_id,
        current_user=current_user,
        db=db,
    )

    db.delete(chat)
    db.commit()


@router.post(
    "/{chat_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    chat_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = get_owned_chat(
        chat_id=chat_id,
        current_user=current_user,
        db=db,
    )

    if message_data.role not in ALLOWED_MESSAGE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message role must be 'user' or 'assistant'",
        )

    message = Message(
        chat_id=chat.id,
        user_id=current_user.id,
        role=message_data.role,
        content=message_data.content,
    )

    db.add(message)
    # Keep conversation ordering aligned with its latest user or assistant turn.
    chat.updated_at = func.now()

    db.commit()
    db.refresh(message)

    return message

@router.post(
    "/{chat_id}/ask",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def ask_chat(
    chat_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = get_owned_chat(
        chat_id=chat_id,
        current_user=current_user,
        db=db,
    )

    if message_data.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ask endpoint accepts user messages only.",
        )

    user_message = Message(
        chat_id=chat.id,
        user_id=current_user.id,
        role="user",
        content=message_data.content,
    )

    db.add(user_message)
    db.flush()

    try:
        result = run_orchestrator(
            question=message_data.content,
            user_id=current_user.id,
            notebook_id=chat.notebook_id,
        )

        agent = result.get("agent", "tutor")

        if agent == "tutor":
            assistant_content = result.get(
                "answer",
                "",
            )

        elif agent == "quiz":
            assistant_content = str(
                result.get("quiz", result)
            )

        else:
            assistant_content = str(
                result.get("results", [])
            )

        assistant_message = Message(
            chat_id=chat.id,
            user_id=current_user.id,
            role="assistant",
            content=assistant_content,
        )

        db.add(assistant_message)
        chat.updated_at = func.now()
        db.commit()
        db.refresh(assistant_message)

        return assistant_message

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat request.",
        ) from exc

@router.get(
    "/{chat_id}/messages",
    response_model=list[MessageResponse],
)
def list_messages(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chat = get_owned_chat(
        chat_id=chat_id,
        current_user=current_user,
        db=db,
    )

    query = (
        select(Message)
        .where(
            Message.chat_id == chat.id,
            Message.user_id == current_user.id,
        )
        .order_by(Message.created_at.asc(), Message.id.asc())
    )

    return list(db.scalars(query).all())


# FILE PURPOSE:
# Provides authenticated chat and message management with strict
# user ownership and notebook isolation.
