"""Missing-data completion engine: detection, proposals, patient decisions, validation, provenance, isolation.

Offline: no Gemini calls (GEMINI_API_KEY is blank in tests), so the rule-based agent review is used.
"""
from datetime import date, timedelta

from conftest import register

from app.agents import missing_data_agent as agent
from app.db import SessionLocal
from app.models import ConfirmedInput
from app.services import predictions as svc

DENGUE_ANSWERS = {"Age": 30, "Sex": 1, "Work": 0, "Systolic BP": 110, "Diastolic BP": 70,
                  "Pulse": 90, "Cough": 0, "Fever": 1}
DENGUE_ALL = [f["name"] for f in svc.load_spec("dengue")["features"]]


def auth_for(client, email):
    token = register(client, email)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def user_id(client, headers):
    return client.get("/api/v1/auth/me", headers=headers).json()["id"]


def unknown_rest(answers):
    return [n for n in DENGUE_ALL if n not in answers]


def run_full_prediction(client, headers, answers):
    """Create a report, answer the rest as unknown, predict. Confirmed answers are stored by the predict step."""
    r = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": answers}, headers=headers)
    assert r.status_code == 201, r.text
    report = r.json()
    decisions = [{"field": n, "action": "unknown"} for n in report["unresolved_fields"]]
    if decisions:
        r = client.post(f"/api/v1/missing-data/reports/{report['id']}/decisions",
                        json={"decisions": decisions}, headers=headers)
        assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/missing-data/reports/{report['id']}/predict", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "complete"
    return report["id"]


def field(view, name):
    return next(f for f in view["fields"] if f["name"] == name)


def test_review_lists_missing_fields_and_adds_no_values(client):
    h = auth_for(client, "detect@example.com")
    r = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {"Age": 30}}, headers=h)
    assert r.status_code == 201, r.text
    view = r.json()
    assert view["ready"] is False
    assert view["counts"]["patient_entered"] == 1
    assert view["counts"]["completed"] == 0
    assert field(view, "Age")["status"] == "patient_entered"
    assert field(view, "Age")["final_value"] == "30.0"
    assert field(view, "Work")["status"] == "missing"
    assert field(view, "Work")["final_value"] is None


def test_new_patient_has_no_proposals(client):
    h = auth_for(client, "fresh@example.com")
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {}}, headers=h).json()
    assert all(f["proposals"] == [] for f in view["fields"])


def test_unknown_model_and_unknown_field_are_rejected(client):
    h = auth_for(client, "bad@example.com")
    assert client.post("/api/v1/missing-data/reports", json={"model": "nope", "features": {}}, headers=h).status_code == 404
    r = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {"Bogus": 1}}, headers=h)
    assert r.status_code == 422


def test_confirmed_answer_from_earlier_run_is_proposed_not_filled(client):
    h = auth_for(client, "reuse@example.com")
    run_full_prediction(client, h, DENGUE_ANSWERS)
    answers_now = {k: v for k, v in DENGUE_ANSWERS.items() if k != "Work"}
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": answers_now},
                       headers=h).json()
    work = field(view, "Work")
    assert work["status"] == "missing"  # not filled automatically
    assert len(work["proposals"]) == 1
    p = work["proposals"][0]
    assert p["category"] == "retrieved"
    assert p["value"] == "0.0"
    assert p["requires_confirmation"] is True
    assert p["status"] == "pending"
    assert "accept" in p["allowed_actions"]
    assert p["evidence"][0]["source_date"] == date.today().isoformat()


