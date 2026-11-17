# API reference

Interactive OpenAPI docs: **http://localhost:8000/docs** (Swagger) and `/redoc`. Every endpoint except
`/auth/register`, `/auth/login` and `/health` needs `Authorization: Bearer <token>`.

## Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/register` | `{"email", "password"}` (password ≥ 8 chars) | `201` user · `409` email taken |
| POST | `/auth/login` | form: `username` (email), `password` | `{"access_token", "token_type": "bearer"}` · `401` |
| GET | `/auth/me` | | current user |

```bash
curl -X POST localhost:8000/auth/register -H 'content-type: application/json' \
  -d '{"email":"alice@example.com","password":"alice-password"}'
TOKEN=$(curl -s -X POST localhost:8000/auth/login -d 'username=alice@example.com&password=alice-password' | jq -r .access_token)
```

Tokens are HS256 JWTs with `sub` (user id), `role`, `aud` and `exp` (60 min by default). Emails listed in
`ADMIN_EMAILS` get the `admin` role when they register.

## Documents

| Method | Path | Notes |
|---|---|---|
| POST | `/documents` | multipart `file`: `.pdf .docx .txt .md`, ≤ `MAX_UPLOAD_MB`. Returns `202` with `status: pending`; ingestion runs in the background |
| GET | `/documents` | the caller's documents only |
| GET | `/documents/{id}` | `status`: `pending` → `ready` or `failed` (with `error`). Another user's id returns `404` |
| DELETE | `/documents/{id}` | `204`; deletes its chunks and invalidates the caller's answer cache |

```bash
curl -H "Authorization: Bearer $TOKEN" -F file=@eval/corpus/product_faq.txt localhost:8000/documents
```

## Search (retrieval only, no LLM)

`POST /search` with `{"query": "E-417", "mode": "hybrid" | "vector" | "bm25", "top_k": 5}`.
Each hit has `filename`, `page`, `text`, the fused `score`, `vector_score` (cosine), `bm25_score`, and
`ranks` (its rank in each retriever list). Use it to compare retrieval modes.

## Chat (agent)

`POST /chat` with `{"question": "...", "conversation_id": null}`. Pass the returned
`conversation_id` to ask follow-ups.

```json
{
  "answer": "E-417 means a thermal sensor fault [S1].",
  "answer_type": "grounded",
  "route": "retrieve",
  "grounded": true,
  "citations": [{"id": "S1", "document_id": "…", "filename": "product_faq.txt", "page": 1,
                 "chunk_index": 0, "snippet": "What does error code E-417 mean? …"}],
  "tool_calls": [],
  "trace": ["route -> retrieve", "retrieve 'What does error code E-417 mean?' -> 4 hits (best cosine 0.81)",
            "grade -> 1/4 relevant", "generate (attempt 1)", "verify -> grounded, 1 citation(s)"],
  "conversation_id": "…",
  "cached": false
}
```

The `trace` above shows the shape of the response; its scores are illustrative.

| `answer_type` | Meaning |
|---|---|
| `grounded` | Answer passed the citation check and the fact-check |
| `refused` | No relevant sources: "I don't know based on your documents." |
| `unverified` | An answer was generated but failed verification twice, so it was withheld |
| `tool` | Answered by the MCP tool agent (library questions such as "which documents do I have?") |
| `direct` | Greeting or a question about the assistant; no document facts |

`GET /conversations/{id}/messages` returns the stored history. Another user's conversation returns `404`.
`/chat` returns `429` when the per-user rate limit is exceeded.

### Streaming

`POST /chat/stream` takes the same body and returns `text/event-stream`. Events arrive in order:
`{"type":"start","conversation_id"}`, then one `{"type":"step","node","trace"}` per agent node as it
finishes, then `{"type":"final", …}` (same shape as the `/chat` response). If the model call fails after
streaming has started, the last event is `{"type":"error","detail"}`. Validation, auth, rate-limit and
"LLM not configured" (`503`) errors are returned as normal HTTP errors before the stream starts.

`GET /conversations` lists the caller's 30 most recent conversations (title = first question).
`GET /stats` returns the caller's own counts: documents by status, pages, passages, questions and
answers by type. The web dashboard is built on it.

## Admin (role `admin`)

| Method | Path | Returns |
|---|---|---|
| GET | `/admin/users` | all users (no passwords) |
| GET | `/admin/stats` | counts of users, documents (by status) and chunks; never document content |

## Ops

`GET /health` returns `200 {"status":"ok","database":"ok","cache":"ok"}`, or `503` when a dependency is down.
Every response carries an `x-request-id` header, which also appears in the logs.

## MCP server

Streamable HTTP at `http://localhost:8001/mcp`, stateless, JSON responses. Every request needs
`Authorization: Bearer <same JWT as the REST API>`; a bad token gets HTTP `401`.

| Tool | Arguments | Returns |
|---|---|---|
| `search_knowledge_base` | `query`, `top_k` (1–20), `mode` (`hybrid`/`vector`/`bm25`) | passages with filename, page, score |
| `list_my_documents` | | id, filename, status, pages, chunks, upload time |
| `read_document_page` | `document_id`, `page` | full text of that page |
| `knowledge_base_stats` | | document and chunk counts by status |

No tool takes a `user_id`: the server reads the user from the verified token, so a client cannot ask for
another user's data. Any MCP client can connect, for example the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector   # transport: Streamable HTTP, URL above, header Authorization: Bearer $TOKEN
```
