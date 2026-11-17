from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cache import bump_corpus_version
from app.config import get_settings
from app.db import get_db
from app.ingestion.extract import SUPPORTED_EXTENSIONS
from app.ingestion.pipeline import ingest_document
from app.models import Conversation, Document, Message, User
from app.retrieval.search import search
from app.schemas import DocumentOut, SearchHitOut, SearchRequest, WorkspaceStats
from app.security import get_current_user

router = APIRouter(tags=["documents"])


def _owned_document(db: Session, user: User, document_id: str) -> Document:
    doc = db.get(Document, document_id)
    if doc is None or doc.owner_id != user.id:  # 404, not 403: never confirm another user's id exists
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile, background: BackgroundTasks,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Document:
    """Accepts the file and returns at once; poll GET /documents/{id} until status is `ready`."""
    filename = (file.filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Allowed types: {sorted(SUPPORTED_EXTENSIONS)}")
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Max upload size is {get_settings().max_upload_mb} MB")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    doc = Document(owner_id=user.id, filename=filename, content_type=file.content_type or "application/octet-stream")
    db.add(doc)
    db.commit()
    background.add_task(ingest_document, doc.id, data)
    return doc


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.owner_id == user.id).order_by(Document.created_at.desc())))


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Document:
    return _owned_document(db, user, document_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    db.delete(_owned_document(db, user, document_id))
    db.commit()
    bump_corpus_version(user.id)


@router.post("/search", response_model=list[SearchHitOut], tags=["search"])
def search_documents(
    body: SearchRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    """Raw retrieval, no LLM. Compare `mode` = vector | bm25 | hybrid on the same query."""
    return [h.to_dict() for h in search(db, user.id, body.query, body.top_k, body.mode)]


@router.get("/stats", response_model=WorkspaceStats, tags=["workspace"])
def workspace_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WorkspaceStats:
    """The caller's own numbers for the home dashboard: library size and how questions were answered."""
    docs = db.execute(
        select(Document.status, func.count(), func.coalesce(func.sum(Document.num_pages), 0),
               func.coalesce(func.sum(Document.num_chunks), 0))
        .where(Document.owner_id == user.id).group_by(Document.status)
    ).all()
    owned = select(Conversation.id).where(Conversation.owner_id == user.id)
    messages = db.execute(
        select(Message.role, Message.answer_type, func.count())
        .where(Message.conversation_id.in_(owned)).group_by(Message.role, Message.answer_type)
    ).all()
    return WorkspaceStats(
        documents=sum(n for _, n, _, _ in docs),
        documents_by_status={s: n for s, n, _, _ in docs},
        pages=sum(int(p) for _, _, p, _ in docs),
        chunks=sum(int(c) for _, _, _, c in docs),
        conversations=db.scalar(select(func.count()).select_from(owned.subquery())) or 0,
        questions=sum(n for role, _, n in messages if role == "user"),
        answers_by_type={t: n for role, t, n in messages if role == "assistant" and t},
    )
