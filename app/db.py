import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        path = url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores ON DELETE CASCADE unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


def is_postgres() -> bool:
    return get_engine().dialect.name == "postgresql"


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def SessionLocal() -> Session:
    return _session_factory()()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  (registers tables)

    engine = get_engine()
    if engine.dialect.name != "postgresql":
        Base.metadata.create_all(engine)
        return
    with engine.begin() as conn:
        # Every API worker and the MCP server run this at boot; "IF NOT EXISTS" still races without a lock.
        conn.execute(text("SELECT pg_advisory_xact_lock(7340291)"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(conn)
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)"
        ))
