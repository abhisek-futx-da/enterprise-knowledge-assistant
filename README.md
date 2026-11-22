# Enterprise Knowledge Assistant

An agentic RAG application: users upload documents, then ask questions. Answers come from a
**LangGraph** agent that routes each question, runs **hybrid search** (pgvector + BM25), checks its own
answer for unsupported claims, and cites the exact document and page. The knowledge base is also exposed
through an **MCP server**, which the agent uses through an MCP client for library-level questions.

| Requirement | Where |
|---|---|
| RAG pipeline: extraction, chunking, embeddings, vector DB, semantic search | `app/ingestion/`, `app/retrieval/search.py` |
| Hybrid search: vectors + BM25 | `app/retrieval/search.py` (Reciprocal Rank Fusion) |
| LangChain + LangGraph agent: tool calling, conditional routing, state | `app/agent/graph.py` |
| MCP server (4 tools) + MCP client | `app/mcp_server.py`, `app/agent/mcp_client.py` |
| Citations + hallucination mitigation | `app/agent/graph.py` (`grade`, `verify`), `app/agent/prompts.py` |
| FastAPI REST API | `app/main.py`, `app/routers/` |
| PostgreSQL / SQLite + Redis | `app/db.py`, `app/models.py`, `app/cache.py` |
| Auth, roles, per-user data isolation | `app/security.py`, every query filtered by `owner_id` |
| Web app: sign-in, dashboard, streaming chat with evidence, library, search lab | `web/` (React + TypeScript + Tailwind) |
| Docker deployment | `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml` |
| Tests and evaluation | `tests/` (49 tests), `eval/` |

## Architecture

```mermaid
flowchart LR
    U[Web app<br/>React · nginx] -->|JWT · SSE| API[FastAPI<br/>auth · documents · search · chat]
    API -->|background task| ING[Ingestion<br/>extract → chunk → embed]
    ING --> PG[(PostgreSQL + pgvector<br/>users · documents · chunks · chats)]
    API --> AG[LangGraph agent]
    AG -->|hybrid search| RET[Retriever<br/>pgvector HNSW + BM25 → RRF]
    RET --> PG
    AG -->|chat model| LLM[LLM provider<br/>OpenAI / Anthropic / Ollama]
    AG -->|MCP client + user JWT| MCP[MCP server<br/>Streamable HTTP]
    MCP --> RET
    MCP --> PG
    API <--> R[(Redis<br/>answer cache · embedding cache<br/>rate limits · corpus versions)]
```

### Agent graph

```mermaid
flowchart TD
    S([question]) --> route{route}
    route -->|about document content| retrieve
    route -->|about the document library| tool_agent[tool agent<br/>MCP tools, ≤3 rounds]
    route -->|greeting / meta| direct
    retrieve --> grade{relevant sources?}
    grade -->|yes| generate
    grade -->|no, first try| rewrite[rewrite query] --> retrieve
    grade -->|no, retries used| refuse[refuse: “I don't know”]
    generate --> verify{citations valid<br/>and claims supported?}
    verify -->|yes| done([answer + citations])
    verify -->|no, retries left| generate
    verify -->|no, retries used| withhold[withhold answer]
    tool_agent -->|MCP unreachable| retrieve
    tool_agent --> done
    direct --> done
```

### Request flow for a question

1. `POST /chat/stream` (or `/chat`) checks the JWT, applies the per-user rate limit (Redis), and checks the answer cache.
2. **route**: the LLM classifies the question and rewrites follow-ups into standalone questions using
   the conversation history.
3. **retrieve**: hybrid search over **only this user's chunks**: pgvector cosine search plus BM25,
   merged with Reciprocal Rank Fusion. If the best cosine score is below `MIN_RELEVANCE`, there are no
   sources and the LLM is never asked to answer.
4. **grade**: the LLM keeps only the relevant sources. If none are relevant, the query is rewritten and
   retrieved once more, then the agent refuses.
5. **generate**: the LLM answers only from the numbered sources and cites them as `[S1]`.
6. **verify**: code rejects invented or missing citation ids. Then an LLM fact-check rejects claims not
   supported by the sources. A failed answer is regenerated once with that feedback, then withheld.
