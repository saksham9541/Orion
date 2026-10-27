import json
import re
from railopt.models import DefectSeverity, DefectCategory
from genai.llm_mixin import GeminiMixin

class DefectTextClassifier(GeminiMixin):
    """Classifies unstructured defect remarks."""
    def __init__(self, use_llm: bool = True):
        self._init_llm(use_llm=use_llm, model="gemini-2.5-flash")
        # Keep backward-compat attribute
        self.has_genai = self.llm_available
            
    def classify(self, text: str, use_llm: bool = True) -> dict:
        """Extract information from text."""
        if use_llm and self.has_genai:
            try:
                return self._classify_llm(text)
            except Exception:
                # Fallback on failure
                return self._classify_fallback(text)
        return self._classify_fallback(text)
        
    def _classify_llm(self, text: str) -> dict:
        all_categories = ', '.join(c.value for c in DefectCategory)
        prompt = f"""
        Analyze the following railway maintenance inspector remark.
        Extract:
        1. severity (EMERGENCY, HIGH, MEDIUM, LOW)
        2. defect_category (must be one of: {all_categories})
        3. action_taken (string)
        4. requires_followup (boolean)
        
        Remark: "{text}"
        
        Respond in pure JSON format:
        {{"severity": "...", "defect_category": "...", "action_taken": "...", "requires_followup": true/false}}
        """
        response = self._llm_generate(prompt, max_tokens=200)
        if not response:
            return self._classify_fallback(text)

        content = response.strip()
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
            
        parsed = json.loads(content)
        
        valid_cats = {c.value for c in DefectCategory}
        if parsed.get("defect_category") not in valid_cats:
            fallback = self._classify_fallback(text)
            parsed["defect_category"] = fallback["defect_category"]
            
        return parsed
        
    def _classify_fallback(self, text: str) -> dict:
        text_lower = text.lower()
        
        severity = DefectSeverity.LOW.value
        if any(w in text_lower for w in ["emergency", "fracture", "broken", "derailment", "immediate"]):
            severity = DefectSeverity.EMERGENCY.value
        elif any(w in text_lower for w in ["high", "urgent", "critical"]):
            severity = DefectSeverity.HIGH.value
        elif any(w in text_lower for w in ["medium", "soon"]):
            severity = DefectSeverity.MEDIUM.value
            
        defect_category = DefectCategory.GAUGE_IRREGULARITY.value
        if "rail" in text_lower and "fracture" in text_lower:
            defect_category = DefectCategory.RAIL_FRACTURE.value
        elif "signal" in text_lower and "fail" in text_lower:
            defect_category = DefectCategory.SIGNAL_FAILURE.value
        elif "ohe" in text_lower and "break" in text_lower:
            defect_category = DefectCategory.OHE_BREAK.value
            
        return {
            "severity": severity,
            "defect_category": defect_category,
            "action_taken": "Unknown",
            "requires_followup": "followup" in text_lower or "check again" in text_lower
        }
