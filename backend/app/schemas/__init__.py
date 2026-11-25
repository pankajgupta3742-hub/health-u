"""Request and response models. Categorical inputs are closed sets, so unknown values are rejected with 422."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PrimarySymptom = Literal[
    "chest_pain", "fever", "vomiting", "headache", "shortness_of_breath",
    "abdominal_pain", "sore_throat", "cough", "dizziness",
]
Duration = Literal["short", "medium", "long"]
Frequency = Literal["rare", "frequent", "persistent"]
AgeGroup = Literal["child", "adult", "elderly"]
Breathlessness = Literal["none", "mild", "severe"]
Vomiting = Literal["none", "mild", "severe"]
Fever = Literal["none", "mild", "high"]
PainType = Literal["sharp", "dull", "none"]


class SymptomInput(BaseModel):
    """Triage input. A field left out (or null) is MISSING: the assessment is then incomplete and nothing is filled in.

    accepted maps a field to a suggestion id the patient accepted from their earlier assessments.
    The server checks each id against the patient's own current suggestions before using its value.
    """
    model_config = ConfigDict(extra="forbid")

    primary_symptom: Optional[PrimarySymptom] = None
    severity_score: Optional[int] = Field(default=None, ge=1, le=10)
    duration_category: Optional[Duration] = None
    frequency: Optional[Frequency] = None
    age_group: Optional[AgeGroup] = None
    breathlessness_level: Optional[Breathlessness] = None
    vomiting_severity: Optional[Vomiting] = None
    fever_level: Optional[Fever] = None
    pain_type: Optional[PainType] = None
    accepted: dict[str, str] = Field(default_factory=dict, max_length=9)


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    name: str


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChatTurn(BaseModel):
    role: Literal["user", "ai"]
    content: str = Field(max_length=2000)


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


class TermInput(BaseModel):
    term: str = Field(min_length=1, max_length=100)


class MedicineInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class AssessmentOut(BaseModel):
    id: str
    created_at: datetime
    input: dict
    final_urgency: str
    status: str
    missing_data: Optional[dict] = None  # this assessment's own missing-data report
    rule_output: dict
    ml_output: dict
    ai_explanation: dict


class ReportOut(BaseModel):
    id: str
    assessment_id: str
    created_at: datetime


class LabCandidate(BaseModel):
    test_name: str
    value: str
    unit: str = ""
    reference_range: str = ""
    source_line: str = ""


class ExtractOut(BaseModel):
    filename: str
    pages_read: int
    candidates: list[LabCandidate]
    note: str


class LabResultIn(BaseModel):
    test_name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=60)
    unit: str = Field(default="", max_length=40)
    reference_range: str = Field(default="", max_length=80)
    recorded_on: Optional[date] = None

    @field_validator("test_name", "value")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class LabResultsIn(BaseModel):
    results: list[LabResultIn] = Field(min_length=1, max_length=100)


class LabResultOut(BaseModel):
    id: str
    test_name: str
    value: str
    unit: str
    reference_range: str
    recorded_on: Optional[date]
    created_at: datetime
