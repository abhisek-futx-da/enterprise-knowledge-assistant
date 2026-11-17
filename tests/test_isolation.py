"""User B must never see, search, cite, read or delete user A's data, through any surface."""
from tests.conftest import register, upload


def test_documents_are_invisible_across_users(client):
    alice, bob = register(client), register(client)
    doc = upload(client, alice, "it_security_policy.md")
    assert client.get("/documents", headers=bob["headers"]).json() == []
    assert client.get(f"/documents/{doc['id']}", headers=bob["headers"]).status_code == 404
    assert client.delete(f"/documents/{doc['id']}", headers=bob["headers"]).status_code == 404
    assert client.get(f"/documents/{doc['id']}", headers=alice["headers"]).status_code == 200


def test_search_never_crosses_users(client):
    alice, bob = register(client), register(client)
    upload(client, alice, "it_security_policy.md")
    upload(client, bob, "travel_policy.md")
    for mode in ("vector", "bm25", "hybrid"):
        hits = client.post("/search", headers=bob["headers"], json={"query": "password MFA incident", "mode": mode}).json()
        assert all(h["filename"] == "travel_policy.md" for h in hits), mode


def test_chat_never_cites_other_users_documents(client):
    alice, bob = register(client), register(client)
    upload(client, alice, "product_faq.txt")
    out = client.post("/chat", headers=bob["headers"], json={"question": "What does error code E-417 mean?"}).json()
    assert out["answer_type"] == "refused"
    assert out["citations"] == []
