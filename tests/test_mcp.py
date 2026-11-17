"""Runs the real MCP server over Streamable HTTP and talks to it with the real MCP client."""
import asyncio
import socket
import threading
import time

import pytest
import uvicorn

from app.agent import mcp_client
from app.config import get_settings
from app.mcp_server import create_mcp_server
from tests.conftest import register, upload


@pytest.fixture(scope="module")
def mcp_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(
        create_mcp_server(port=port).streamable_http_app(), host="127.0.0.1", port=port, log_level="warning"
    ))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def tools_for(mcp_url, monkeypatch):
    monkeypatch.setattr(get_settings(), "mcp_server_url", mcp_url)

    def _load(token):
        tools = asyncio.run(mcp_client.load_mcp_tools(token))
        return {t.name: t for t in tools}

    return _load


def _call(tool, args):
    return str(asyncio.run(tool.ainvoke(args)))


def test_tool_discovery_lists_four_tools(client, tools_for):
    user = register(client)
    assert set(tools_for(user["token"])) == {
        "search_knowledge_base", "list_my_documents", "read_document_page", "knowledge_base_stats",
    }


def test_tools_are_scoped_to_the_token_owner(client, tools_for):
    alice, bob = register(client), register(client)
    doc = upload(client, alice, "product_faq.txt")
    alice_tools, bob_tools = tools_for(alice["token"]), tools_for(bob["token"])

    assert "product_faq.txt" in _call(alice_tools["list_my_documents"], {})
    assert "E-417" in _call(alice_tools["search_knowledge_base"], {"query": "E-417 thermal"})
    assert "thermal sensor" in _call(alice_tools["read_document_page"], {"document_id": doc["id"], "page": 1})
    assert '"total_documents":1' in _call(alice_tools["knowledge_base_stats"], {}).replace(" ", "")

    assert "product_faq.txt" not in _call(bob_tools["list_my_documents"], {})
    assert "E-417" not in _call(bob_tools["search_knowledge_base"], {"query": "E-417 thermal"})
    assert "not found" in _call(bob_tools["read_document_page"], {"document_id": doc["id"], "page": 1})


def test_invalid_token_is_rejected(tools_for):
    with pytest.raises(ExceptionGroup) as exc:  # the MCP client surfaces the HTTP error from a task group
        tools_for("not-a-valid-jwt")
    status = [getattr(getattr(e, "response", None), "status_code", None) for e in exc.value.exceptions]
    assert 401 in status
