"""LangGraph workflow for the missing-data engine: graph wiring, review -> decide -> predict path, safety and explanation.

Offline: GEMINI_API_KEY is blank in tests, so the rule-based agent review is used.
"""
from conftest import register

from app.db import SessionLocal
from app.models import User
from app.workflows import missing_data_graph as wf
from app.services import predictions as svc

DENGUE_ANSWERS = {"Age": 30, "Sex": 1, "Work": 0, "Systolic BP": 110, "Diastolic BP": 70,
                  "Pulse": 90, "Cough": 0, "Fever": 1}


def auth_for(client, email):
    token = register(client, email)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_graphs_have_the_required_stages():
    review_nodes = set(wf.review_graph.get_graph().nodes)
    final_nodes = set(wf.finalize_graph.get_graph().nodes)
    assert {"detect", "retrieve", "agent_review", "persist"} <= review_nodes
    assert {"validate", "predict_and_record", "safety", "explain"} <= final_nodes


def test_run_review_returns_a_report_and_adds_no_values(client):
    headers = auth_for(client, "wf-review@example.com")
    email = "wf-review@example.com"
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        report = wf.run_review(db, user, "dengue", {"Age": 30})
        report_id = report.id
    view = client.get(f"/api/v1/missing-data/reports/{report_id}", headers=headers).json()
    assert view["unresolved_fields"], "fields not given must be listed as unresolved"
    assert "Work" in view["unresolved_fields"]
    assert "Age" not in view["unresolved_fields"]


def test_review_to_prediction_path_adds_safety_notes_and_explanation(client):
    headers = auth_for(client, "wf-path@example.com")
    # Earlier complete run so that a confirmed Work value exists for retrieval.
    first = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": DENGUE_ANSWERS},
                        headers=headers).json()
    client.post(f"/api/v1/missing-data/reports/{first['id']}/decisions",
                json={"decisions": [{"field": n, "action": "unknown"} for n in first["unresolved_fields"]]},
                headers=headers)
    client.post(f"/api/v1/missing-data/reports/{first['id']}/predict", headers=headers)

    answers_now = {k: v for k, v in DENGUE_ANSWERS.items() if k != "Work"}
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": answers_now},
                       headers=headers).json()
    work = next(f for f in view["fields"] if f["name"] == "Work")
    pid = work["proposals"][0]["id"]
    rest = [{"field": n, "action": "unknown"} for n in view["unresolved_fields"] if n != "Work"]
    r = client.post(f"/api/v1/missing-data/reports/{view['id']}/decisions",
                    json={"decisions": [{"field": "Work", "action": "accept", "proposal_id": pid}] + rest},
                    headers=headers)
    assert r.status_code == 200, r.text
    pred = client.post(f"/api/v1/missing-data/reports/{view['id']}/predict", headers=headers).json()

    assert pred["outcome"] == "complete"
    assert pred["safety_notes"], "safety notes are required on every finished estimate"
    assert any("not a diagnosis" in n for n in pred["safety_notes"])
    assert "Built from" in pred["explanation"] and "marked unknown" in pred["explanation"]
    assert any(p["field"] == "Work" and p["approval"] == "approved" for p in pred["provenance"])


def test_incomplete_path_returns_no_estimate_and_says_so(client):
    headers = auth_for(client, "wf-incomplete@example.com")
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {"Age": 30}},
                       headers=headers).json()
    # Leave everything unanswered: the workflow must not run the model.
    pred = client.post(f"/api/v1/missing-data/reports/{view['id']}/predict", headers=headers)
    body = pred.json()
    assert pred.status_code in (200, 422)
    assert body.get("outcome") != "complete"
    assert "probability_positive" not in body or body["probability_positive"] is None
    if pred.status_code == 200:
        assert any("No estimate" in n for n in body["safety_notes"])


def test_finalize_never_invents_a_probability_for_missing_fields():
    # Unit-level check on the prediction service: an unknown field is passed through as unknown, never as 0.
    spec = svc.load_spec("dengue")
    features = {f["name"]: None for f in spec["features"]}
    features["Age"] = 30
    result = svc.predict("dengue", features, unknown=[n for n in features if n != "Age"])
    assert result["outcome"] == "incomplete"
    assert result.get("probability_positive") is None
