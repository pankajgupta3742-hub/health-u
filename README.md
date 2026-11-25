# Health-U

Health-U is a health assessment web app. A person enters symptoms and vitals, and a deterministic rule engine sets the urgency level. A Gemini-based health assistant answers general health questions and writes explanation text. Users can keep a record of assessments and lab results and download PDF reports. Separate disease models trained on public datasets are included as research prototypes.

**Safety rules the code follows**

- Urgency comes only from the rule engine. The language model writes text and never sets urgency.
- Triage runs as a LangGraph workflow: validate, rules, explain, guard. The guard copies urgency from the rules and caps text length.
- The legacy synthetic-data ML model from MedAssist is off by default. Enable it only for comparison with `HEALTHU_ENABLE_LEGACY_ML=1`.
- The assistant does not diagnose or prescribe. It refuses non-medical questions.
- The disease models are research prototypes. They have not been clinically validated. Each one has a model card with its limitations.

## Repository layout

| Path | What it contains |
|---|---|
| `backend/` | FastAPI app (`app/`), tests (`tests/`), rule engine, Gemini clients |
| `frontend/` | React + TypeScript + Vite app. Custom CSS, Framer Motion for animation |
| `ml/` | Dataset specs, download, preparation, training, and model-card scripts |
| `data/raw/` | Downloaded source files (small public datasets) |
| `data/processed/` | Cleaned datasets used for training |
| `data/dataset_manifest.json` | Sources, licences, row counts, label counts, excluded columns |
| `models/<key>/` | Trained model, `metrics.json`, `feature_spec.json`, `MODEL_CARD.md` |
| `models/legacy/`, `data/legacy_synthetic/`, `scripts/legacy/`, `docs/legacy/` | Earlier MedAssist artefacts, kept for reference |
| `render.yaml` | Render deployment blueprint (backend start command `app.main:app`) |

## Quick start

### Easiest: run in VS Code

1. Install Python 3.11+ and Node.js 20+.
2. Open `health-u.code-workspace` in VS Code and install the recommended extensions.
3. **Tasks: Run Task → 0. Set up everything (first time only)**. This creates the Python environment, `backend/.env` (with a generated `JWT_SECRET`), and installs the frontend packages.
4. **Tasks: Run Task → Run Health-U (API + web app)**, then open http://localhost:3015.

Full guide with troubleshooting: [docs/VSCODE_SETUP.md](docs/VSCODE_SETUP.md). Without a terminal, the same setup runs as `python3 scripts/setup.py` (Windows: `py -3 scripts\setup.py`).

### Manual setup (any editor)

### 1. Backend

Requires Python 3.11+.

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # then edit .env on your machine; never commit it
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Required settings in `.env`:

- `JWT_SECRET`: a long random string. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `GEMINI_API_KEY`: your own key from https://aistudio.google.com/apikey. It is read from the environment only.
- `GEMINI_MODEL` (optional): defaults to `gemini-3.5-flash`. The client falls back to `gemini-3.5-flash-lite` and then `gemini-3.1-flash-lite`.

Without a database URL the app uses SQLite. For PostgreSQL, set `DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/healthu`. The tests use `psycopg2-binary`; the `psycopg` v3 driver failed with SQLAlchemy in testing.

To run the test suite on PostgreSQL: `HEALTHU_TEST_DATABASE_URL=postgresql+psycopg2://... python3 -m pytest -q`.

Run the tests:

```bash
cd backend && python3 -m pytest -q
```

### 2. Frontend

Requires Node.js 18+.

```bash
cd frontend
npm install
cp .env.example .env
npm run dev                 # dev server on http://localhost:3015
npm run build               # production build in frontend/dist/
```

The frontend calls `/api` on its own origin. Vite forwards those calls to the API on port 8000 during development. CORS is only needed when the frontend and API are on different origins. In that case, set `VITE_API_URL` at build time and include the frontend origin in `CORS_ORIGINS`.

To preview the built app with the API behind the same origin:

```bash
cd frontend && npm run build && cd ..
python3 scripts/serve_preview.py --port 4173 --api http://127.0.0.1:8000
```

### 3. Data and models

