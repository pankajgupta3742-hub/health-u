import os
import tempfile

# Must be set before the app imports. Tests run offline: no Gemini calls, isolated DB and reports.
os.environ["GEMINI_API_KEY"] = ""
os.environ["JWT_SECRET"] = "test-secret-not-for-production-0123456789abcdef"
_tmp = tempfile.mkdtemp(prefix="healthu-test-")
# Set HEALTHU_TEST_DATABASE_URL to run the same tests against PostgreSQL.
os.environ["DATABASE_URL"] = os.environ.get("HEALTHU_TEST_DATABASE_URL") or f"sqlite:///{os.path.join(_tmp, 'test.db')}"
os.environ["REPORTS_DIR"] = os.path.join(_tmp, "reports")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    """Each test starts with empty tables so emails and IDs never leak between tests."""
    from app.db import Base, engine
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


SYMPTOMS = {
    "primary_symptom": "cough",
    "severity_score": 3,
    "duration_category": "short",
    "frequency": "rare",
    "age_group": "adult",
    "breathlessness_level": "none",
    "vomiting_severity": "none",
    "fever_level": "none",
    "pain_type": "none",
}


def register(client, email, password="correct-horse-1", name="Test"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password, "name": name})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def user_a(client):
    return register(client, "alice@example.com", name="Alice")


@pytest.fixture()
def user_b(client):
    return register(client, "bob@example.com", name="Bob")


def auth(token_payload):
    return {"Authorization": f"Bearer {token_payload['access_token']}"}
