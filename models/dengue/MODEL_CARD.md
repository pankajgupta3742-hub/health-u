# Model card: Dengue (NS1-antigen positive)

**Model key:** `dengue` · **Task:** binary · **Trained:** 2026-11-23
**Status: RESEARCH PROTOTYPE**

Trained and evaluated on a public dataset. Not clinically validated.

> This model is trained on public retrospective data. It has **not** been clinically validated, prospectively
> tested, or approved for diagnosis or treatment decisions. The language model in Health-U never sets urgency or
> produces a diagnosis; urgency comes only from the rule engine.

## Intended use
Estimate dengue NS1 positivity for febrile patients from age, vitals and symptoms, to support NS1 test ordering.

**Not intended for:** diagnosis, treatment, triage on its own, use outside the populations described under
"Data", or any setting where a wrong output could delay care.

## Data
- **Dataset:** Early detection of dengue, Chittagong and Cox's Bazar (Bangladesh)
- **Source:** GitHub TurhanSakib/Machine-Learning-based-Early-detection-of-dengue-Case-study-Chittagong
- **Licence:** MIT (repository licence). The README says the raw patient data is 'not included' and asks researchers to contact the authors, yet the CSV is present in the repository. Confirm permission with the authors before any public release.
- **Citation:** Sakib T. et al., BSc thesis, IIUC, Bangladesh. 308 patients from public and private hospitals.
- **Raw size:** 308 records, 20 columns, normalised 0–2 scale values
- **Rows used:** 308 (train 231, test 77; stratified 75/25 split, seed 42)
- **Class counts (all rows):** {'0': 103, '1': 205}
- **Class counts (test):** {'0': 26, '1': 51}
- **Processed file:** `data/processed/chittagong_dengue.csv`
- **Manifest:** `data/dataset_manifest.json`

**Label:** NS1 antigen result positive (1) or negative (0), as recorded in the dataset.

**Input requirements:** Clinical and exposure inputs only; no laboratory result is required.

### Features used (16)
- Numeric: 16; categorical: 0
- Excluded or dropped columns, with reasons:
- `LLBplatelet`: platelet count is a laboratory result, not available at first contact
- `IgG`: serology result (laboratory), part of the diagnostic workup
- `IgM`: serology result (laboratory), part of the diagnostic workup

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
| logistic_regression | 0.969 ± 0.033 |
| random_forest **(selected)** | 0.979 ± 0.024 |
| xgboost | 0.972 ± 0.030 |

Selected algorithm: **random_forest**. Versions: scikit-learn 1.6.1, xgboost 3.4.1.

## Results (held-out test set)
| Metric (held-out test set) | Value |
|---|---|
| ROC AUC | 0.983 (95% CI 0.942–1.000) |
| PR AUC | 0.989 |
| Sensitivity (recall, positive class) | 0.980 |
| Specificity | 0.962 |
| PPV | 0.980 |
| NPV | 0.962 |
| Balanced accuracy | 0.971 |
| F1 | 0.980 |
| Brier score (lower is better) | 0.032 |

At a 0.5 threshold on the test set: TN 25, FP 1, FN 1, TP 50. Positive class: 1.

These are estimates on one public dataset and one split. They are not a measure of how the model would perform
in a clinic, in another country, or on another population. Confidence intervals are wide when a class is small.

## Limitations
- The label is itself a laboratory test (NS1). The model predicts NS1 positivity, not clinical dengue.
- IgG, IgM and platelet counts are laboratory results and are excluded.
- 308 patients from two cities in Bangladesh. Not validated elsewhere.
- Licence/provenance needs confirmation (see dataset notes).
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
