"""Missing-data review: create a report, record the patient's decisions, then predict. Signed-in patients only."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import MissingDataReport, User
from app.schemas.missing_data import CorrectionInput, DecisionsInput, ReviewInput
from app.services import missing_data_service as svc
from app.services import predictions as pred
from app.workflows.missing_data_graph import run_finalize, run_review

router = APIRouter(prefix="/api/v1/missing-data", tags=["missing-data"])


def _owned_report(db: Session, report_id: str, user: User) -> MissingDataReport:
    row = db.get(MissingDataReport, report_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return row


def _bad(e: Exception):
    return HTTPException(422, str(e))


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(body: ReviewInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.model not in pred.MODEL_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown model")
    try:
        report = run_review(db, user, body.model, dict(body.features))
    except svc.MissingDataError as e:
        raise _bad(e)
    return svc.report_view(db, report)


@router.get("/reports")
def list_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(MissingDataReport).where(MissingDataReport.user_id == user.id)
                      .order_by(MissingDataReport.created_at.desc()).limit(100)).all()
    return [{"id": r.id, "model": r.model_key, "status": r.status,
             "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.report_view(db, _owned_report(db, report_id, user))


@router.post("/reports/{report_id}/decisions")
def decide(report_id: str, body: DecisionsInput, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    report = _owned_report(db, report_id, user)
    try:
        svc.apply_decisions(db, user, report, body.decisions)
    except svc.MissingDataError as e:
        raise _bad(e)
    return svc.report_view(db, report)


@router.post("/reports/{report_id}/predict")
def predict(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _owned_report(db, report_id, user)
    try:
        return run_finalize(db, user, report)
    except svc.MissingDataError as e:
        raise _bad(e)


@router.post("/reports/{report_id}/corrections")
def correct_value(report_id: str, body: CorrectionInput, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    report = _owned_report(db, report_id, user)
    try:
        svc.correct(db, user, report, body.field, body.value)
    except svc.MissingDataError as e:
        raise _bad(e)
    return {"status": report.status, "provenance": svc.history(db, user, report)}


@router.get("/reports/{report_id}/history")
def report_history(report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _owned_report(db, report_id, user)
    return svc.history(db, user, report)
