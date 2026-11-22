from app.retrieval.search import SearchHit, reciprocal_rank_fusion
from app.text import tokenize
from tests.conftest import register, upload


def _hit(cid: str) -> SearchHit:
    return SearchHit(cid, "d", "f", 1, 0, "t")


def test_rrf_rewards_agreement_between_retrievers():
    fused = reciprocal_rank_fusion(
        {"vector": [_hit("a"), _hit("b"), _hit("c")], "bm25": [_hit("c"), _hit("b"), _hit("x")]}, k=4, rrf_k=60
    )
    order = [h.chunk_id for h in fused]
    # b is rank 2 in both lists (2/62) and beats a, which is rank 1 in only one list (1/61)
    assert order[0] in {"b", "c"} and order.index("b") < order.index("a")
    assert fused[0].score == max(h.score for h in fused)
    assert set(fused[0].ranks) == {"vector", "bm25"}


def test_tokenize_drops_stopwords_keeps_codes():
    assert tokenize("What does error code E-417 mean?") == ["error", "code", "e", "417", "mean"]


def test_bm25_finds_exact_identifier(client):
    user = register(client)
    upload(client, user, "product_faq.txt")
    upload(client, user, "employee_handbook.md")
    hits = client.post("/search", headers=user["headers"], json={"query": "E-417", "mode": "bm25"}).json()
    assert hits[0]["filename"] == "product_faq.txt"
    assert "E-417" in hits[0]["text"]


def test_hybrid_returns_fused_ranks(client):
    user = register(client)
    upload(client, user, "travel_policy.md")
    upload(client, user, "employee_handbook.md")
    hits = client.post(
        "/search", headers=user["headers"], json={"query": "hotel cap per night", "mode": "hybrid", "top_k": 3}
    ).json()
    assert hits[0]["filename"] == "travel_policy.md"
    assert hits[0]["ranks"]
    assert len(hits) <= 3


def test_vector_mode_scores_are_cosine(client):
    user = register(client)
    upload(client, user, "travel_policy.md")
    hits = client.post("/search", headers=user["headers"], json={"query": "hotel per night", "mode": "vector"}).json()
    assert all(-1.0 <= h["vector_score"] <= 1.0 for h in hits)
    assert hits == sorted(hits, key=lambda h: h["vector_score"], reverse=True)


def test_bm25_index_notices_new_documents_without_the_shared_cache(client, monkeypatch):
    """Without Redis, the API and MCP processes don't share corpus versions; the index must still refresh."""
    user = register(client)
    upload(client, user, "employee_handbook.md")
    assert client.post("/search", headers=user["headers"], json={"query": "E-417", "mode": "bm25"}).json() == []
    monkeypatch.setattr("app.ingestion.pipeline.bump_corpus_version", lambda user_id: None)  # signal lost
    upload(client, user, "product_faq.txt")
    hits = client.post("/search", headers=user["headers"], json={"query": "E-417", "mode": "bm25"}).json()
    assert hits and hits[0]["filename"] == "product_faq.txt"
