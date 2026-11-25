"""Trains one model per disease from the processed datasets and writes models/<key>/ artefacts.

Protocol (the same for every model):
  1. Stratified 75/25 train/test split, fixed seed. The test set is never used for choosing models.
  2. Candidate models (logistic regression, random forest, XGBoost) are compared by stratified
     cross-validation ROC AUC on the training split only.
  3. The winning model is refit on the training split and scored once on the test set.
  4. 95% confidence intervals come from 1,000 bootstrap resamples of the test set.
Outputs: models/<key>/model.joblib, metrics.json, feature_spec.json. Model cards are written by
ml/write_model_cards.py from these files.

Run from the project root:   python ml/train_models.py [model_key ...]
"""
import json
import os
import sys
import time
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, brier_score_loss, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score, average_precision_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import MODELS  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
MODELS_DIR = os.path.join(ROOT, "models")
SEED = 42
MAX_CATEGORIES = 25


def load(spec):
    if spec.dataset == "burkina_vector_borne":
        df = pd.read_csv(os.path.join(PROC, "burkina_vector_borne.csv"))
        label_col = "malaria_label" if spec.key == "malaria" else "vector_borne_label"
        feats = [c for c in df.columns if c not in ("malaria_label", "vector_borne_label")]
        return df[feats], df[label_col]
    files = {
        "chittagong_dengue": ("chittagong_dengue.csv", "ns1_label"),
        "brazil_sinan_arboviral": ("brazil_sinan_sample.csv", "label"),
        "typhodx_bd_typhoid": ("typhodx_bd.csv", "label"),
        "srilanka_leptospirosis": ("srilanka_leptospirosis.csv", "label"),
    }
    fname, label_col = files[spec.dataset]
    df = pd.read_csv(os.path.join(PROC, fname))
    return df.drop(columns=[label_col]), df[label_col]


def column_kinds(X: pd.DataFrame):
    """Decide numeric vs categorical per column. Columns over 50% missing are dropped (and reported)."""
    numeric, categorical, dropped = [], [], {}
    for c in X.columns:
        missing = X[c].isna().mean()
        if missing > 0.5 or X[c].dropna().nunique() <= 1:
            dropped[c] = f"{missing:.0%} missing or constant"
            continue
        as_num = pd.to_numeric(X[c], errors="coerce")
        if as_num.notna().sum() >= 0.9 * X[c].notna().sum():
            numeric.append(c)
        else:
            categorical.append(c)
    return numeric, categorical, dropped


def to_frame(X: pd.DataFrame, numeric, categorical):
    out = pd.DataFrame(index=X.index)
    for c in numeric:
        out[c] = pd.to_numeric(X[c], errors="coerce")
    for c in categorical:
        vals = X[c].astype(object)
        out[c] = [np.nan if pd.isna(v) else str(v).strip() for v in vals]
    return out


def make_pipeline(estimator, numeric, categorical):
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), numeric),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False, min_frequency=5))]), categorical),
    ], remainder="drop")
    return Pipeline([("pre", pre), ("clf", estimator)])


def candidates(n_classes: int, n_rows: int):
    big = n_rows > 50_000
    xgb_params = dict(n_estimators=150 if big else 200, max_depth=3, learning_rate=0.05, subsample=0.8,
                      colsample_bytree=0.8, random_state=SEED, n_jobs=2, tree_method="hist")
    if n_classes > 2:
        xgb_params.update(objective="multi:softprob")
    return {
        "logistic_regression": LogisticRegression(max_iter=5000, class_weight="balanced", C=0.5, random_state=SEED),
        "random_forest": RandomForestClassifier(n_estimators=150 if big else 300, min_samples_leaf=3,
                                                class_weight="balanced_subsample", random_state=SEED, n_jobs=2),
        "xgboost": XGBClassifier(**xgb_params),
    }


def cv_score(pipe, X, y, n_classes, folds):
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=SEED)
    scoring = "roc_auc" if n_classes == 2 else "roc_auc_ovr"
    scores = cross_val_score(pipe, X, y, cv=skf, scoring=scoring, n_jobs=1)
    return float(scores.mean()), float(scores.std())


