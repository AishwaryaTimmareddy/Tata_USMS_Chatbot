from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from pydantic import EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=80)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str
    role: Literal["user", "admin"]


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)


class Citation(BaseModel):
    title: str
    source: str
    page_number: int | None = None
    excerpt: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[Citation]
    grounded: bool
    latency_ms: int


class FeedbackRequest(BaseModel):
    session_id: str
    helpful: bool
    message_id: str | None = None
    comment: str | None = Field(default=None, max_length=1000)
    contact: str | None = Field(default=None, max_length=254)


class ConversationSummary(BaseModel):
    session_id: str
    title: str
    updated_at: datetime
    message_count: int


class ConversationTurn(BaseModel):
    id: str
    created_at: datetime
    question: str
    answer: str
    citations: list[Citation]
    grounded: bool
    latency_ms: int


class ConversationDetail(BaseModel):
    session_id: str
    turns: list[ConversationTurn]


class DocumentItem(BaseModel):
    name: str
    size: int
    content_type: str | None
    last_modified: datetime
    url: str


class IndexerStatusResponse(BaseModel):
    status: str
    last_result: str | None = None
    processed: int = 0
    failed: int = 0
    errors: list[str] = []
    warnings: list[str] = []


class ReadinessResponse(BaseModel):
    ready: bool
    services: dict[str, dict[str, object]]
