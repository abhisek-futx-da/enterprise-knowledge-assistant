from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Chunk, Document, User
from app.schemas import AdminStats, UserOut
from app.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


@router.get("/stats", response_model=AdminStats)
def stats(db: Session = Depends(get_db)) -> AdminStats:
    """Aggregate counts only; admins never see other users' document content."""
    by_status = dict(db.execute(select(Document.status, func.count()).group_by(Document.status)).all())
    return AdminStats(
        users=db.scalar(select(func.count()).select_from(User)) or 0,
        documents=sum(by_status.values()),
        chunks=db.scalar(select(func.count()).select_from(Chunk)) or 0,
        documents_by_status=by_status,
    )
