from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255, examples=["alice@example.com"])
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    role: str
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    content_type: str
    status: str
    error: str | None
    num_pages: int
    num_chunks: int
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: Literal["hybrid", "vector", "bm25"] = "hybrid"


class SearchHitOut(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page: int
    chunk_index: int
    text: str
    score: float
    vector_score: float | None
    bm25_score: float | None
    ranks: dict[str, int]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


class Citation(BaseModel):
    id: str
    document_id: str
    filename: str
    page: int
    chunk_index: int
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    answer_type: Literal["grounded", "refused", "unverified", "tool", "direct"]
    route: str | None
    grounded: bool | None
    citations: list[Citation]
    tool_calls: list[dict]
    trace: list[str]
    conversation_id: str
    cached: bool = False


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role: str
    content: str
    citations: list | None
    created_at: datetime


class AdminStats(BaseModel):
    users: int
    documents: int
    chunks: int
    documents_by_status: dict[str, int]
