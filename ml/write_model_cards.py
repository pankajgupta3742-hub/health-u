"""Writes models/<key>/MODEL_CARD.md from the saved metrics, specs and dataset manifest.

Every number in a card comes from models/<key>/metrics.json or data/dataset_manifest.json. Nothing
is typed in by hand. Run after train_models.py:  python ml/write_model_cards.py
"""
import json
import os
import sys
from dataclasses import asdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import DATASETS, MODELS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = json.load(open(os.path.join(ROOT, "data", "dataset_manifest.json"), encoding="utf-8"))


def fmt(v, digits=3):
    return "n/a" if v is None else (f"{v:.{digits}f}" if isinstance(v, float) else str(v))


def results_block(m):
    lines = ["| Metric (held-out test set) | Value |", "|---|---|"]
    if "roc_auc" in m:
        lines += [
            f"| ROC AUC | {fmt(m['roc_auc'])} (95% CI {m['roc_auc_95ci'][0]:.3f}–{m['roc_auc_95ci'][1]:.3f}) |",
            f"| PR AUC | {fmt(m['pr_auc'])} |",
            f"| Sensitivity (recall, positive class) | {fmt(m['sensitivity'])} |",
            f"| Specificity | {fmt(m['specificity'])} |",
            f"| PPV | {fmt(m['ppv'])} |",
            f"| NPV | {fmt(m['npv'])} |",
            f"| Balanced accuracy | {fmt(m['balanced_accuracy'])} |",
            f"| F1 | {fmt(m['f1'])} |",
            f"| Brier score (lower is better) | {fmt(m['brier'])} |",
        ]
        cm = m["confusion_matrix_threshold_0.5"]
        cm_text = (f"At a 0.5 threshold on the test set: TN {cm['tn']}, FP {cm['fp']}, FN {cm['fn']}, TP {cm['tp']}. "
                   f"Positive class: {m['positive_class']}.")
    else:
        lines += [
            f"| Macro ROC AUC (one-vs-rest) | {fmt(m['roc_auc_macro_ovr'])} (95% CI {m['roc_auc_macro_95ci'][0]:.3f}–{m['roc_auc_macro_95ci'][1]:.3f}) |",
            f"| Accuracy | {fmt(m['accuracy'])} |",
            f"| Balanced accuracy | {fmt(m['balanced_accuracy'])} |",
            f"| Macro F1 | {fmt(m['f1_macro'])} |",
        ]
        per = "; ".join(f"{c}: recall {v['recall']:.3f}, precision {v['precision']:.3f}, AUC {v['roc_auc_ovr']:.3f}"
                         for c, v in m["per_class"].items())
        cm_text = f"Per class (test set): {per}. Confusion matrix rows = true class, columns = predicted: {m['confusion_matrix']}."
    return "\n".join(lines) + "\n\n" + cm_text


def cv_block(m):
    rows = ["| Candidate | CV ROC AUC (mean ± sd, training split only) |", "|---|---|"]
    for name, v in m["candidate_cv"].items():
        mark = " **(selected)**" if name == m["selected_algorithm"] else ""
        rows.append(f"| {name}{mark} | {v['cv_roc_auc_mean']:.3f} ± {v['cv_roc_auc_sd']:.3f} |")
    return "\n".join(rows)


def excluded_block(m, ds_key):
    ds = MANIFEST["datasets"].get(ds_key, {})
    ex = ds.get("excluded_columns", {})
    dropped = m.get("dropped_features", {})
    out = []
    for k, why in ex.items():
        out.append(f"- `{k.strip()}`: {why}")
    for k, why in dropped.items():
        out.append(f"- `{k.strip()}` (model-level): {why}")
    return "\n".join(out) if out else "- none"


