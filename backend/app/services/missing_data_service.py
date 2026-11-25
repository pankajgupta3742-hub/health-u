"""Missing-data completion engine: detection, retrieval, proposals, patient decisions, validation, provenance.

Rules this module enforces:
- Nothing is filled in silently. Retrieved and derived values are PROPOSALS. A value is used only after the
  patient accepts it, edits it, or types it in. The patient can also mark a field unknown.
- Only the signed-in patient's own records are read (every query filters on user_id).
- Old information is not reused as current. Each proposal carries its source date and age. Proposals older
  than the limit for their field cannot be accepted; the patient must answer again.
- Categories are never mixed: retrieved (found in a record), derived (calculated by a fixed formula),
  inferred (reserved for context-based proposals; none are generated yet), and unknown (not established).
- The LLM agent (app/agents/missing_data_agent.py) only reviews candidates. It cannot change a value.
- Every completed field has a CompletionHistory row: original value, final value, source, source date,
  method, approval status, and timestamp.
"""
import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.missing_data_agent import review_candidates
from app.models import (
    CompletionHistory,
    CompletionSource,
    ConfirmedInput,
    MissingDataReport,
    MissingFieldRecord,
    PatientApproval,
    ProposedCompletion,
    User,
)
from app.services import predictions as svc

AGE_FIELDS = {"Age", "age_years"}          # numeric age: can be derived from an older confirmed age
STABLE_FIELDS = {"Sex", "Gender", "sex"}   # rarely change: longer reuse window
ACCEPTABLE_DAYS = 90                       # symptoms and measurements: older than this cannot be accepted
STABLE_ACCEPTABLE_DAYS = 365
AGE_ACCEPTABLE_DAYS = 730                  # a derived age is only as good as the age it started from

RESOLVED = ("patient_entered", "completed", "unknown")
METHOD_TO_CONFIRMED_CATEGORY = {
    "accepted_retrieved": "retrieved",
    "accepted_derived": "derived",
    "edited_proposal": "edited",
    "manual_entry": "manual",
}


class MissingDataError(ValueError):
    """Bad request for this engine. The router turns it into HTTP 422."""


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _canonical(feature: dict, value) -> str | None:
    """Check a value against the feature spec and return its stored text form."""
    try:
        coerced = svc._coerce(feature, value)
    except svc.PredictionError as e:
        raise MissingDataError(str(e))
    return None if coerced is None else str(coerced)


def _features_by_name(key: str) -> dict[str, dict]:
    return {f["name"]: f for f in svc.load_spec(key)["features"]}


# ---------------------------------------------------------------- 1. detection

def detect(key: str, features: dict) -> dict[str, dict]:
    """Status of every model field: patient_entered, missing, or invalid (an answer that breaks the spec)."""
    by_name = _features_by_name(key)
    unknown = [k for k in features if k not in by_name]
    if unknown:
        raise MissingDataError(f"Unknown fields: {', '.join(sorted(unknown)[:10])}")
    state = {}
    for name, feature in by_name.items():
        raw = features.get(name)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            state[name] = {"status": "missing", "detail": "No answer yet.", "value": None}
            continue
        try:
            value = _canonical(feature, raw)
        except MissingDataError as e:
            state[name] = {"status": "invalid", "detail": str(e), "value": None}
            continue
        state[name] = {"status": "patient_entered", "detail": "Answered by you.", "value": value}
    return state


# ---------------------------------------------------------------- 2. contextual retrieval

