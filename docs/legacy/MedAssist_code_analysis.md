# MedAssist v2: Code Analysis

Repository: https://github.com/sa1165/Medassist (cloned to `/home/user/Medassist`, 50 files, one commit)

## 1. What the project is

MedAssist is a clinical triage demo. A user answers a short symptom questionnaire, the app returns an urgency level (High / Moderate / Low), and it offers an explanation, first-aid text, and a PDF report. It also has a chat assistant, a medicine lookup, and a medical dictionary. All AI features call Groq's API (Llama 3.3 70B), not Grok. The README calls the project "safety-first, not chatbot-first."

```
React + TypeScript frontend (frontend/src/App.tsx)
        │  fetch()  (VITE_API_URL)
        ▼
FastAPI backend (backend/main.py)
 ├─ POST /predict ──► DecisionLayer ──► RuleEngine (rules)
 │                                  ├─► XGBoost model (models/best_model.joblib)
 │                                  └─► LLMLayer (fixed-text template, no AI call)
 ├─ POST /chat ─────► GrokBrain (Groq: gatekeeper + answer)
 ├─ POST /medicine ─► ExtrasClient (Groq)
 ├─ POST /dictionary► ExtrasClient (Groq)
 ├─ GET  /report ───► ReportGenerator (fpdf → PDF file)
 └─ /auth/*  ───────► Supabase auth
```

## 2. File-by-file guide

### Root
| File | Purpose |
|---|---|
| `README.md` | Project overview, architecture, setup. Several sections are out of date (see §5). |
| `LICENSE` | MIT License, © 2026 Sanjeev A. |
| `.env.example` | Template for `SUPABASE_URL`, `SUPABASE_KEY`, `GROQ_API_KEY`, `GROQ_API_KEY_EXTRAS`. |
| `.gitignore` | Excludes `.env` files, `node_modules`, `__pycache__`, `venv`, and build output. |
| `render.yaml` | Render.com deploy config: Python 3.12, `pip install -r requirements.txt`, starts uvicorn on `$PORT`. |
| `screenshots/*.png` | 9 screenshots used by the README. Images only. |

### Backend (`backend/`)
| File | Purpose |
|---|---|
| `main.py` | FastAPI app. Defines all routes, CORS, and the request models (`SymptomInput`, `ChatInput`, `DictionaryInput`, `MedicineInput`). |
| `decision_layer.py` | Core triage pipeline. Validates input, runs the rule engine, runs the ML model, compares the two, and attaches the explanation. The rule result is always the final answer. |
| `rule_engine.py` | Hand-written clinical rules, checked in priority order (High → Moderate → Low → default). Also has `validate_input()`, which catches contradictions such as a symptom with severity 1. |
| `llm_layer.py` | Builds the triage explanation from a fixed text table (`ADVICE_REPO`) and urgency-specific sentences. **It does not call an AI model**, despite the README. |
| `grok_client.py` | `GrokBrain`. Two-step chat: (1) an LLM "gatekeeper" rejects non-medical queries, (2) a second call writes the answer in one of three modes (emergency / structured / conversational). Keeps the last 6 messages of history. |
| `extras_client.py` | `ExtrasClient`. Returns JSON from Groq for medicine lookup and dictionary lookup. Uses a separate API key if one is set. Also creates the shared `extras_client` instance. |
| `report_generator.py` | Builds a one-page PDF with `fpdf`: urgency banner, patient inputs, rule that fired, explanation, first aid, next steps, disclaimer. Writes to `reports/`. |
| `supabase_client.py` | Creates a Supabase client if `SUPABASE_URL` and `SUPABASE_KEY` are set. Otherwise returns `None`. |
| `requirements.txt` | Lists fastapi, uvicorn, pydantic, openai, python-dotenv, supabase, reportlab, python-multipart, jinja2. **Missing packages used by the code**; see §5. |

### Frontend (`frontend/`)
| File | Purpose |
|---|---|
| `src/App.tsx` (1,594 lines) | The whole application in one React component. Contains the login/register screens, a chat UI with localStorage history, the 6-step triage form, the results and report view, and the medicine and dictionary modals. |
| `src/App.css` (1,813 lines) | Styling for the whole app. Sections: navbar, triage cards, results, report, auth, sidebar, chat, modals. Reviewed by structure; not read line by line. |
| `src/index.css` | Two base rules: body font and code font. |
| `src/main.tsx` | Mounts `<App />` with `ReactDOM.render` (React 17 API) inside `StrictMode`. Logs mount status. |
| `src/react-app-env.d.ts` | TypeScript type declarations for image and CSS imports, and for `process.env`. |
| `src/medassist_logo.png`, `src/logo.svg` | Logos. The PNG is used in the splash screen. |
| `index.html` | Vite HTML shell with a `#root` div and the title "MedAssist v2". |
| `package.json` | React 17, Lucide icons, Vite 2, TypeScript 4. Build runs `tsc && vite build`. Includes an unused `vite-plugin-react` package. |
| `package-lock.json` | Locked dependency versions. |
| `vite.config.ts` | React plugin, dev server on port 3015. |
| `tsconfig.json` | Strict TypeScript config for `src/`. |
| `vercel.json` | Vercel config: build with Vite, output `dist`, rewrite all routes to `index.html`. |
| `.env.example` | Sets `VITE_API_URL` (backend URL). Defaults to `http://localhost:8000`. |
| `.gitignore` | Ignores `node_modules`, `dist`, and local env files. |