def write(key):
    spec = MODELS[key]
    ds = DATASETS[spec.dataset]
    d = asdict(spec)
    d_ds = asdict(ds)
    mdir = os.path.join(ROOT, "models", key)
    m = json.load(open(os.path.join(mdir, "metrics.json"), encoding="utf-8"))
    ds_entry = MANIFEST["datasets"].get(spec.dataset, {})
    status_banner = {
        "research": "Status: RESEARCH PROTOTYPE",
        "limited": "Status: LIMITED. Do not use for decisions.",
    }[m["status"]]

    card = f"""# Model card: {spec.title}

**Model key:** `{key}` · **Task:** {spec.task} · **Trained:** {date.today().isoformat()}
**{status_banner}**

{m['status_reason']}

> This model is trained on public retrospective data. It has **not** been clinically validated, prospectively
> tested, or approved for diagnosis or treatment decisions. The language model in Health-U never sets urgency or
> produces a diagnosis; urgency comes only from the rule engine.

## Intended use
{spec.intended_use}

**Not intended for:** diagnosis, treatment, triage on its own, use outside the populations described under
"Data", or any setting where a wrong output could delay care.

## Data
- **Dataset:** {d_ds['title']}
- **Source:** {d_ds['source_name']}
- **Licence:** {d_ds['licence']}
- **Citation:** {d_ds['citation']}
- **Raw size:** {d_ds['n_raw_note']}
- **Rows used:** {m['n_rows']} (train {m['n_train']}, test {m['n_test']}; stratified 75/25 split, seed {m['seed']})
- **Class counts (all rows):** {m['class_counts_all']}
- **Class counts (test):** {m['class_counts_test']}
- **Processed file:** `{ds_entry.get('processed_file', 'see manifest')}`
- **Manifest:** `data/dataset_manifest.json`

**Label:** {spec.label_description}

**Input requirements:** {'Includes laboratory inputs (for example Widal or Rickettsia tests), which must be available at the point of use.' if spec.requires_lab_input else 'Clinical and exposure inputs only; no laboratory result is required.'}

### Features used ({m['features_used']})
- Numeric: {len(m['numeric_features'])}; categorical: {len(m['categorical_features'])}
- Excluded or dropped columns, with reasons:
{excluded_block(m, spec.dataset)}

## Method
1. Rows with a missing label are removed. Columns over 50% missing or constant are dropped.
2. A stratified 75/25 train/test split, fixed seed {m['seed']}. The test set is not used for model choice.
3. Logistic regression, random forest, and XGBoost are compared by {m['cv_folds']}-fold stratified CV ROC AUC on the
   training split only. The best is refit on the full training split.
4. The test set is scored once. 95% CIs come from 1,000 bootstrap resamples of the test set.
5. Missing values are imputed (median for numeric, most-frequent for categorical). Categorical values are one-hot encoded.
   Unseen categories at prediction time are ignored.

{cv_block(m)}

Selected algorithm: **{m['selected_algorithm']}**. Versions: scikit-learn {m['versions']['scikit_learn']}, xgboost {m['versions']['xgboost']}.

## Results (held-out test set)
{results_block(m)}

These are estimates on one public dataset and one split. They are not a measure of how the model would perform
in a clinic, in another country, or on another population. Confidence intervals are wide when a class is small.

## Limitations
"""
    for lim in spec.limitations:
        card += f"- {lim}\n"
    card += """- The model reflects the populations, sites, and time periods in its source data. Distribution shift is expected.
- Predictions are probabilities of a label in the source dataset. They are not diagnoses.
- No fairness audit has been run. Sex, age, and site effects have not been tested for bias.
- The source dataset licence or permission must be confirmed before any public redistribution (see the dataset entry).

## Files
- `model.joblib`: fitted pipeline (preprocessing and estimator), feature names, and class order
- `feature_spec.json`: feature names, types, and defaults for the API and UI
- `metrics.json`: every number in this card
- `MODEL_CARD.md`: this file

## Reproduce
```
python ml/download_data.py
python ml/prepare_datasets.py
python ml/train_models.py {key}
python ml/write_model_cards.py
```
"""
    with open(os.path.join(mdir, "MODEL_CARD.md"), "w", encoding="utf-8") as f:
        f.write(card)
    print("wrote", os.path.join("models", key, "MODEL_CARD.md"))


if __name__ == "__main__":
    for k in sys.argv[1:] or list(MODELS):
        write(k)
