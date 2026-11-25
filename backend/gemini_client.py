"""Shared Google Gemini client for Health-U.

- The API key is read from GEMINI_API_KEY (environment or backend/.env). It is never hard-coded.
- Calls try GEMINI_MODEL first, then the fallback models, because free-tier models often return
  503 "high demand". Each model gets a short retry on 429/503 before the next one is tried.
- Every AI feature uses this module, so the fallback and error handling apply everywhere.
"""
import asyncio
import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.config import BACKEND_DIR

load_dotenv(os.path.join(BACKEND_DIR, ".env"), override=False)

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
FALLBACK_MODELS = [m.strip() for m in os.getenv(
    "GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite").split(",") if m.strip()]
ATTEMPTS_PER_MODEL = 2
BACKOFF_SECONDS = (2, 6)
REQUEST_TIMEOUT_MS = 15_000
PASSES = 2
PASS_PAUSE_SECONDS = 4
TOTAL_BUDGET_SECONDS = 50  # hard cap across all models and retries, so users never wait minutes


class GeminiError(Exception):
    """Raised when Gemini is not configured, or no model returned a usable answer."""


def _build_client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))


client = _build_client()


def is_configured() -> bool:
    return client is not None


def is_rate_limited(error: Exception) -> bool:
    text = str(error).upper()
    return "429" in text or "RESOURCE_EXHAUSTED" in text


def is_quota_exhausted(error: Exception) -> bool:
    text = str(error).upper()
    return "RESOURCE_EXHAUSTED" in text or "QUOTA" in text


def is_busy_text(text: str) -> bool:
    upper = text.upper()
    return "429" in upper or "RESOURCE_EXHAUSTED" in upper or "503" in upper or "UNAVAILABLE" in upper or "DEADLINE" in upper


def is_busy(error: Exception) -> bool:
    text = str(error).upper()
    return is_rate_limited(error) or "503" in text or "UNAVAILABLE" in text or "DEADLINE" in text


def model_chain(preferred: str | None = None) -> list[str]:
    chain: list[str] = []
    for name in [preferred or DEFAULT_MODEL, *FALLBACK_MODELS]:
        if name and name not in chain:
            chain.append(name)
    return chain


def to_contents(history, latest_user_message=None):
    """Convert chat history ([{role: 'user'|'ai', content: str}]) into Gemini contents ('ai' -> 'model')."""
    contents = []
    for msg in history or []:
        role = "model" if msg.get("role") == "ai" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg.get("content", ""))]))
    if latest_user_message is not None:
        contents.append(types.Content(role="user", parts=[types.Part(text=latest_user_message)]))
    return contents


def _parse(response) -> dict:
    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise GeminiError("Empty response from Gemini")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise GeminiError(f"Gemini returned invalid JSON: {e}")


def _config(system_instruction: str) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(system_instruction=system_instruction, response_mime_type="application/json")


async def generate_json(system_instruction: str, prompt, model: str = None) -> dict:
    """Async call that returns parsed JSON. `prompt` is a string or a list of contents.

    Makes up to PASSES passes over the model chain. A pass is skipped once the total budget is used.
    """
    if client is None:
        raise GeminiError("GEMINI_API_KEY is not set")
    last_error: Exception | None = None
    started = time.monotonic()
    for pass_no in range(PASSES):
        for name in model_chain(model):
            for attempt in range(ATTEMPTS_PER_MODEL):
                if time.monotonic() - started > TOTAL_BUDGET_SECONDS:
                    raise GeminiError(f"Gemini did not respond within {TOTAL_BUDGET_SECONDS}s. Last error: {str(last_error)[:160]}")
                try:
                    response = await client.aio.models.generate_content(
                        model=name, contents=prompt, config=_config(system_instruction))
                    return _parse(response)
                except GeminiError:
                    raise
                except Exception as e:  # network, quota, overload, or model-not-found
                    last_error = e
                    if is_quota_exhausted(e) or not is_busy(e):
                        break  # quota is per model: retrying the same model only wastes time
                    if attempt < ATTEMPTS_PER_MODEL - 1:
                        await asyncio.sleep(BACKOFF_SECONDS[attempt])
        if time.monotonic() - started > TOTAL_BUDGET_SECONDS - PASS_PAUSE_SECONDS:
            break
        await asyncio.sleep(PASS_PAUSE_SECONDS)  # the service is overloaded: give it a moment
    raise GeminiError(f"All Gemini models failed. Last error: {str(last_error)[:200]}")


def generate_json_sync(system_instruction: str, prompt, model: str = None) -> dict:
    """Synchronous version of generate_json (used by the triage explanation)."""
    if client is None:
        raise GeminiError("GEMINI_API_KEY is not set")
    last_error: Exception | None = None
    started = time.monotonic()
    for name in model_chain(model):
        for attempt in range(ATTEMPTS_PER_MODEL):
            if time.monotonic() - started > TOTAL_BUDGET_SECONDS:
                raise GeminiError(f"Gemini did not respond within {TOTAL_BUDGET_SECONDS}s. Last error: {str(last_error)[:160]}")
            try:
                response = client.models.generate_content(
                    model=name, contents=prompt, config=_config(system_instruction))
                return _parse(response)
            except GeminiError:
                raise
            except Exception as e:
                last_error = e
                if is_quota_exhausted(e) or not is_busy(e):
                    break  # quota is per model: retrying the same model only wastes time
                if attempt < ATTEMPTS_PER_MODEL - 1:
                    time.sleep(BACKOFF_SECONDS[attempt])
    raise GeminiError(f"All Gemini models failed. Last error: {str(last_error)[:200]}")
