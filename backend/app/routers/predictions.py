"""Disease model catalog, model cards, and predictions. Sign-in required for predictions and cards."""
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.deps import get_current_user
from app.models import User
from app.services import predictions as svc

router = APIRouter(prefix="/api/v1", tags=["models"])


class PredictInput(BaseModel):
    # Free-form per-model fields, validated against the model's feature spec.
    features: dict = Field(default_factory=dict, max_length=200)
    # Fields the patient explicitly marked unknown. Any other missing field makes the result incomplete.
    unknown: list[str] = Field(default_factory=list, max_length=200)


@router.get("/models")
def list_models(user: User = Depends(get_current_user)):
    """Every disease model with its status, headline metric, and the reason for that status."""
    return {"models": svc.catalog()}


@router.get("/models/{key}")
def model_detail(key: str, user: User = Depends(get_current_user)):
    if key not in svc.MODEL_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown model")
    return svc.describe(key)


@router.get("/models/{key}/card", response_class=PlainTextResponse)
def model_card(key: str, user: User = Depends(get_current_user)):
    if key not in svc.MODEL_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown model")
    path = os.path.join(svc.MODELS_DIR, key, "MODEL_CARD.md")
    if not os.path.exists(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model card not found")
    with open(path, encoding="utf-8") as f:
        return f.read()


@router.post("/predictions/{key}")
def predict(key: str, body: PredictInput, user: User = Depends(get_current_user)):
    if key not in svc.MODEL_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown model")
    try:
        result = svc.predict(key, body.features, body.unknown)
    except svc.PredictionError as e:
        raise HTTPException(422, str(e))
    # Direct calls record no review or provenance. The app uses the missing-data review, which does.
    result["recorded"] = False
    result["note"] = ("Values were sent directly. No review or provenance was recorded. "
                      "Use the missing-data review for a recorded estimate.")
    return result
