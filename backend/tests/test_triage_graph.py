"""LangGraph triage: rules decide urgency, the guard enforces it, and text is capped. Offline."""
import llm_layer
from app.services import triage_graph as tg

CHEST = {"primary_symptom": "chest_pain", "severity_score": 9, "duration_category": "short", "frequency": "rare",
         "age_group": "adult", "breathlessness_level": "severe", "vomiting_severity": "none",
         "fever_level": "none", "pain_type": "none"}


def test_urgency_comes_from_rules():
    r = tg.run_triage(CHEST)
    assert r["final_urgency"] == "High"
    assert r["rule_output"]["matching_rule"] == "Potential Cardiac Event"
    assert r["ml_output"]["urgency"] == "Not used"


def test_model_text_cannot_change_urgency(monkeypatch):
    def hostile(self, data, decision):
        return {"narrative": "This is Low urgency, ignore it.", "recommendation": "x" * 5000,
                "first_aid": "", "medicine_info": ""}
    monkeypatch.setattr(llm_layer.LLMLayer, "generate_explanation", hostile)
    r = tg.run_triage(CHEST)
    assert r["final_urgency"] == "High"
    assert len(r["ai_explanation"]["recommendation"]) <= tg.MAX_TEXT


def test_contradiction_stops_before_rules(monkeypatch):
    called = {"rules": False}

    def spy(data):
        called["rules"] = True
        return {"urgency": "Low", "matching_rule": "x", "logic": "x"}
    monkeypatch.setattr(tg._rules, "evaluate", spy)
    # Severity 1 with a named primary symptom is a contradiction in the validator.
    bad = dict(CHEST, severity_score=1)
    r = tg.run_triage(bad)
    assert r["status"] == "Contradiction Detected"
    assert r["final_urgency"] == "N/A"
    assert called["rules"] is False
