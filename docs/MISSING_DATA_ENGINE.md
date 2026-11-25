# Missing-data completion engine

The engine handles missing, outdated or inconsistent inputs in two places: symptom triage (`/assessments`) and the
disease models (`/missing-data/...`). Its rule is simple: **nothing is filled in silently.** A value is used only when
the patient accepts it, edits it, types it in, or it is taken from the patient's own confirmed record and the patient
approves it.

## Flow

Patient input → missing-data detection → contextual retrieval → proposed completion → patient permission →
data validation → disease ML prediction → clinical safety notes → explanation.

- **Detection** lists each field as answered, missing, invalid (breaks the spec) or unknown (patient said "not sure").
- **Retrieval** reads only the signed-in patient's own records: earlier completed assessments (triage) and earlier
  confirmed model inputs (disease models). Nothing from other patients, and no uploaded files.
- **Proposals** are offered with four categories kept separate: `retrieved` (found in a record), `derived`
  (calculated by a fixed formula, e.g. age moved forward by the years elapsed), `inferred` (reserved; no code path
  produces these), and `unknown`.
- **Patient permission**: accept, reject, edit, answer manually, or mark unknown.
- **Validation** checks every value against the model's feature spec: type, allowed values, range, units.
- **Prediction** runs only when every field is answered or marked unknown. Otherwise the result is `incomplete` and
  no estimate is given. Missing values are never replaced with zeros, averages or assumed negatives.
- **Safety and explanation** add notes (not a diagnosis; limited models; unknown fields; seek care if severe). The
  explanation is built from the stored result only. No language model is used, so it cannot change a number.

## Freshness rules

| Information | Can be accepted if recorded within |
|---|---|
| Triage symptom answers (severity, duration, frequency, etc.) | 7 days |
| Triage age group | 365 days |
| Disease model: symptoms and measurements | 90 days |
| Disease model: stable fields such as Sex | 365 days |
| Derived age | 730 days (the source age must be that recent) |

Older information is shown as **too old** and cannot be accepted. The patient must answer again. A reused value keeps
its original date, so reuse never makes old data look new.

## Provenance

Every completed field has a history row: original value, final value, source, source date, method, approval status
and timestamp. This includes values typed at intake (`entered_at_intake`), accepted or edited proposals, manual
answers, and corrections. A correction keeps the old value in history and writes a new confirmed-input row. A
correction made after a prediction marks that report **stale**. Its estimate can no longer be produced, and the
patient must run a new check.

## Endpoints

Disease models (`/api/v1/missing-data`, sign-in required):

| Method and path | Purpose |
|---|---|
| `POST /reports` | Body `{model, features}`. Creates the report, lists missing fields and proposals. Adds no values. |
| `GET /reports`, `GET /reports/{id}` | List or view a report (own reports only). |
| `POST /reports/{id}/decisions` | Body `{decisions: [{field, action, proposal_id?, value?}]}`. Actions: accept, reject, edit, manual, unknown. |
| `POST /reports/{id}/corrections` | Body `{field, value}`. Changes an answered value and keeps the old one in history. |
| `POST /reports/{id}/predict` | Runs the model when all fields are resolved. Returns the estimate, safety notes, explanation and provenance. |
| `GET /reports/{id}/history` | Provenance rows for the report. |

Triage (`/api/v1`):

| Method and path | Purpose |
|---|---|
| `POST /assessments` | Each symptom field is optional. A missing one makes the result incomplete (`status: "Incomplete: missing information"`, `final_urgency: "N/A"`). `accepted: {field: proposal_id}` uses an earlier answer the patient accepted. |
| `GET /assessments/{id}/missing-data` | That assessment's own report: missing fields, proposals, provenance. |
| `POST /assessments/{id}/report` | PDF. Includes a "Missing information and sources" section. |

Legacy `POST /predictions/{key}` still exists for direct API use. It refuses incomplete input, but it records no
review or provenance, and its response says `recorded: false`. The app uses the missing-data review instead.

## Storage

New tables: `confirmed_inputs`, `missing_data_reports`, `missing_field_records`, `proposed_completions`,
`completion_sources`, `patient_approvals`, `completion_history`, and `assessment_missing_reports` (one row per triage
assessment). Every row carries `user_id`. New tables are created automatically on start-up; no migration is needed.

## Limits (stated, not hidden)

- **Lab values are not used for retrieval.** None of the six disease models takes a lab value as an input (their
  features are symptoms, vitals and demographics), so there is nothing to retrieve into. Lab values are still stored
  and can be used once a model needs them.
- **No `inferred` proposals are generated.** The category exists in the data model. The language model only reviews
  candidates: it can drop one or lower its confidence, and it cannot raise confidence or create values.
- **The language model is not used to explain ML results.** The explanation is a template built from the result.
- **Triage suggestions are shown after an incomplete result.** The form lets the patient mark a question "Not sure".
  A suggestion is accepted from the incomplete result, and the review screen shows it before the assessment is rerun.
