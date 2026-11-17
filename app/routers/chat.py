from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import HISTORY_TURNS, run_agent
from app.agent.llm import get_llm
from app.agent.mcp_client import load_mcp_tools
from app.cache import cache_answer, get_cached_answer, hit_rate_limit
from app.db import get_db
from app.models import Conversation, Message, User
from app.schemas import ChatRequest, ChatResponse, MessageOut
from app.security import get_current_user, oauth2_scheme

router = APIRouter(tags=["chat"])


def get_tool_loader():
    return load_mcp_tools


def _conversation(db: Session, user: User, conversation_id: str | None) -> Conversation:
    if conversation_id is None:
        convo = Conversation(owner_id=user.id)
        db.add(convo)
        db.commit()
        return convo
    convo = db.get(Conversation, conversation_id)
    if convo is None or convo.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return convo


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    llm=Depends(get_llm),
    tool_loader=Depends(get_tool_loader),
) -> dict:
    if hit_rate_limit(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded, try again in a minute")
    convo = _conversation(db, user, body.conversation_id)
    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(db.scalars(
            select(Message).where(Message.conversation_id == convo.id)
            .order_by(Message.created_at.desc()).limit(HISTORY_TURNS)
        ).all())
    ]

    # Only first turns are cacheable: a follow-up's meaning depends on its history.
    result = get_cached_answer(user.id, body.question) if not history else None
    cached = result is not None
    if result is None:
        result = await run_agent(
            question=body.question, history=history, user_id=user.id, token=token,
            llm=llm, tool_loader=tool_loader,
        )
        if not history and result["answer_type"] in ("grounded", "refused"):
            cache_answer(user.id, body.question, result)

    db.add_all([
        Message(conversation_id=convo.id, role="user", content=body.question),
        Message(conversation_id=convo.id, role="assistant", content=result["answer"], citations=result["citations"]),
    ])
    db.commit()
    return {**result, "conversation_id": convo.id, "cached": cached}


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def conversation_messages(
    conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Message]:
    convo = _conversation(db, user, conversation_id)
    return list(db.scalars(select(Message).where(Message.conversation_id == convo.id).order_by(Message.created_at)))
