import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.config import get_settings
from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class EmbeddingType(TypeDecorator):
    """pgvector on PostgreSQL (HNSW-indexed); JSON list on SQLite for local dev and tests."""

    impl = JSON
    cache_ok = True
    comparator_factory = Vector.comparator_factory  # exposes .cosine_distance(); only called on PostgreSQL

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(get_settings().embedding_dim))
        return dialect.type_descriptor(JSON())

    def process_result_value(self, value, dialect):
        return None if value is None else [float(x) for x in value]


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|ready|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    num_pages: Mapped[int] = mapped_column(Integer, default=0)
    num_chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    # Denormalised owner so every search filters on one indexed column, never via a join.
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingType)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
