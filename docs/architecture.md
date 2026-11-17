# Architecture and design decisions

The diagrams are in the [README](../README.md#architecture). This page explains why each piece is the
way it is: the questions an architecture review asks.

## Technology choices

| Choice | Why | Alternative considered |
|---|---|---|
| **FastAPI** | Async, Pydantic validation, OpenAPI docs generated for free | Flask (no typing or validation built in) |
| **PostgreSQL + pgvector** | One database for users, documents, chunks *and* vectors. Ownership filters and deletes are ordinary SQL in one transaction. HNSW index for approximate search | Separate vector DB (Qdrant, Pinecone): another system to secure and keep in sync |
| **SQLite fallback** | Zero-setup local runs and tests. Vectors stored as JSON, cosine in NumPy | |
| **BM25 (`rank_bm25`)** | Real BM25 scoring. Embeddings blur exact tokens such as `E-417` or `4.2.1`; BM25 matches them | Postgres `ts_rank` (not BM25); OpenSearch (heavier) |
| **Reciprocal Rank Fusion** | Combines rankings, not raw scores, so cosine (0–1) and BM25 (unbounded) never need normalising | Weighted score sum (needs per-corpus tuning) |
| **fastembed `bge-small-en-v1.5`** | Local ONNX model, 384-d. No API key, no per-token cost, baked into the image | OpenAI embeddings (supported via `EMBEDDING_PROVIDER=openai`) |
| **LangGraph** | The agent is an explicit state machine: every branch, loop and retry limit is visible and testable | A free-form ReAct loop (unbounded, hard to test) |
| **MCP (official SDK, Streamable HTTP)** | A standard tool protocol. The same tools serve this agent *and* any MCP client (IDEs, desktop assistants) | Hard-coded LangChain tools (only this agent could use them) |
| **Redis** | Shared cache and rate-limit counters across API replicas | In-process cache (used when `REDIS_URL` is unset) |

## RAG pipeline

1. **Extract**: `pypdf` per page, `python-docx`, UTF-8 text/markdown. A file's content must match its
   extension (a fake `.pdf` is rejected). Scanned PDFs with no text layer are marked `failed` with a clear
   reason (OCR is not enabled).
2. **Chunk**: `RecursiveCharacterTextSplitter`, 800 characters with 120 overlap. It splits on
   paragraphs, then lines, then sentences. Splitting happens **per page**, so every chunk keeps an exact
   page number for its citation.
3. **Embed**: batches of 64 passages. Query embeddings are cached in Redis by hash of
   (model, text).
4. **Store**: chunks keep a copy of `owner_id`, so every search filters on one indexed column without a join.
5. **Search**: each retriever fetches `4 × k` candidates, RRF (`k=60`) fuses them, and the top `k` are kept.

## How the agent decides

The graph is in `app/agent/graph.py`. Routing uses LLM output parsed as JSON into Pydantic models
(`RouteDecision`, `GradeResult`, `VerifyResult`). If the reply can't be parsed, the agent falls back to
a safe default (route → `retrieve`, verifier → *not grounded*) instead of crashing. Runtime objects
(LLM, MCP tool loader, user token) are passed in through LangGraph's `config["configurable"]`, so the
graph is compiled once and shared by all requests.

**Worst-case LLM calls per question** (estimate, with the default `MAX_ATTEMPTS=2`):
route 1 + grade 2 + rewrite 1 + generate 2 + verify 2 = **8**. The common case is 4: route, grade,
generate, verify. The tool path is at most 1 + 3 tool rounds + 1 final = 5. Because every loop has a
limit, the cost per question has a known maximum.

## Hallucination controls (layered)

1. **Relevance gate**: if the best cosine score is below `MIN_RELEVANCE`, the agent refuses without
   calling the generator. The value comes from `eval/run_eval.py`, which prints the in-scope vs
   out-of-scope gap.
2. **Grader**: the LLM drops retrieved passages that don't help, and an empty result leads to a query
   rewrite and then a refusal.
3. **Prompt**: answer only from the numbered sources, cite every factual sentence, and say "I don't know"
   otherwise. Temperature is 0.
4. **Citation check in code**: invented ids (`[S9]` when there are 4 sources) or no citations at all mean
   the answer is rejected. This check does not trust the model.
5. **Fact-check**: a second LLM pass lists unsupported claims. On failure the answer is regenerated
   once with that feedback, then **withheld** rather than shown.
6. **Citations returned**: file, page and snippet, so a user can check any claim themselves.

## Security model

- **Authentication**: bcrypt password hashes and short-lived HS256 JWTs with audience checks. An
  unknown email and a wrong password get the identical error, so login can't be used to find accounts.
- **Authorization**: `user` and `admin` roles. Admin endpoints return counts only, never other users'
  content.
- **Data isolation**: every document, chunk, search, conversation and MCP query is filtered by the
  caller's id. Another user's resource returns `404` rather than `403`, which doesn't confirm it
  exists. Tests cover isolation on every surface and fail when the filter is removed.
- **MCP auth**: the MCP server checks the **end user's** JWT (it is an OAuth resource server via the
  SDK's `TokenVerifier`). No tool accepts a user id, so neither the agent nor any other client can
  ask for another user's data. DNS-rebinding protection is on (allowed `Host` headers are configured).
- **Prompt injection**: retrieved text and tool output are treated as data. Sources are wrapped in
  `<source>` tags, with any `<source`/`</source` inside a document escaped so it cannot break out. The
  prompts say content inside tags is never an instruction. The model's output only becomes text shown
  to the user; it never triggers an action that writes data.
- **Input limits**: allowed file extensions, magic-byte check for PDFs, upload size cap, request length
  caps (Pydantic), per-user rate limit.
- **Containers**: run as a non-root user. Secrets come only from the environment (`.env` is git-ignored).

## Errors and resilience

- Ingestion failures mark the document `failed` with a readable reason. The API never returns a 500 for
  a bad file.
- If the MCP server is down, the tool route **falls back to normal RAG** (tested).
- LLM clients retry twice with a timeout. Unparseable structured output falls back to safe defaults.
- Unhandled exceptions return a JSON 500 with a `request_id`. `/health` reports the database and cache
  separately and returns 503 when either is down.
- Schema setup at boot takes a Postgres advisory lock. Without it, two API workers starting together
  raced on `CREATE EXTENSION`. The first `docker compose up` caught this bug.

## Scaling to production

| Pressure | Change |
|---|---|
| More API traffic | API and MCP are stateless (JWT, Redis, Postgres; MCP runs `stateless_http`), so add replicas behind a load balancer |
| Large uploads / ingestion spikes | Move `BackgroundTasks` to a queue (Celery, arq or SQS) with dedicated workers, and store raw files in object storage (S3) |
| BM25 over large corpora | The per-user in-memory BM25 index is rebuilt when that user's corpus changes. At scale, move to OpenSearch/Elasticsearch, or a Postgres BM25 extension (e.g. ParadeDB `pg_search`) |
| Millions of vectors | pgvector HNSW tuning (`m`, `ef_search`), partitioning by tenant, or a dedicated vector DB |
| Retrieval quality | Add a cross-encoder reranker after RRF, then measure on a larger labelled set before keeping it |
| LLM cost and latency | Use a cheaper model for route/grade and a stronger one for generate; stream tokens over SSE; the Redis answer cache is already in place |
| Multi-tenant enterprise | Organisation-level tenancy and sharing, Postgres row-level security as a second layer, SSO (OIDC) instead of local passwords |
| Observability | OpenTelemetry traces per graph node, LangSmith or Langfuse for LLM traces, token and cost metrics per user |
| Secrets and deploy | A secrets manager, managed Postgres and Redis, Kubernetes or ECS with the health checks already defined |
