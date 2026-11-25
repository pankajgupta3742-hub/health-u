from dotenv import load_dotenv
import gemini_client

load_dotenv()


class ExtrasClient:
    """Medicine and dictionary lookups, powered by Google Gemini."""

    async def get_dictionary_definition(self, term: str):
        prompt = f"""
        TERM: "{term}"
        
        TASK: Provide a comprehensive medical dictionary entry.
        
        RULES:
        - Be accurate and professional.
        - If the term is NOT a medical/clinical term, return {{"error": "This tool only defines medical terminology. Please enter a valid medical term."}}
        - Provide 3 related medical terms as suggestions.
        
        Return JSON:
        {{
            "term": "{term}",
            "phonetic": "...",
            "simple_definition": "...",
            "clinical_definition": "...",
            "context": "...",
            "related_terms": ["...", "...", "..."]
        }}
        """
        try:
            return await gemini_client.generate_json(
                "You are a professional medical lexicographer. You ONLY define medical and clinical terms. Respond ONLY in valid JSON.",
                prompt,
            )
        except Exception as e:
            print(f"Dictionary Error: {e}")
            return {"error": "Could not retrieve definition"}

    async def get_medicine_info(self, medicine: str):
        prompt = f"""
        QUERY: "{medicine}"
        
        IMPORTANT RULE: You are a strict medical pharmacist assistant.
        - ONLY answer if the query is a medicine, drug, supplement, or pharmaceutical product name.
        - If the query is NOT a medicine/drug name (e.g., food, animal, person, place, general question), 
          return {{"error": "This tool only provides information about medicines and drugs. Please enter a valid medicine or drug name."}}
        
        If it IS a medicine, provide this structured JSON:
        {{
            "medicine": "<official medicine name>",
            "subtitle": "<generic name and typical dose, e.g., Paracetamol 650mg>",
            "description": "<1-2 sentence overview of what this medicine is>",
            "uses": ["<use 1>", "<use 2>", "<use 3>"],
            "side_effects": ["<side effect 1>", "<side effect 2>", "<side effect 3>"],
            "precautions": ["<precaution 1>", "<precaution 2>", "<precaution 3>"],
            "warnings": ["<warning 1>", "<warning 2>"],
            "tags": ["<brand name tag>", "<generic name tag>"],
            "related_medicines": ["<alt 1>", "<alt 2>", "<alt 3>"]
        }}
        """
        try:
            return await gemini_client.generate_json(
                "You are a senior clinical pharmacist. You ONLY answer questions about medicines, drugs and pharmaceuticals. For non-medicine queries, return an error JSON. Respond ONLY in valid JSON.",
                prompt,
            )
        except Exception as e:
            print(f"Medicine Info Error: {e}")
            return {"error": "Could not retrieve medicine information"}


extras_client = ExtrasClient()