7. Each node's progress streams to the UI as Server-Sent Events while it runs. The answer, its citations
   (file, page, passage) and the agent trace are returned and stored.

## The web app

A focused workspace for asking documents questions and checking the answers. It is built with React,
TypeScript and Tailwind; the charts are plain SVG, and there is no UI framework dependency.

- **Sign in**: the left panel shows a verified answer being built step by step, so the product explains
  itself before login. One click opens the demo workspace.
- **Home**: an oversized ask field with suggested questions, a drop-to-upload tile, library metrics, an
  answer-quality dial (verified, declined, withheld) and recent conversations.
- **Ask**: answers stream in as the agent works ("Searching your documents… Verifying every claim…").
  Numbered citation chips open the exact passage in the **evidence panel**, with your question's words
  highlighted. Declined and withheld answers say why. Conversation history is on the left.
- **Library**: drag-and-drop upload, live indexing status, per-document "Ask about it", and delete with
  a confirmation step.
- **Search lab**: semantic, BM25 and hybrid results side by side. Hovering a passage shows where it
  ranks in each list, which makes the fusion visible.
- Light and dark themes (the system setting by default), keyboard first (`⌘K` to ask, `Enter` to send),
  responsive down to phones with a bottom tab bar, reduced-motion aware, and a strict CSP from nginx.

## Quick start (Docker)

```bash
cp .env.example .env    # set JWT_SECRET and GROQ_API_KEY (free at console.groq.com). Keys are read only from .env
docker compose up --build
```

| Service | URL |
|---|---|
| **Web app** | **http://localhost:3000** |
| REST API + Swagger docs | http://localhost:8000/docs |
| MCP server (Streamable HTTP) | http://localhost:8001/mcp |

Load a demo account (`demo@example.com` / `demo-password-1`) with the sample documents. It is safe to
re-run, including after `docker compose down -v` wipes the database:

```bash
python scripts/seed_demo.py
```

Check the running stack end to end (auth, ingestion, all three search modes, isolation and MCP):

```bash
python scripts/smoke_test.py          # no LLM calls
python scripts/smoke_test.py --chat   # also asks the agent three questions
```

## Run in VS Code (no Docker)

The repo ships a ready launch setup in `.vscode/`. No Docker is needed: it uses SQLite in place of Postgres and an
in-process cache in place of Redis.

1. Open the folder in VS Code and install the recommended extensions when asked (Python, Python Debugger).
2. One-time setup in VS Code's terminal (Terminal → New Terminal):
   ```bash
   python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
   cd web && npm install && cd ..
   cp .env.example .env      # then set JWT_SECRET and GROQ_API_KEY in .env
   ```
3. Open **Run and Debug** (⇧⌘D), pick **Run app (API + MCP + Web)** and press ▶. That starts the API on :8000,
   the MCP server on :8001 and the web app on :5173. The red ■ stops all three.
4. First time only: run **Seed demo account** from the same menu, then open **http://localhost:5173**.

If the Docker stack is running, stop it first (`docker compose stop`), because it uses the same ports.
Breakpoints work in the API and MCP server, since they run under the debugger.