def test_accepting_a_proposal_records_provenance(client):
    h = auth_for(client, "accept@example.com")
    run_full_prediction(client, h, DENGUE_ANSWERS)
    answers_now = {k: v for k, v in DENGUE_ANSWERS.items() if k != "Work"}
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": answers_now},
                       headers=h).json()
    pid = field(view, "Work")["proposals"][0]["id"]
    rest = [{"field": n, "action": "unknown"} for n in view["unresolved_fields"] if n != "Work"]
    r = client.post(f"/api/v1/missing-data/reports/{view['id']}/decisions",
                    json={"decisions": [{"field": "Work", "action": "accept", "proposal_id": pid}] + rest},
                    headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["ready"] is True
    hist = client.get(f"/api/v1/missing-data/reports/{view['id']}/history", headers=h).json()
    work_rows = [x for x in hist if x["field"] == "Work"]
    assert len(work_rows) == 1
    row = work_rows[0]
    assert row["method"] == "accepted_retrieved"
    assert row["source"] == "confirmed_input"
    assert row["final_value"] == "0.0"
    assert row["approval"] == "approved"
    assert row["source_date"] and row["timestamp"]

    pred = client.post(f"/api/v1/missing-data/reports/{view['id']}/predict", headers=h).json()
    assert pred["outcome"] == "complete"
    assert any(p["field"] == "Work" for p in pred["provenance"])


def test_rejected_proposal_leaves_field_missing_and_prediction_incomplete(client):
    h = auth_for(client, "reject@example.com")
    run_full_prediction(client, h, DENGUE_ANSWERS)
    answers_now = {k: v for k, v in DENGUE_ANSWERS.items() if k != "Work"}
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": answers_now},
                       headers=h).json()
    pid = field(view, "Work")["proposals"][0]["id"]
    r = client.post(f"/api/v1/missing-data/reports/{view['id']}/decisions",
                    json={"decisions": [{"field": "Work", "action": "reject", "proposal_id": pid}]}, headers=h)
    assert r.status_code == 200, r.text
    assert field(r.json(), "Work")["status"] == "missing"
    pred = client.post(f"/api/v1/missing-data/reports/{view['id']}/predict", headers=h).json()
    assert pred["outcome"] == "incomplete"
    assert "Work" in pred["unresolved_fields"]
    assert "probabilities" not in pred


def test_too_old_value_cannot_be_accepted(client):
    h = auth_for(client, "stale@example.com")
    uid = user_id(client, h)
    with SessionLocal() as db:
        db.add(ConfirmedInput(user_id=uid, model_key="dengue", field_name="Work", value="1.0",
                              category="patient_entered", source_date=date.today() - timedelta(days=120)))
        db.commit()
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {}}, headers=h).json()
    work = field(view, "Work")
    assert work["proposals"][0]["status"] == "too_old"
    assert "accept" not in work["proposals"][0]["allowed_actions"]
    pid = work["proposals"][0]["id"]
    r = client.post(f"/api/v1/missing-data/reports/{view['id']}/decisions",
                    json={"decisions": [{"field": "Work", "action": "accept", "proposal_id": pid}]}, headers=h)
    assert r.status_code == 422
    assert "no longer open" in r.text  # refused: the patient must answer the question again


def test_old_age_is_derived_forward_and_marked_derived(client):
    h = auth_for(client, "age@example.com")
    uid = user_id(client, h)
    with SessionLocal() as db:
        db.add(ConfirmedInput(user_id=uid, model_key="dengue", field_name="Age", value="30",
                              category="patient_entered", source_date=date.today() - timedelta(days=400)))
        db.commit()
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {}}, headers=h).json()
    props = field(view, "Age")["proposals"]
    assert len(props) == 1
    assert props[0]["category"] == "derived"
    assert props[0]["value"] == "31.0"
    assert props[0]["requires_confirmation"] is True


def test_patient_cannot_change_an_answer_they_already_gave(client):
    h = auth_for(client, "answered@example.com")
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {"Age": 30}},
                       headers=h).json()
    r = client.post(f"/api/v1/missing-data/reports/{view['id']}/decisions",
                    json={"decisions": [{"field": "Age", "action": "manual", "value": 40}]}, headers=h)
    assert r.status_code == 422


def test_edited_value_must_match_the_model_spec(client):
    h = auth_for(client, "edit@example.com")
    run_full_prediction(client, h, DENGUE_ANSWERS)
    answers_now = {k: v for k, v in DENGUE_ANSWERS.items() if k != "Work"}
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": answers_now},
                       headers=h).json()
    pid = field(view, "Work")["proposals"][0]["id"]
    r = client.post(f"/api/v1/missing-data/reports/{view['id']}/decisions",
                    json={"decisions": [{"field": "Work", "action": "edit", "proposal_id": pid, "value": 7}]},
                    headers=h)
    assert r.status_code == 422  # Work is binary: 7 is not allowed


