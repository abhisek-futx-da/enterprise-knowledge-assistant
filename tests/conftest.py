import json
import os
import re
import tempfile
import uuid
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="eka-tests-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
    "REDIS_URL": "",
    "EMBEDDING_PROVIDER": "hash",
    "EMBEDDING_DIM": "256",
    "MIN_RELEVANCE": "0.1",
    "ADMIN_EMAILS": "admin@example.com",
    "JWT_SECRET": "test-secret-test-secret-test-secret",
    "RATE_LIMIT_PER_MINUTE": "1000",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from langchain_core.language_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult  # noqa: E402

from app.agent import prompts  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.chat import chat_llm, get_tool_loader  # noqa: E402

CORPUS = Path(__file__).resolve().parent.parent / "eval" / "corpus"
_SOURCE = re.compile(r'<source id="(S\d+)"[^>]*>\n(.*?)\n</source>', re.DOTALL)


class ScriptedLLM(BaseChatModel):
    """Deterministic stand-in for the chat model. It recognises which node is calling by the system
    prompt and answers the way a well-behaved model would, unless a test overrides a behaviour."""

    answer_override: str | None = None
    verify_grounded: bool = True
    calls: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._reply(messages))])

    def _reply(self, messages) -> AIMessage:
        system = messages[0].content if isinstance(messages[0], SystemMessage) else ""
        last = messages[-1].content
        if system == prompts.ROUTER_PROMPT:
            self.calls.append("route")
            msg = last.split("Message:", 1)[-1].strip()
            low = msg.lower()
            if low.startswith(("hello", "hi", "thanks")):
                route = "direct"
            elif "which documents" in low or "how many documents" in low:
                route = "tools"
            else:
                route = "retrieve"
            return AIMessage(content=f'{{"route": "{route}", "standalone_question": "{msg}"}}')
        if system == prompts.GRADER_PROMPT:
            self.calls.append("grade")
            ids = [i for i, _ in _SOURCE.findall(last)]
            return AIMessage(content=json.dumps({"relevant_ids": ids}))
        if system == prompts.REWRITE_PROMPT:
            self.calls.append("rewrite")
            return AIMessage(content=json.dumps({"query": last}))
        if system == prompts.ANSWER_PROMPT:
            self.calls.append("generate")
            if self.answer_override is not None:
                return AIMessage(content=self.answer_override)
            sid, text = _SOURCE.findall(last)[0]
            sentence = next(s for s in re.split(r"(?<=[.?!])\s+", text) if len(s) > 20)
            return AIMessage(content=f"{sentence.strip()} [{sid}]")
        if system == prompts.VERIFY_PROMPT:
            self.calls.append("verify")
            return AIMessage(content=json.dumps({"grounded": self.verify_grounded, "unsupported_claims": []}))
        if system == prompts.TOOL_AGENT_PROMPT:
            self.calls.append("tool_agent")
            if isinstance(last, str) and not isinstance(messages[-1], ToolMessage):
                return AIMessage(content="", tool_calls=[{"name": "list_my_documents", "args": {}, "id": "call_1"}])
            return AIMessage(content=f"Your documents: {last}")
        self.calls.append("direct")
        return AIMessage(content="Hello! Upload documents and ask me about them.")


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM(calls=[])


@pytest.fixture
def client(llm):
    async def no_tools(token: str):
        raise ConnectionError("MCP not running in this test")

    app.dependency_overrides[chat_llm] = lambda: llm
    app.dependency_overrides[get_tool_loader] = lambda: no_tools
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client: TestClient, email: str | None = None, password: str = "correct-horse-1") -> dict:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code in (201, 409), r.text
    token = client.post("/auth/login", data={"username": email, "password": password}).json()["access_token"]
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


def upload(client: TestClient, user: dict, name: str, content: bytes | None = None) -> dict:
    data = content if content is not None else (CORPUS / name).read_bytes()
    r = client.post("/documents", headers=user["headers"], files={"file": (name, data, "text/plain")})
    assert r.status_code == 202, r.text
    doc = client.get(f"/documents/{r.json()['id']}", headers=user["headers"]).json()
    return doc
