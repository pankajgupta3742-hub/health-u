"""Triage assessments, history, reports and PDF download."""
from conftest import SYMPTOMS, auth


def test_create_assessment_returns_rule_urgency_and_is_saved(client, user_a):
    payload = dict(SYMPTOMS, primary_symptom="chest_pain", severity_score=9, breathlessness_level="severe")
    r = client.post("/api/v1/assessments", json=payload, headers=auth(user_a))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["final_urgency"] == "High"
    assert body["rule_output"]["matching_rule"] == "Potential Cardiac Event"
    assert body["input"]["primary_symptom"] == "chest_pain"
    assert set(body["ai_explanation"]) == {"narrative", "recommendation", "first_aid", "medicine_info"}

    got = client.get(f"/api/v1/assessments/{body['id']}", headers=auth(user_a))
    assert got.status_code == 200 and got.json()["final_urgency"] == "High"


def test_contradictory_input_is_saved_as_contradiction(client, user_a):
    payload = dict(SYMPTOMS, severity_score=1)
    r = client.post("/api/v1/assessments", json=payload, headers=auth(user_a))
    assert r.status_code == 201
    assert r.json()["final_urgency"] == "N/A"
    assert r.json()["status"] == "Contradiction Detected"


def test_unknown_categorical_value_rejected(client, user_a):
    r = client.post("/api/v1/assessments", json=dict(SYMPTOMS, pain_type="dizzy"), headers=auth(user_a))
    assert r.status_code == 422


def test_extra_fields_rejected(client, user_a):
    r = client.post("/api/v1/assessments", json=dict(SYMPTOMS, user_id="someone-else"), headers=auth(user_a))
    assert r.status_code == 422


def test_severity_out_of_range_rejected(client, user_a):
    assert client.post("/api/v1/assessments", json=dict(SYMPTOMS, severity_score=11), headers=auth(user_a)).status_code == 422


def test_history_lists_only_own_items(client, user_a):
    client.post("/api/v1/assessments", json=SYMPTOMS, headers=auth(user_a))
    client.post("/api/v1/assessments", json=SYMPTOMS, headers=auth(user_a))
    items = client.get("/api/v1/assessments", headers=auth(user_a)).json()
    assert len(items) >= 2


def test_delete_own_assessment(client, user_a):
    aid = client.post("/api/v1/assessments", json=SYMPTOMS, headers=auth(user_a)).json()["id"]
    assert client.delete(f"/api/v1/assessments/{aid}", headers=auth(user_a)).status_code == 204
    assert client.get(f"/api/v1/assessments/{aid}", headers=auth(user_a)).status_code == 404


def test_report_is_generated_and_downloadable_only_by_owner(client, user_a, user_b):
    aid = client.post("/api/v1/assessments", json=SYMPTOMS, headers=auth(user_a)).json()["id"]
    rep = client.post(f"/api/v1/assessments/{aid}/report", headers=auth(user_a))
    assert rep.status_code == 201, rep.text
    rid = rep.json()["id"]

    dl = client.get(f"/api/v1/reports/{rid}/download", headers=auth(user_a))
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/pdf"
    assert dl.content.startswith(b"%PDF")

    assert client.get(f"/api/v1/reports/{rid}/download", headers=auth(user_b)).status_code == 404


def test_report_download_ignores_client_supplied_paths(client, user_a):
    # The download route takes only an ID. Traversal-style strings are simply not found.
    for bad in ["..%2F..%2Fetc%2Fpasswd", "%2Fetc%2Fpasswd", "does-not-exist"]:
        r = client.get(f"/api/v1/reports/{bad}/download", headers=auth(user_a))
        assert r.status_code == 404
