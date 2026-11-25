# Model card: Dengue vs chikungunya vs neither (surveillance)

**Model key:** `dengue_chikungunya` · **Task:** multiclass · **Trained:** 2026-11-23
**Status: RESEARCH PROTOTYPE**

Trained and evaluated on a public dataset. Not clinically validated.

> This model is trained on public retrospective data. It has **not** been clinically validated, prospectively
> tested, or approved for diagnosis or treatment decisions. The language model in Health-U never sets urgency or
> produces a diagnosis; urgency comes only from the rule engine.

## Intended use
Support clinical differentiation between dengue and chikungunya in the surveillance setting, with symptoms and demographics only.

**Not intended for:** diagnosis, treatment, triage on its own, use outside the populations described under
"Data", or any setting where a wrong output could delay care.

## Data
- **Dataset:** Brazil SINAN notifications: dengue and chikungunya
- **Source:** Mendeley Data 2d3kr8zynf (pre-processed SINAN notifications, Brazil 2013–2020)
- **Licence:** CC BY 4.0 (stated on Mendeley Data)
- **Citation:** Pre-processed SINAN (Brazilian national notifiable-disease system) data, 2013–2020, on Mendeley Data 2d3kr8zynf.
- **Raw size:** 6,732,542 rows, 56 columns; CLASSI_FIN: Dengue 4,307,513 / Discarded-Inconclusive 2,100,029 / Chikungunya 325,000
- **Rows used:** 149849 (train 112386, test 37463; stratified 75/25 split, seed 42)
- **Class counts (all rows):** {'chikungunya': 7304, 'dengue': 95927, 'neither': 46618}
- **Class counts (test):** {'chikungunya': 1826, 'dengue': 23982, 'neither': 11655}
- **Processed file:** `data/processed/brazil_sinan_sample.csv`
- **Manifest:** `data/dataset_manifest.json`

**Label:** National SINAN case classification: Dengue, Chikungunya, or Discarded/Inconclusive (neither).

**Input requirements:** Clinical and exposure inputs only; no laboratory result is required.

### Features used (21)
- Numeric: 21; categorical: 0
- Excluded or dropped columns, with reasons:
- `RESUL_SORO`: serology result (laboratory; defines the diagnosis)
- `RESUL_NS1`: NS1 result (laboratory; defines the diagnosis)
- `RESUL_VI_N`: virus isolation result (laboratory)
- `RESUL_PCR_`: PCR result (laboratory; defines the diagnosis)
- `HISTOPA_N`: histopathology (laboratory)
- `IMUNOH_N`: immunohistochemistry (laboratory)
- `LEUCOPENIA`: laboratory-derived finding (white-cell count)
- `HOSPITALIZ`: severity / outcome-related field
- `EVOLUCAO`: outcome field (follows the diagnosis)
- `TPAUTOCTO`: case classification detail (defines the diagnosis)
- `COUFINF`: municipality of infection (geography; excluded)
- `COPAISINF`: country of infection (geography; excluded)
- `COMUNINF`: municipality of infection (geography; excluded)
- `DT_NOTIFIC`: date field (time leakage)
- `DT_SIN_PRI`: date field (time leakage)
- `DT_NASC`: date of birth (identifier-like; age used instead)
- `DT_INVEST`: date field
- `DT_ENCERRA`: closing date (follows the diagnosis)
- `ID_AGRAVO`: record identifier
- `ID_MUNICIP`: geography identifier
- `ID_UNIDADE`: health-unit identifier
- `ID_REGIONA`: geography identifier
- `ID_MN_RESI`: geography identifier
- `ID_RG_RESI`: geography identifier
- `ID_PAIS`: geography identifier
- `SG_UF`: geography identifier
- `SG_UF_NOT`: geography identifier
- `CS_RACA`: not clinical (kept out for simplicity)
- `CS_ESCOL_N`: not clinical (kept out for simplicity)
- `SEM_NOT`: time field
- `SEM_PRI`: time field
- `NU_ANO`: year (time leakage)
- `sex` (model-level): 0% missing or constant
- `pregnant` (model-level): 0% missing or constant

## Method
1. Rows with a missing label are removed. Columns over 50% missing or constant are dropped.
2. A stratified 75/25 train/test split, fixed seed 42. The test set is not used for model choice.
3. Logistic regression, random forest, and XGBoost are compared by 3-fold stratified CV ROC AUC on the
   training split only. The best is refit on the full training split.
4. The test set is scored once. 95% CIs come from 1,000 bootstrap resamples of the test set.
5. Missing values are imputed (median for numeric, most-frequent for categorical). Categorical values are one-hot encoded.
   Unseen categories at prediction time are ignored.

| Candidate | CV ROC AUC (mean ± sd, training split only) |
|---|---|
| logistic_regression | 0.639 ± 0.000 |
| random_forest | 0.652 ± 0.001 |
| xgboost **(selected)** | 0.668 ± 0.002 |

Selected algorithm: **xgboost**. Versions: scikit-learn 1.6.1, xgboost 3.4.1.

## Results (held-out test set)
| Metric (held-out test set) | Value |
|---|---|
| Macro ROC AUC (one-vs-rest) | 0.668 (95% CI 0.663–0.672) |
| Accuracy | 0.642 |
| Balanced accuracy | 0.339 |
| Macro F1 | 0.276 |

Per class (test set): chikungunya: recall 0.000, precision 0.000, AUC 0.794; dengue: recall 0.991, precision 0.643, AUC 0.600; neither: recall 0.025, precision 0.583, AUC 0.610. Confusion matrix rows = true class, columns = predicted: [[0, 1826, 0], [0, 23775, 207], [0, 11366, 289]].

These are estimates on one public dataset and one split. They are not a measure of how the model would perform
in a clinic, in another country, or on another population. Confidence intervals are wide when a class is small.

## Limitations
- Trained on a random 2% sample of 6.7 million national notifications (see manifest). Class mix is kept, but the model is not calibrated to any hospital.
- Laboratory results (NS1, PCR, serology, histopathology) and outcome fields are excluded as they define or follow the diagnosis.
- Symptom reporting in surveillance forms is incomplete; blanks are imputed.
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
