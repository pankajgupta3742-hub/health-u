"""Request and response models for the missing-data completion engine.

Values are kept as text in the database, so every request value is checked against the model's feature
spec before it is used (see app/services/missing_data_service.py).
"""
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

Action = Literal["accept", "reject", "edit", "manual", "unknown"]
Scalar = Union[str, int, float, bool]


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Only the values the patient actually entered. The engine never adds values to this dict.
    model: str = Field(min_length=1, max_length=40)
    features: dict[str, Optional[Scalar]] = Field(default_factory=dict, max_length=200)


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=120)
    action: Action
    proposal_id: Optional[str] = Field(default=None, max_length=36)
    value: Optional[Scalar] = None


class CorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=120)
    value: Scalar


class DecisionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[DecisionInput] = Field(min_length=1, max_length=200)
