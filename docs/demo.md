# Demo script (about 10 minutes)

## 0. Start

```bash
cp .env.example .env   # set JWT_SECRET and OPENAI_API_KEY
docker compose up --build
python scripts/smoke_test.py    # shows every subsystem passing before the live demo
python scripts/seed_demo.py     # demo@example.com / demo-password-1 with the sample documents
```

## 1. Architecture (2 min)

Open the README diagrams. Follow one question through the system: API → agent → hybrid retrieval →
LLM → verify → citations. Point out the MCP server as a separate service that shares the retriever.

## 2. Auth and isolation (1 min)

UI at http://localhost:8501: register **alice** and **bob** in two browser windows (one private).

## 3. Ingestion (1 min)

As alice, upload the four files in `eval/corpus/`. Each document shows ⏳, then ✅ with its page and
chunk counts.

## 4. Hybrid search (2 min)

Open the **Search playground** tab and run each query:

- `E-417`: BM25 ranks the exact error-code passage first. Vector search gets the right file, but
  for a reason that is less certain.
- `how much time off do I get`: there is no word overlap with "annual leave", but vector search
  finds it.
- Hybrid combines both. Show the `ranks` field in `/docs` → `POST /search`.

## 5. Agent with citations (2 min)

In the **Chat** tab, open **Agent trace** for each answer:

1. "What does error code E-417 mean?" → grounded, cites `product_faq.txt` page 1.
2. Follow-up: "And what should I do if it comes back?" → the router turns it into a standalone
   question using the history.
3. "What is the capital of Australia?" → refused. The trace shows the relevance gate and the rewrite
   retry.
4. "Which documents do I have?" → the **tools** route: MCP tool discovery, then the
   `list_my_documents` call.

## 6. Isolation (30 s)

As bob, ask "What does error code E-417 mean?" → refused, no citations. Bob's documents list is empty.

## 7. MCP from outside (1 min)

Connect the MCP Inspector to `http://localhost:8001/mcp` with alice's token: the four tools are
discovered. Call `search_knowledge_base`. Then try a bad token → 401.

## 8. Quality (1 min)

Run `pytest -q` (37 passed) and `python -m eval.run_eval`, then show the vector/BM25/hybrid table and
the relevance-gate calibration.
