"""Privacy controls: export and permanent deletion of a user's own data."""
import os

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import Assessment, LabResult, Report, User

router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Deletes the account, every assessment, lab result, and generated report file."""
    for rep in db.scalars(select(Report).where(Report.user_id == user.id)).all():
        try:
            if rep.file_path and os.path.isfile(rep.file_path):
                os.remove(rep.file_path)
        except OSError:
            pass
        db.delete(rep)
    db.flush()  # reports reference assessments: delete them first (PostgreSQL enforces this)
    for model in (Assessment, LabResult):
        for row in db.scalars(select(model).where(model.user_id == user.id)).all():
            db.delete(row)
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/export")
def export_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Everything stored for this user as one JSON file. Report PDFs are listed by name, not embedded."""
    import json as _json
    from datetime import datetime, timezone

    def _iso(v):
        return v.isoformat() if hasattr(v, "isoformat") else v

    assessments = [
        {"id": a.id, "created_at": _iso(a.created_at), "input": _json.loads(a.input_json or "{}"),
         "final_urgency": a.final_urgency, "matching_rule": a.matching_rule, "rule_logic": a.rule_logic,
         "narrative": a.narrative, "recommendation": a.recommendation, "first_aid": a.first_aid,
         "medicine_info": a.medicine_info}
        for a in db.scalars(select(Assessment).where(Assessment.user_id == user.id)).all()
    ]
    labs = [
        {"id": r.id, "test_name": r.test_name, "value": r.value, "unit": r.unit,
         "reference_range": r.reference_range, "recorded_on": _iso(r.recorded_on), "created_at": _iso(r.created_at)}
        for r in db.scalars(select(LabResult).where(LabResult.user_id == user.id)).all()
    ]
    reports = [
        {"id": r.id, "assessment_id": r.assessment_id, "created_at": _iso(r.created_at)}
        for r in db.scalars(select(Report).where(Report.user_id == user.id)).all()
    ]
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {"id": user.id, "email": user.email, "name": user.name},
        "assessments": assessments,
        "lab_results": labs,
        "reports": reports,
        "note": "Chat history is stored in your browser, not on the server, so it is not included.",
    }
    return JSONResponse(payload, headers={"Content-Disposition": 'attachment; filename="health-u-my-data.json"'})
