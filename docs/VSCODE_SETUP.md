# Run Health-U in VS Code

This guide sets up the whole project (backend API, web app, tests) in Visual Studio Code.
Setup is one task. Running the app is one task. You do not need to type commands by hand.

## 1. Install the prerequisites

| Tool | Version | Check with |
|---|---|---|
| Python | 3.11 or newer (3.13 tested) | `python3 --version` (Windows: `py -3 --version`) |
| Node.js | 20 or newer (20.x tested) | `node --version` |
| VS Code | latest | — |

No database server is needed. The app uses SQLite by default and creates `backend/healthu.db` on first start.
The first setup downloads about 1 GB of Python packages (scikit-learn, XGBoost, pandas). Allow a few minutes on a good connection.

## 2. Open the workspace

1. Open VS Code.
2. **File → Open Workspace from File…** and choose `health-u.code-workspace` in the project root.
3. When VS Code asks to install recommended extensions, click **Install**: Python, Pylance, Python Debugger.

The Explorer then shows four folders: **Health-U**, **Backend (API)**, **Frontend (web)** and **Docs**.

## 3. Set up everything (one time)

1. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS).
2. Choose **Tasks: Run Task → 0. Set up everything (first time only)**.
3. Wait until the terminal says `Setup finished`.

This single task:

- creates `backend/.venv` and installs the Python packages,
- creates `backend/.env` from `backend/.env.example`, with a random `JWT_SECRET` already filled in,
- creates `frontend/.env`,
- runs `npm install` in `frontend/`.

It is safe to run again. It never overwrites an existing `backend/.env`.

**Optional, to enable the chatbot:** open `backend/.env` and set `GEMINI_API_KEY` to a free key from https://aistudio.google.com/apikey. Without it, the app works, and the chatbot replies with setup instructions.

**Select the Python interpreter:** press `Ctrl+Shift+P` → **Python: Select Interpreter** → choose `backend/.venv`. The editor's checks and the test runner then use the same packages.

## 4. Run the app

**Option A — one command (recommended)**

Run **Tasks: Run Task → Run Health-U (API + web app)**. Two terminal panels open: one for the API, one for the web app.

**Option B — from the Run and Debug panel**

Press `Ctrl+Shift+D`, choose **Run Health-U (API + web app)**, press F5.

**Option C — separately**

- **Run Task → Start API (backend, port 8000)**
- **Run Task → Start web app (frontend, port 3015)**

**Open the app:** go to **http://localhost:3015**.

The web app sends its `/api` requests to the API on port 8000 automatically, so there is nothing else to configure.

**Stop the app:** click the trash icon on the task panel, or press `Ctrl+C` in its terminal.

## 5. Test and debug

- **Run backend tests:** **Run Task → Run backend tests (pytest)**. Expected: all 117 tests pass.
- You can also open the **Testing** panel (flask icon). Pytest is already configured for `backend/tests`.
- **Debug the API:** Run and Debug panel → **Debug: API (backend)** → F5. Breakpoints in `backend/app/` work.
- **Check the frontend builds:** **Run Task → Build frontend (type-check + production build)**.

## 6. Troubleshooting

| Problem | What to do |
|---|---|
| "Interpreter not found" or missing packages | Run **0. Set up everything** again, then select `backend/.venv` as the interpreter. |
| "Port 8000 is already in use" or "Port 3015 is already in use" | Stop the old run (trash icon on its task, or close its terminal), then start again. |
| Setup says "No space left on device" | The Python packages need about 1 GB. Free disk space, then run the setup task again. |
| Setup fails with "ensurepip is not available" (Linux) | Install the venv package, for example `sudo apt install python3-venv`, then run the setup task again. |
| Setup says "npm was not found" | Install Node.js 20 or newer from https://nodejs.org/, then run the setup task again. The backend is already set up. |
| Sign-in works but the app says "Your session ended" | `JWT_SECRET` changed or the database was reset. Sign in again. |
| Chatbot says it is not configured | Add `GEMINI_API_KEY` to `backend/.env`, then restart the API task. |
| Chatbot is slow or says "high demand" | The free Gemini tier is busy. Replies can take 30–60 seconds at busy times. Wait and try again. |
| Medicine or dictionary lookup fails | These use Gemini too. Same fix as the chatbot. |
| Tests fail with "SimpleImputer has no attribute _fill_dtype" | The scikit-learn version is wrong. Run the setup task again so the pinned `scikit-learn==1.6.1` is installed. |
| Windows: "running scripts is disabled" | You do not need to activate the environment. The tasks call `.venv\Scripts\python.exe` directly. |

## 7. Project layout

| Folder | What it contains |
|---|---|
| `backend/app/` | API code: routes, security, database models, triage and prediction services |
| `backend/tests/` | Backend tests (run with pytest) |
| `backend/.env` | Your local secrets and settings. Created by setup. Not in git. Never share it. |
| `frontend/src/` | React web app (components in `src/components/`) |
| `models/` | Trained disease models served by the API (read-only at runtime) |
| `scripts/setup.py` | The one-command setup used by the VS Code task |
| `docs/` | Project documentation |
| `.vscode/` | Tasks, debug settings, test settings and recommended extensions for VS Code |

`JWT_SECRET` must stay the same between restarts. If it changes, every saved sign-in is rejected.
