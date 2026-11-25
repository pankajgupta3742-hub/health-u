"""LLM review of proposed completions for missing data.

The agent judges one thing: does the retrieved evidence support using a candidate value for a missing field,
and how sure can we be? It cannot create, change, or fill a value. Its answers can only:
- drop a candidate it says is not supported, or
- lower the confidence that the rules already set (it can never raise it).

With no Gemini key, or on any model error, the rule-based review is used instead, so the feature still works.
"""
import json

import gemini_client

_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
MAX_REASON_CHARS = 400

SYSTEM_PROMPT = """You review candidate values for missing health-assessment fields.
For each candidate you receive the field name, the proposed value, when the information was recorded
(source_date, age_days), and whether it was retrieved or derived.

Decide whether the evidence supports using the proposed value as a CURRENT answer.
Old information is weaker evidence. Symptoms change quickly; stable facts (such as sex) change rarely.

Rules:
- Never suggest a different value. Only answer support, confidence and reasoning.
- confidence is "high", "medium" or "low".
- Keep reasoning to one or two plain sentences that the patient can read.

Return JSON only: {"reviews": [{"id": "<candidate id>", "supports": true|false, "confidence": "high|medium|low", "reasoning": "..."}]}"""


def _rule_cap(candidate: dict) -> str:
    """The highest confidence the rules allow. The agent can lower it, never raise it."""
    age = int(candidate.get("age_days", 0))
    if candidate.get("category") == "derived":
        return "medium" if age <= 90 else "low"
    if age <= 30:
        return "high"
    if age <= 90:
        return "medium"
    return "low"


def _rule_reasoning(candidate: dict) -> str:
    age = int(candidate.get("age_days", 0))
    when = candidate.get("source_date", "an earlier date")
    if candidate.get("category") == "derived":
        return (f"Calculated from your confirmed value recorded on {when}. "
                "Please confirm it still applies today.")
    if age <= 30:
        return f"You confirmed this on {when}, which is recent. Please confirm it is still true."
    if age <= 90:
        return f"You confirmed this on {when}. Symptoms may have changed, so please check it."
    return (f"You confirmed this on {when}, more than 90 days ago. It is too old to reuse. "
            "Please answer this question again.")


def _rule_review(candidate: dict) -> dict:
    return {"supports": True, "confidence": _rule_cap(candidate), "reasoning": _rule_reasoning(candidate),
            "reviewed_by": "rules"}


def review_candidates(candidates: list[dict]) -> dict[str, dict]:
    """Return {candidate_id: {supports, confidence, reasoning, reviewed_by}} for every candidate."""
    if not candidates:
        return {}
    fallback = {c["id"]: _rule_review(c) for c in candidates}
    if not gemini_client.is_configured():
        return fallback
    try:
        payload = json.dumps([{k: c[k] for k in ("id", "field", "proposed_value", "category", "source_date",
                                                  "age_days")} for c in candidates])
        data = gemini_client.generate_json_sync(SYSTEM_PROMPT, f"Candidates:\n{payload}")
    except Exception:
        return fallback  # any model problem: rules decide, nothing is lost

    reviews = data.get("reviews") if isinstance(data, dict) else None
    if not isinstance(reviews, list):
        return fallback
    by_id = {c["id"]: c for c in candidates}
    out = dict(fallback)
    for item in reviews:
        if not isinstance(item, dict) or item.get("id") not in by_id:
            continue
        cand = by_id[item["id"]]
        cap = _rule_cap(cand)
        requested = str(item.get("confidence", "")).lower()
        confidence = requested if requested in _CONFIDENCE_ORDER else cap
        if _CONFIDENCE_ORDER[confidence] > _CONFIDENCE_ORDER[cap]:
            confidence = cap  # the model cannot raise confidence above the rules
        reasoning = str(item.get("reasoning", "")).strip()[:MAX_REASON_CHARS] or _rule_reasoning(cand)
        out[item["id"]] = {"supports": bool(item.get("supports", True)), "confidence": confidence,
                           "reasoning": reasoning, "reviewed_by": "llm"}
    return out
