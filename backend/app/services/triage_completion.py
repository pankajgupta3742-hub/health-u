"""Missing-data handling for symptom triage.

- detect:   which triage fields have no answer. Nothing is filled in for them.
- propose:  candidate values from THIS patient's earlier assessments, with source date, age and reasoning.
            Symptom answers older than SYMPTOM_DAYS cannot be accepted. They are shown as too old.
- resolve:  turns the patient's accepted proposal ids into values. A proposal is only used if it is still
            in the patient's current candidate list and is not too old at the time of acceptance.

Proposal ids are derived from (user, field, source assessment, value). They are not stored separately, so
they cannot point at another patient's data: the server recomputes candidates from the signed-in user's rows.
"""
import hashlib
import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.missing_data_agent import review_candidates
from app.models import Assessment, AssessmentMissingReport, User

TRIAGE_FIELDS = (
    "primary_symptom", "severity_score", "duration_category", "frequency", "age_group",
    "breathlessness_level", "vomiting_severity", "fever_level", "pain_type",
)
STABLE_FIELDS = {"age_group"}   # changes rarely: 365-day reuse window
SYMPTOM_DAYS = 7                # symptoms change quickly: a week at most
STABLE_DAYS = 365
MAX_PROPOSALS = 20
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


class TriageError(ValueError):
    """Bad request for triage completion. The router returns HTTP 422."""


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_missing(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def detect(data: dict) -> list[str]:
    return [f for f in TRIAGE_FIELDS if is_missing(data.get(f))]


def limit_days(field: str) -> int:
    return STABLE_DAYS if field in STABLE_FIELDS else SYMPTOM_DAYS


def proposal_id(user_id: str, field: str, source_assessment_id: str, value) -> str:
    raw = f"{user_id}|{field}|{source_assessment_id}|{value}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def retrieve(db: Session, user: User, fields: list[str]) -> list[dict]:
    """Newest earlier value per field, from this user's completed assessments only."""
    if not fields:
        return []
    rows = db.scalars(
        select(Assessment).where(Assessment.user_id == user.id, Assessment.final_urgency != "N/A")
        .order_by(Assessment.created_at.desc()).limit(50)
    ).all()
    reports = {r.assessment_id: r for r in db.scalars(
        select(AssessmentMissingReport).where(AssessmentMissingReport.user_id == user.id)).all()}
    today = _today()
    seen: set[str] = set()
    out: list[dict] = []
    for a in rows:
        data = json.loads(a.input_json or "{}")
        prov = json.loads(reports[a.id].provenance_json or "{}") if a.id in reports else {}
        for field in fields:
            if field in seen or is_missing(data.get(field)):
                continue
            seen.add(field)
            value = data[field]
            # A reused value keeps the date it was originally given, not the date it was reused.
            src = prov.get(field, {})
            source_date = date.fromisoformat(src["source_date"]) if src.get("source_date") else _utc(a.created_at).date()
            age_days = (today - source_date).days
            limit = limit_days(field)
            out.append({
                "id": proposal_id(user.id, field, a.id, value), "field": field, "value": str(value),
                "category": "retrieved", "source_assessment_id": a.id, "source_date": source_date,
                "age_days": age_days, "limit_days": limit, "too_old": age_days > limit,
                "description": f"Your earlier answer '{str(value).replace('_', ' ')}' from {source_date.isoformat()}.",
            })
    return out[:MAX_PROPOSALS]


def propose(db: Session, user: User, missing: list[str]) -> list[dict]:
    """Proposals to show the patient. The agent only adds reasoning and can lower confidence."""
    cands = retrieve(db, user, missing)
    if not cands:
        return []
    payload = [{"id": c["id"], "field": c["field"], "proposed_value": c["value"], "category": c["category"],
                "source_date": c["source_date"].isoformat(), "age_days": c["age_days"]} for c in cands]
    reviews = review_candidates(payload)
    out = []
    for c in cands:
        rev = reviews.get(c["id"], {})
        # Symptom answers: high confidence only when fresh. Anything older than the limit is low.
        cap = "low" if c["too_old"] else ("high" if c["age_days"] <= 1 else "medium")
        confidence = rev.get("confidence", "low")
        if CONFIDENCE_ORDER.get(confidence, 0) > CONFIDENCE_ORDER[cap]:
            confidence = cap
        out.append({
            "id": c["id"], "field": c["field"], "value": c["value"], "category": c["category"],
            "source_assessment_id": c["source_assessment_id"], "source_date": c["source_date"].isoformat(),
            "age_days": c["age_days"], "limit_days": c["limit_days"],
            "status": "too_old" if c["too_old"] else "pending",
            "allowed_actions": [] if c["too_old"] else ["accept"],
            "confidence": confidence, "requires_confirmation": True,
            "reasoning": rev.get("reasoning") or c["description"],
            "reviewed_by": rev.get("reviewed_by", "rules"),
        })
    return out


def resolve_accepted(db: Session, user: User, data: dict, accepted: dict[str, str]) -> tuple[dict, dict]:
    """Return (input with accepted values, provenance per field). Raises TriageError for any unsafe acceptance."""
    today = _today()
    merged = {k: v for k, v in data.items() if not is_missing(v)}
    provenance: dict[str, dict] = {f: {"source": "patient_entered", "source_date": today.isoformat()} for f in merged}
    if not accepted:
        return merged, provenance

    cands = {c["id"]: c for c in retrieve(db, user, list(accepted))}
    for field, pid in accepted.items():
        if field not in TRIAGE_FIELDS:
            raise TriageError(f"Unknown field: {field}")
        cand = cands.get(pid)
        if cand is None or cand["field"] != field:
            raise TriageError("That suggestion is no longer available. Please answer the question directly.")
        if cand["too_old"]:
            raise TriageError(f"Your earlier answer for {field.replace('_', ' ')} is too old to reuse. Please answer again.")
        if field in merged:
            raise TriageError(f"'{field}' already has your answer. Remove one of them.")
        # Stored values are text. Numeric fields are converted back so the rules compare numbers, not strings.
        merged[field] = int(cand["value"]) if field == "severity_score" else cand["value"]
        provenance[field] = {"source": "retrieved", "source_date": cand["source_date"].isoformat(),
                             "source_assessment_id": cand["source_assessment_id"], "proposal_id": pid,
                             "original_value": cand["value"], "approval": "accepted"}
    return merged, provenance


def save_report(db: Session, user: User, assessment_id: str, missing: list[str], proposals: list[dict],
                provenance: dict) -> AssessmentMissingReport:
    rep = AssessmentMissingReport(
        user_id=user.id, assessment_id=assessment_id, missing_json=json.dumps(missing),
        proposals_json=json.dumps(proposals, default=str), provenance_json=json.dumps(provenance),
    )
    db.add(rep)
    return rep


def report_out(rep: AssessmentMissingReport | None) -> dict | None:
    if rep is None:
        return None
    return {
        "missing_fields": json.loads(rep.missing_json or "[]"),
        "proposals": json.loads(rep.proposals_json or "[]"),
        "provenance": json.loads(rep.provenance_json or "{}"),
        "created_at": _utc(rep.created_at).isoformat() if rep.created_at else None,
    }
