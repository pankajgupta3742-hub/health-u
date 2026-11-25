"""Medical report upload. Files are read in memory, scanned for lab values, and discarded.

Only values the user confirms are stored, as LabResult rows.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_BYTES
from app.deps import get_current_user, get_db
from app.models import LabResult, User
from app.routers.assessments import _owned
from app.schemas import ExtractOut, LabResultOut, LabResultsIn
from app.services import lab_extraction

router = APIRouter(prefix="/api/v1", tags=["documents"])
_PDF_MAGIC = b"%PDF-"


@router.post("/documents/extract", response_model=ExtractOut)
async def extract(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    name = (file.filename or "upload").split("/")[-1].split("\\")[-1][:120]
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413,
                            f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is empty.")

    if data.startswith(_PDF_MAGIC):
        try:
            text, pages = lab_extraction.extract_text_from_pdf(data)
        except Exception:
            raise HTTPException(422, "Could not read this PDF.")
    elif (file.content_type or "").startswith("text/") or name.lower().endswith(".txt"):
        text, pages = data.decode("utf-8", errors="replace"), 1
    else:
        # Image OCR is not enabled in this build. Reject instead of guessing.
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            "Upload a text-based PDF or a .txt file. Scanned images are not supported yet.")

    candidates = lab_extraction.extract_candidates(text)
    note = ("No lab values were recognised. You can still type values manually." if not candidates else
            "Review each value against your report before saving. Nothing is stored yet.")
    return ExtractOut(filename=name, pages_read=pages, candidates=candidates, note=note)


@router.post("/lab-results", response_model=list[LabResultOut], status_code=status.HTTP_201_CREATED)
def save_lab_results(body: LabResultsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = [LabResult(user_id=user.id, test_name=r.test_name, value=r.value, unit=r.unit,
                      reference_range=r.reference_range, recorded_on=r.recorded_on) for r in body.results]
    db.add_all(rows)
    db.commit()
    return [_lab_out(r) for r in rows]


@router.get("/lab-results", response_model=list[LabResultOut])
def list_lab_results(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(LabResult).where(LabResult.user_id == user.id)
                      .order_by(LabResult.created_at.desc()).limit(500)).all()
    return [_lab_out(r) for r in rows]


@router.delete("/lab-results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lab_result(result_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, LabResult, result_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _lab_out(r: LabResult) -> LabResultOut:
    created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=timezone.utc)
    return LabResultOut(id=r.id, test_name=r.test_name, value=r.value, unit=r.unit,
                        reference_range=r.reference_range, recorded_on=r.recorded_on, created_at=created)
