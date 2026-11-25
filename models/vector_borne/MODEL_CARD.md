# Model card: Vector-borne fever (malaria, dengue, typhoid or yellow fever)

**Model key:** `vector_borne` · **Task:** binary · **Trained:** 2026-11-23
**Status: LIMITED. Do not use for decisions.**

Only 14 examples in the smallest class overall and 4 in the test set. Metrics are unstable; do not use for decisions.

> This model is trained on public retrospective data. It has **not** been clinically validated, prospectively
> tested, or approved for diagnosis or treatment decisions. The language model in Health-U never sets urgency or
> produces a diagnosis; urgency comes only from the rule engine.

## Intended use
Flag febrile patients whose features resemble a vector-borne infection, to prioritise diagnostic testing.

**Not intended for:** diagnosis, treatment, triage on its own, use outside the populations described under
"Data", or any setting where a wrong output could delay care.

## Data
- **Dataset:** Clinical dataset on malaria, dengue, yellow fever and other vector-borne diseases (Burkina Faso)
- **Source:** GitHub zombiboy/Tabular-dataset-for-AI-based-vector-borne-disease-prediction
- **Licence:** CC BY 4.0 (stated in the dataset README)
- **Citation:** Nazi Boni University, Burkina Faso (AI4D Africa). 300 consultations from the DO and DAFRA districts, Sept–Nov 2024.
- **Raw size:** 300 records, 109 columns, semicolon-separated, French/English headers
- **Rows used:** 299 (train 224, test 75; stratified 75/25 split, seed 42)
- **Class counts (all rows):** {'0': 14, '1': 285}
- **Class counts (test):** {'0': 4, '1': 71}
- **Processed file:** `data/processed/burkina_vector_borne.csv`
- **Manifest:** `data/dataset_manifest.json`

**Label:** Any of the four vector-borne diagnoses flagged in the clinical record (malaria, dengue, typhoid, yellow fever).

**Input requirements:** Clinical and exposure inputs only; no laboratory result is required.

### Features used (67)
- Numeric: 5; categorical: 62
- Excluded or dropped columns, with reasons:
- `Centre de santé`: recruitment site (not a clinical feature; would leak site-level prevalence)
- `Test TDR`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Goutte épaisse`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Hémoconcentration`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Pâleur cutanéo muqueuse ou Anémie (Mucosal skin pallor or Anemia)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Hypoglycémie (Hypoglycemia)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Hematocrite (Hematrocrit)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Transaminases (Transaminases)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Thrombocytopénie(Thrombocytopenia)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Lymphocytopénie (Lymphocytopenia)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Lymphocytes`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Neutropénie (Neutropenia)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Nombre de globules blancs (cellules/ML) / White blood cell count / WBC count (cells/ML)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Numération plaquettaire Platelet count`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Neutrophiles / Neutrophils`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `CRP>50 /CRP 10-50`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Créatinine élevée / Elevated Creatinine`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `ALAT / ASAT élevés. / Elevated ALAT / Elevated ASAT`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Pneumonie (Pneumonia)`: diagnosis-like comorbidity; kept out to keep the feature set clinical
- `Dengue (Dengua)`: laboratory or diagnostic test result (not available at triage, or defines the diagnosis)
- `Maladies diagnostiquées`: diagnosis label or diagnosis text (leakage)
- `Maladies diagnostiquées/Paludisme (Malaria)`: diagnosis label or diagnosis text (leakage)
- `Maladies diagnostiquées/Dengue`: diagnosis label or diagnosis text (leakage)
- `Maladies diagnostiquées/Chikunguya`: diagnosis label or diagnosis text (leakage)
- `Maladies diagnostiquées/Fièvre jaune (yellow fever)`: diagnosis label or diagnosis text (leakage)
- `Maladies diagnostiquées/Fièvre Typhoïde (Thyphoid fever)`: diagnosis label or diagnosis text (leakage)
- `Maladies diagnostiquées/Zika`: diagnosis label or diagnosis text (leakage)
- `Maladies diagnostiquées/Autres maladies diagnostiqué (Others diseases)`: diagnosis label or diagnosis text (leakage)
- `Maladies diagnostiquées/Option 8`: diagnosis label or diagnosis text (leakage)
- `Autres maladies présentées par le patient`: diagnosis label or diagnosis text (leakage)
- `_uuid`: record identifier
- `Mua circumference` (model-level): 92% missing or constant
- `Inflammation de conjonctivite` (model-level): 0% missing or constant
- `Facial flushing` (model-level): 0% missing or constant
- `Profuse sweating` (model-level): 0% missing or constant
- `mean mmHg ± SD` (model-level): 57% missing or constant
- `median secs IQR` (model-level): 70% missing or constant
- `Maladie rhumatismale` (model-level): 1% missing or constant
- `Maladie auto immune` (model-level): 1% missing or constant
- `Allergies` (model-level): 1% missing or constant
- `Cancer` (model-level): 1% missing or constant
- `Leucopenia` (model-level): 0% missing or constant

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
| logistic_regression | 0.544 ± 0.234 |
| random_forest **(selected)** | 0.767 ± 0.132 |
| xgboost | 0.608 ± 0.189 |

Selected algorithm: **random_forest**. Versions: scikit-learn 1.6.1, xgboost 3.4.1.

## Results (held-out test set)
| Metric (held-out test set) | Value |
|---|---|
| ROC AUC | 0.884 (95% CI 0.758–0.986) |
| PR AUC | 0.993 |
| Sensitivity (recall, positive class) | 1.000 |
| Specificity | 0.000 |
| PPV | 0.947 |
| NPV | nan |
| Balanced accuracy | 0.500 |
| F1 | 0.973 |
| Brier score (lower is better) | 0.048 |

At a 0.5 threshold on the test set: TN 0, FP 4, FN 0, TP 71. Positive class: 1.

These are estimates on one public dataset and one split. They are not a measure of how the model would perform
in a clinic, in another country, or on another population. Confidence intervals are wide when a class is small.

## Limitations
- Small sample (300). Confidence intervals are wide.
- Label groups four different diseases; it does not say which one.
- Diagnostic test results and the free-text diagnosis column are excluded to prevent leakage.
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
