# Health-U: Integration Audit (current state)

Audit date: 2026-11-23 (sandbox). Scope: `health-u/` only. The earlier MedAssist code analysis is kept in `docs/legacy/MedAssist_code_analysis.md`.

## 1. What is integrated end to end (verified)
| Area | Frontend | Backend | Verified how |
|---|---|---|---|
| Sign-up, sign-in, session restore | Auth screen, `/auth/me` on load | `auth` router, PBKDF2 hashes, JWT | Browser test; API tests |
| Sign-out | Log out button clears token | (client-side) | Browser test |
| Session expiry | 401 clears the session and returns to landing | token checks in `deps.py` | Browser test with an invalid token |
| Symptom triage | 6-step questionnaire, result card | `POST /assessments` -> LangGraph (validate, rules, explain, guard) | Browser test; API and graph tests |
| Triage PDF | "Download PDF report" | `POST .../report`, `GET /reports/{id}/download` | Browser test; file starts with `%PDF-` |
| Records list and delete | My records modal | `GET/DELETE /assessments` | Browser test |
| Records PDF | "Download PDF" in records | same report routes | Browser test |
| Lab upload | Pick a PDF or .txt, review drafts, save | `POST /documents/extract`, `POST /lab-results` | Browser test; 3 values confirmed and found in PostgreSQL |
| Health assistant | Chat, suggestions, history per account | `POST /chat` (one Gemini call) | API test: dengue answered; cricket refused. Busy messages seen when Gemini is overloaded |
| Medicine and dictionary lookups | Modals | `POST /lookups/*` | Route exists; not retested in this audit |
| Disease models | Catalog, form, probabilities, card | `GET /models`, `GET /models/{key}`, `GET /models/{key}/card`, `POST /predictions/{key}` | Browser test; 11 API tests |
| Data export | Records modal: "Export my data (JSON)" | `GET /account/export` | API test; browser test (JSON has the saved assessment) |
| Account deletion | Not in UI | `DELETE /account` | API test (SQLite and PostgreSQL) |

## 2. Defects found and fixed in this audit
1. **Chat made two sequential Gemini calls** with an 8,000-character prompt. Merged into one call with a shorter prompt. Refusals now take about 1–4 s.
2. **Account and assessment deletes failed on PostgreSQL** because reports were deleted after the assessments they reference. SQLite hid this because it does not enforce foreign keys by default. Fixed with an explicit flush. The test suite now also runs on PostgreSQL.
3. **The legacy synthetic-data model ran by default** and its output appeared beside the rule-based urgency. It is now off unless `HEALTHU_ENABLE_LEGACY_ML=1`. Urgency comes only from the rules.
4. **Disease model form pre-filled every field**, which made the "typical values were used" note misleading. Fields are blank by default now.
5. **Typhoid model used the Widal titres**, which nearly define the label (CV AUC 1.000). Excluded. Documented in the card.
6. **Favicon and logo path** pointed to a moved file. Fixed.
7. **Documentation claims** (the 99.8% synthetic accuracy and the "data export" feature) were not supported. Removed or corrected.

## 3. Known gaps and risks
- **Gemini availability:** the free key's `gemini-3.5-flash` quota is used up (429), and the lite models return 503/504 at times. Chat and explanations fall back to a busy message or a template. This is an external limit, not a code defect.
- **Hosted frontend:** `frontend/src/api.ts` uses `VITE_API_URL` (default `http://localhost:8000`). A hosted frontend must set this at build time, or it cannot reach the API.
- **CORS:** `CORS_ORIGINS` must include the frontend origin in production.
- **Tokens** are stored in browser `localStorage`. A stolen token is valid until it expires (default 24 h).
- **PostgreSQL** was tested on version 18 with `psycopg2-binary`. The `psycopg` (v3) driver failed with SQLAlchemy 2.1 in this environment, so it is not the documented driver.
- **Disease models:** all six are research prototypes or limited. None is clinically validated. Chittagong data provenance is unresolved.
- **Local test database:** the PostgreSQL server in this sandbox uses trust authentication. Do not reuse that setup for real data.
- **No automated browser tests in CI.** The Playwright scripts live in the sandbox `shots/` folder and are not part of the repository yet.
- **Frontend routes for disease models do not have their own URL.** It is a modal.

## 4. Environment facts
- Backend tests: 65 passing on SQLite and on PostgreSQL 18.
- Browser suite (8 flows, PostgreSQL-backed API): all pass. The two console 401 messages come from the deliberate expired-token check.
- Frontend: TypeScript clean, production build passes.
- Ports: API 8000, frontend dev 3015, production preview 4173 (sandbox only).