### Data (`data/`)
| File | Purpose |
|---|---|
| `symptoms_dataset.csv` | 5,000 synthetic rows (1,668 High, 1,666 Low, 1,666 Moderate). Columns are the 9 intake features plus `urgency`. The labels come from `generate_dataset.py`, not from clinicians. |
| `clinical_rules.md` | Human-readable list of 16 rules (6 High, 5 Moderate, 5 Low) and the priority policy. |
| `schema.json` | Lists allowed values for each feature and the three urgency classes. |

### Models (`models/`)
| File | Purpose |
|---|---|
| `best_model.joblib` | The trained model used at runtime. **It is an XGBoost classifier**, not the MLP the README describes. Takes 31 one-hot features. |
| `metadata.joblib` | Class names (`High`, `Low`, `Moderate`), the 31 expected feature columns, and the list of categorical columns. Used to reshape each input to match training. |
| `medassist_model.pkl` | Also an XGBoost classifier. Not loaded anywhere in the code. |

### Scripts (`scripts/`)
| File | Purpose |
|---|---|
| `generate_dataset.py` | Creates `symptoms_dataset.csv`. Samples random features, applies its own copy of the rules to label each row, and balances the three classes. Writes to `data/` relative to the working directory. |
| `train_models.py` | Trains Logistic Regression, Random Forest, and XGBoost on the CSV, keeps the most accurate one, and saves it plus metadata to `models/`. |

### Docs (`docs/`)
| File | Purpose |
|---|---|
| `concept_note.md` | Short project concept: separate communication (LLM) from decisions (rules and ML). |
| `research_paper_guide.md` | Viva and report notes. Reports 99.8% accuracy for XGBoost and ~80% for Logistic Regression. |

## 3. How a triage request flows (as coded)

1. The user answers questions in the UI and presses "Run triage." The browser sends `POST /predict`.
2. `DecisionLayer.predict()` fills in default values for missing fields.
3. `validate_input()` returns "Contradiction Detected" if a symptom and its severity conflict. The request stops here.
4. `RuleEngine.evaluate()` returns the first matching rule's urgency. This is the **final** urgency.
5. The XGBoost model predicts an urgency from the same inputs. It is only used to set `status` to "Agreement" or "Conflict (Rule Overrides ML)". It never changes the result.
6. `LLMLayer.generate_explanation()` builds the narrative and advice from templates.
7. The frontend shows the result. The PDF is requested with `GET /report?urgency=...&explanation=...`.

## 4. What works well

- Urgency is decided by deterministic rules, not by a language model. This is easier to audit and test.
- Explanations are fixed text, so triage makes no AI API calls and costs nothing.
- The medical dictionary and medicine endpoints ask the model to refuse non-medical queries and return JSON. The frontend handles the error cases.
- The chat gatekeeper rejects off-topic queries before the answer is generated.
- Secrets come from environment variables, and `.env` files are git-ignored.

## 5. Problems found

### A. Safety-critical (fix first)

1. **The in-app 6-step triage can't be reached.** `step` only increases through the "Next" buttons on steps 1–6, and nothing moves it from 0 to 1. The chat's "Start Symptom Analysis" button opens an external iframe (`https://smart-triage-buddy-94.lovable.app`), not this repo's triage flow. As a result, the rule engine and `/predict` are never called from the UI shown to users.

2. **Severe cases can't be selected even if the form is reached.** The "Breathlessness" and "Vomiting" toggles only set `mild` or `none`. No UI path produces `severe`. The High-urgency rules that need `breathlessness_level == 'severe'` or `vomiting_severity == 'severe'` can never fire from the UI. Examples: chest pain with severe breathlessness, severe shortness of breath, high fever with severe breathlessness.

3. **Pain type is never set to sharp or dull.** The UI only writes `pain_type` as `dizzy` or `none`, so the sharp-pain rules (stroke, sharp chest pain) can't fire.

4. **Values the model has never seen.** The age option `adult_plus` (41–60) and the pain value `dizzy` are not in the training data. The encoder produces all zeros for them, so the ML prediction is wrong for those inputs, and the code does not flag it.

5. **Rule set doesn't match the documentation.** `clinical_rules.md`, `generate_dataset.py`, and `rule_engine.py` differ. For example, "sharp chest pain with severity > 6 → High" appears in the docs and dataset generator but not in `rule_engine.py`, which requires severe breathlessness instead. `rule_engine.py` also has a "high fever → Moderate" rule that is not documented.

