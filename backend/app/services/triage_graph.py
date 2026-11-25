"""Triage as a LangGraph workflow:  detect -> validate -> rules -> explain -> guard.

- detect:   lists triage fields with no answer. If any are missing, the run stops here with an INCOMPLETE result.
            No urgency is calculated and no value is filled in. Proposals are made elsewhere (triage_completion).
- validate: rejects contradictory or impossible symptom combinations (no urgency is given).
- rules:    the rule engine sets the urgency. This is the only source of urgency.
- explain:  the language model writes the narrative text, given the rule result. It cannot change urgency.
- guard:    enforces the safety rules in code. The final urgency is copied from the rules, text fields are
            length-capped, and the output is checked for the required fields.

The legacy synthetic ML model is not part of this graph.
"""
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.services.triage_completion import detect
from llm_layer import LLMLayer
from rule_engine import RuleEngine

MAX_TEXT = 1500


class TriageState(TypedDict, total=False):
    input: dict
    missing: list
    validation_error: str | None
    rule_output: dict
    final_urgency: str
    explanation: dict
    result: dict


_rules = RuleEngine()
_llm = LLMLayer()


def _detect(state: TriageState) -> dict:
    return {"missing": detect(state["input"])}


def _validate(state: TriageState) -> dict:
    ok, msg = _rules.validate_input(state["input"])
    return {"validation_error": None if ok else msg}


def _rules_node(state: TriageState) -> dict:
    out = _rules.evaluate(state["input"])
    return {"rule_output": out, "final_urgency": out["urgency"]}


def _explain(state: TriageState) -> dict:
    text = _llm.generate_explanation(state["input"], {
        "final_urgency": state["final_urgency"], "rule_output": state["rule_output"]})
    return {"explanation": text or {}}


def _guard(state: TriageState) -> dict:
    urgency = state["rule_output"]["urgency"]  # always the rule result, never the text
    expl = {k: str((state.get("explanation") or {}).get(k, ""))[:MAX_TEXT]
            for k in ("narrative", "recommendation", "first_aid", "medicine_info")}
    result = {
        "final_urgency": urgency,
        "status": "Rule engine decision",
        "rule_output": state["rule_output"],
        "ml_output": {"urgency": "Not used", "confidence": 0.0},
        "ai_explanation": expl,
    }
    return {"final_urgency": urgency, "result": result}


def _contradiction(state: TriageState) -> dict:
    msg = state["validation_error"]
    return {"result": {
        "final_urgency": "N/A", "status": "Contradiction Detected",
        "ai_explanation": {"narrative": msg, "recommendation": "Please re-enter your symptoms accurately.",
                           "first_aid": "N/A", "medicine_info": "N/A"},
        "ml_output": {"urgency": "N/A", "confidence": 0},
        "rule_output": {"matching_rule": "N/A", "logic": msg},
    }}


def _incomplete(state: TriageState) -> dict:
    missing = state.get("missing", [])
    names = ", ".join(f.replace("_", " ") for f in missing)
    return {"result": {
        "final_urgency": "N/A", "status": "Incomplete: missing information",
        "missing_fields": missing,
        "ai_explanation": {"narrative": f"Some answers are missing ({names}), so no urgency level was calculated.",
                           "recommendation": "Answer the questions listed, or accept a suggestion from your earlier records.",
                           "first_aid": "N/A", "medicine_info": "N/A"},
        "ml_output": {"urgency": "N/A", "confidence": 0},
        "rule_output": {"matching_rule": "N/A", "logic": "Not evaluated: information is missing."},
    }}


def _route_detect(state: TriageState) -> str:
    return "incomplete" if state.get("missing") else "validate"


def _route(state: TriageState) -> str:
    return "contradiction" if state.get("validation_error") else "rules"


_graph = StateGraph(TriageState)
_graph.add_node("detect", _detect)
_graph.add_node("incomplete", _incomplete)
_graph.add_node("validate", _validate)
_graph.add_node("rules", _rules_node)
_graph.add_node("explain", _explain)
_graph.add_node("guard", _guard)
_graph.add_node("contradiction", _contradiction)
_graph.set_entry_point("detect")
_graph.add_conditional_edges("detect", _route_detect, {"validate": "validate", "incomplete": "incomplete"})
_graph.add_conditional_edges("validate", _route, {"rules": "rules", "contradiction": "contradiction"})
_graph.add_edge("incomplete", END)
_graph.add_edge("rules", "explain")
_graph.add_edge("explain", "guard")
_graph.add_edge("guard", END)
_graph.add_edge("contradiction", END)
triage_app = _graph.compile()


def run_triage(data: dict[str, Any]) -> dict:
    """Run triage on exactly what the patient provided. Missing fields are never filled in."""
    state = triage_app.invoke({"input": {k: v for k, v in data.items() if v is not None}})
    return state["result"]
