# Health-U Implementation Plan

Status legend: **DONE**, **IN PROGRESS**, **BLOCKED**, **NOT STARTED**.

## Decisions taken so far
- D1. Project name is Health-U. No license.
- D2. Frontend styling: custom CSS design system (clinical premium, teal and white) with Framer Motion. Tailwind is **not** used. The master prompt asks for Tailwind; this is a deviation to confirm with the owner.
- D3. The Gemini key is read from `GEMINI_API_KEY`. Default model `gemini-3.5-flash`.
- D4. AI writes narrative text only. Urgency comes from the rule engine.
- D5. Existing datasets and models are not deleted. Synthetic models are labelled as demonstrations.

## Open blockers
1. **health-U repository not provided.** Phase 1 section A cannot complete. Needed: zip upload or GitHub URL.
2. **Master prompt scope vs MedAssist.** Confirm whether Health-U is the merged result of both projects, or whether the master prompt replaces the MedAssist code base.
3. **Dataset access.** Each disease dataset must be checked for licence and content. Downloads cannot be verified from this workspace without network access to each host.
4. **Gemini key.** The owner's key has not yet returned a successful response. Revoke both pasted keys and set a new key in `backend/.env` on the owner's machine.

## Phases

### Phase 0 — Rename, licence removal, frontend rebuild (current)
- [x] Rename user-facing brand to Health-U (frontend, README, backend titles, PDF, render.yaml, vercel.json)
- [x] Remove LICENSE and licence references
- [x] Redesigned frontend: landing, auth, chat shell, triage, result, modals
- [x] `npm run build` passes
- [x] App.tsx router, chat shell, and real endpoint wiring (written; builds; not yet run against a live backend)
- [x] Browser test against a running backend (sign-up, records panel, session restore: passed)

### Phase 1 — Audit
- [x] MedAssist audit (`docs/INTEGRATION_AUDIT.md` sections B–K)
- [ ] health-U audit (**BLOCKED** on repository)
- [ ] Merge plan (depends on health-U audit)

### Phase 2 — Backend foundation
- [x] Split `main.py` into `app/` modules (routers, schemas, services)
- [x] Authentication dependency and ownership checks (tests cover cross-user access)
- [x] Fix download route (ID-only, owner-scoped), CORS (no credentials), error handling
- [x] SQLAlchemy models; PostgreSQL via DATABASE_URL (not yet tested against Postgres). [ ] Alembic migrations
- [x] Tests: 45 pytest tests passing (auth, ownership, rules, uploads, reports, privacy, assistant)

### Phase 3 — Requirements and dependencies
- [x] Complete `requirements.txt` (pandas, numpy, joblib, scikit-learn, xgboost, fpdf2, google-genai, python-dotenv, sqlalchemy, alembic, pytest)

### Phase 4 — Rule engine and assessment
- [ ] Reconcile `rule_engine.py` with `data/clinical_rules.md` (spot-check first)
- [ ] Add test cases for each rule, including severe-level paths
- [ ] Assessment history stored per user

### Phase 5 — LangGraph and Gemini agents
- [ ] LangGraph workflows: NOT implemented. Current AI calls are single Gemini calls with fixed JSON shapes
- [ ] Guardrails: no diagnosis, no prescription, no urgency from the LLM

### Phase 6 — Disease models (one at a time)
**Status: NOT STARTED.** No licensed, verified dataset has been obtained, so no disease model has been trained.
Each disease needs: dataset audit, licence check, pipeline, evaluation on a held-out split, model card. If a dataset is unavailable, document it and do not substitute.
- [ ] Vector-borne (general) — dataset lead: GitHub zombiboy/Tabular-dataset-for-AI-based-vector-borne-disease-prediction (to audit)
- [ ] Dengue — lead: GitHub TurhanSakib/Machine-Learning-based-Early-detection-of-dengue-Case-study-Chittagong (308 patients reported, to audit); opendengue.org (to audit)
- [ ] Malaria — no verified dataset yet
- [ ] Typhoid — lead: Mendeley m9pnvv2vpv (to audit)
- [ ] Leptospirosis — lead: Mendeley zmxmp42g9p (to audit)
- [ ] Dengue/Chikungunya — lead: Mendeley 2d3kr8zynf (to audit)

### Phase 7 — Medical report upload and extraction
- [x] Upload endpoint with type and size checks. Scanned images are rejected (no OCR yet)
- [x] Text extraction (PDF/.txt) with a conservative pattern matcher. [ ] OCR for images
- [x] User review before any value is saved

### Phase 8 — PDF reports, security, privacy
- [x] Reports include the real inputs and the disclaimer
- [x] Data-deletion endpoint (DELETE /api/v1/account). [ ] Audit log, [ ] rate limits
- [ ] Security review pass

### Phase 9 — Documentation and release
- [ ] README rewritten for Health-U (remove 99.8% claims and stale file names)
- [x] API documentation (`docs/API.md`)
- [x] Dataset catalogue (`docs/datasets/DATASET_CATALOG.md`), all leads UNVERIFIED
- [x] Model card for the demo triage model. [ ] Disease model cards (none trained)

## Testing rule
Tests run at the end of every phase. A phase is not marked DONE until its tests pass.
