"""LangGraph orchestration for the missing-data completion engine.

Two graphs, because the patient answers in between:

1. review_graph:   detect -> retrieve -> agent_review -> persist
   Runs when the patient submits inputs. Produces the missing-data report and PROPOSALS only.
2. finalize_graph: validate -> predict_and_record -> safety -> explain
   Runs after the patient has decided each field. Predicts only when every field is resolved,
   records the provenance of every value used, then adds safety notes and a plain explanation.
   Neither the safety step nor the explanation changes a probability or class; both only describe it.

The business rules live in app/services/missing_data_service.py. These graphs only sequence them.
"""
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.missing_data_agent import review_candidates
from app.services import missing_data_service as svc


class ReviewState(TypedDict, total=False):
    db: Any
    user: Any
    key: str
    features: dict
    detected: dict
    candidates: list
    reviews: dict
    report: Any


def _detect(state: ReviewState) -> dict:
    return {"detected": svc.detect(state["key"], state["features"])}


def _retrieve(state: ReviewState) -> dict:
    return {"candidates": svc.retrieve(state["db"], state["user"], state["key"], state["detected"])}


def _agent_review(state: ReviewState) -> dict:
    payload = [{
        "id": c["id"], "field": c["field"], "proposed_value": c["proposed_value"], "category": c["category"],
        "source_date": c["source_date"].isoformat(), "age_days": c["age_days"],
    } for c in state.get("candidates", [])]
    return {"reviews": review_candidates(payload)}


def _persist(state: ReviewState) -> dict:
    report = svc.persist(state["db"], state["user"], state["key"], state["features"], state["detected"],
                         state.get("candidates", []), state.get("reviews", {}))
    return {"report": report}


_review = StateGraph(ReviewState)
_review.add_node("detect", _detect)
_review.add_node("retrieve", _retrieve)
_review.add_node("agent_review", _agent_review)
_review.add_node("persist", _persist)
_review.set_entry_point("detect")
_review.add_edge("detect", "retrieve")
_review.add_edge("retrieve", "agent_review")
_review.add_edge("agent_review", "persist")
_review.add_edge("persist", END)
review_graph = _review.compile()


class FinalizeState(TypedDict, total=False):
    db: Any
    user: Any
    report: Any
    unresolved: list
    result: dict


def _validate(state: FinalizeState) -> dict:
    view = svc.report_view(state["db"], state["report"])
    return {"unresolved": view["unresolved_fields"]}


def _predict_and_record(state: FinalizeState) -> dict:
    # Unresolved fields make the result "incomplete" inside svc.finalize; nothing is predicted for them.
    return {"result": svc.finalize(state["db"], state["user"], state["report"])}


_final = StateGraph(FinalizeState)
_final.add_node("validate", _validate)
def _safety(state: FinalizeState) -> dict:
    """Clinical safety notes. Added to the result; never changes a value."""
    result = dict(state["result"])
    notes = ["This is an estimate from a research model. It is not a diagnosis."]
    if result.get("outcome") != "complete":
        notes.append("No estimate was calculated because some information is missing.")
    else:
        if result.get("status") == "limited":
            notes.append(f"This model has a known limitation: {result.get('status_reason', '')}")
        if result.get("unknown_fields"):
            notes.append("Some fields were marked unknown and were handled by the model's own missing-value method. "
                         "The estimate is less certain for them.")
        notes.append("If you feel unwell, or your symptoms are severe or getting worse, seek medical care now.")
    result["safety_notes"] = notes
    return {"result": result}


def _explain(state: FinalizeState) -> dict:
    """Plain-language summary built only from the stored result and provenance. No language model is used."""
    result = dict(state["result"])
    if result.get("outcome") != "complete":
        result["explanation"] = "The model did not run. Answer or mark the remaining questions, then try again."
        return {"result": result}
    if result.get("task") == "binary" and result.get("probability_positive") is not None:
        headline = f"Estimated probability of a positive result: {result['probability_positive'] * 100:.1f}%."
    else:
        headline = f"Most likely class in this model: {result.get('top_class', 'not stated')}."
    counts = (f"Built from {result.get('answered_count', 0)} value(s) you entered or approved, "
              f"and {result.get('unknown_count', 0)} value(s) you marked unknown.")
    result["explanation"] = f"{headline} {counts}"
    return {"result": result}


_final.add_node("predict_and_record", _predict_and_record)
_final.add_node("safety", _safety)
_final.add_node("explain", _explain)
_final.set_entry_point("validate")
_final.add_edge("validate", "predict_and_record")
_final.add_edge("predict_and_record", "safety")
_final.add_edge("safety", "explain")
_final.add_edge("explain", END)
finalize_graph = _final.compile()


def run_review(db, user, key: str, features: dict) -> dict:
    out = review_graph.invoke({"db": db, "user": user, "key": key, "features": features})
    return out["report"]


def run_finalize(db, user, report) -> dict:
    out = finalize_graph.invoke({"db": db, "user": user, "report": report})
    return out["result"]
