import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import HISTORY_TURNS, stream_agent
from app.agent.llm import get_llm
from app.agent.mcp_client import load_mcp_tools
from app.cache import cache_answer, get_cached_answer, hit_rate_limit
from app.db import SessionLocal, get_db
from app.models import Conversation, Message, User
from app.schemas import ChatRequest, ChatResponse, ConversationOut, MessageOut
from app.security import get_current_user, oauth2_scheme

router = APIRouter(tags=["chat"])
log = logging.getLogger(__name__)


def _failure_detail(exc: Exception) -> str:
    """Safe to show users: names the error class only, never its message (it may echo request data)."""
    return (f"The assistant couldn't reach the language model ({type(exc).__name__}). "
            "Check LLM_PROVIDER, the API key and its credits, then try again.")


def chat_llm():
    try:
        return get_llm()
    except Exception as exc:  # missing key / unknown provider: say what to fix instead of a bare 500
        log.warning("LLM not configured: %s", type(exc).__name__)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"The language model isn't configured ({type(exc).__name__}). "
            "Set LLM_PROVIDER and its API key in .env, then restart the API.",
        ) from exc


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


def _prepare(db: Session, user: User, body: ChatRequest) -> tuple[str, list[dict], dict | None]:
    """Rate limit, resolve the conversation, load history and check the answer cache."""
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
    cached = get_cached_answer(user.id, body.question) if not history else None
    return convo.id, history, cached


def _persist(user_id: str, conversation_id: str, question: str, result: dict, cacheable: bool) -> None:
    db = SessionLocal()  # own session: a streaming response outlives the request-scoped one
    try:
        db.add_all([
            Message(conversation_id=conversation_id, role="user", content=question),
            Message(conversation_id=conversation_id, role="assistant", content=result["answer"],
                    answer_type=result["answer_type"], citations=result["citations"]),
        ])
        db.commit()
    finally:
        db.close()
    if cacheable and result["answer_type"] in ("grounded", "refused"):
        cache_answer(user_id, question, result)


async def _events(
    user: User, token: str, body: ChatRequest, conversation_id: str, history: list[dict],
    cached: dict | None, llm, tool_loader,
) -> AsyncIterator[dict]:
    yield {"type": "start", "conversation_id": conversation_id}
    result = cached
    if result is None:
        async for event in stream_agent(question=body.question, history=history, user_id=user.id, token=token,
                                        llm=llm, tool_loader=tool_loader):
            if event["type"] == "final":
                result = {k: v for k, v in event.items() if k != "type"}
            else:
                yield event
    _persist(user.id, conversation_id, body.question, result, cacheable=cached is None and not history)
    yield {"type": "final", **result, "conversation_id": conversation_id, "cached": cached is not None}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    llm=Depends(chat_llm),
    tool_loader=Depends(get_tool_loader),
) -> dict:
    conversation_id, history, cached = _prepare(db, user, body)
    final: dict = {}
    try:
        async for event in _events(user, token, body, conversation_id, history, cached, llm, tool_loader):
            final = event
    except Exception as exc:
        log.exception("chat failed")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, _failure_detail(exc)) from exc
    return {k: v for k, v in final.items() if k != "type"}


@router.post("/chat/stream", response_class=StreamingResponse, responses={200: {"content": {"text/event-stream": {}}}})
async def chat_stream(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    llm=Depends(chat_llm),
    tool_loader=Depends(get_tool_loader),
) -> StreamingResponse:
    """Server-Sent Events: `start`, one `step` per agent node as it finishes, then `final` (same shape as /chat)."""
    conversation_id, history, cached = _prepare(db, user, body)

    async def sse() -> AsyncIterator[str]:
        try:
            async for event in _events(user, token, body, conversation_id, history, cached, llm, tool_loader):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:  # headers are already sent, so the error travels as an event and the stream ends cleanly
            log.exception("chat stream failed")
            yield f"data: {json.dumps({'type': 'error', 'detail': _failure_detail(exc)})}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    convos = db.scalars(
        select(Conversation).where(Conversation.owner_id == user.id).order_by(Conversation.created_at.desc()).limit(30)
    ).all()
    ids = [c.id for c in convos]
    first_question: dict[str, str] = {}
    counts: dict[str, int] = {}
    for m in db.scalars(  # one query for all conversations' messages, not one per conversation
        select(Message).where(Message.conversation_id.in_(ids), Message.role == "user").order_by(Message.created_at)
    ):
        first_question.setdefault(m.conversation_id, m.content)
        counts[m.conversation_id] = counts.get(m.conversation_id, 0) + 1
    return [
        {"id": c.id, "title": first_question[c.id][:120], "questions": counts[c.id], "created_at": c.created_at}
        for c in convos if c.id in first_question
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def conversation_messages(
    conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Message]:
    convo = _conversation(db, user, conversation_id)
    return list(db.scalars(select(Message).where(Message.conversation_id == convo.id).order_by(Message.created_at)))
