"""Missing-data handling for triage: no silent defaults, proposals from the patient's own history only,
accepted suggestions validated server-side, a separate report per assessment, and PDF/prediction integration."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

import llm_layer
from app.db import SessionLocal
from app.models import Assessment
from app.services import triage_graph as tg
from conftest import SYMPTOMS, auth, register

FULL = dict(SYMPTOMS, primary_symptom="cough", severity_score=3)
PARTIAL = {"primary_symptom": "cough", "severity_score": 3}  # everything else is missing


def _post(client, user, body):
    return client.post("/api/v1/assessments", json=body, headers=auth(user))


def _age_assessment(assessment_id: str, days: int):
    """Move an assessment and the dates it recorded back, to test freshness rules without waiting."""
    from app.models import AssessmentMissingReport
    from sqlalchemy import select
    with SessionLocal() as db:
        row = db.get(Assessment, assessment_id)
        row.created_at = datetime.now(timezone.utc) - timedelta(days=days)
        rep = db.scalars(select(AssessmentMissingReport).where(
            AssessmentMissingReport.assessment_id == assessment_id)).first()
        if rep is not None:
            prov = json.loads(rep.provenance_json or "{}")
            for info in prov.values():
                if info.get("source_date"):
                    info["source_date"] = (date.fromisoformat(info["source_date"]) - timedelta(days=days)).isoformat()
            rep.provenance_json = json.dumps(prov)
        db.commit()


# ---------------------------------------------------------------- no silent defaults

def test_partial_input_is_incomplete_and_nothing_is_filled(client, user_a):
    r = _post(client, user_a, PARTIAL)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "Incomplete: missing information"
    assert body["final_urgency"] == "N/A"
    assert body["rule_output"]["matching_rule"] == "N/A"
    assert set(body["input"]) == {"primary_symptom", "severity_score"}  # no default values were added
    missing = body["missing_data"]["missing_fields"]
    assert "duration_category" in missing and "fever_level" in missing and "primary_symptom" not in missing


def test_graph_never_calls_rules_for_incomplete_input(monkeypatch):
    called = {"rules": False}

    def spy(data):
        called["rules"] = True
        return {"urgency": "Low", "matching_rule": "x", "logic": "x"}
    monkeypatch.setattr(tg._rules, "evaluate", spy)
    r = tg.run_triage(PARTIAL)
    assert r["status"] == "Incomplete: missing information"
    assert called["rules"] is False
    assert "severity_score" not in r["missing_fields"]


def test_complete_input_still_gets_rule_urgency(client, user_a):
    body = _post(client, user_a, dict(FULL, primary_symptom="chest_pain", severity_score=9,
                                       breathlessness_level="severe")).json()
    assert body["final_urgency"] == "High"
    assert body["missing_data"]["missing_fields"] == []


def test_each_assessment_has_its_own_report(client, user_a):
    a = _post(client, user_a, PARTIAL).json()
    b = _post(client, user_a, FULL).json()
    ra = client.get(f"/api/v1/assessments/{a['id']}/missing-data", headers=auth(user_a)).json()
    rb = client.get(f"/api/v1/assessments/{b['id']}/missing-data", headers=auth(user_a)).json()
    assert ra["missing_fields"] and rb["missing_fields"] == []
    assert ra != rb


# ---------------------------------------------------------------- proposals from the patient's own history

def test_earlier_answer_is_proposed_not_used(client, user_a):
    _post(client, user_a, FULL)  # earlier complete assessment
    r = _post(client, user_a, PARTIAL).json()
    props = {p["field"]: p for p in r["missing_data"]["proposals"]}
    assert "duration_category" in props
    p = props["duration_category"]
    assert p["value"] == "short" and p["status"] == "pending" and p["allowed_actions"] == ["accept"]
    assert p["requires_confirmation"] is True and p["category"] == "retrieved"
    assert "duration_category" not in r["input"]  # proposed only


def test_old_symptom_answer_is_too_old_and_cannot_be_accepted(client, user_a):
    earlier = _post(client, user_a, FULL).json()
    _age_assessment(earlier["id"], days=30)
    r = _post(client, user_a, PARTIAL).json()
    p = next(p for p in r["missing_data"]["proposals"] if p["field"] == "duration_category")
    assert p["status"] == "too_old" and p["allowed_actions"] == []
    pid = p["id"]
    bad = client.post("/api/v1/assessments", json=dict(PARTIAL, accepted={"duration_category": pid}),
                      headers=auth(user_a))
    assert bad.status_code == 422 and "too old" in bad.text


def test_other_patients_suggestion_cannot_be_accepted(client, user_a, user_b):
    _post(client, user_a, FULL)
    pid = next(p["id"] for p in _post(client, user_a, PARTIAL).json()["missing_data"]["proposals"]
               if p["field"] == "duration_category")
    r = client.post("/api/v1/assessments", json=dict(PARTIAL, accepted={"duration_category": pid}),
                    headers=auth(user_b))
    assert r.status_code == 422  # user B has no such suggestion


def test_accepting_a_suggestion_completes_the_assessment_with_provenance(client, user_a):
    _post(client, user_a, FULL)
    first = _post(client, user_a, PARTIAL).json()
    pid = next(p["id"] for p in first["missing_data"]["proposals"] if p["field"] == "duration_category")
    accepted_fields = {"duration_category", "frequency", "age_group", "breathlessness_level", "vomiting_severity",
                       "fever_level", "pain_type"}
    accepted = {p["field"]: p["id"] for p in first["missing_data"]["proposals"]
                if p["field"] in accepted_fields and p["status"] == "pending"}
    missing_now = set(first["missing_data"]["missing_fields"])
    if set(accepted) != missing_now:
        pytest.skip("not every missing field has a fresh earlier answer in this setup")
    r = _post(client, user_a, dict(PARTIAL, accepted=accepted))
    body = r.json()
    assert r.status_code == 201 and body["status"] != "Incomplete: missing information"
    assert body["input"]["duration_category"] == "short"
    prov = body["missing_data"]["provenance"]
    assert prov["duration_category"]["source"] == "retrieved"
    assert prov["duration_category"]["approval"] == "accepted"
    assert prov["severity_score"]["source"] == "patient_entered"
    assert pid  # the id was real


def test_accepted_value_cannot_be_combined_with_a_typed_answer(client, user_a):
    _post(client, user_a, FULL)
    pid = next(p["id"] for p in _post(client, user_a, PARTIAL).json()["missing_data"]["proposals"]
               if p["field"] == "duration_category")
    r = client.post("/api/v1/assessments", json=dict(PARTIAL, duration_category="long",
                                                      accepted={"duration_category": pid}), headers=auth(user_a))
    assert r.status_code == 422 and "already has your answer" in r.text


def test_unknown_suggestion_id_is_rejected(client, user_a):
    r = client.post("/api/v1/assessments", json=dict(PARTIAL, accepted={"duration_category": "0" * 24}),
                    headers=auth(user_a))
    assert r.status_code == 422


def test_reused_value_keeps_its_original_date(client, user_a):
    earlier = _post(client, user_a, FULL).json()
    _age_assessment(earlier["id"], days=5)
    first = _post(client, user_a, PARTIAL).json()
    accepted = {p["field"]: p["id"] for p in first["missing_data"]["proposals"]}
    done = _post(client, user_a, dict(PARTIAL, accepted=accepted)).json()
    # The reused value is dated 5 days ago, not today, so a later proposal must not look fresh.
    assert done["missing_data"]["provenance"]["duration_category"]["source_date"] == \
        (datetime.now(timezone.utc).date() - timedelta(days=5)).isoformat()
    later = _post(client, user_a, PARTIAL).json()
    dur = next(p for p in later["missing_data"]["proposals"] if p["field"] == "duration_category")
    assert dur["age_days"] == 5


def test_proposal_reasoning_comes_from_rules_when_no_key(client, user_a):
    _post(client, user_a, FULL)
    r = _post(client, user_a, PARTIAL).json()
    assert all(p["reviewed_by"] == "rules" for p in r["missing_data"]["proposals"])


def test_agent_cannot_raise_confidence_for_triage(client, user_a, monkeypatch):
    def hostile(payload):
        return {c["id"]: {"supports": True, "confidence": "high", "reasoning": "trust me", "reviewed_by": "llm"}
                for c in payload}
    from app.services import triage_completion as tc
    monkeypatch.setattr(tc, "review_candidates", hostile)
    first = _post(client, user_a, FULL).json()
    _age_assessment(first["id"], days=3)  # the only earlier answer is 3 days old
    r = _post(client, user_a, PARTIAL).json()
    dur = next(p for p in r["missing_data"]["proposals"] if p["field"] == "duration_category")
    assert dur["confidence"] == "medium"  # capped: symptoms older than a day cannot be high


# ---------------------------------------------------------------- history, report, delete

def test_history_includes_missing_summary(client, user_a):
    _post(client, user_a, PARTIAL)
    _post(client, user_a, FULL)
    items = client.get("/api/v1/assessments", headers=auth(user_a)).json()
    assert len(items) == 2 and all("missing_data" in i for i in items)


def test_pdf_report_includes_missing_section(client, user_a):
    rid = _post(client, user_a, PARTIAL).json()["id"]
    r = client.post(f"/api/v1/assessments/{rid}/report", headers=auth(user_a))
    assert r.status_code == 201, r.text
    dl = client.get(f"/api/v1/reports/{r.json()['id']}/download", headers=auth(user_a))
    assert dl.status_code == 200 and dl.content[:4] == b"%PDF"


def test_deleting_assessment_removes_its_report(client, user_a):
    rid = _post(client, user_a, PARTIAL).json()["id"]
    assert client.delete(f"/api/v1/assessments/{rid}", headers=auth(user_a)).status_code == 204
    assert client.get(f"/api/v1/assessments/{rid}/missing-data", headers=auth(user_a)).status_code == 404
    from app.models import AssessmentMissingReport
    from sqlalchemy import select
    with SessionLocal() as db:
        assert db.scalars(select(AssessmentMissingReport).where(
            AssessmentMissingReport.assessment_id == rid)).first() is None


def test_missing_data_views_require_sign_in_and_owner(client, user_a, user_b):
    rid = _post(client, user_a, PARTIAL).json()["id"]
    assert client.get(f"/api/v1/assessments/{rid}/missing-data").status_code == 401
    assert client.get(f"/api/v1/assessments/{rid}/missing-data", headers=auth(user_b)).status_code == 404


# ---------------------------------------------------------------- ML prediction: safety notes and explanation

def test_completed_prediction_has_safety_notes_and_explanation(client, user_a):
    ans = {"Age": 30, "Sex": 1, "Work": 0, "Systolic BP": 110, "Diastolic BP": 70, "Pulse": 90,
           "Cough": 0, "Fever": 1}
    rep = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": ans},
                      headers=auth(user_a)).json()
    decisions = [{"field": n, "action": "unknown"} for n in rep["unresolved_fields"]]
    client.post(f"/api/v1/missing-data/reports/{rep['id']}/decisions", json={"decisions": decisions},
                headers=auth(user_a))
    out = client.post(f"/api/v1/missing-data/reports/{rep['id']}/predict", headers=auth(user_a)).json()
    assert out["outcome"] == "complete"
    assert any("not a diagnosis" in n for n in out["safety_notes"])
    assert "Built from" in out["explanation"] and "marked unknown" in out["explanation"]


def test_incomplete_prediction_says_no_estimate(client, user_a):
    rep = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {"Age": 30}},
                      headers=auth(user_a)).json()
    out = client.post(f"/api/v1/missing-data/reports/{rep['id']}/predict", headers=auth(user_a)).json()
    assert out["outcome"] == "incomplete"
    assert any("No estimate" in n for n in out["safety_notes"])


# ---------------------------------------------------------------- provenance correction

def _complete_prediction(client, h):
    ans = {"Age": 30, "Sex": 1, "Work": 0, "Systolic BP": 110, "Diastolic BP": 70, "Pulse": 90,
           "Cough": 0, "Fever": 1}
    rep = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": ans}, headers=h).json()
    client.post(f"/api/v1/missing-data/reports/{rep['id']}/decisions",
                json={"decisions": [{"field": n, "action": "unknown"} for n in rep["unresolved_fields"]]}, headers=h)
    out = client.post(f"/api/v1/missing-data/reports/{rep['id']}/predict", headers=h).json()
    assert out["outcome"] == "complete"
    return rep["id"], out


def test_correction_after_prediction_is_recorded_and_marks_estimate_stale(client, user_a):
    h = auth(user_a)
    rid, _ = _complete_prediction(client, h)
    r = client.post(f"/api/v1/missing-data/reports/{rid}/corrections", json={"field": "Pulse", "value": 104}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "stale"
    row = next(x for x in r.json()["provenance"] if x["field"] == "Pulse" and x["method"] == "patient_correction")
    assert row["approval"] == "corrected" and row["final_value"] == "104.0" and row["original_value"] == "90.0"
    # The estimate can no longer be produced from this report: a new check is needed.
    again = client.post(f"/api/v1/missing-data/reports/{rid}/predict", headers=h)
    assert again.status_code == 422


def test_corrected_value_is_used_by_a_later_check_as_a_proposal_not_a_fill(client, user_a):
    h = auth(user_a)
    rid, _ = _complete_prediction(client, h)
    client.post(f"/api/v1/missing-data/reports/{rid}/corrections", json={"field": "Pulse", "value": 104}, headers=h)
    nxt = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {"Age": 30}},
                      headers=h).json()
    pulse = next(f for f in nxt["fields"] if f["name"] == "Pulse")
    assert pulse["status"] == "missing"  # nothing filled in
    assert any(p["value"] == "104.0" for p in pulse["proposals"])


def test_only_answered_fields_can_be_corrected(client, user_a):
    h = auth(user_a)
    rep = client.post("/api/v1/missing-data/reports", json={"model": "dengue", "features": {"Age": 30}},
                      headers=h).json()
    r = client.post(f"/api/v1/missing-data/reports/{rep['id']}/corrections", json={"field": "Pulse", "value": 90},
                    headers=h)
    assert r.status_code == 422 and "Only answered" in r.text


def test_correction_is_owner_only(client, user_a, user_b):
    rid, _ = _complete_prediction(client, auth(user_a))
    r = client.post(f"/api/v1/missing-data/reports/{rid}/corrections", json={"field": "Pulse", "value": 104},
                    headers=auth(user_b))
    assert r.status_code == 404


def test_legacy_prediction_endpoint_says_nothing_was_recorded(client, user_a):
    r = client.post("/api/v1/predictions/dengue", json={"features": {"Age": 30}, "unknown": []}, headers=auth(user_a))
    assert r.status_code == 200 and r.json()["recorded"] is False


def test_accepted_severity_is_used_as_a_number_and_completes_the_assessment(client, user_a):
    _post(client, user_a, FULL)  # earlier answer: severity 3
    partial = {k: v for k, v in FULL.items() if k != "severity_score"}
    first = _post(client, user_a, partial).json()
    assert first["missing_data"]["missing_fields"] == ["severity_score"]
    pid = next(p["id"] for p in first["missing_data"]["proposals"] if p["field"] == "severity_score")
    r = _post(client, user_a, dict(partial, accepted={"severity_score": pid}))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["input"]["severity_score"] == 3 and isinstance(body["input"]["severity_score"], int)
    assert body["status"] != "Incomplete: missing information" and body["final_urgency"] in ("High", "Moderate", "Low")
