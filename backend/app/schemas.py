from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from datetime import datetime
from typing import Literal

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class NotebookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class NotebookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_archived: bool | None = None


class NotebookResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None
    is_archived: bool

    model_config = ConfigDict(from_attributes=True)

class ChatCreate(BaseModel):
    title: str = Field(
        default="New Chat",
        min_length=1,
        max_length=255,
    )


class ChatUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    is_pinned: bool | None = None
    is_archived: bool | None = None


class ChatResponse(BaseModel):
    id: int
    user_id: int
    notebook_id: int
    title: str
    is_pinned: bool
    is_archived: bool

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    role: str = Field(
        min_length=1,
        max_length=20,
    )
    content: str = Field(
        min_length=1,
        max_length=20000,
    )


class MessageResponse(BaseModel):
    id: int
    chat_id: int
    user_id: int
    role: str
    content: str

    model_config = ConfigDict(from_attributes=True)

class StudioGenerateRequest(BaseModel):
    notebook_id: int
    artifact_type: str = Field(
        min_length=1,
        max_length=30,
    )
    title: str | None = Field(
        default=None,
        max_length=255,
    )
    instructions: str | None = Field(
        default=None,
        max_length=5000,
    )


class LearningArtifactResponse(BaseModel):
    id: int
    user_id: int
    notebook_id: int
    artifact_type: str
    title: str
    content: str

    model_config = ConfigDict(from_attributes=True)


class SpeechAssessmentResponse(BaseModel):
    id: int
    filename: str
    transcript: str
    reference_text: str | None
    semantic_analysis: dict
    tone_analysis: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuizAttemptRequest(BaseModel):
    chat_id: int = Field(gt=0)
    message_id: int = Field(gt=0)
    answers: list[Literal["A", "B", "C", "D"]] = Field(min_length=1, max_length=20)


class QuizAttemptResponse(BaseModel):
    id: int
    notebook_id: int
    chat_id: int
    message_id: int
    answers: list[str]
    results: list[dict]
    score: int
    total_questions: int
    percentage: float
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


# FILE PURPOSE:
# Defines validated request and response schemas for auth, notebooks,
# scheduling, chat management, Learning Studio, speech history,
# and authenticated quiz attempts.
