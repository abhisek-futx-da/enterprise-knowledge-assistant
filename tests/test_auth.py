from tests.conftest import register


def test_register_login_me(client):
    user = register(client)
    me = client.get("/auth/me", headers=user["headers"])
    assert me.status_code == 200
    assert me.json()["email"] == user["email"]
    assert me.json()["role"] == "user"


def test_duplicate_email_rejected(client):
    user = register(client)
    r = client.post("/auth/register", json={"email": user["email"], "password": "another-pass-1"})
    assert r.status_code == 409


def test_wrong_password_and_unknown_email_look_identical(client):
    user = register(client)
    bad_pw = client.post("/auth/login", data={"username": user["email"], "password": "wrong-password"})
    unknown = client.post("/auth/login", data={"username": "nobody@example.com", "password": "wrong-password"})
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json() == unknown.json()


def test_protected_routes_need_valid_token(client):
    assert client.get("/documents").status_code == 401
    assert client.get("/documents", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_weak_password_rejected(client):
    r = client.post("/auth/register", json={"email": "short@example.com", "password": "short"})
    assert r.status_code == 422


def test_admin_role_is_enforced(client):
    user = register(client)
    assert client.get("/admin/stats", headers=user["headers"]).status_code == 403
    admin = register(client, email="admin@example.com")
    r = client.get("/admin/stats", headers=admin["headers"])
    assert r.status_code == 200
    assert r.json()["users"] >= 2