def bootstrap_ci(y_true, y_score, fn, n=1000):
    rng = np.random.default_rng(SEED)
    vals = []
    idx = np.arange(len(y_true))
    for _ in range(n):
        s = rng.choice(idx, size=len(idx), replace=True)
        if len(np.unique(y_true[s])) < 2:
            continue
        vals.append(fn(y_true[s], y_score[s]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def train_one(key: str):
    spec = MODELS[key]
    t0 = time.time()
    X_raw, y_raw = load(spec)
    keep = y_raw.notna()
    X_raw, y_raw = X_raw[keep], y_raw[keep]
    leak_note = None
    if key == "typhoid":
        # Check: how well do the Widal titres alone separate the label? (depth-2 tree, 5-fold CV)
        from sklearn.tree import DecisionTreeClassifier
        widal = [c for c in X_raw.columns if "Widal" in c]
        probe = cross_val_score(DecisionTreeClassifier(max_depth=2, random_state=SEED),
                                X_raw[widal].fillna(0), y_raw, cv=5, scoring="roc_auc").mean()
        leak_note = {"check": "depth-2 decision tree on Widal titres only, 5-fold CV ROC AUC",
                     "value": round(float(probe), 4)}
        print(f"[typhoid] Widal-only probe AUC {probe:.3f}; excluding Widal titres to avoid circular evaluation", flush=True)
        X_raw = X_raw.drop(columns=widal)
    numeric, categorical, dropped = column_kinds(X_raw)
    X = to_frame(X_raw, numeric, categorical)
    le = LabelEncoder().fit(y_raw.astype(str))
    y = le.transform(y_raw.astype(str))
    n_classes = len(le.classes_)
    if spec.task == "binary" and n_classes != 2:
        raise SystemExit(f"{key}: expected 2 classes, got {n_classes}")

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=SEED)
    print(f"[{key}] rows={len(X)} train={len(X_tr)} test={len(X_te)} features={X.shape[1]} "
          f"numeric={len(numeric)} categorical={len(categorical)} dropped={len(dropped)}", flush=True)
    folds = 3 if len(X_tr) > 50_000 else 5

    cv_results, fitted = {}, {}
    for name, est in candidates(n_classes, len(X_tr)).items():
        pipe = make_pipeline(est, numeric, categorical)
        mean, sd = cv_score(pipe, X_tr, y_tr, n_classes, folds)
        cv_results[name] = {"cv_roc_auc_mean": round(mean, 4), "cv_roc_auc_sd": round(sd, 4)}
        print(f"   {name:20s} CV AUC {mean:.3f} ± {sd:.3f}", flush=True)
    best = max(cv_results, key=lambda k: cv_results[k]["cv_roc_auc_mean"])
    final = make_pipeline(candidates(n_classes, len(X_tr))[best], numeric, categorical)
    final.fit(X_tr, y_tr)
    proba = final.predict_proba(X_te)
    pred = proba.argmax(axis=1)

    metrics = {
        "model": key, "selected_algorithm": best, "candidate_cv": cv_results,
        "n_rows": int(len(X)), "n_train": int(len(X_tr)), "n_test": int(len(X_te)),
        "class_counts_all": {str(c): int(n) for c, n in zip(le.classes_, np.bincount(y))},
        "class_counts_test": {str(c): int(n) for c, n in zip(le.classes_, np.bincount(y_te, minlength=n_classes))},
        "classes": [str(c) for c in le.classes_], "task": spec.task,
        "features_used": int(X.shape[1]), "numeric_features": numeric, "categorical_features": categorical,
        "dropped_features": dropped, "cv_folds": folds, "seed": SEED,
        "versions": {"scikit_learn": sklearn.__version__, "xgboost": xgboost.__version__},
        "train_seconds": round(time.time() - t0, 1),
    }
    if n_classes == 2:
        s = proba[:, 1]
        auc = roc_auc_score(y_te, s)
        lo, hi = bootstrap_ci(y_te, s, roc_auc_score)
        tn, fp, fn, tp = confusion_matrix(y_te, pred, labels=[0, 1]).ravel()
        metrics.update({
            "roc_auc": round(auc, 4), "roc_auc_95ci": [round(lo, 4), round(hi, 4)],
            "pr_auc": round(average_precision_score(y_te, s), 4),
            "accuracy": round(accuracy_score(y_te, pred), 4),
            "balanced_accuracy": round(balanced_accuracy_score(y_te, pred), 4),
            "sensitivity": round(recall_score(y_te, pred, zero_division=0), 4),
            "specificity": round(tn / (tn + fp) if (tn + fp) else float("nan"), 4),
            "ppv": round(precision_score(y_te, pred, zero_division=0), 4),
            "npv": round(tn / (tn + fn) if (tn + fn) else float("nan"), 4),
            "f1": round(f1_score(y_te, pred, zero_division=0), 4),
            "brier": round(brier_score_loss(y_te, s), 4),
            "confusion_matrix_threshold_0.5": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "decision_threshold": 0.5,
            "positive_class": str(le.classes_[1]),
        })
        minority = min(int((y_te == 0).sum()), int((y_te == 1).sum()))
        negatives_all = int((y == 0).sum())
    else:
        onehot = np.eye(n_classes)[y_te]
        lo, hi = bootstrap_ci(y_te, proba, lambda yt, ps: roc_auc_score(np.eye(n_classes)[yt], ps, average="macro", multi_class="ovr"))
        per_class = {}
        for i, c in enumerate(le.classes_):
            per_class[str(c)] = {
                "recall": round(recall_score(y_te == i, pred == i, zero_division=0), 4),
                "precision": round(precision_score(y_te == i, pred == i, zero_division=0), 4),
                "roc_auc_ovr": round(roc_auc_score(onehot[:, i], proba[:, i]), 4),
            }
        metrics.update({
            "roc_auc_macro_ovr": round(roc_auc_score(onehot, proba, average="macro", multi_class="ovr"), 4),
            "roc_auc_macro_95ci": [round(lo, 4), round(hi, 4)],
            "accuracy": round(accuracy_score(y_te, pred), 4),
            "balanced_accuracy": round(balanced_accuracy_score(y_te, pred), 4),
            "f1_macro": round(f1_score(y_te, pred, average="macro", zero_division=0), 4),
            "per_class": per_class,
            "confusion_matrix": confusion_matrix(y_te, pred).tolist(),
            "confusion_matrix_labels": [str(c) for c in le.classes_],
        })
        minority = int(min(np.bincount(y_te)))
        negatives_all = int(min(np.bincount(y)))

    # Status: small or unbalanced test sets are flagged, not hidden.
    if negatives_all < 30 or minority < 10:
        status = "limited"
        status_reason = (f"Only {negatives_all} examples in the smallest class overall and {minority} in the test set. "
                         "Metrics are unstable; do not use for decisions.")
    elif metrics["roc_auc_95ci" if n_classes == 2 else "roc_auc_macro_95ci"][0] <= 0.5:
        status = "limited"
        status_reason = ("The 95% CI for ROC AUC includes 0.5 (chance). The model shows no reliable "
                         "discrimination on this data and must not be used for decisions.")
    else:
        status = "research"
        status_reason = "Trained and evaluated on a public dataset. Not clinically validated."
    metrics.update({"status": status, "status_reason": status_reason})
    if leak_note:
        metrics["label_definition_check"] = leak_note
        metrics["dropped_features"].update({c: "excluded: label appears determined by these titres (see label_definition_check)" for c in widal})

    # Feature specification for the UI and API validation (values from the training split only).
    feat_spec = []
    for c in X.columns:
        if c in numeric:
            col = X_tr[c].dropna()
            vals = set(col.unique())
            kind = "binary" if vals <= {0.0, 1.0} else "numeric"
            entry = {"name": c, "type": kind, "default": float(col.median()) if len(col) else 0.0}
            if kind == "numeric":
                entry.update({"min": float(col.min()), "max": float(col.max())})
            feat_spec.append(entry)
        else:
            opts = X_tr[c].dropna().astype(str).value_counts().head(MAX_CATEGORIES).index.tolist()
            default = X_tr[c].dropna().astype(str).mode().iloc[0] if X_tr[c].notna().any() else opts[0]
            feat_spec.append({"name": c, "type": "categorical", "options": opts, "default": default})

    out_dir = os.path.join(MODELS_DIR, key)
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump({"pipeline": final, "feature_names": list(X.columns), "classes": [str(c) for c in le.classes_],
                 "numeric": numeric, "categorical": categorical, "task": spec.task}, os.path.join(out_dir, "model.joblib"))
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    with open(os.path.join(out_dir, "feature_spec.json"), "w", encoding="utf-8") as f:
        json.dump({"model": key, "task": spec.task, "classes": metrics["classes"], "features": feat_spec}, f, indent=2)
    headline = (f"AUC {metrics['roc_auc']:.3f} [{metrics['roc_auc_95ci'][0]:.3f}-{metrics['roc_auc_95ci'][1]:.3f}]"
                if n_classes == 2 else f"macro AUC {metrics['roc_auc_macro_ovr']:.3f}")
    print(f"[{key}] selected={best} test {headline} status={status} ({time.time() - t0:.0f}s)", flush=True)
    return metrics


if __name__ == "__main__":
    keys = sys.argv[1:] or list(MODELS)
    for k in keys:
        train_one(k)
