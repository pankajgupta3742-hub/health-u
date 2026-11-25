"""Triage assessments and PDF reports. Every query is scoped to the signed-in user."""
import json
import os
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import Assessment, AssessmentMissingReport, Report, User
from app.schemas import AssessmentOut, ReportOut, SymptomInput
from app.services import reports as report_service
from app.services import triage_completion as tc
from app.services.triage_graph import run_triage

router = APIRouter(prefix="/api/v1", tags=["assessments"])


def _utc(dt):
    """SQLite returns naive datetimes. Stored values are UTC, so mark them as such."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _to_out(a: Assessment, missing: dict | None = None) -> AssessmentOut:
    return AssessmentOut(
        id=a.id,
        created_at=_utc(a.created_at),
        input=json.loads(a.input_json),
        final_urgency=a.final_urgency,
        status=a.status,
        missing_data=missing,
        rule_output={"matching_rule": a.matching_rule, "logic": a.rule_logic},
        ml_output={"urgency": a.ml_urgency, "confidence": a.ml_confidence},
        ai_explanation={
            "narrative": a.narrative,
            "recommendation": a.recommendation,
            "first_aid": a.first_aid,
            "medicine_info": a.medicine_info,
        },
    )


def _owned(db: Session, model, record_id: str, user: User):
    """Return the row only if it belongs to the user. Otherwise 404, so other users' IDs are not revealed."""
    row = db.get(model, record_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return row


def _report_for(db: Session, assessment_id: str) -> dict | None:
    rep = db.scalars(select(AssessmentMissingReport).where(
        AssessmentMissingReport.assessment_id == assessment_id)).first()
    return tc.report_out(rep)


@router.post("/assessments", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
def create_assessment(body: SymptomInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude={"accepted"})
    try:
        # Only the patient's accepted suggestions are used, each checked against the patient's own records.
        merged, provenance = tc.resolve_accepted(db, user, data, body.accepted)
    except tc.TriageError as e:
        raise HTTPException(422, str(e))

    result = run_triage(merged)  # LangGraph: detect -> validate -> rules -> explain -> guard
    missing = tc.detect(merged)
    proposals = tc.propose(db, user, missing) if missing else []
    expl = result.get("ai_explanation") or {}
    rule = result.get("rule_output") or {}
    ml = result.get("ml_output") or {}
    row = Assessment(
        user_id=user.id,
        input_json=json.dumps(merged),
        final_urgency=str(result.get("final_urgency", "N/A")),
        status=str(result.get("status", "")),
        matching_rule=str(rule.get("matching_rule", "")),
        rule_logic=str(rule.get("logic", "")),
        ml_urgency=str(ml.get("urgency", "")),
        ml_confidence=float(ml.get("confidence", 0.0) or 0.0),
        narrative=str(expl.get("narrative", "")),
        recommendation=str(expl.get("recommendation", "")),
        first_aid=str(expl.get("first_aid", "")),
        medicine_info=str(expl.get("medicine_info", "")),
    )
    db.add(row)
    db.flush()
    rep = tc.save_report(db, user, row.id, missing, proposals, provenance)
    db.commit()
    db.refresh(row)
    return _to_out(row, tc.report_out(rep))


@router.get("/assessments", response_model=list[AssessmentOut])
def list_assessments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Assessment).where(Assessment.user_id == user.id)
                      .order_by(Assessment.created_at.desc()).limit(100)).all()
    reps = {r.assessment_id: r for r in db.scalars(select(AssessmentMissingReport).where(
        AssessmentMissingReport.user_id == user.id)).all()}
    return [_to_out(r, tc.report_out(reps.get(r.id))) for r in rows]


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut)
def get_assessment(assessment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, Assessment, assessment_id, user)
    return _to_out(row, _report_for(db, row.id))


@router.get("/assessments/{assessment_id}/missing-data")
def get_missing_data(assessment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, Assessment, assessment_id, user)
    return _report_for(db, row.id) or {"missing_fields": [], "proposals": [], "provenance": {}, "created_at": None}


@router.delete("/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(assessment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, Assessment, assessment_id, user)
    for rep in db.scalars(select(Report).where(Report.assessment_id == row.id)).all():
        _remove_file(rep.file_path)
        db.delete(rep)
    for mr in db.scalars(select(AssessmentMissingReport).where(
            AssessmentMissingReport.assessment_id == row.id)).all():
        db.delete(mr)
    db.flush()  # reports reference this assessment: remove them first
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/assessments/{assessment_id}/report", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(assessment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _owned(db, Assessment, assessment_id, user)
    report = Report(user_id=user.id, assessment_id=a.id, file_path="")
    db.add(report)
    db.flush()
    path = report_service.generate_pdf(
        json.loads(a.input_json), a.final_urgency,
        {"matching_rule": a.matching_rule, "logic": a.rule_logic},
        {"narrative": a.narrative, "recommendation": a.recommendation,
         "first_aid": a.first_aid, "medicine_info": a.medicine_info},
        report_id=report.id, created_at=a.created_at,
        missing=_report_for(db, a.id),  # report intelligence: missing answers and where each value came from
    )
    report.file_path = path
    db.commit()
    return ReportOut(id=report.id, assessment_id=a.id, created_at=_utc(report.created_at))


@router.get("/reports/{report_id}/download")
def download_report(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rep = _owned(db, Report, report_id, user)
    if not rep.file_path or not os.path.isfile(rep.file_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report file is no longer available.")
    return FileResponse(rep.file_path, media_type="application/pdf", filename="Health-U_Report.pdf")


def _remove_file(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
