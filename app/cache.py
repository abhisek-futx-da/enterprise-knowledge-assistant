"""Redis for query-embedding cache, answer cache, corpus versions and rate limits.

Falls back to an in-process store when REDIS_URL is unset, so tests and a laptop run need no Redis.
"""
import hashlib
import json
import threading
import time
from functools import lru_cache
from typing import Any

from app.config import get_settings


class InMemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}
        self._lock = threading.Lock()

    def _alive(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and expires < time.time():
            del self._data[key]
            return None
        return value

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._alive(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        with self._lock:
            self._data[key] = (value, time.time() + ex if ex else None)

    def incr(self, key: str) -> int:
        with self._lock:
            value = int(self._alive(key) or 0) + 1
            expires = self._data.get(key, (None, None))[1]
            self._data[key] = (str(value), expires)
            return value

    def expire(self, key: str, seconds: int) -> None:
        with self._lock:
            if (value := self._alive(key)) is not None:
                self._data[key] = (value, time.time() + seconds)

    def ping(self) -> bool:
        return True


@lru_cache
def get_store() -> Any:
    url = get_settings().redis_url
    if not url:
        return InMemoryStore()
    import redis

    return redis.Redis.from_url(url, decode_responses=True)


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]


def corpus_version(user_id: str) -> str:
    return get_store().get(f"corpus:{user_id}") or "0"


def bump_corpus_version(user_id: str) -> None:
    """Called on every upload/delete: invalidates that user's answer cache and BM25 index."""
    get_store().incr(f"corpus:{user_id}")


def get_cached_embedding(text: str) -> list[float] | None:
    raw = get_store().get(f"emb:{_digest(get_settings().embedding_model, text)}")
    return json.loads(raw) if raw else None


def cache_embedding(text: str, vector: list[float]) -> None:
    get_store().set(f"emb:{_digest(get_settings().embedding_model, text)}", json.dumps(vector), ex=86400)


def answer_key(user_id: str, question: str) -> str:
    return f"ans:{user_id}:{corpus_version(user_id)}:{_digest(question.strip().lower())}"


def get_cached_answer(user_id: str, question: str) -> dict | None:
    raw = get_store().get(answer_key(user_id, question))
    return json.loads(raw) if raw else None


def cache_answer(user_id: str, question: str, payload: dict) -> None:
    get_store().set(answer_key(user_id, question), json.dumps(payload), ex=get_settings().answer_cache_ttl)


def hit_rate_limit(user_id: str) -> bool:
    """Fixed one-minute window per user. Returns True when the request must be rejected."""
    key = f"rl:{user_id}:{int(time.time() // 60)}"
    store = get_store()
    count = store.incr(key)
    if count == 1:
        store.expire(key, 60)
    return count > get_settings().rate_limit_per_minute
