# Health-U API (v1)

Base path: `/api/v1`. Interactive docs when the server runs: `/docs`.
Authentication: `Authorization: Bearer <access_token>` from `/auth/login` or `/auth/register`.
Every patient record is scoped to the signed-in user. Other users' IDs return 404.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /health | no | Service status |
| POST | /auth/register | no | Create account (email, password ≥ 8 chars, name) |
| POST | /auth/login | no | Get token |
| GET | /auth/me | yes | Current user |
| POST | /assessments | yes | Run rules + demo ML + AI explanation; saved to history |
| GET | /assessments | yes | Own assessment history (newest first, max 100) |
| GET | /assessments/{id} | yes | One assessment |
| DELETE | /assessments/{id} | yes | Delete an assessment and its reports |
| POST | /assessments/{id}/report | yes | Generate a PDF report |
| GET | /reports/{id}/download | yes | Download the PDF (owner only) |
| POST | /documents/extract | yes | Upload PDF or .txt (≤ 5 MB, ≤ 20 pages); returns candidate lab values. Nothing is stored |
| POST | /lab-results | yes | Save user-confirmed lab values |
| GET | /lab-results | yes | Own saved lab values |
| DELETE | /lab-results/{id} | yes | Delete one saved value |
| POST | /chat | yes | Health assistant (non-medical-advice guardrails) |
| POST | /lookups/dictionary | yes | Medical term definition |
| POST | /lookups/medicine | yes | Medicine information |
| DELETE | /account | yes | Permanently delete the account and all its data |

## Triage input (POST /assessments)
Closed sets; unknown values return 422.
- primary_symptom: chest_pain, fever, vomiting, headache, shortness_of_breath, abdominal_pain, sore_throat, cough, dizziness
- severity_score: integer 1–10
- duration_category: short, medium, long
- frequency: rare, frequent, persistent
- age_group: child, adult, elderly
- breathlessness_level, vomiting_severity: none, mild, severe
- fever_level: none, mild, high
- pain_type: sharp, dull, none

Urgency (`final_urgency`) comes from the rule engine. The ML output is shown for comparison only. The AI writes explanation text and never sets urgency.

## Errors
`{"detail": "..."}` with the HTTP status. 401 means sign in again. 502 means an upstream AI service failed.
