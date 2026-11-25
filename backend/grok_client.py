"""Health assistant brain for Health-U (name kept for compatibility with the routers).

One Gemini call per chat turn. The model returns JSON with a status (allowed or rejected), a reply,
and suggestions. An earlier version made two sequential calls (classify, then answer). That doubled
the chance of a busy-model failure, so the two steps were merged.

Safety rules that stay in code, not in the model's hands:
- The assistant never sets urgency. The rule engine does that for triage. Chat replies are text only.
- Replies to non-medical questions are refused.
- The disclaimer is added in code, so the model cannot drop it.
"""
import json

import gemini_client

DISCLAIMER = ("DISCLAIMER: This information is for educational purposes. "
              "Please consult a qualified physician for a formal diagnosis.")
REFUSAL = ("I am a dedicated medical clinical support system. I only provide assistance with symptoms, "
           "diseases, medications, and medical education. I cannot answer queries about non-medical topics.")
ERROR_REPLY = "I'm having trouble connecting. Please try again later."
NOT_CONFIGURED_REPLY = ("The chat assistant is not set up yet. Add your GEMINI_API_KEY to backend/.env "
                        "(free key at https://aistudio.google.com/apikey), then restart the API.")
BUSY_REPLY = "Health-U is currently experiencing high demand. Try again in a moment."

SYSTEM_PROMPT = """You are the Health-U clinical support assistant. You give general health education.

RULES
1. Scope: answer only medical questions (symptoms, diseases, medicines, treatment, first aid, prevention, medical education). If the question is not medical, set "status" to "rejected" and leave "reply" empty.
2. You do not diagnose, prescribe doses for a specific person, or say how urgent someone's condition is. Describe conditions in general terms and advise seeing a clinician.
3. Emergencies (chest pain, stroke signs, severe bleeding, trouble breathing, unconsciousness, seizure, suicidal intent): set "response_type" to "emergency". Keep the reply short and tell the user to call local emergency services now (108 in India, 112 or 911 elsewhere).
4. "structured" for explain/how/treatment/causes questions: use 4 or more bold section headers with bullet points.
5. "conversational" for short questions and greetings: a warm, clear answer, no headers.
6. Write in plain language. Do not invent statistics, study names, or dates.
7. Give exactly 3 short follow-up questions in "suggestions".

Return only JSON:
{"status": "allowed" | "rejected", "response_type": "emergency" | "structured" | "conversational", "reply": "...", "suggestions": ["...", "...", "..."]}
"""


class GrokBrain:
    def __init__(self):
        # Does not raise when the key is missing: the app still starts and chat returns a friendly error.
        self.configured = gemini_client.is_configured()
        if not self.configured:
            print("WARNING: GEMINI_API_KEY is not set. The chat assistant will reply with setup instructions.")

    async def classify_and_respond(self, query: str, history: list | None = None) -> dict:
        history = history or []
        if not self.configured:
            return {"reply": NOT_CONFIGURED_REPLY, "suggestions": [], "status": "not_configured"}

        # Drop the new message from history if it was already appended by the client.
        latest = None if (history and history[-1].get("content") == query) else query
        contents = gemini_client.to_contents(history[-6:], latest)
        try:
            data = await gemini_client.generate_json(SYSTEM_PROMPT, contents)
        except gemini_client.GeminiError as e:
            busy = gemini_client.is_busy_text(str(e))
            print(f"Gemini Error: {e}")
            if busy:
                return {"reply": BUSY_REPLY, "suggestions": [], "status": "rate_limited"}
            return {"reply": ERROR_REPLY, "suggestions": [], "status": "error"}

        if not isinstance(data, dict):
            return {"reply": ERROR_REPLY, "suggestions": [], "status": "error"}
        if str(data.get("status", "")).lower() == "rejected":
            return {"reply": REFUSAL, "suggestions": [], "status": "rejected"}

        reply = str(data.get("reply", "")).strip()
        if not reply:
            return {"reply": ERROR_REPLY, "suggestions": [], "status": "error"}
        if not reply.endswith(DISCLAIMER):
            reply = f"{reply}\n\n{DISCLAIMER}"
        suggestions = [str(s) for s in (data.get("suggestions") or []) if str(s).strip()][:3]
        return {"reply": reply, "suggestions": suggestions, "status": "allowed",
                "response_type": data.get("response_type", "conversational")}


grok_brain = GrokBrain()
