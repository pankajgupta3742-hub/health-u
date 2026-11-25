"""Chat logic with Gemini stubbed: one call per turn, refusals, disclaimer, and busy handling. Offline."""
import asyncio

import gemini_client
import grok_client
from conftest import register


def run(coro):
    return asyncio.run(coro)


def test_refusal_from_model_is_returned_without_answer(monkeypatch):
    async def fake(system_instruction, prompt, model=None):
        return {"status": "rejected", "response_type": "conversational", "reply": "", "suggestions": []}
    monkeypatch.setattr(gemini_client, "generate_json", fake)
    monkeypatch.setattr(grok_client.grok_brain, "configured", True)
    r = run(grok_client.grok_brain.classify_and_respond("Who won the cricket world cup?", []))
    assert r["status"] == "rejected"
    assert "cannot answer" in r["reply"]


def test_allowed_answer_gets_disclaimer_and_three_suggestions(monkeypatch):
    async def fake(system_instruction, prompt, model=None):
        return {"status": "allowed", "response_type": "structured", "reply": "**OVERVIEW**\n- Fever",
                "suggestions": ["a", "b", "c", "d"]}
    monkeypatch.setattr(gemini_client, "generate_json", fake)
    monkeypatch.setattr(grok_client.grok_brain, "configured", True)
    r = run(grok_client.grok_brain.classify_and_respond("What is dengue?", []))
    assert r["status"] == "allowed"
    assert r["reply"].endswith(grok_client.DISCLAIMER)
    assert len(r["suggestions"]) == 3


def test_busy_service_gives_friendly_message(monkeypatch):
    async def fake(system_instruction, prompt, model=None):
        raise gemini_client.GeminiError("All Gemini models failed. Last error: 503 UNAVAILABLE")
    monkeypatch.setattr(gemini_client, "generate_json", fake)
    monkeypatch.setattr(grok_client.grok_brain, "configured", True)
    r = run(grok_client.grok_brain.classify_and_respond("What is dengue?", []))
    assert r["status"] == "rate_limited"
    assert "high demand" in r["reply"]


def test_not_configured_reports_error_without_calling_gemini(monkeypatch, client):
    monkeypatch.setattr(grok_client.grok_brain, "configured", False)
    h = {"Authorization": f"Bearer {register(client, 'chatoff@example.com')['access_token']}"}
    r = client.post("/api/v1/chat", json={"message": "What is dengue?"}, headers=h)
    assert r.status_code == 200
    assert r.json()["reply"] == grok_client.NOT_CONFIGURED_REPLY
    assert "GEMINI_API_KEY" in r.json()["reply"]
