"""Authentication, token handling and ownership: a user must never see or change another user's data."""
from conftest import SYMPTOMS, auth, register


def test_register_then_me(client):
    body = register(client, "carol@example.com", name="Carol")
    assert body["token_type"] == "bearer" and body["user"]["email"] == "carol@example.com"
    me = client.get("/api/v1/auth/me", headers=auth(body))
    assert me.status_code == 200 and me.json()["name"] == "Carol"


def test_duplicate_email_rejected(client):
    register(client, "dup@example.com")
    r = client.post("/api/v1/auth/register", json={"email": "DUP@example.com", "password": "another-pass-1"})
    assert r.status_code == 409


def test_short_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={"email": "short@example.com", "password": "abc"})
    assert r.status_code == 422


def test_login_wrong_password_and_correct(client):
    register(client, "login@example.com", password="right-password-1")
    assert client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "wrong-password"}).status_code == 401
    ok = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "right-password-1"})
    assert ok.status_code == 200 and ok.json()["access_token"]


def test_protected_routes_require_token(client):
    assert client.get("/api/v1/assessments").status_code == 401
    assert client.post("/api/v1/assessments", json=SYMPTOMS).status_code == 401
    assert client.post("/api/v1/chat", json={"message": "hello"}).status_code == 401
    assert client.post("/api/v1/lookups/dictionary", json={"term": "fever"}).status_code == 401
    assert client.post("/api/v1/documents/extract").status_code == 401


def test_invalid_token_rejected(client):
    r = client.get("/api/v1/assessments", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_tampered_token_rejected(client, user_a):
    token = user_a["access_token"]
    bad = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_users_cannot_read_each_others_assessments(client, user_a, user_b):
    created = client.post("/api/v1/assessments", json=SYMPTOMS, headers=auth(user_a))
    assert created.status_code == 201
    aid = created.json()["id"]

    assert client.get(f"/api/v1/assessments/{aid}", headers=auth(user_b)).status_code == 404
    assert client.delete(f"/api/v1/assessments/{aid}", headers=auth(user_b)).status_code == 404
    assert client.post(f"/api/v1/assessments/{aid}/report", headers=auth(user_b)).status_code == 404

    listing_b = client.get("/api/v1/assessments", headers=auth(user_b)).json()
    assert all(item["id"] != aid for item in listing_b)
    listing_a = client.get("/api/v1/assessments", headers=auth(user_a)).json()
    assert any(item["id"] == aid for item in listing_a)
