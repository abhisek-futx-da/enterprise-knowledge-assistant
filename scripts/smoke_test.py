"""End-to-end check against a running stack (docker compose up).

    python scripts/smoke_test.py            # auth, ingestion, pgvector/BM25/hybrid search, isolation, MCP
    python scripts/smoke_test.py --chat     # also asks the agent questions (calls the configured LLM)
"""
import argparse
import asyncio
import sys
import time
import uuid
from pathlib import Path

import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient

API = "http://localhost:8000"
MCP = "http://localhost:8001/mcp"
CORPUS = Path(__file__).resolve().parent.parent / "eval" / "corpus"


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}{'  ' + detail if detail else ''}")
    if not ok:
        sys.exit(1)


def new_user(c: httpx.Client) -> dict:
    email, pw = f"smoke-{uuid.uuid4().hex[:6]}@example.com", "smoke-password-1"
    c.post("/auth/register", json={"email": email, "password": pw}).raise_for_status()
    token = c.post("/auth/login", data={"username": email, "password": pw}).json()["access_token"]
    return {"token": token, "h": {"Authorization": f"Bearer {token}"}}


async def mcp_tools(token: str) -> dict:
    client = MultiServerMCPClient({"kb": {"transport": "streamable_http", "url": MCP,
                                          "headers": {"Authorization": f"Bearer {token}"}}})
    return {t.name: t for t in await client.get_tools()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat", action="store_true")
    args = parser.parse_args()
    c = httpx.Client(base_url=API, timeout=120)
    check("health", c.get("/health").json().get("status") == "ok")

    alice, bob = new_user(c), new_user(c)
    ids = []
    for path in sorted(CORPUS.iterdir()):
        r = c.post("/documents", headers=alice["h"], files={"file": (path.name, path.read_bytes(), "text/plain")})
        ids.append(r.json()["id"])
    for _ in range(60):
        statuses = {c.get(f"/documents/{i}", headers=alice["h"]).json()["status"] for i in ids}
        if statuses == {"ready"}:
            break
        time.sleep(1)
    check("ingestion", statuses == {"ready"}, str(statuses))

    for mode, query, expected in [("vector", "how much time off do I get", "employee_handbook.md"),
                                  ("bm25", "E-417", "product_faq.txt"),
                                  ("hybrid", "hotel cap London", "travel_policy.md")]:
        hits = c.post("/search", headers=alice["h"], json={"query": query, "mode": mode}).json()
        check(f"search {mode}", bool(hits) and hits[0]["filename"] == expected, hits[0]["filename"] if hits else "none")

    check("isolation: bob sees no documents", c.get("/documents", headers=bob["h"]).json() == [])
    check("isolation: bob search empty", c.post("/search", headers=bob["h"], json={"query": "E-417"}).json() == [])
    check("isolation: bob gets 404 on alice's doc", c.get(f"/documents/{ids[0]}", headers=bob["h"]).status_code == 404)

    tools = asyncio.run(mcp_tools(alice["token"]))
    check("mcp discovery", len(tools) == 4, str(sorted(tools)))
    listed = str(asyncio.run(tools["list_my_documents"].ainvoke({})))
    check("mcp list_my_documents", "product_faq.txt" in listed)
    bob_tools = asyncio.run(mcp_tools(bob["token"]))
    check("mcp isolation", "product_faq.txt" not in str(asyncio.run(bob_tools["list_my_documents"].ainvoke({}))))

    if args.chat:
        for q in ["What does error code E-417 mean?", "Which documents do I have?", "What is the capital of Australia?"]:
            out = c.post("/chat", headers=alice["h"], json={"question": q}).json()
            print(f"\nQ: {q}\n[{out['answer_type']} via {out['route']}] {out['answer']}")
            for cite in out["citations"]:
                print(f"   [{cite['id']}] {cite['filename']} p{cite['page']}")
            print("   trace:", " | ".join(out["trace"]))
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
