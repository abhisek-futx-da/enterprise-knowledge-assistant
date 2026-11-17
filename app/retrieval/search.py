"""Hybrid retrieval: dense vectors (semantic) + BM25 (exact terms), fused with Reciprocal Rank Fusion.

Every query is scoped by owner_id first; there is no code path that searches across users.
"""
import threading
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import corpus_version
from app.config import get_settings
from app.db import is_postgres
from app.ingestion.embeddings import embed_query
from app.models import Chunk, Document
from app.text import tokenize

Mode = Literal["vector", "bm25", "hybrid"]


@dataclass
class SearchHit:
    chunk_id: str
    document_id: str
    filename: str
    page: int
    chunk_index: int
    text: str
    score: float = 0.0
    vector_score: float | None = None  # cosine similarity, 0..1 for normalised vectors
    bm25_score: float | None = None
    ranks: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _row_to_hit(chunk: Chunk, filename: str) -> SearchHit:
    return SearchHit(chunk.id, chunk.document_id, filename, chunk.page, chunk.chunk_index, chunk.text)


def _base_query(user_id: str):
    return (
        select(Chunk, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.owner_id == user_id, Document.status == "ready")
    )


def vector_search(db: Session, user_id: str, query: str, k: int) -> list[SearchHit]:
    qvec = embed_query(query)
    if is_postgres():
        distance = Chunk.embedding.cosine_distance(qvec)
        rows = db.execute(_base_query(user_id).add_columns(distance.label("d")).order_by(distance).limit(k))
        hits = []
        for chunk, filename, d in rows:
            hit = _row_to_hit(chunk, filename)
            hit.vector_score = 1.0 - float(d)
            hits.append(hit)
        return hits

    rows = db.execute(_base_query(user_id)).all()
    if not rows:
        return []
    matrix = np.array([c.embedding for c, _ in rows])
    sims = matrix @ np.array(qvec)
    hits = []
    for i in np.argsort(-sims)[:k]:
        chunk, filename = rows[i]
        hit = _row_to_hit(chunk, filename)
        hit.vector_score = float(sims[i])
        hits.append(hit)
    return hits


class _BM25Cache:
    """One BM25 index per (user, corpus version), LRU-bounded. Rebuilt only after that user's corpus changes."""

    def __init__(self, max_users: int = 256) -> None:
        self._items: OrderedDict[str, tuple[str, BM25Okapi | None, list]] = OrderedDict()
        self._max = max_users
        self._lock = threading.Lock()

    def get(self, db: Session, user_id: str) -> tuple[BM25Okapi | None, list]:
        version = corpus_version(user_id)
        with self._lock:
            item = self._items.get(user_id)
            if item and item[0] == version:
                self._items.move_to_end(user_id)
                return item[1], item[2]
        rows = db.execute(_base_query(user_id).order_by(Chunk.id)).all()
        index = BM25Okapi([tokenize(c.text) or ["_"] for c, _ in rows]) if rows else None
        with self._lock:
            self._items[user_id] = (version, index, rows)
            self._items.move_to_end(user_id)
            while len(self._items) > self._max:
                self._items.popitem(last=False)
        return index, rows


bm25_cache = _BM25Cache()


def bm25_search(db: Session, user_id: str, query: str, k: int) -> list[SearchHit]:
    index, rows = bm25_cache.get(db, user_id)
    terms = tokenize(query)
    if index is None or not terms:
        return []
    scores = index.get_scores(terms)
    hits = []
    for i in np.argsort(-scores)[:k]:
        if scores[i] <= 0:
            break
        chunk, filename = rows[i]
        hit = _row_to_hit(chunk, filename)
        hit.bm25_score = float(scores[i])
        hits.append(hit)
    return hits


def reciprocal_rank_fusion(result_lists: dict[str, list[SearchHit]], k: int, rrf_k: int) -> list[SearchHit]:
    """score(d) = sum over lists of 1 / (rrf_k + rank). Rank-based, so BM25 and cosine scales never mix."""
    fused: dict[str, SearchHit] = {}
    for name, hits in result_lists.items():
        for rank, hit in enumerate(hits, start=1):
            merged = fused.setdefault(hit.chunk_id, hit)
            merged.score += 1.0 / (rrf_k + rank)
            merged.ranks[name] = rank
            merged.vector_score = merged.vector_score if hit.vector_score is None else hit.vector_score
            merged.bm25_score = merged.bm25_score if hit.bm25_score is None else hit.bm25_score
    return sorted(fused.values(), key=lambda h: h.score, reverse=True)[:k]


def search(db: Session, user_id: str, query: str, k: int | None = None, mode: Mode = "hybrid") -> list[SearchHit]:
    s = get_settings()
    k = k or s.top_k
    candidates = k * 4  # wider pool per retriever so fusion has something to re-rank
    if mode == "vector":
        hits = vector_search(db, user_id, query, k)
        for h in hits:
            h.score = h.vector_score or 0.0
        return hits
    if mode == "bm25":
        hits = bm25_search(db, user_id, query, k)
        for h in hits:
            h.score = h.bm25_score or 0.0
        return hits
    return reciprocal_rank_fusion(
        {"vector": vector_search(db, user_id, query, candidates), "bm25": bm25_search(db, user_id, query, candidates)},
        k=k, rrf_k=s.rrf_k,
    )
