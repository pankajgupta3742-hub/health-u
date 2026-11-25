"""Account deletion removes all personal data; assistant endpoints fail safely when no key is configured."""
import os

from conftest import SYMPTOMS, auth, register


def test_account_delete_removes_everything(client):
    u = register(client, "gone@example.com")
    aid = client.post("/api/v1/assessments", json=SYMPTOMS, headers=auth(u)).json()["id"]
    rid = client.post(f"/api/v1/assessments/{aid}/report", headers=auth(u)).json()["id"]
    client.post("/api/v1/lab-results", json={"results": [{"test_name": "Hemoglobin", "value": "12"}]},
                headers=auth(u))
    from app.db import SessionLocal
    from app.models import Report
    with SessionLocal() as db:
        path = db.get(Report, rid).file_path
    assert os.path.isfile(path)

    assert client.delete("/api/v1/account", headers=auth(u)).status_code == 204
    assert not os.path.exists(path)
    assert client.get("/api/v1/auth/me", headers=auth(u)).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "gone@example.com",
                                                    "password": "correct-horse-1"}).status_code == 401


def test_chat_without_key_returns_safe_message(client, user_a):
    r = client.post("/api/v1/chat", json={"message": "What is dengue?"}, headers=auth(user_a))
    assert r.status_code == 200
    assert isinstance(r.json()["reply"], str) and r.json()["reply"]


def test_chat_input_limits(client, user_a):
    assert client.post("/api/v1/chat", json={"message": "x" * 1001}, headers=auth(user_a)).status_code == 422
    assert client.post("/api/v1/chat", json={"message": ""}, headers=auth(user_a)).status_code == 422


def test_dictionary_without_key_is_clean_error(client, user_a):
    r = client.post("/api/v1/lookups/dictionary", json={"term": "tachycardia"}, headers=auth(user_a))
    assert r.status_code == 503
    assert "detail" in r.json()


def test_health_endpoint_is_public(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_cors_does_not_allow_credentials(client):
    r = client.options("/api/v1/health", headers={"Origin": "https://evil.example",
                                                   "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_export_contains_my_data_and_nobody_elses(client, user_a, user_b):
    ha, hb = auth(user_a), auth(user_b)
    client.post("/api/v1/assessments", json=SYMPTOMS, headers=ha)
    client.post("/api/v1/assessments", json=SYMPTOMS, headers=hb)
    r = client.get("/api/v1/account/export", headers=ha)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    body = r.json()
    assert body["account"]["email"] == user_a["user"]["email"]
    assert len(body["assessments"]) == 1
    assert body["assessments"][0]["input"]["primary_symptom"] == "cough"
    assert "password" not in r.text.lower()
    assert user_b["user"]["email"] not in r.text


def test_export_requires_sign_in(client):
    assert client.get("/api/v1/account/export").status_code == 401
