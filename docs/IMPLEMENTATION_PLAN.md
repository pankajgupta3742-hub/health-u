# Health-U: Implementation Plan and Status

Status key: **Done** (built and tested), **Partial** (built, with a known gap), **Open** (not built).

## Phase 1: Foundations
| Item | Status | Notes |
|---|---|---|
| Project structure, docs, licence removed | Done | No licence file in the project |
| Environment-based configuration (no secrets in code) | Done | `.env.example` lists every variable |
| Database layer, SQLite and PostgreSQL | Done | PostgreSQL 18 tested with `psycopg2-binary`; full test suite passes on both |

## Phase 2: Accounts and triage
| Item | Status | Notes |
|---|---|---|
| Register, sign in, session restore, sign out | Done | Browser-tested |
| Session expiry handling | Done | Browser-tested |
| Account deletion | Done | Fixed PostgreSQL foreign-key order |
| Symptom triage with rule engine | Done | Urgency from rules only |
| LangGraph triage workflow (validate, rules, explain, guard) | Done | Graph tests cover guard and contradictions |
| Triage PDF report | Done | Browser-tested |
| Assessment records (list, delete, PDF) | Done | Browser-tested |
| Data export (download my data) | Done | `GET /api/v1/account/export`; browser-tested |

## Phase 3: Lab reports and assistant
| Item | Status | Notes |
|---|---|---|
| Lab report upload (PDF and .txt), draft review, save | Done | Browser-tested. Conservative matcher; user confirms every value |
| Health assistant (one Gemini call, scope rules, disclaimer) | Partial | Works live. Gemini overload gives a busy message at times (external limit) |
| Medicine and dictionary lookups | Partial | Routes exist; not retested in this audit |

## Phase 4: Public-data disease models
| Item | Status | Notes |
|---|---|---|
| Dataset download, preparation, manifest | Done | `ml/download_data.py` (no-network path tested), `ml/prepare_datasets.py` |
| Six models trained with cross-validation and bootstrap CIs | Done | `ml/train_models.py` |
| Model cards with limitations and measured results | Done | `models/<key>/MODEL_CARD.md` |
| Serving: catalog, detail, card, predictions with validation | Done | 11 API tests |
| Disease models screen | Done | Browser-tested |
| Typhoid label check (Widal titres) | Done | Titres excluded; finding documented |
| Leptospirosis label mapping verified against codebook | Done | |
| External validation and fairness audit | Open | Needed before any claim beyond research |

## Phase 5: Platform hardening
| Item | Status | Notes |
|---|---|---|
| Legacy synthetic ML model off by default | Done | `HEALTHU_ENABLE_LEGACY_ML=1` to enable |
| Browser test suite for all user flows | Done | 8 flows pass (sign-up, triage, PDFs, export, lab upload, sign-out, session expiry). Scripts are in the sandbox, not yet in the repository |
| Hosted frontend configuration | Partial | Set `VITE_API_URL` at build time. Not tested on a hosted domain |
| Automated browser tests in the repository | Open | Scripts exist in the sandbox only |
| Token storage hardening (httpOnly cookies) | Open | Currently localStorage |
| Render deployment verified | Open | `render.yaml` written; not deployed |

## Phase 6: Documentation
| Item | Status | Notes |
|---|---|---|
| README (setup, layout, status) | Done | |
| API reference | Done | `docs/API.md` |
| Concept note | Done | `docs/concept_note.md` |
| Research paper guide | Done | Uses measured results only; the 99.8% claim was removed |
| Integration audit | Done | `docs/INTEGRATION_AUDIT.md` |

## Next steps (in order)
1. Move the browser test scripts into the repository with a short runner note.
2. Decide on token storage (keep localStorage with a short TTL, or move to httpOnly cookies).
3. Deploy the backend and frontend to a hosted environment and test with the public `VITE_API_URL`.
4. Obtain an external validation dataset or cohort before any performance claim.
