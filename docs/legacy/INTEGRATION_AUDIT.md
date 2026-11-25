# Health-U Integration Audit

Status: **PARTIAL.** The MedAssist side is audited. The health-U repository was **not available** in the workspace, so its section (A) cannot be completed yet. No health-U datasets or models were inspected or changed.

Project name: **Health-U** (formerly "MedAssist"). Project license: **none** (the MIT LICENSE file was removed at the owner's request).

---

## A. Existing health-U repository

**NOT AUDITED.** Required before any merge work:

- Frontend framework and components
- Backend framework, endpoints, database configuration
- Authentication setup
- Uploaded datasets, trained models, training scripts, preprocessing code
- Existing chatbot or Gemini / LangGraph code
- Report-processing code, environment variables, deployment config

Action needed: upload the health-U repository as a zip, or give the GitHub URL.

---

## B. MedAssist-main (audited)

### Frontend (React 18 + TypeScript + Vite 5, rebuilt in this session)
| Component | Status |
|---|---|
| Landing page, auth screens, chat workspace, six-step triage, result view, medicine and dictionary modals | Rebuilt; `npm run build` passes; wired to real endpoints (`/predict`, `/chat`, `/dictionary`, `/medicine`, `/generate-report`, `/auth/*`); screenshot-tested with mocked API only |
| `App.css` / `index.css` (original) | Replaced by `styles.css` |
| Styling | Custom CSS, not Tailwind (see plan, decision D2) |

### Backend (FastAPI, single `main.py`)
| File | Purpose | Reuse decision |
|---|---|---|
| `main.py` | All routes in one file, CORS `*` with credentials, unauthenticated routes, path-traversal download route | **Replace** (split into modules) |
| `decision_layer.py` | Rules first, ML for comparison, explanation attached | **Modify**: keep the rules-first principle, remove the synthetic model |
| `rule_engine.py` | Hand-written triage rules | **Reuse as baseline**, after reconciling with `clinical_rules.md` and clinical review |
| `llm_layer.py` | Explanation via Gemini, template fallback | **Modify** into the Explanation agent |
| `grok_client.py` | Chat: gatekeeper + answer via Gemini | **Modify** into the Health Assistant agent |
| `extras_client.py` | Medicine and dictionary lookups via Gemini | **Reuse** with stricter schemas and sources |
| `report_generator.py` | fpdf PDF report | **Reuse** (fpdf dependency must be added to requirements) |
| `gemini_client.py` (added this session) | Shared Gemini client with retry | **Reuse** |
| `supabase_client.py` | Supabase client | **Reuse** if Supabase auth is kept |

### Machine learning
| Asset | Finding | Decision |
|---|---|---|
| `data/symptoms_dataset.csv` | 5,000 **synthetic** rows labelled by the same rules that the model learns | **Do not use** as clinical evidence. Keep as a research baseline only |
| `models/best_model.joblib` | XGBoost (README says MLP), trained on the synthetic labels | **Demonstration only**. Not a disease model |
| `models/medassist_model.pkl` | XGBoost, not loaded by the code | **Remove from production path** |
| `scripts/train_models.py` | LR / RF / XGBoost comparison, saves best model | Reference for the new per-disease pipeline |
| `scripts/generate_dataset.py` | Generates synthetic labelled data using rules | Not for production use |
| 99.8% accuracy in docs | Circular: the labels come from the rules | **Remove** from all claims |

### Known defects carried over from the earlier review
1. The in-app triage was unreachable (an external iframe was used). **Fixed**: the redesigned frontend runs triage in-app and calls `/predict`. Not yet tested against a live backend.
2. Severe symptom levels could not be selected. **Fixed** in the redesigned frontend.
3. The PDF had placeholder inputs. **Partly fixed**: the frontend now sends the real answers and result to `/generate-report`. The backend route itself is unchanged and still has no auth.
4. `/download-report/{filename:path}` serves any readable file. **Open**: must be replaced with an authenticated, owner-scoped download.
5. CORS `*` with credentials. **Open**.
6. No authentication on API routes. **Open**.
7. `requirements.txt` missing pandas, numpy, joblib, scikit-learn, xgboost, fpdf. **Open** (partly addressed by google-genai).
8. Chat history in browser localStorage, shared across accounts. **Partly addressed**: key renamed; per-account storage still open.

---

## C. Features

### Reusable (after modification)
- Rules-first triage with explanation and first-aid templates
- Medicine and dictionary lookups (Gemini JSON schema)
- PDF report generation
- Gatekeeping that refuses off-topic chat
- Guided multi-step intake UI

### Must be replaced
- Synthetic-data urgency model as a "validated" component
- Monolithic `main.py`
- Unauthenticated, wide-open CORS API
- Browser-only chat history
- Hard-coded claims ("99.8%", "ML validated")

### Missing (required by the master prompt)
- Per-patient accounts with ownership checks
- PostgreSQL schema and migrations
- Disease-specific models with validated datasets
- Medical report upload, OCR and lab-value extraction
- Assessment history and stored reports
- LangGraph agent workflows
- Tests (none exist in the repository)

---

## D. Dependencies

Frontend (current): react 18, react-dom 18, framer-motion 11, lucide-react, vite 5, typescript 5, @vitejs/plugin-react 4.

Backend (must be corrected): see section B. `requirements.txt` is incomplete and must be rebuilt in phase 3.

---

## E. Database migration requirements

None exist yet. MedAssist has no database. Health-U's existing schema is unknown until its repository is inspected. A migration plan will be written after that audit.

---

## F. API migration requirements

Current MedAssist endpoints (`/predict`, `/chat`, `/medicine`, `/dictionary`, `/report`, `/generate-report`, `/download-report/{path}`, `/auth/login`, `/auth/register`) do not match the target `/api/v1/...` design. Plan: versioned routes, Pydantic schemas, authentication dependency, ownership checks, and a deprecation period for the old routes.

---

## G. Security issues (summary)

| Issue | Severity | Status |
|---|---|---|
| Arbitrary file read via `/download-report` | High | Open |
| CORS `*` with credentials | High | Open |
| No auth on API routes | High | Open |
| Auth returns raw Supabase response | Medium | Open |
| Medical chat stored in shared browser storage | Medium | Partly fixed |
| Prompt text includes raw user input | Low | Open (mitigate with schema-bounded inputs) |
| Demo API key was pasted in chat (two keys) | High | **Action for owner**: revoke both keys in Google AI Studio |

---

## H. ML limitations

- Symptom-only tabular models trained on synthetic data cannot establish clinical performance.
- Rules and labels that come from the same source make accuracy meaningless.
- No calibration, no external validation, no patient-level splits exist in MedAssist.
- Disease models for dengue, malaria, typhoid, leptospirosis and chikungunya need real, licensed, patient-level datasets. None is verified yet.

---

## I. Dataset limitations

See `docs/datasets/DATASET_CATALOG.md`. Summary: every candidate dataset in the master prompt is **unverified**. Their licences, label definitions, and suitability for individual-level prediction have not been checked.

---

## J. Recommended architecture

As set out in the master prompt (modular FastAPI, PostgreSQL + SQLAlchemy + migrations, Supabase or equivalent auth, LangGraph workflows with Gemini, separate per-disease model pipelines and registry, document-intelligence pipeline for PDFs and images). Finalise after section A is complete.

---

## K. Files that will be reused, replaced, modified, and created

Reused: `gemini_client.py`, `report_generator.py`, `extras_client.py`, frontend components (landing, auth, chat, triage, modals).
Modified: `decision_layer.py`, `rule_engine.py`, `llm_layer.py`, `grok_client.py`, frontend `Triage.tsx` (adaptive questions).
Replaced: `main.py` (into `app/` modules), `App.css`, `supabase_client.py` (if auth changes), `models/` demonstration artifacts (kept but relabelled).
Created: `docs/`, `app/` package, `tests/`, `datasets/` structure, model registry, migrations.
