"""Health-U API entry point.

Run from the backend/ directory:  uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.db import init_db
from app.routers import account, assessments, assistant, auth, documents, missing_data, predictions

app = FastAPI(
    title="Health-U API",
    version="2.0.0",
    description="Symptom triage, assistant, report extraction and PDF reports. Not a diagnostic service.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # Bearer tokens are sent in headers, not cookies, so credentials are not needed.
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

init_db()

for r in (auth.router, assessments.router, documents.router, assistant.router, account.router, predictions.router,
          missing_data.router):
    app.include_router(r)


@app.get("/api/v1/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "health-u", "version": app.version}
