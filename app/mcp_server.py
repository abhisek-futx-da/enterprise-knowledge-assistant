"""MCP server exposing the knowledge base as tools over Streamable HTTP.

It is an OAuth resource server: every request carries the end user's JWT, verified here, and every
tool is scoped to that user. No tool takes a user_id argument, so a caller cannot ask for someone else's data.
Run: python -m app.mcp_server
"""
import asyncio
import os
from typing import Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Chunk, Document
from app.retrieval.search import search
from app.security import decode_token


class JWTVerifier:
    """Accepts the same access tokens the REST API issues (same secret, audience and expiry)."""

    async def verify_token(self, token: str) -> AccessToken | None:
        claims = decode_token(token)
        if not claims:
            return None
        return AccessToken(
            token=token, client_id=claims["sub"], subject=claims["sub"], scopes=["kb"],
            expires_at=int(claims["exp"]), claims={"role": claims.get("role")},
        )


def _current_user_id() -> str:
    token = get_access_token()
    if token is None or not token.subject:
        raise PermissionError("Unauthenticated")
    return token.subject


def _search(user_id: str, query: str, top_k: int, mode: str) -> list[dict]:
    db = SessionLocal()
    try:
        return [
            {"document_id": h.document_id, "filename": h.filename, "page": h.page,
             "chunk_index": h.chunk_index, "score": round(h.score, 4), "text": h.text}
            for h in search(db, user_id, query, top_k, mode)
        ]
    finally:
        db.close()


def _list_documents(user_id: str) -> list[dict]:
    db = SessionLocal()
    try:
        docs = db.scalars(select(Document).where(Document.owner_id == user_id).order_by(Document.created_at.desc()))
        return [
            {"id": d.id, "filename": d.filename, "status": d.status, "pages": d.num_pages,
             "chunks": d.num_chunks, "uploaded_at": d.created_at.isoformat()}
            for d in docs
        ]
    finally:
        db.close()


def _read_page(user_id: str, document_id: str, page: int) -> dict:
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None or doc.owner_id != user_id:  # same answer for "missing" and "not yours": no existence oracle
            return {"error": "Document not found"}
        texts = db.scalars(
            select(Chunk.text).where(Chunk.document_id == document_id, Chunk.page == page).order_by(Chunk.chunk_index)
        ).all()
        if not texts:
            return {"error": f"Page {page} not found; document has {doc.num_pages} page(s)"}
        return {"document_id": doc.id, "filename": doc.filename, "page": page, "text": "\n".join(texts)}
    finally:
        db.close()


def _stats(user_id: str) -> dict:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Document.status, func.count(Document.id), func.coalesce(func.sum(Document.num_chunks), 0))
            .where(Document.owner_id == user_id).group_by(Document.status)
        ).all()
        by_status = {status: {"documents": n, "chunks": int(c)} for status, n, c in rows}
        return {
            "total_documents": sum(v["documents"] for v in by_status.values()),
            "total_chunks": sum(v["chunks"] for v in by_status.values()),
            "by_status": by_status,
        }
    finally:
        db.close()


def create_mcp_server(host: str = "127.0.0.1", port: int = 8001) -> FastMCP:
    s = get_settings()
    allowed = os.getenv("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,mcp:*").split(",")
    mcp = FastMCP(
        "knowledge-base",
        instructions="Tools over the authenticated user's private document library.",
        host=host, port=port,
        stateless_http=True,  # no sticky sessions: any replica can serve any request
        json_response=True,
        token_verifier=JWTVerifier(),
        auth=AuthSettings(
            issuer_url=os.getenv("AUTH_ISSUER_URL", "http://localhost:8000"),
            resource_server_url=os.getenv("MCP_PUBLIC_URL", s.mcp_server_url),
            validate_token_resource=False,  # JWTVerifier checks the audience itself
        ),
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed,
            allowed_origins=[f"http://{h}" for h in allowed],
        ),
    )

    @mcp.tool()
    async def search_knowledge_base(
        query: str, top_k: int = 5, mode: Literal["hybrid", "vector", "bm25"] = "hybrid"
    ) -> list[dict]:
        """Search the user's documents. Hybrid = semantic vectors + BM25 keywords fused with RRF.
        Returns passages with filename, page and score."""
        return await asyncio.to_thread(_search, _current_user_id(), query, max(1, min(top_k, 20)), mode)

    @mcp.tool()
    async def list_my_documents() -> list[dict]:
        """List the user's uploaded documents with id, filename, status, page and chunk counts."""
        return await asyncio.to_thread(_list_documents, _current_user_id())

    @mcp.tool()
    async def read_document_page(document_id: str, page: int) -> dict:
        """Return the full text of one page of one of the user's documents (get ids from list_my_documents)."""
        return await asyncio.to_thread(_read_page, _current_user_id(), document_id, page)

    @mcp.tool()
    async def knowledge_base_stats() -> dict:
        """Counts of the user's documents and chunks, grouped by ingestion status."""
        return await asyncio.to_thread(_stats, _current_user_id())

    return mcp


if __name__ == "__main__":
    init_db()
    server = create_mcp_server(host=os.getenv("MCP_HOST", "0.0.0.0"), port=int(os.getenv("MCP_PORT", "8001")))
    server.run(transport="streamable-http")
