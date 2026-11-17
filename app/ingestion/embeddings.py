import hashlib
from functools import lru_cache

import numpy as np

from app.cache import cache_embedding, get_cached_embedding
from app.config import get_settings
from app.text import tokenize


def _normalise(vectors: np.ndarray) -> list[list[float]]:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vectors / norms).astype(float).tolist()


class HashEmbedder:
    """Deterministic hashed bag-of-words. No model download: used by tests and CI only."""

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _one(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim)
        for tok in tokenize(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0 if (h >> 8) % 2 else -1.0
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _normalise(np.array([self._one(t) for t in texts]))

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class FastEmbedEmbedder:
    """Local ONNX model (default BAAI/bge-small-en-v1.5, 384-d): free, offline, no API key."""

    def __init__(self, model: str) -> None:
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _normalise(np.array(list(self.model.passage_embed(texts))))

    def embed_query(self, text: str) -> list[float]:
        return _normalise(np.array(list(self.model.query_embed(text))))[0]


class OpenAIEmbedder:
    def __init__(self, model: str, dim: int) -> None:
        from langchain_openai import OpenAIEmbeddings

        self.model = OpenAIEmbeddings(model=model, dimensions=dim)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _normalise(np.array(self.model.embed_documents(texts)))

    def embed_query(self, text: str) -> list[float]:
        return _normalise(np.array([self.model.embed_query(text)]))[0]


@lru_cache
def get_embedder():
    s = get_settings()
    if s.embedding_provider == "hash":
        return HashEmbedder(s.embedding_dim)
    if s.embedding_provider == "openai":
        return OpenAIEmbedder(s.embedding_model, s.embedding_dim)
    if s.embedding_provider == "fastembed":
        return FastEmbedEmbedder(s.embedding_model)
    raise ValueError(f"Unknown EMBEDDING_PROVIDER '{s.embedding_provider}'")


def embed_query(text: str) -> list[float]:
    if (cached := get_cached_embedding(text)) is not None:
        return cached
    vector = get_embedder().embed_query(text)
    cache_embedding(text, vector)
    return vector


def embed_documents(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        out.extend(get_embedder().embed_documents(texts[i : i + batch_size]))
    return out
