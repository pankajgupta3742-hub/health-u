"""Rule engine behaviour. Urgency must come from these rules, never from the LLM or the ML model."""
import pytest

from rule_engine import RuleEngine

engine = RuleEngine()


def base(**kw):
    d = {"primary_symptom": "cough", "severity_score": 3, "duration_category": "short", "frequency": "rare",
         "age_group": "adult", "breathlessness_level": "none", "vomiting_severity": "none",
         "fever_level": "none", "pain_type": "none"}
    d.update(kw)
    return d


@pytest.mark.parametrize("data,urgency,rule", [
    (base(primary_symptom="chest_pain", severity_score=9, breathlessness_level="severe"),
     "High", "Potential Cardiac Event"),
    (base(primary_symptom="shortness_of_breath", breathlessness_level="severe"),
     "High", "Severe Respiratory Distress"),
    (base(primary_symptom="vomiting", vomiting_severity="severe", duration_category="medium", severity_score=5),
     "High", "Dehydration Risk / Severe Vomiting"),
    (base(fever_level="high", breathlessness_level="severe"), "High", "Sepsis / Severe Infection Risk"),
    (base(fever_level="high"), "Moderate", "Significant Infection"),
    (base(fever_level="mild", primary_symptom="fever", frequency="rare", duration_category="short"),
     "Low", "Minor Viral Symptoms"),
    (base(primary_symptom="cough", severity_score=2), "Low", "Simple Respiratory Irritation"),
    (base(primary_symptom="sore_throat", severity_score=4), "Low", "Minor Pharyngitis"),
])
def test_rule_outcomes(data, urgency, rule):
    out = engine.evaluate(data)
    assert out["urgency"] == urgency
    assert out["matching_rule"] == rule


def test_default_path_is_low_monitoring_for_mild_input():
    assert engine.evaluate(base(severity_score=3))["urgency"] == "Low"


def test_high_severity_default_escalates_to_moderate():
    out = engine.evaluate(base(primary_symptom="dizziness", severity_score=8))
    assert out["urgency"] == "Moderate"
    assert out["matching_rule"] == "Severity-Based Escalation"


def test_contradiction_low_severity_with_symptom_is_rejected():
    ok, msg = engine.validate_input(base(severity_score=1))
    assert ok is False and "Contradiction" in msg


def test_vomiting_with_low_severity_contradiction():
    ok, _ = engine.validate_input(base(primary_symptom="vomiting", vomiting_severity="mild", severity_score=1))
    assert ok is False


def test_valid_input_passes_validation():
    ok, msg = engine.validate_input(base())
    assert ok is True and msg is None



@pytest.mark.parametrize("severity", [1, 3, 5])
def test_chest_pain_is_never_low(severity):
    out = engine.evaluate(base(primary_symptom="chest_pain", severity_score=severity, breathlessness_level="none"))
    assert out["urgency"] == "Moderate"
    assert out["matching_rule"] == "Chest Pain Needs Prompt Evaluation"
