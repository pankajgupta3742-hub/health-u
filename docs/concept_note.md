# Health-U: Concept Note

## What it is
Health-U is a health assessment web application. It helps a person judge how quickly they should seek care, understand a symptom or medicine in plain language, keep a personal record of assessments and lab results, and see how public-data disease models estimate risk. It is an information and triage aid. It does not diagnose.

## Problem
- **Search panic:** a web search for a symptom returns frightening, unranked results with no context.
- **Unsafe generative answers:** a general language model can sound confident and still invent a diagnosis or an urgency level.

## Approach: separate decisions from language
- **Triage urgency** comes only from a deterministic rule engine with named rules (for example, "Potential Cardiac Event"). The language model never sets urgency.
- **Language model (Google Gemini)** writes explanations and answers general health questions. Its replies get a fixed disclaimer added in code. It refuses non-medical questions.
- **Disease models** are trained on public datasets and reported as research prototypes. Each has a model card with its data source, licence, method, measured results, and limitations. Models with too few examples or with no signal above chance are labelled "limited" and must not be used for decisions.
- **Lab reports** are read by a conservative pattern matcher. The user confirms every value before it is saved.

## Who it is for
- Patients who want a structured first check and a record to share with a clinician.
- Students and researchers who want to see how a public-data model was built and where it fails.

## Privacy and safety
- Accounts are protected by signed tokens. Passwords are hashed.
- Users can permanently delete their account and all their data. Data export is planned but not built yet.
- Secrets (the Gemini key and token secret) are read from environment variables and are never committed.
- Limits: this is not a medical device, is not clinically validated, and has not been reviewed by a regulator.

## Status
See `docs/IMPLEMENTATION_PLAN.md` and `docs/INTEGRATION_AUDIT.md` for what is built, tested, and still open.
