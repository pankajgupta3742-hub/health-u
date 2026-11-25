# Health-U: Research Paper and Project Guide

This guide supports a report or paper. Every number below comes from `models/<key>/metrics.json` and the dataset manifest. Where a result was not measured, this guide says so. The earlier "99.8% accuracy" claim for MedAssist was dropped. It came from a synthetic dataset built to be internally consistent, so it does not show clinical performance.

## 1. Abstract (draft)
Health-U combines a deterministic triage rule engine, a language-model assistant that writes text but never sets urgency, and six disease models trained on public datasets. The disease models are evaluated on held-out test sets with bootstrap 95% confidence intervals. Four models are research prototypes. Three models (malaria, vector-borne, and typhoid) are marked limited because their test performance is unstable or no better than chance. The study does not show clinical validity.

## 2. Architecture
- Triage: validate (rejects contradictory inputs) -> rules (urgency) -> explanation (language model text) -> guard (copies urgency from rules, caps text length). Implemented as a LangGraph workflow.
- Assistant: one Gemini call per turn with a fixed scope and a code-enforced disclaimer.
- Disease models: scikit-learn and XGBoost pipelines served through the API with input validation against the training feature spec.

## 3. Data (public sources)
| Model | Dataset | Rows used | Licence | Notes |
|---|---|---|---|---|
| Malaria, vector-borne | Burkina Faso vector-borne clinical data | 299 | CC BY 4.0 (README) | 14 vector-borne negatives |
| Dengue (NS1) | Chittagong dengue | 308 | MIT (repository) | Provenance flagged: the README says raw data is not included, yet the CSV is present. Confirm with authors. |
| Dengue vs chikungunya vs neither | Brazil SINAN notifications (sample) | 149,849 of 6.7M | CC BY 4.0 | Surveillance labels, not clinical diagnoses |
| Typhoid | TyphoDx-BD (Bangladesh) | 540 | CC BY 4.0 | Widal titres excluded (see section 5) |
| Leptospirosis | Sri Lanka leptospirosis cohort | 1,734 | CC BY 4.0 | Label mapping checked against codebook |

## 4. Method
- Stratified 75/25 split, seed 42. Test set not used for model choice.
- Logistic regression, random forest, and XGBoost compared by stratified cross-validated ROC AUC on the training split.
- Best model refit on the training split and scored once on the test set.
- 95% CIs from 1,000 bootstrap resamples of the test set.

## 5. Results (held-out test set)
| Model | Selected algorithm | ROC AUC (95% CI) | Status |
|---|---|---|---|
| Dengue (NS1) | random forest | 0.983 (0.942–1.000) | research |
| Dengue vs chikungunya vs neither | XGBoost | macro 0.668 | research |
| Leptospirosis | XGBoost | 0.614 (0.557–0.669) | research |
| Malaria | random forest | 0.685 (0.479–0.879) | limited |
| Vector-borne | random forest | 0.884 (0.758–0.986) | limited |
| Typhoid (Widal excluded) | logistic regression | 0.563 (0.421–0.710) | limited |

**Typhoid label finding (report this).** With the Widal titres included, a depth-2 decision tree reached CV AUC 1.000. The label therefore appears to be defined by those titres. A model that uses them tests the label definition, not diagnostic skill. The titres were excluded, and the remaining model has no reliable discrimination. This is a useful negative result for the report.

**Dengue caution.** The dengue NS1 score is high, but NS1 is a laboratory test. The model predicts NS1 positivity in this cohort. It does not predict clinical dengue.

## 6. Limitations to state in any write-up
- Retrospective public data, single split per model, no external validation.
- Small and imbalanced classes (Burkina has 14 negatives in the vector-borne label).
- No fairness audit (sex, age, and site effects are not tested).
- No prospective or clinical study. Results are not evidence for clinical use.
- Chittagong data provenance is unresolved.

## 7. Reproduce
```
python ml/download_data.py
python ml/prepare_datasets.py
python ml/train_models.py
python ml/write_model_cards.py
cd backend && python3 -m pytest -q
```

## 8. Future work
- External validation on a held-out country or hospital.
- Calibration plots and decision-curve analysis.
- Fairness audit by sex and age.
- Replace the typhoid model with data that has an independent reference standard.
- Clinical study and regulatory review before any clinical use.