def retrieve(db: Session, user: User, key: str, detected: dict[str, dict]) -> list[dict]:
    """Candidate values for missing fields, from this patient's own confirmed answers only."""
    missing = [n for n, s in detected.items() if s["status"] in ("missing", "invalid")]
    if not missing:
        return []
    rows = db.scalars(
        select(ConfirmedInput)
        .where(ConfirmedInput.user_id == user.id, ConfirmedInput.model_key == key,
               ConfirmedInput.field_name.in_(missing))
        .order_by(ConfirmedInput.recorded_at.desc())
    ).all()
    latest: dict[str, ConfirmedInput] = {}
    for row in rows:  # newest first: keep the first one per field
        latest.setdefault(row.field_name, row)

    by_name = _features_by_name(key)
    today = _today()
    candidates = []
    for name, row in latest.items():
        age_days = (today - row.source_date).days
        if name in AGE_FIELDS:
            try:
                base = float(row.value)
            except ValueError:
                continue
            elapsed_years = int(age_days // 365.25)
            new_value = int(base) + elapsed_years if base == int(base) else base
            try:
                canonical = _canonical(by_name[name], new_value)
            except MissingDataError:
                continue  # the derived age is outside the model's range: do not propose it
            candidates.append({
                "id": new_id(), "field": name, "category": "derived", "proposed_value": canonical,
                "original_value": row.value, "source_record_id": row.id, "source_date": row.source_date,
                "age_days": age_days, "too_old": age_days > AGE_ACCEPTABLE_DAYS,
                "description": f"Age {row.value} confirmed on {row.source_date.isoformat()}, plus {elapsed_years} year(s).",
            })
            continue
        limit = STABLE_ACCEPTABLE_DAYS if name in STABLE_FIELDS else ACCEPTABLE_DAYS
        try:
            canonical = _canonical(by_name[name], row.value)
        except MissingDataError:
            continue
        candidates.append({
            "id": new_id(), "field": name, "category": "retrieved", "proposed_value": canonical,
            "original_value": row.value, "source_record_id": row.id, "source_date": row.source_date,
            "age_days": age_days, "too_old": age_days > limit,
            "description": f"Your confirmed answer '{canonical}' from {row.source_date.isoformat()}.",
        })
    return candidates


# ---------------------------------------------------------------- 3. review (agent) and persistence

def persist(db: Session, user: User, key: str, features: dict, detected: dict, candidates: list[dict],
            reviews: dict[str, dict]) -> MissingDataReport:
    """Write the report, one field record per model field, and a pending proposal per supported candidate."""
    report = MissingDataReport(
        user_id=user.id, model_key=key,
        input_json=json.dumps({k: v for k, v in features.items() if v not in (None, "")}),
        status="open",
    )
    db.add(report)
    db.flush()  # assigns report.id

    today = _today()
    for name, state in detected.items():
        db.add(MissingFieldRecord(
            report_id=report.id, user_id=user.id, field_name=name, status=state["status"],
            detail=state["detail"], final_value=state["value"] if state["status"] == "patient_entered" else None,
        ))
        if state["status"] == "patient_entered":
            # A value typed at intake is a completed field too, so it gets a provenance row.
            db.add(CompletionHistory(
                report_id=report.id, user_id=user.id, field_name=name, original_value=None,
                final_value=state["value"], source="patient", source_date=today,
                completion_method="entered_at_intake", approval_status="entered_by_patient",
            ))

    for cand in candidates:
        review = reviews.get(cand["id"], {})
        if not review.get("supports", True):
            continue  # the agent judged the evidence unsupportive: no proposal is made
        evidence = [{"record_id": cand["source_record_id"], "source_date": cand["source_date"].isoformat(),
                     "original_value": cand["original_value"], "description": cand["description"]}]
        proposal = ProposedCompletion(
            report_id=report.id, user_id=user.id, field_name=cand["field"], category=cand["category"],
            proposed_value=cand["proposed_value"], source_date=cand["source_date"], age_days=cand["age_days"],
            reasoning=review.get("reasoning", ""), evidence_json=json.dumps(evidence),
            confidence=review.get("confidence", "low"), requires_confirmation=True,
            status="too_old" if cand["too_old"] else "pending",
        )
        db.add(proposal)
        db.flush()
        db.add(CompletionSource(
            proposal_id=proposal.id, user_id=user.id, source_type="confirmed_input",
            source_record_id=cand["source_record_id"], source_date=cand["source_date"],
            description=cand["description"],
        ))
    db.commit()
    db.refresh(report)
    return report


# ---------------------------------------------------------------- views

def _allowed_actions(status: str, proposal_status: str | None = None) -> list[str]:
    if status in ("patient_entered", "completed", "unknown"):
        return []
    return ["manual", "unknown"]


def report_view(db: Session, report: MissingDataReport) -> dict:
    by_name = _features_by_name(report.model_key)
    records = {r.field_name: r for r in db.scalars(
        select(MissingFieldRecord).where(MissingFieldRecord.report_id == report.id)).all()}
    proposals = db.scalars(
        select(ProposedCompletion).where(ProposedCompletion.report_id == report.id)
        .order_by(ProposedCompletion.created_at)).all()

    fields, unresolved = [], []
    for name, feature in by_name.items():
        rec = records.get(name)
        status = rec.status if rec else "missing"
        if status not in RESOLVED:
            unresolved.append(name)
        field_proposals = []
        for p in proposals:
            if p.field_name != name:
                continue
            evidence = json.loads(p.evidence_json or "[]")
            actions = []
            if status not in RESOLVED and p.status == "pending":
                actions = ["accept", "reject", "edit", "manual", "unknown"]
            elif status not in RESOLVED and p.status == "too_old":
                actions = ["edit", "manual", "unknown"]  # cannot be accepted: the patient answers again
            field_proposals.append({
                "id": p.id, "category": p.category, "value": p.proposed_value,
                "source_date": p.source_date.isoformat(), "age_days": p.age_days,
                "reasoning": p.reasoning, "evidence": evidence, "confidence": p.confidence,
                "requires_confirmation": p.requires_confirmation, "status": p.status,
                "allowed_actions": actions,
            })
        fields.append({
            "name": name, "type": feature["type"], "status": status,
            "final_value": rec.final_value if rec else None,
            "detail": rec.detail if rec else "",
            "options": feature.get("options"), "min": feature.get("min"), "max": feature.get("max"),
            "proposals": field_proposals,
            "allowed_actions": _allowed_actions(status),
        })
    counts = {s: sum(1 for f in fields if f["status"] == s)
              for s in ("patient_entered", "completed", "unknown", "missing", "invalid")}
    return {
        "id": report.id, "model": report.model_key, "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "fields": fields, "unresolved_fields": unresolved, "ready": not unresolved,
        "counts": counts,
        "disclaimer": svc.DISCLAIMER,
    }


def history(db: Session, user: User, report: MissingDataReport) -> list[dict]:
    rows = db.scalars(
        select(CompletionHistory).where(CompletionHistory.report_id == report.id,
                                        CompletionHistory.user_id == user.id)
        .order_by(CompletionHistory.created_at)).all()
    return [{
        "field": r.field_name, "original_value": r.original_value, "final_value": r.final_value,
        "source": r.source, "source_date": r.source_date.isoformat() if r.source_date else None,
        "method": r.completion_method, "approval": r.approval_status,
        "timestamp": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


# ---------------------------------------------------------------- 4. patient decisions

def apply_decisions(db: Session, user: User, report: MissingDataReport, decisions: list) -> None:
    if report.status != "open":
        raise MissingDataError("This report was already used for a prediction. Start a new check.")
    by_name = _features_by_name(report.model_key)
    records = {r.field_name: r for r in db.scalars(
        select(MissingFieldRecord).where(MissingFieldRecord.report_id == report.id)).all()}
    today = _today()

    for d in decisions:
        if d.field not in by_name:
            raise MissingDataError(f"Unknown field: {d.field}")
        rec = records.get(d.field)
        if rec is None or rec.status in ("patient_entered",):
            raise MissingDataError(f"'{d.field}' was already answered by you.")
        feature = by_name[d.field]

        proposal = None
        if d.proposal_id:
            proposal = db.get(ProposedCompletion, d.proposal_id)
            if proposal is None or proposal.report_id != report.id or proposal.user_id != user.id \
                    or proposal.field_name != d.field:
                raise MissingDataError("Proposal not found for this field.")
        if d.action in ("accept", "reject", "edit") and proposal is None:
            raise MissingDataError(f"'{d.action}' needs the proposal it applies to.")

        original = None
        final = None
        source, source_date = "patient", today
        method, approval = "", "approved"

        if d.action == "accept":
            if proposal.status != "pending":
                raise MissingDataError("This suggestion is no longer open. Answer the question directly.")
            final = _canonical(feature, proposal.proposed_value)
            original = json.loads(proposal.evidence_json or "[{}]")[0].get("original_value")
            source, source_date = "confirmed_input", proposal.source_date
            method = f"accepted_{proposal.category}"
            proposal.status = "accepted"
        elif d.action == "reject":
            method, approval = "rejected_proposal", "rejected"
            proposal.status = "rejected"
            original = proposal.proposed_value
            source, source_date = "confirmed_input", proposal.source_date
        elif d.action == "edit":
            if d.value is None:
                raise MissingDataError("Enter the corrected value.")
            final = _canonical(feature, d.value)
            original = proposal.proposed_value
            source, source_date = "confirmed_input", proposal.source_date
            method = "edited_proposal"
            proposal.status = "edited"
        elif d.action == "manual":
            if d.value is None:
                raise MissingDataError("Enter the value.")
            final = _canonical(feature, d.value)
            if proposal is not None and proposal.status == "pending":
                proposal.status = "superseded"
            method = "manual_entry"
        elif d.action == "unknown":
            method, approval = "patient_unknown", "unknown"
            if proposal is not None and proposal.status == "pending":
                proposal.status = "superseded"

        # Any other open suggestion for this field is replaced by the patient's decision.
        if d.action in ("accept", "edit", "manual", "unknown"):
            for other in db.scalars(select(ProposedCompletion).where(
                    ProposedCompletion.report_id == report.id, ProposedCompletion.field_name == d.field,
                    ProposedCompletion.status.in_(["pending", "too_old"]))).all():
                if other.id != (proposal.id if proposal else None):
                    other.status = "superseded"

        if d.action in ("accept", "edit", "manual"):
            rec.status, rec.final_value = "completed", final
        elif d.action == "unknown":
            rec.status, rec.final_value = "unknown", None
        # A rejected suggestion leaves the field missing until the patient decides otherwise.

        db.add(PatientApproval(
            report_id=report.id, user_id=user.id, field_name=d.field, action=d.action,
            proposal_id=proposal.id if proposal else None, final_value=final,
        ))
        db.add(CompletionHistory(
            report_id=report.id, user_id=user.id, field_name=d.field, original_value=original,
            final_value=final, source=source, source_date=source_date, completion_method=method,
            approval_status=approval,
        ))
    db.commit()


# ---------------------------------------------------------------- 4b. patient corrections

CORRECTABLE_REPORT_STATES = ("open", "predicted", "stale")


def correct(db: Session, user: User, report: MissingDataReport, field: str, value) -> None:
    """The patient changes a value they already answered or approved. The old value stays in the history.

    A correction made after a prediction marks the report stale: that estimate used the earlier value and
    cannot be read as current. The patient runs a new check to get an updated estimate.
    """
    by_name = _features_by_name(report.model_key)
    if field not in by_name:
        raise MissingDataError(f"Unknown field: {field}")
    if report.status not in CORRECTABLE_REPORT_STATES:
        raise MissingDataError("This report cannot be changed.")
    rec = db.scalars(select(MissingFieldRecord).where(
        MissingFieldRecord.report_id == report.id, MissingFieldRecord.field_name == field)).first()
    if rec is None or rec.status not in ("patient_entered", "completed"):
        raise MissingDataError("Only answered fields can be corrected. Answer the question first.")
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise MissingDataError("Enter the corrected value.")
    new = _canonical(by_name[field], value)
    if new == rec.final_value:
        raise MissingDataError("That is already the value in use.")

    today = _today()
    original = rec.final_value
    rec.final_value = new
    db.add(CompletionHistory(
        report_id=report.id, user_id=user.id, field_name=field, original_value=original, final_value=new,
        source="patient", source_date=today, completion_method="patient_correction", approval_status="corrected",
    ))
    db.add(PatientApproval(report_id=report.id, user_id=user.id, field_name=field, action="correct",
                           proposal_id=None, final_value=new))
    db.add(ConfirmedInput(user_id=user.id, model_key=report.model_key, field_name=field, value=new,
                          category="corrected", source_date=today))
    if report.status == "predicted":
        report.status = "stale"
    db.commit()


# ---------------------------------------------------------------- 5. validation and prediction

def finalize(db: Session, user: User, report: MissingDataReport) -> dict:
    """Validate the report, run the disease model, and record what was used. Returns the result plus provenance."""
    if report.status != "open":
        raise MissingDataError("This report was already used for a prediction.")
    records = db.scalars(select(MissingFieldRecord).where(MissingFieldRecord.report_id == report.id)).all()
    values = {r.field_name: r.final_value for r in records if r.status in ("patient_entered", "completed")}
    unknown = sorted(r.field_name for r in records if r.status == "unknown")
    try:
        result = svc.predict(report.model_key, values, unknown)
    except svc.PredictionError as e:
        raise MissingDataError(str(e))

    if result.get("outcome") == "complete":
        hist = {h.field_name: h for h in db.scalars(select(CompletionHistory).where(
            CompletionHistory.report_id == report.id)).all()}
        for r in records:
            if r.status == "patient_entered":
                category, src_date = "patient_entered", _today()
            elif r.status == "completed":
                h = hist.get(r.field_name)
                category = METHOD_TO_CONFIRMED_CATEGORY.get(h.completion_method if h else "", "manual")
                src_date = (h.source_date if h and h.source_date else _today())
            else:
                continue
            db.add(ConfirmedInput(user_id=user.id, model_key=report.model_key, field_name=r.field_name,
                                  value=r.final_value, category=category, source_date=src_date))
        report.status = "predicted"
    db.commit()
    result["report_id"] = report.id
    result["provenance"] = history(db, user, report)
    result["answered_count"] = sum(1 for r in records if r.status in ("patient_entered", "completed"))
    result["unknown_count"] = len(unknown)
    return result


def new_id() -> str:
    from app.models import _uuid
    return _uuid()
