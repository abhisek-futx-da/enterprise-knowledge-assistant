from app.agent import prompts
from app.main import app
from app.routers.chat import get_tool_loader
from tests.conftest import register, upload


def _ask(client, user, question, conversation_id=None):
    r = client.post("/chat", headers=user["headers"], json={"question": question, "conversation_id": conversation_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_grounded_answer_has_valid_citations(client, llm):
    user = register(client)
    doc = upload(client, user, "product_faq.txt")
    out = _ask(client, user, "What does error code E-417 mean?")
    assert out["answer_type"] == "grounded"
    assert out["grounded"] is True
    assert out["route"] == "retrieve"
    assert out["citations"] and out["citations"][0]["document_id"] == doc["id"]
    assert f"[{out['citations'][0]['id']}]" in out["answer"]
    assert llm.calls == ["route", "grade", "generate", "verify"]


def test_out_of_scope_question_is_refused_without_generating(client, llm):
    user = register(client)
    upload(client, user, "product_faq.txt")
    out = _ask(client, user, "Who painted the Mona Lisa?")
    assert out["answer_type"] == "refused"
    assert out["answer"] == prompts.REFUSAL
    assert "generate" not in llm.calls  # relevance gate stopped it before the model could improvise
    assert "rewrite" in llm.calls  # one corrective retry before giving up


def test_invented_citation_is_rejected_then_withheld(client, llm):
    llm.answer_override = "The warranty is 99 years [S9]."
    user = register(client)
    upload(client, user, "product_faq.txt")
    out = _ask(client, user, "What warranty does the HX-200 have?")
    assert out["answer_type"] == "unverified"
    assert out["citations"] == []
    assert "99 years" not in out["answer"]
    assert llm.calls.count("generate") == 2  # bounded: max_attempts regenerations


def test_ungrounded_answer_fails_verifier(client, llm):
    llm.verify_grounded = False
    user = register(client)
    upload(client, user, "product_faq.txt")
    out = _ask(client, user, "What does error code E-417 mean?")
    assert out["answer_type"] == "unverified"
    assert any("unsupported" in t for t in out["trace"])


def test_direct_route_skips_retrieval(client, llm):
    user = register(client)
    out = _ask(client, user, "hello there")
    assert out["route"] == "direct"
    assert llm.calls == ["route", "direct"]


def test_tools_route_calls_mcp_tools(client, llm):
    from langchain_core.tools import tool

    @tool
    def list_my_documents() -> str:
        """List documents."""
        return "product_faq.txt (ready)"

    async def fake_loader(token: str):
        assert token  # the user's JWT is forwarded to MCP
        return [list_my_documents]

    app.dependency_overrides[get_tool_loader] = lambda: fake_loader
    user = register(client)
    out = _ask(client, user, "Which documents do I have?")
    assert out["route"] == "tools"
    assert out["answer_type"] == "tool"
    assert out["tool_calls"] == [{"tool": "list_my_documents", "args": {}}]
    assert "product_faq.txt" in out["answer"]


def test_mcp_outage_falls_back_to_rag(client, llm):
    user = register(client)
    upload(client, user, "product_faq.txt")
    out = _ask(client, user, "How many documents mention E-417?")
    assert any("mcp unavailable" in t for t in out["trace"])
    assert out["answer_type"] in ("grounded", "refused")


def test_conversation_history_is_kept_and_scoped(client):
    user = register(client)
    upload(client, user, "product_faq.txt")
    first = _ask(client, user, "What does error code E-417 mean?")
    second = _ask(client, user, "What does error code E-102 mean?", first["conversation_id"])
    assert second["conversation_id"] == first["conversation_id"]
    msgs = client.get(f"/conversations/{first['conversation_id']}/messages", headers=user["headers"]).json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    other = register(client)
    assert client.get(f"/conversations/{first['conversation_id']}/messages", headers=other["headers"]).status_code == 404


def test_answer_cache_hits_and_invalidates_on_upload(client, llm):
    user = register(client)
    upload(client, user, "product_faq.txt")
    q = "What does error code E-417 mean?"
    assert _ask(client, user, q)["cached"] is False
    calls_after_first = len(llm.calls)
    assert _ask(client, user, q)["cached"] is True
    assert len(llm.calls) == calls_after_first  # no model calls on a cache hit
    upload(client, user, "travel_policy.md")  # corpus changed -> cached answer is stale
    assert _ask(client, user, q)["cached"] is False


def test_rate_limit(client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 2)
    user = register(client)
    codes = [client.post("/chat", headers=user["headers"], json={"question": "hello"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
