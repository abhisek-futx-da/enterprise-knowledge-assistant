import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.cache import get_store
from app.config import Settings, get_settings
from app.db import SessionLocal, init_db
from app.routers import admin, auth, chat, documents

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    if not s.database_url.startswith("sqlite") and s.jwt_secret == Settings.model_fields["jwt_secret"].default:
        raise RuntimeError("JWT_SECRET is still the development default; set a real secret before deploying")
    init_db()
    yield


app = FastAPI(
    title=get_settings().app_name,
    version="1.0.0",
    description="Upload documents, search them (hybrid vector + BM25), and ask an agent that answers with "
    "citations. Authenticate with **POST /auth/login**, then use the Authorize button.",
    lifespan=lifespan,
)
for r in (auth.router, documents.router, chat.router, admin.router):
    app.include_router(r)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error request_id=%s", request_id)
        response = JSONResponse({"detail": "Internal server error", "request_id": request_id}, status_code=500)
    response.headers["x-request-id"] = request_id
    log.info("%s %s %s %.0fms id=%s", request.method, request.url.path, response.status_code,
             (time.perf_counter() - start) * 1000, request_id)
    return response


@app.get("/health", tags=["ops"])
def health() -> JSONResponse:
    checks = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        get_store().ping()
        checks["cache"] = "ok"
    except Exception as exc:
        checks["cache"] = f"error: {type(exc).__name__}"
    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ok" if healthy else "degraded", **checks}, status_code=200 if healthy else 503)