def test_manual_answer_is_recorded_with_patient_source(client):
    h = auth_for(client, "manual@example.com")
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {"Age": 30}},
                       headers=h).json()
    decisions = [{"field": "Work", "action": "manual", "value": 1}]
    decisions += [{"field": n, "action": "unknown"} for n in view["unresolved_fields"] if n != "Work"]
    r = client.post(f"/api/v1/missing-data/reports/{view['id']}/decisions", json={"decisions": decisions}, headers=h)
    assert r.status_code == 200, r.text
    hist = client.get(f"/api/v1/missing-data/reports/{view['id']}/history", headers=h).json()
    work = next(x for x in hist if x["field"] == "Work")
    assert work["method"] == "manual_entry" and work["source"] == "patient" and work["final_value"] == "1.0"
    unknown_row = next(x for x in hist if x["method"] == "patient_unknown")
    assert unknown_row["approval"] == "unknown" and unknown_row["final_value"] is None
    intake = next(x for x in hist if x["field"] == "Age")  # typed at intake: recorded with its own provenance
    assert intake["approval"] == "entered_by_patient" and intake["final_value"] == "30.0"


def test_prediction_refuses_a_report_twice(client):
    h = auth_for(client, "twice@example.com")
    rid = run_full_prediction(client, h, DENGUE_ANSWERS)
    r = client.post(f"/api/v1/missing-data/reports/{rid}/predict", headers=h)
    assert r.status_code == 422


def test_other_patients_reports_and_answers_are_invisible(client):
    a = auth_for(client, "owner@example.com")
    b = auth_for(client, "other@example.com")
    rid = run_full_prediction(client, a, DENGUE_ANSWERS)
    assert client.get(f"/api/v1/missing-data/reports/{rid}", headers=b).status_code == 404
    assert client.get(f"/api/v1/missing-data/reports/{rid}/history", headers=b).status_code == 404
    assert client.post(f"/api/v1/missing-data/reports/{rid}/predict", headers=b).status_code == 404
    listed = client.get("/api/v1/missing-data/reports", headers=b).json()
    assert all(r["id"] != rid for r in listed)
    view = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {}}, headers=b).json()
    assert all(f["proposals"] == [] for f in view["fields"])  # A's confirmed answers are not retrieved for B


def test_reports_require_sign_in(client):
    assert client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {}}).status_code == 401


# ---------------------------------------------------------------- agent: can review, never raise confidence

def _cand(category="retrieved", age_days=10, supports=True):
    return {"id": "c1", "field": "Work", "proposed_value": "0.0", "category": category,
            "source_date": "2026-01-01", "age_days": age_days}


def test_agent_falls_back_to_rules_without_a_key(monkeypatch):
    monkeypatch.setattr(agent.gemini_client, "is_configured", lambda: False)
    out = agent.review_candidates([_cand(age_days=10)])
    assert out["c1"]["reviewed_by"] == "rules"
    assert out["c1"]["confidence"] == "high"
    assert out["c1"]["supports"] is True


def test_agent_cannot_raise_confidence_above_the_rules(monkeypatch):
    monkeypatch.setattr(agent.gemini_client, "is_configured", lambda: True)
    monkeypatch.setattr(agent.gemini_client, "generate_json_sync",
                        lambda *a, **k: {"reviews": [{"id": "c1", "supports": True, "confidence": "high",
                                                      "reasoning": "Looks fine."}]})
    out = agent.review_candidates([_cand(age_days=120)])  # rules cap: low
    assert out["c1"]["confidence"] == "low"
    assert out["c1"]["reviewed_by"] == "llm"


def test_agent_can_drop_an_unsupported_candidate(monkeypatch):
    monkeypatch.setattr(agent.gemini_client, "is_configured", lambda: True)
    monkeypatch.setattr(agent.gemini_client, "generate_json_sync",
                        lambda *a, **k: {"reviews": [{"id": "c1", "supports": False, "confidence": "low",
                                                      "reasoning": "Not relevant."}]})
    out = agent.review_candidates([_cand()])
    assert out["c1"]["supports"] is False


def test_agent_model_error_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(agent.gemini_client, "is_configured", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("quota")
    monkeypatch.setattr(agent.gemini_client, "generate_json_sync", boom)
    out = agent.review_candidates([_cand()])
    assert out["c1"]["reviewed_by"] == "rules"
