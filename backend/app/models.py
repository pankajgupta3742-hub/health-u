"""ORM tables. Every patient-owned row carries user_id and is queried only with that user's id."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    input_json: Mapped[str] = mapped_column(Text)
    final_urgency: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(64))
    matching_rule: Mapped[str] = mapped_column(String(200), default="")
    rule_logic: Mapped[str] = mapped_column(Text, default="")
    ml_urgency: Mapped[str] = mapped_column(String(16), default="")
    ml_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    narrative: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    first_aid: Mapped[str] = mapped_column(Text, default="")
    medicine_info: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), index=True)
    # Server-generated path only. Never taken from a client.
    file_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LabResult(Base):
    """A lab value the user has reviewed and confirmed. Uploaded files are never stored."""

    __tablename__ = "lab_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    test_name: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(String(60))
    unit: Mapped[str] = mapped_column(String(40), default="")
    reference_range: Mapped[str] = mapped_column(String(80), default="")
    recorded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------------------
# Missing-data completion engine. Every row is patient-owned (user_id) and queried with that user's id.
# A completed value is never stored without its source, source date, method and approval.
# ---------------------------------------------------------------------------


class ConfirmedInput(Base):
    """A model input the patient confirmed in a completed prediction run. The only retrieval source for model fields."""

    __tablename__ = "confirmed_inputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    model_key: Mapped[str] = mapped_column(String(40), index=True)
    field_name: Mapped[str] = mapped_column(String(160))
    value: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(24))  # patient_entered | retrieved | derived | edited | manual
    source_date: Mapped[date] = mapped_column(Date)  # date the underlying information was recorded
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MissingDataReport(Base):
    __tablename__ = "missing_data_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    model_key: Mapped[str] = mapped_column(String(40))
    input_json: Mapped[str] = mapped_column(Text)  # only what the patient entered
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | predicted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class MissingFieldRecord(Base):
    """One row per model field in a report: what is missing, and how it was resolved."""

    __tablename__ = "missing_field_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("missing_data_reports.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(160))
    # patient_entered | missing | invalid | completed | unknown
    status: Mapped[str] = mapped_column(String(24))
    detail: Mapped[str] = mapped_column(Text, default="")
    final_value: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProposedCompletion(Base):
    __tablename__ = "proposed_completions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("missing_data_reports.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(16))  # retrieved | derived | inferred
    proposed_value: Mapped[str] = mapped_column(String(160))
    source_date: Mapped[date] = mapped_column(Date)
    age_days: Mapped[int] = mapped_column(default=0)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[str] = mapped_column(String(8))  # high | medium | low
    requires_confirmation: Mapped[bool] = mapped_column(default=True)
    # pending | accepted | rejected | edited | superseded | too_old
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CompletionSource(Base):
    """Where a proposed value came from. Kept separate from the proposal so one source can back many proposals."""

    __tablename__ = "completion_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposed_completions.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))  # confirmed_input
    source_record_id: Mapped[str] = mapped_column(String(36))
    source_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(300), default="")


class PatientApproval(Base):
    __tablename__ = "patient_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("missing_data_reports.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(16))  # accept | reject | edit | manual | unknown
    proposal_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    final_value: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CompletionHistory(Base):
    """Provenance: one row per completed or refused field. Never edited after it is written."""

    __tablename__ = "completion_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_id: Mapped[str] = mapped_column(ForeignKey("missing_data_reports.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(160))
    original_value: Mapped[str | None] = mapped_column(String(160), nullable=True)
    final_value: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source: Mapped[str] = mapped_column(String(64))  # e.g. confirmed_input, patient
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_method: Mapped[str] = mapped_column(String(40))  # accepted_retrieved, edited_proposal, manual_entry, ...
    approval_status: Mapped[str] = mapped_column(String(16))  # approved | rejected | unknown
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AssessmentMissingReport(Base):
    """One per triage assessment: which answers were missing, the proposals offered, and where each value came from.

    The table is new, so it is created by create_all without a migration. Assessment itself is unchanged.
    """

    __tablename__ = "assessment_missing_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), unique=True, index=True)
    missing_json: Mapped[str] = mapped_column(Text, default="[]")     # field names that had no answer
    proposals_json: Mapped[str] = mapped_column(Text, default="[]")   # suggestions shown to the patient
    provenance_json: Mapped[str] = mapped_column(Text, default="{}")  # field -> {source, source_date, ...}
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
