"""One-command setup for Health-U on Windows, macOS and Linux. Works from VS Code or any terminal.

    python scripts/setup.py              # Python venv + packages, frontend packages, config files
    python scripts/setup.py --skip-node  # backend only

What it does (safe to run again; it never overwrites an existing backend/.env):
  1. Checks Python 3.11 or newer.
  2. Creates backend/.venv and installs backend/requirements.txt into it.
  3. Creates backend/.env from backend/.env.example with a generated JWT_SECRET.
  4. Creates frontend/.env from frontend/.env.example.
  5. Runs npm install in frontend/ when Node.js is available.
"""
import os
import secrets
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")
VENV = os.path.join(BACKEND, ".venv")
IS_WINDOWS = os.name == "nt"


def say(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def venv_python() -> str:
    return os.path.join(VENV, "Scripts" if IS_WINDOWS else "bin", "python.exe" if IS_WINDOWS else "python")


def run(cmd: list[str], cwd: str) -> None:
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def check_python() -> None:
    if sys.version_info < (3, 11):
        sys.exit(f"Python 3.11 or newer is required. You have {sys.version.split()[0]}. "
                 "Install a newer Python from https://www.python.org/downloads/ and run setup again.")
    print(f"Python {sys.version.split()[0]} OK")


def setup_backend() -> None:
    say("Backend: creating backend/.venv and installing packages (a few minutes the first time)")
    if not os.path.exists(venv_python()):
        run([sys.executable, "-m", "venv", VENV], cwd=BACKEND)
    py = venv_python()
    run([py, "-m", "pip", "install", "--upgrade", "pip"], cwd=BACKEND)
    run([py, "-m", "pip", "install", "-r", "requirements.txt"], cwd=BACKEND)


def copy_env(example: str, target: str, label: str) -> bool:
    if os.path.exists(target):
        print(f"{label} already exists; left unchanged.")
        return False
    with open(example, "r", encoding="utf-8") as fh:
        text = fh.read()
    lines = []
    for line in text.splitlines():
        if line.startswith("JWT_SECRET="):
            line = f"JWT_SECRET={secrets.token_urlsafe(48)}"
        elif line.startswith("GEMINI_API_KEY="):
            # The example holds a placeholder. Leave it empty: the chatbot then says it is not configured.
            line = "GEMINI_API_KEY="
        lines.append(line)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass  # Windows ignores POSIX permissions
    print(f"Created {label}.")
    return True


def setup_config() -> None:
    say("Configuration files")
    copy_env(os.path.join(BACKEND, ".env.example"), os.path.join(BACKEND, ".env"), "backend/.env")
    copy_env(os.path.join(FRONTEND, ".env.example"), os.path.join(FRONTEND, ".env"), "frontend/.env")


def setup_frontend() -> None:
    npm = shutil.which("npm")
    if not npm:
        print("\nNode.js (npm) was not found. Install Node.js 20 or newer from https://nodejs.org/ "
              "and run this script again. The backend is already set up.")
        return
    say("Frontend: npm install")
    run([npm, "install"], cwd=FRONTEND)


def gemini_key_set() -> bool:
    path = os.path.join(BACKEND, ".env")
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("GEMINI_API_KEY="):
                return bool(line.split("=", 1)[1].strip())
    return False


def main() -> None:
    skip_node = "--skip-node" in sys.argv
    check_python()
    setup_backend()
    setup_config()
    if not skip_node:
        setup_frontend()
    say("Setup finished")
    if not gemini_key_set():
        print("\n!! The chatbot is OFF until you add a Gemini key:")
        print("   1. Get a free key at https://aistudio.google.com/apikey")
        print("   2. Open backend/.env and set   GEMINI_API_KEY=your-key   (no quotes, no spaces)")
        print("   3. Stop the API task and run 'Run Health-U (API + web app)' again.")
    print("Next: in VS Code, run the task 'Run Health-U (API + web app)'.")
    print("Then open http://localhost:3015 in your browser.")


if __name__ == "__main__":
    main()
