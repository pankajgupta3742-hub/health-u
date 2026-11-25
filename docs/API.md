# Health-U API (v2)

Base path: `/api/v1`. Interactive docs when the server runs: `http://localhost:8000/docs`.
Authentication: `Authorization: Bearer <access_token>` from `register` or `login`. Tokens expire (see `TOKEN_TTL_MINUTES`). Every endpoint except `register`, `login`, and `health` requires a valid token.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service status and version. No sign-in. |
| POST | `/auth/register` | Create an account. Returns `access_token` and `user`. |
| POST | `/auth/login` | Sign in. Returns `access_token` and `user`. |
| GET | `/auth/me` | Current user. Used to restore a session. |
| GET | `/account/export` | Download everything stored for the user as JSON (assessments, lab results, report list). |
| DELETE | `/account` | Delete the account, its assessments, lab results, and report files. |
| POST | `/assessments` | Run symptom triage. Body: symptom fields (see schema in `/docs`). Urgency comes from the rule engine. |
| GET | `/assessments` | List the user's assessments (newest first, max 100). |
| GET | `/assessments/{id}` | One assessment. |
| DELETE | `/assessments/{id}` | Delete an assessment and its reports. |
| POST | `/assessments/{id}/report` | Generate a PDF report. Returns the report id. |
| GET | `/reports/{id}/download` | Download the PDF. |
| POST | `/documents/extract` | Upload a text-based PDF or `.txt` lab report. Returns candidate values for review. Nothing is saved. |
| GET | `/lab-results` | List saved lab results. |
| POST | `/lab-results` | Save the values the user confirmed. |
| DELETE | `/lab-results/{id}` | Delete a lab result. |
| POST | `/chat` | Health assistant. Body: `{message, history}`. Returns `{reply, suggestions}`. Refuses non-medical questions. |
| POST | `/lookups/dictionary` | Medical term definition. |
| POST | `/lookups/medicine` | Medicine information. |
| GET | `/models` | Disease model catalog: status, headline metric with 95% CI, and the reason for that status. |
| GET | `/models/{key}` | Model detail: metrics, input fields, classes, disclaimer. |
| GET | `/models/{key}/card` | The model card (Markdown). |
| POST | `/predictions/{key}` | Probabilities from a disease model. Body: `{features: {name: value}}`. Blank fields use training defaults and are listed in `defaults_used_for`. |

## Errors
- `401`: missing or invalid token. The web app signs the user out and returns to the landing page.
- `404`: unknown id or model key.
- `422`: validation failed. For predictions this includes unknown fields, out-of-range numbers, and invalid categories. The message says which field and why.
- `502`: an external lookup failed.

## Disease model response (example, abbreviated)
```json
{
  "model": "dengue",
  "task": "binary",
  "probabilities": {"0": 0.19, "1": 0.81},
  "probability_positive": 0.81,
  "positive_class": "1",
  "decision_threshold": 0.5,
  "status": "research",
  "status_reason": "Trained and evaluated on a public dataset. Not clinically validated.",
  "defaults_used_for": ["Sex", "Pulse"],
  "disclaimer": "Research prototype trained on public retrospective data. Not clinically validated. This is not a diagnosis. Discuss results with a qualified clinician."
}
```
The response never contains an urgency level.

## Chat response statuses
`status` is internal (not in the response body except as `reply`). Possible outcomes: an answer with the disclaimer appended; a refusal for non-medical questions; a busy message when Gemini is overloaded; or a generic error message.


## Missing-data review and triage completion

See `MISSING_DATA_ENGINE.md` for the rules and the full endpoint list. Summary:

- `POST /api/v1/missing-data/reports`, `.../decisions`, `.../corrections`, `.../predict`, `GET .../history`
- `POST /api/v1/assessments` accepts optional symptom fields and `accepted: {field: proposal_id}`. A partial input returns `status: "Incomplete: missing information"` with `final_urgency: "N/A"`.
- `GET /api/v1/assessments/{id}/missing-data`
