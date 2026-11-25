# Model card: Typhoid (clinical features, Widal titres excluded)

**Model key:** `typhoid` · **Task:** binary · **Trained:** 2026-11-23
**Status: LIMITED. Do not use for decisions.**

The 95% CI for ROC AUC includes 0.5 (chance). The model shows no reliable discrimination on this data and must not be used for decisions.

> This model is trained on public retrospective data. It has **not** been clinically validated, prospectively
> tested, or approved for diagnosis or treatment decisions. The language model in Health-U never sets urgency or
> produces a diagnosis; urgency comes only from the rule engine.

## Intended use
Research only: estimate typhoid likelihood from age, sex and suspicion of rickettsial infection. Not a diagnostic tool.

**Not intended for:** diagnosis, treatment, triage on its own, use outside the populations described under
"Data", or any setting where a wrong output could delay care.

## Data
- **Dataset:** TyphoDx-BD: clinically validated typhoid dataset (Bangladesh)
- **Source:** Mendeley Data m9pnvv2vpv
- **Licence:** CC BY 4.0 (stated on Mendeley Data)
- **Citation:** TyphoDx-BD clinical dataset, 1,106 patients, Bangladesh, Oct 2024–Jan 2025 (Mendeley Data m9pnvv2vpv).
- **Raw size:** 1,106 records, 17 columns
- **Rows used:** 540 (train 405, test 135; stratified 75/25 split, seed 42)
- **Class counts (all rows):** {'0': 462, '1': 78}
- **Class counts (test):** {'0': 115, '1': 20}
- **Processed file:** `data/processed/typhodx_bd.csv`
- **Manifest:** `data/dataset_manifest.json`

**Label:** Typhoid column = Positive (1) or Negative (0). 'Minimal' results are dropped as ambiguous.

**Input requirements:** Clinical and exposure inputs only; no laboratory result is required.

### Features used (3)
- Numeric: 2; categorical: 1
- Excluded or dropped columns, with reasons:
- `Name`: encrypted patient token; identifier, never used or stored in processed data
- `Acute_typhoid`: other diagnosis outcome (leakage)
- `Paratyphoid_A`: other diagnosis outcome (leakage)
- `Paratyphoid_B`: other diagnosis outcome (leakage)
- `Widal O (TO) (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)
- `Widal H (TH) (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)
- `Widal AH (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)
- `Widal BH (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)
- `Widal OX2 (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)
- `Widal OXK (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)
- `Widal OX9 (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)
- `Widal A (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)
- `Widal M (log2 titre)` (model-level): excluded: label appears determined by these titres (see label_definition_check)

## Method
1. Rows with a missing label are removed. Columns over 50% missing or constant are dropped.
2. A stratified 75/25 train/test split, fixed seed 42. The test set is not used for model choice.
3. Logistic regression, random forest, and XGBoost are compared by 5-fold stratified CV ROC AUC on the
   training split only. The best is refit on the full training split.
4. The test set is scored once. 95% CIs come from 1,000 bootstrap resamples of the test set.
5. Missing values are imputed (median for numeric, most-frequent for categorical). Categorical values are one-hot encoded.
   Unseen categories at prediction time are ignored.

| Candidate | CV ROC AUC (mean ± sd, training split only) |
|---|---|
| logistic_regression **(selected)** | 0.642 ± 0.057 |
| random_forest | 0.492 ± 0.015 |
| xgboost | 0.571 ± 0.041 |

Selected algorithm: **logistic_regression**. Versions: scikit-learn 1.6.1, xgboost 3.4.1.

## Results (held-out test set)
| Metric (held-out test set) | Value |
|---|---|
| ROC AUC | 0.563 (95% CI 0.421–0.710) |
| PR AUC | 0.260 |
| Sensitivity (recall, positive class) | 0.450 |
| Specificity | 0.617 |
| PPV | 0.170 |
| NPV | 0.866 |
| Balanced accuracy | 0.534 |
| F1 | 0.247 |
| Brier score (lower is better) | 0.231 |

At a 0.5 threshold on the test set: TN 71, FP 44, FN 11, TP 9. Positive class: 1.

These are estimates on one public dataset and one split. They are not a measure of how the model would perform
in a clinic, in another country, or on another population. Confidence intervals are wide when a class is small.

## Limitations
- Widal titres were excluded. Alone, they separate the label almost perfectly (depth-2 tree, CV AUC 1.000), so the label appears to be defined by them and a model using them would be circular.
- Without Widal titres the model has no reliable discrimination (test AUC about 0.56, CI includes 0.5). Do not use it.
- Acute-typhoid and paratyphoid columns are other outcomes and are excluded.
- Patient name (encrypted token) is dropped during preparation.
- The model reflects the populations, sites, and time periods in its source data. Distribution shift is expected.
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
