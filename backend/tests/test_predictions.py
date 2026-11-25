"""Disease model endpoints: catalog, cards, validation, and prediction output. Offline (no Gemini)."""
from conftest import register


def auth(client, email="pred@example.com"):
    token = register(client, email)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_predictions_require_sign_in(client):
    assert client.get("/api/v1/models").status_code == 401
    assert client.post("/api/v1/predictions/dengue", json={"features": {}}).status_code == 401


def test_catalog_lists_all_six_models_with_status(client):
    h = auth(client)
    r = client.get("/api/v1/models", headers=h)
    assert r.status_code == 200
    models = r.json()["models"]
    assert {m["key"] for m in models} == {"malaria", "vector_borne", "dengue", "dengue_chikungunya", "typhoid", "leptospirosis"}
    for m in models:
        assert m["status"] in ("research", "limited")
        assert m["status_reason"]
        assert m["headline_metric"]["metric"]


def test_card_is_served_and_has_limitations(client):
    h = auth(client)
    r = client.get("/api/v1/models/typhoid/card", headers=h)
    assert r.status_code == 200
    assert "Limitations" in r.text and "Widal" in r.text


def test_unknown_model_is_404(client):
    h = auth(client)
    assert client.get("/api/v1/models/nope", headers=h).status_code == 404
    assert client.post("/api/v1/predictions/nope", json={"features": {}}, headers=h).status_code == 404


def test_unknown_field_rejected(client):
    h = auth(client)
    r = client.post("/api/v1/predictions/dengue", json={"features": {"Not a field": 1}}, headers=h)
    assert r.status_code == 422
    assert "Unknown fields" in r.json()["detail"]


def test_out_of_range_numeric_rejected(client):
    h = auth(client)
    r = client.post("/api/v1/predictions/dengue", json={"features": {"Age": 500}}, headers=h)
    assert r.status_code == 422
    assert "between" in r.json()["detail"]


def test_bad_binary_value_rejected(client):
    h = auth(client)
    r = client.post("/api/v1/predictions/dengue", json={"features": {"Fever": 3}}, headers=h)
    assert r.status_code == 422


def test_bad_category_rejected(client):
    h = auth(client)
    r = client.post("/api/v1/predictions/leptospirosis", json={"features": {"Sex": "Alien"}}, headers=h)
    assert r.status_code == 422


def test_binary_prediction_returns_probabilities_and_status(client):
    h = auth(client)
    answered = {"Age": 30, "Sex": 1, "Work": 0, "Systolic BP": 110, "Diastolic BP": 70, "Pulse": 90, "Cough": 0, "Fever": 1}
    unknown = [n for n in DENGUE_FEATURES if n not in answered]
    r = client.post("/api/v1/predictions/dengue", json={"features": answered, "unknown": unknown}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "complete"
    assert abs(sum(body["probabilities"].values()) - 1.0) < 0.01
    assert 0.0 <= body["probability_positive"] <= 1.0
    assert body["status"] in ("research", "limited")
    assert "diagnosis" in body["disclaimer"].lower()
    assert body["unknown_fields"] == sorted(unknown)
    assert "notice" in body


def test_missing_answers_return_incomplete_not_a_guess(client):
    h = auth(client)
    r = client.post("/api/v1/predictions/dengue", json={"features": {"Age": 30, "Fever": 1}}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "incomplete"
    assert "probabilities" not in body
    assert "Work" in body["unresolved_fields"]


def test_prediction_never_returns_urgency(client):
    h = auth(client)
    r = client.post("/api/v1/predictions/malaria", json={"features": {"Age": 10}}, headers=h)
    assert r.status_code == 200, r.text
    text = r.text.lower()
    for word in ("urgency", "urgent", "emergency", "triage"):
        assert word not in text


def test_multiclass_prediction_has_all_classes(client):
    h = auth(client)
    spec = svc_spec("dengue_chikungunya")
    names = [f["name"] for f in spec["features"]]
    answered = {"age_years": 25, "Fever": 3, "Myalgia": 1, "Headache": 1, "Rash": 1, "Vomiting": 1,
                "Nausea": 1, "Back pain": 1, "Conjunctivitis": 1, "Arthritis": 1, "Arthralgia": 1}
    unknown = [n for n in names if n not in answered]
    r = client.post("/api/v1/predictions/dengue_chikungunya",
                    json={"features": answered, "unknown": unknown}, headers=h)
    assert r.status_code == 200, r.text
    assert set(r.json()["probabilities"]) == {"chikungunya", "dengue", "neither"}
    assert "probability_positive" not in r.json()


def svc_spec(key):
    from app.services import predictions as svc
    return svc.load_spec(key)


DENGUE_FEATURES = [f["name"] for f in svc_spec("dengue")["features"]]
