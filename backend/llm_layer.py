import json
import gemini_client

ADVICE_REPO = {
    "chest_pain": {
        "First Aid": "Stop all physical activity. Sit or lie down in a comfortable position. If pain is sharp and severe, seek emergency help.",
        "Medicine": "Do not take any medication unless directed by emergency services or a doctor."
    },
    "shortness_of_breath": {
        "First Aid": "Sit upright. Avoid lying flat. Try pursed-lip breathing. Use your rescue inhaler if you have asthma/COPD.",
        "Medicine": "Use prescribed inhaled medications only."
    },
    "fever": {
        "First Aid": "Stay hydrated. Tepid sponge baths may help. Rest in a cool, well-ventilated room.",
        "Medicine": "Standard antipyretics (like Acetaminophen/Paracetamol) as per dosage guidelines."
    },
    "abdominal_pain": {
        "First Aid": "Rest in a position of comfort. Avoid solid foods until the pain subsides. Sips of clear fluids are okay.",
        "Medicine": "Avoid pain killers that might mask appendicitis symptoms until evaluated."
    },
    "headache": {
        "First Aid": "Rest in a quiet, dark room. Apply a cool compress to the forehead.",
        "Medicine": "Over-the-counter pain relief as per instructions."
    },
    "default": {
        "First Aid": "Monitor symptoms closely and rest.",
        "Medicine": "Consult a pharmacist for general symptoms."
    }
}

EXPLANATION_SYSTEM_PROMPT = """You are the explanation writer for Health-U, a clinical TRIAGE tool (not a diagnosis tool).
The urgency level has ALREADY been decided by a deterministic rule engine. You must:
- Never change, question, or re-decide the urgency level.
- Explain the decision in plain language for a patient, referring to the matching rule.
- Keep it short (2-4 sentences). No diagnosis, no prescriptions, no dosages.
Respond ONLY in JSON: {"narrative": "...", "recommendation": "..."}"""


class LLMLayer:
    def __init__(self):
        pass

    def generate_explanation(self, data, decision):
        """
        Uses Google Gemini to write the narrative and next-step recommendation.
        The urgency level always comes from the rule engine. First-aid and medicine
        text comes from the fixed ADVICE_REPO table for safety. If Gemini is not
        configured or fails, the fixed template below is used instead.
        """
        fallback = self._template_explanation(data, decision)
        if not gemini_client.is_configured():
            return fallback
        try:
            advice = ADVICE_REPO.get(data.get('primary_symptom'), ADVICE_REPO['default'])
            prompt = (
                f"Urgency (decided by rules, do not change): {decision['final_urgency']}\n"
                f"Matching rule: {decision['rule_output']['matching_rule']}\n"
                f"Rule logic: {decision['rule_output']['logic']}\n"
                f"Patient inputs: {json.dumps(data)}"
            )
            ai = gemini_client.generate_json_sync(EXPLANATION_SYSTEM_PROMPT, prompt)
            narrative = ai.get("narrative") or fallback["narrative"]
            recommendation = ai.get("recommendation") or fallback["recommendation"]
            return {
                "narrative": narrative,
                "recommendation": recommendation,
                "first_aid": advice["First Aid"],
                "medicine_info": advice["Medicine"],
            }
        except Exception as e:
            print(f"Gemini explanation failed, using template: {e}")
            return fallback

    def _template_explanation(self, data, decision):
        urgency = decision['final_urgency']
        rule_name = decision['rule_output']['matching_rule']
        symptom_key = data.get('primary_symptom', 'default')
        symptom_name = symptom_key.replace('_', ' ')
        severity = data.get('severity_score', 0)
        
        advice = ADVICE_REPO.get(symptom_key, ADVICE_REPO['default'])
        
        base_intro = f"Based on our structured clinical analysis, your situation is classified as **{urgency} Urgency**."
        
        if urgency == "High":
            explanation = (
                f"{base_intro} The clinical assessment flagged **{rule_name}**. "
                f"Your report of {symptom_name} with high severity ({severity}/10) requires immediate professional evaluation."
            )
            next_steps = "URGENT: Proceed to the nearest Emergency Room or call 911/emergency services immediately."
        elif urgency == "Moderate":
            explanation = (
                f"{base_intro} The clinical assessment identified **{rule_name}**. "
                f"While not an immediate life-threat, your symptoms suggest that you should be evaluated by a professional soon."
            )
            next_steps = "Contact your General Practitioner or visit Urgent Care within the next 24 hours."
        else:
            explanation = (
                f"{base_intro} Your condition matches the **{rule_name}** category. "
                f"Indicators suggest this situation can be managed with monitoring and routine care."
            )
            next_steps = "Monitor symptoms. Schedule a non-emergency appointment if symptoms persist for > 48 hours."

        return {
            "narrative": explanation,
            "recommendation": next_steps,
            "first_aid": advice["First Aid"],
            "medicine_info": advice["Medicine"]
        }