```bash
python ml/download_data.py            # small datasets into data/raw/
python ml/download_data.py --brazil   # optional: large Brazil SINAN zip into /var/tmp/healthu_raw/
python ml/prepare_datasets.py         # builds data/processed/ and data/dataset_manifest.json
python ml/train_models.py             # trains all six models into models/<key>/
python ml/write_model_cards.py        # writes models/<key>/MODEL_CARD.md
```

Model results and status are in each `models/<key>/MODEL_CARD.md`. Read the card before using any model.

## Disease models

| Key | Dataset | Task | Status |
|---|---|---|---|
| `malaria` | Burkina Faso vector-borne (300 records) | binary | limited (29 negatives) |
| `vector_borne` | Burkina Faso vector-borne | binary | limited (14 negatives) |
| `dengue` | Chittagong dengue (308 patients) | binary, NS1 result | research prototype |
| `dengue_chikungunya` | Brazil SINAN notifications (sampled) | 3-class surveillance label | research prototype |
| `typhoid` | TyphoDx-BD (Bangladesh) | binary | limited (see card) |
| `leptospirosis` | Sri Lanka leptospirosis cohort | binary | research prototype |

The Widal titres in the typhoid data separate the label almost perfectly, so they are excluded from the model. The typhoid model card explains this.

Brazil training uses the sampled file (149,849 rows, seed 42), not the full 6.7 million rows.

## Licences and data notes

- Datasets are used under their stated licences (CC BY 4.0 for the Mendeley sets and the Burkina Faso set; MIT for the Chittagong repository). Each licence and citation is in `ml/specs.py` and the manifest.
- The upstream Chittagong README says real patient data is not included and asks researchers to contact its authors. This project excludes the raw and processed Chittagong CSV files; obtain authorization from the data owners before adding them.
- No accuracy figures from third-party papers are reused here. All metrics come from `models/<key>/metrics.json`.

## API

The API is served under `/api/v1`. Interactive docs are at `http://localhost:8000/docs` when the server is running. Main groups:

- `auth`: register, login, current user
- `account`: export my data (`GET /account/export`) and delete my account
- `assessments`: create, list, delete; generate and download PDF reports
- `documents/extract`: upload a lab report to extract draft values
- `lab-results`: list, save, delete
- `chat`: health assistant (requires sign-in; one Gemini call per turn; falls back to a friendly message when Gemini is busy)
- `missing-data`: missing-data review for disease models (detect, propose, patient decision, correct, predict). See `docs/MISSING_DATA_ENGINE.md`
- `models`: disease model catalog (`GET /api/v1/models`), model detail, model cards (`GET /api/v1/models/{key}/card`), and predictions (`POST /api/v1/predictions/{key}`). Inputs are validated against each model's feature spec. Output is class probabilities with the model's status. It never sets urgency.
- `lookups`: medical dictionary and medicine information

## Status

- Backend tests: 117 passing on SQLite (includes the missing-data engine, its LangGraph workflow, and triage completion). API feature check: 62/62 (`qa/api_check.py`). Browser sweep: 11/11 on the preview. Earlier PostgreSQL 18 run: 65 passing, before the engine was added. (auth, assessments, documents, privacy and export, rules, triage graph, chat with Gemini stubbed, predictions).
- Browser checks on the latest build: disease-model review (proposal, accept, correction with stale notice), triage (incomplete result, accept an earlier answer, rerun to a result), and sign-in with chat. The session-ended notice did not reproduce.
- Browser suite (earlier run): 8 flows pass against the PostgreSQL-backed API (sign-up, triage, PDFs, export, lab upload, sign-out, session expiry).
- Browser end-to-end test (sign-up, records, reload): passing.
- Assistant: verified live on the API. The dengue question returned a full answer, and the off-topic question was refused. Gemini still returns 503 or 504 at times, and the free-tier quota for gemini-3.5-flash is used up. In those cases the app shows a busy message.
- Frontend favicon and logo path fixed; production build passes. Disease models screen tested in the browser.

## Deployment

`render.yaml` defines the backend service. It has been written but not yet deployed or tested on a hosted domain. The start command is `uvicorn app.main:app`. Set the environment variables above in the Render dashboard. Do not commit `.env`.

## Licence

No licence file is included in this project. The project owner holds all rights.

## Run in VS Code

Open `health-u.code-workspace` in VS Code and follow [docs/VSCODE_SETUP.md](docs/VSCODE_SETUP.md). Setup and run are one-click tasks: **Tasks: Run Task**.
