"""Serves the trained disease models from models/<key>/.

- Inputs are validated against feature_spec.json: unknown fields are rejected, numbers must be in the
  range seen in training, and categories must be one of the training options.
- Nothing is filled in silently. A field that is neither provided nor explicitly marked unknown makes the
  result "incomplete": no probabilities are returned. Fields the patient marks unknown are passed as missing
  to the model's own preprocessing pipeline (its trained imputers), and the response says so.
- Output is a probability per class. It is never an urgency level and never a diagnosis.
- The model's status (research or limited) is returned with every prediction.
"""
import json
import math
import os
from functools import lru_cache

import joblib
import pandas as pd

from app.config import BACKEND_DIR

MODELS_DIR = os.path.abspath(os.path.join(BACKEND_DIR, "..", "models"))
MODEL_KEYS = ["malaria", "vector_borne", "dengue", "dengue_chikungunya", "typhoid", "leptospirosis"]
DISCLAIMER = ("Research prototype trained on public retrospective data. Not clinically validated. "
              "This is not a diagnosis. Discuss results with a qualified clinician.")


# A result needs at least this share of the model's fields answered by the patient (not marked unknown).
MIN_ANSWERED_FRACTION = 0.5


class PredictionError(ValueError):
    """Bad input for a model. The router turns this into HTTP 422."""


def _read(key: str, name: str):
    path = os.path.join(MODELS_DIR, key, name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_bundle(key: str):
    if key not in MODEL_KEYS:
        raise KeyError(key)
    return joblib.load(os.path.join(MODELS_DIR, key, "model.joblib"))


@lru_cache(maxsize=None)
def load_spec(key: str) -> dict:
    return _read(key, "feature_spec.json")


@lru_cache(maxsize=None)
def load_metrics(key: str) -> dict:
    return _read(key, "metrics.json")


def catalog() -> list[dict]:
    out = []
    for key in MODEL_KEYS:
        m = load_metrics(key)
        spec = load_spec(key)
        headline = (
            {"metric": "roc_auc", "value": m["roc_auc"], "ci95": m["roc_auc_95ci"]}
            if "roc_auc" in m else
            {"metric": "roc_auc_macro_ovr", "value": m["roc_auc_macro_ovr"], "ci95": m["roc_auc_macro_95ci"]}
        )
        out.append({
            "key": key, "task": m["task"], "classes": m["classes"], "status": m["status"],
            "status_reason": m["status_reason"], "headline_metric": headline,
            "n_rows": m["n_rows"], "feature_count": len(spec["features"]),
            "card_url": f"/api/v1/models/{key}/card",
        })
    return _json_safe(out)


def _json_safe(value):
    """NaN and infinity are not valid JSON. A value the training run could not compute is reported as null."""
    if isinstance(value, float):
        return None if (math.isnan(value) or math.isinf(value)) else value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def describe(key: str) -> dict:
    m = load_metrics(key)
    spec = load_spec(key)
    return _json_safe({"key": key, "metrics": m, "features": spec["features"], "classes": spec["classes"],
                       "disclaimer": DISCLAIMER})


def _coerce(feature: dict, value):
    name = feature["name"]
    kind = feature["type"]
    if value is None:
        return None
    if kind == "categorical":
        text = str(value).strip()
        if text not in feature["options"]:
            raise PredictionError(f"'{name}' must be one of: {', '.join(feature['options'][:12])}")
        return text
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise PredictionError(f"'{name}' must be a number")
    if math.isnan(number) or math.isinf(number):
        raise PredictionError(f"'{name}' must be a finite number")
    if kind == "binary" and number not in (0.0, 1.0):
        raise PredictionError(f"'{name}' must be 0 or 1")
    if kind == "numeric":
        lo, hi = feature.get("min"), feature.get("max")
        if lo is not None and number < lo or hi is not None and number > hi:
            raise PredictionError(f"'{name}' must be between {lo} and {hi} (the range used in training)")
    return number


def check_values(key: str, values: dict, unknown=()) -> tuple[dict, list[str], list[str]]:
    """Validate patient values against the model's spec.

    Returns (row, unresolved, errors). `row` has every feature: a coerced value, None (explicitly unknown),
    or absent. `unresolved` lists features that are neither provided nor marked unknown. Nothing is defaulted.
    """
    spec = load_spec(key)
    by_name = {f["name"]: f for f in spec["features"]}
    unknown = set(unknown)
    errors = []
    bad = [k for k in list(values) + list(unknown) if k not in by_name]
    if bad:
        errors.append(f"Unknown fields: {', '.join(sorted(set(bad))[:10])}")
    overlap = sorted(n for n in unknown if values.get(n) is not None)
    if overlap:
        errors.append(f"Fields cannot be both provided and unknown: {', '.join(overlap[:10])}")
    row, unresolved = {}, []
    for f in spec["features"]:
        name = f["name"]
        if name in unknown:
            row[name] = None
        elif values.get(name) is not None:
            try:
                row[name] = _coerce(f, values[name])
            except PredictionError as e:
                errors.append(str(e))
        else:
            unresolved.append(name)
    return row, unresolved, errors


def predict(key: str, features: dict, unknown=()) -> dict:
    spec = load_spec(key)
    bundle = load_bundle(key)
    row, unresolved, errors = check_values(key, features, unknown)
    if errors:
        raise PredictionError("; ".join(errors))
    if unresolved:
        return {
            "model": key, "task": spec["task"], "outcome": "incomplete",
            "unresolved_fields": unresolved,
            "message": "Some information is still missing. No prediction was made.",
            "disclaimer": DISCLAIMER,
        }
    total = len(spec["features"])
    answered = sum(1 for n in row if row[n] is not None)
    if answered < total * MIN_ANSWERED_FRACTION:
        return {
            "model": key, "task": spec["task"], "outcome": "incomplete",
            "unresolved_fields": [],
            "insufficient_answers": True,
            "message": (f"Too few answers for a reliable result ({answered} of {total} provided). "
                        "No prediction was made."),
            "disclaimer": DISCLAIMER,
        }

    unknown_fields = sorted(n for n in unknown)
    X = pd.DataFrame([{name: row.get(name) for name in bundle["feature_names"]}], columns=bundle["feature_names"])
    for c in bundle["numeric"]:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    for c in bundle["categorical"]:
        X[c] = [None if pd.isna(v) else str(v) for v in X[c]]

    proba = bundle["pipeline"].predict_proba(X)[0]
    classes = bundle["classes"]
    probs = {str(c): round(float(p), 4) for c, p in zip(classes, proba)}
    top = max(probs, key=probs.get)
    metrics = load_metrics(key)
    result = {
        "model": key,
        "task": spec["task"],
        "outcome": "complete",
        "probabilities": probs,
        "top_class": top,
        "status": metrics["status"],
        "status_reason": metrics["status_reason"],
        "unknown_fields": unknown_fields,
        "disclaimer": DISCLAIMER,
    }
    if unknown_fields:
        result["notice"] = ("Some answers were marked unknown. The model's own missing-value handling was used "
                            "for them, so treat this result with more caution.")
    if spec["task"] == "binary":
        positive = classes[1]
        result["probability_positive"] = probs[positive]
        result["positive_class"] = positive
        result["decision_threshold"] = metrics.get("decision_threshold", 0.5)
    return result