6. **Conflict policy contradicts the README.** The README says conflicts resolve to the "higher urgency." The code always keeps the rule result, even when it is lower than the ML result. The UI labels a conflict as "Uncertain," but the verdict still stands.

### B. Model and evaluation

7. **The 99.8% accuracy is circular.** The training labels come from the same rules the model is meant to check (`generate_dataset.py`). The model only learns to copy the rules, so it adds no independent validation. The "second opinion" framing in the docs is not supported.
8. **The model is XGBoost, not an MLP.** The README and tech stack say "Scikit-learn MLP." The file in `models/` is XGBoost. `train_models.py` also tries Logistic Regression and Random Forest, and the README's `train_model.py` and `triage_mlp.pkl` don't exist.
9. **The dataset is synthetic and balanced by design.** Classes are forced to equal size, and some inputs are generated with logic checks. Real-world performance is unknown.

### C. Security

10. **Path traversal / arbitrary file read.** `GET /download-report/{filename:path}` returns any file the server can read, if the path exists. It should only serve files inside `reports/`.
11. **CORS allows every origin with credentials.** `allow_origins=["*"]` together with `allow_credentials=True` is unsafe. The code comment itself says it should be restricted.
12. **No authentication on API routes.** The README says "Supabase JWT validation on protected routes," but no route checks a token. Anyone can call `/predict`, `/chat`, and the others. The app's "logged in" state is only React state that resets on page refresh.
13. **Login returns the raw Supabase response** to the browser, which may include session tokens. The frontend never uses them.
14. **Chat history is stored in `localStorage` under one key**, `medassist_history`, for every user on that browser. Medical conversations are not encrypted and are not tied to an account.
15. **Unbounded in-memory chat cache.** `chat_cache` in `main.py` grows with every unique message and is never cleared.
16. **Prompt injection risk.** User text is pasted directly into the Groq prompts.

### D. Deployment and dependencies

17. **`requirements.txt` is incomplete.** `decision_layer.py` imports `pandas`, `numpy`, and `joblib`. The model needs `scikit-learn` and `xgboost`. `report_generator.py` imports `fpdf`, which is not listed (the list has `reportlab`, which the code doesn't use). A fresh install of this file will fail on import.
18. **`grok_client.py` raises an error at import time** if `GROQ_API_KEY` is missing, which stops the whole backend from starting. The README's setup uses the variable name `GROK_API_KEY`, which the code does not read.
19. **README project structure is out of date.** It lists `components/`, `hooks/`, `ml_classifier.py`, `llm_pipelines.py`, `pdf_generator.py`, `triage_mlp.pkl`, `clinical_rules.json`, and `train_model.py`. None of these exist in the repo.
20. **The PDF doesn't contain the patient's answers.** The frontend's "Download PDF" calls `GET /report`, which fills every input with "Not Specified." The PDF also has to carry the whole explanation in the URL query string, which can exceed URL length limits.
21. **Hard-coded text in the result screen.** The on-screen report always says "ML model (LOW)." It shows "Score X/10" computed as `confidence × 10`, which is not a clinical score.
22. **Full-page dictionary and medicine views are dead code.** `setView('medicine')` and `setView('dictionary')` are never called. The modals are used instead. The full-page medicine view also reads fields the backend never returns (`overview`, `mechanism`, `dosage_info`).
23. **Frontend structure.** All UI is in one 1,594-line component. `package.json` has an unused `vite-plugin-react` and mixes Vite 2 with React 17 tooling. The commit history is a single commit, so there is no change log.

## 6. Suggested fixes, in priority order

1. Add a button that moves the step from 0 to 1, or route "Start Symptom Analysis" to the in-app triage. Decide whether the external iframe should stay at all.
2. Add a "severe" option for breathlessness and vomiting, and separate sharp and dull pain from the dizziness toggle.
3. Make the frontend and backend use the same category values. Remove or retrain for `adult_plus` and `dizzy`.
4. Reconcile `rule_engine.py`, `clinical_rules.md`, and `generate_dataset.py` so there is one source of truth. Generate the rules from one file.
5. Decide the conflict policy (rule-only, or higher urgency wins) and make the code, README, and UI agree.
6. Restrict `/download-report` to `reports/`, restrict CORS to the frontend domain, and verify Supabase JWTs on protected routes.
7. Fix `requirements.txt` and make `GROQ_API_KEY` optional at import time.
8. Pass the real patient inputs to the PDF, using the existing `POST /generate-report` route or a new one.
9. Update the README to match the code (model type, components, API names, environment variable names).
10. Train on real or clinician-labelled data before claiming any accuracy figure.

## 7. Scope of this review

- Every source file was read: all Python in `backend/` and `scripts/`, all frontend TypeScript and HTML, configs, data files, and docs.
- `App.css` was reviewed by its section headings, not line by line.
- Model files were loaded with scikit-learn and XGBoost to confirm their type and features. The `.pkl` file is the same kind of model as the `.joblib` file.
- Images were not analysed beyond their filenames and the README's captions.
- Nothing was run end to end. The findings come from reading the code, plus the model inspection.