## Local development (no Docker)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                        # SQLite + in-process cache by default
uvicorn app.main:app --reload --port 8000   # terminal 1
python -m app.mcp_server                    # terminal 2
cd web && npm install && npm run dev       # terminal 3 → http://localhost:5173 (proxies /api to :8000)
```

## Tests and evaluation

```bash
pytest -q                  # 49 tests, no API key or network needed
python -m eval.run_eval    # retrieval: vector vs BM25 vs hybrid, plus the relevance gate
python -m eval.run_eval --with-llm   # adds end-to-end answer accuracy (calls the LLM)
```

The tests use a deterministic scripted chat model and a hashing embedder, so they run offline. They cover:

- **Auth:** register and login, the same error for an unknown email and a wrong password, admin role checks.
- **Ingestion:** PDF, DOCX and text extraction, page-aware chunking, rejected file types, size limits.
- **Retrieval:** the RRF maths, BM25 finding exact identifiers, hybrid ranking.
- **Agent paths:** grounded answers, refusals, invented citations, a failed fact-check, the tool route,
  MCP-outage fallback, caching, rate limiting.
- **Isolation:** another user's data never shows up in the REST API, search, chat or MCP.
- **MCP:** a **real MCP server** over HTTP with the real client, covering discovery, scoping and bad tokens.

The isolation tests were checked by deleting the `owner_id` filter on purpose: three tests fail, so
they really catch a leak.

Latest retrieval results (`eval/results.md`, 22 in-scope + 4 out-of-scope questions, `bge-small-en-v1.5`):

| Mode | hit@1 | hit@5 | MRR |
|---|---|---|---|
| vector | 1.00 | 1.00 | 1.00 |
| bm25 | 0.86 | 0.95 | 0.90 |
| hybrid | 0.95 | 1.00 | 0.98 |

End-to-end answers with real models on Groq's free tier (`python -m eval.run_eval --with-llm`, per-model files in `eval/`):

| Model | Correct fact | Cites right document | Off-topic refused | Median per question |
|---|---|---|---|---|
| `openai/gpt-oss-120b` | 22/22 | 22/22 | 4/4 | 16.4 s, ~2,400 tokens |
| `qwen/qwen3.8-27b` | 22/22 | 22/22 | 4/4 | 15.4 s, ~1,900 tokens |

The median time is mostly waiting on the free tier's limit of 8,000 tokens per minute while 26 questions run back
to back. A single question in the app answers in a few seconds. The first run of this eval found two real bugs:
gpt-oss cites as `【S1】` with Unicode no-break spaces (correct answers were rejected as uncited), and Qwen once
routed general-knowledge questions to the greeting path. Both are fixed and covered by tests.

On this small, mostly paraphrased question set, vector search alone is already perfect. Hybrid's value
shows on exact identifiers (error codes, version numbers, names) that embeddings blur. 26 questions is
a smoke test, not a benchmark. Re-run the eval on your own documents before you rely on these numbers.

## Configuration

All settings are environment variables (`app/config.py`). The main ones:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/app.db` | `postgresql+psycopg://…` enables pgvector + an HNSW index |
| `REDIS_URL` | unset → in-process cache | Answer cache, embedding cache, rate limits |
| `LLM_PROVIDER` / `LLM_MODEL` | `groq` / `openai/gpt-oss-120b` | Open-weight model on Groq's free tier. Also `nvidia`, `gemini`, `openai`, `anthropic`, `ollama` |
| `LLM_REASONING_EFFORT` | unset | `low` / `medium` / `high` for reasoning models such as gpt-oss |
| `LLM_MAX_RETRIES` | `6` | Free tiers limit tokens per minute; the client backs off and retries on HTTP 429 |
| `EMBEDDING_PROVIDER` | `fastembed` (`BAAI/bge-small-en-v1.5`, 384-d, local) | Also `openai`; `hash` is for tests only |
| `MIN_RELEVANCE` | `0.55` | Relevance gate, set from the eval (in-scope min 0.62, out-of-scope max 0.54) |
| `GROUNDEDNESS_CHECK` | `true` | LLM fact-check of every answer |
| `MAX_ATTEMPTS` | `2` | Upper limit on query rewrites and regenerations |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per user, `/chat` |

## Documentation

- [docs/api.md](docs/api.md): REST endpoints and MCP tools, with examples. Live OpenAPI docs are at `/docs`.
- [docs/architecture.md](docs/architecture.md): design decisions, security model, scaling to production.
- [docs/demo.md](docs/demo.md): a step-by-step demo script.

## Project layout

```
app/
  main.py            FastAPI app, middleware, health
  config.py          all settings (env vars)
  db.py, models.py   SQLAlchemy models; pgvector on Postgres, JSON vectors on SQLite
  security.py        bcrypt, JWT, current-user and admin dependencies
  cache.py           Redis (or in-process) cache, rate limiter, corpus versions
  ingestion/         extract.py · chunking.py · embeddings.py · pipeline.py
  retrieval/         search.py (vector, BM25, RRF)
  agent/             graph.py (LangGraph) · prompts.py · llm.py · mcp_client.py
  mcp_server.py      MCP server (FastMCP, Streamable HTTP, JWT-verified)
  routers/           auth · documents/search · chat · admin
web/                 React + TypeScript + Tailwind app, served by nginx (web/nginx.conf)
eval/                corpus, labelled questions, run_eval.py, results.md
tests/               pytest suite
scripts/             smoke_test.py
```
