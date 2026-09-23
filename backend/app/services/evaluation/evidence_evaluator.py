from typing import List, Dict, Any
from app.core.config import settings

class EvidenceEvaluator:
    def __init__(
        self, 
        relevance_threshold: float = settings.RELEVANCE_THRESHOLD,
        sufficiency_threshold: float = settings.SUFFICIENCY_THRESHOLD
    ):
        self.relevance_threshold = relevance_threshold
        self.sufficiency_threshold = sufficiency_threshold
        
    def evaluate(
        self, 
        query: str, 
        intent: str, 
        retrieved_chunks: List[Dict[str, Any]], 
        attempt_number: int = 1,
        is_out_of_domain: bool = False
    ) -> Dict[str, Any]:
        if is_out_of_domain:
            return {
                "is_relevant": False,
                "is_sufficient": False,
                "coverage_score": 0.0,
                "action": "OUT_OF_DOMAIN",
                "reason": "Query is outside the procedural domain of the GePNIC eProcurement portal."
            }

        if not retrieved_chunks:
            return {
                "is_relevant": False,
                "is_sufficient": False,
                "coverage_score": 0.0,
                "action": "IRRELEVANT_QUERY" if attempt_number >= settings.MAX_RETRIEVAL_ATTEMPTS else "REFINE",
                "reason": "No candidate chunks satisfied the minimum relevance threshold (0.65)."
            }
            
        top_score = retrieved_chunks[0].get("similarity_score", 0.0)
        avg_score = sum(c.get("similarity_score", 0.0) for c in retrieved_chunks) / len(retrieved_chunks)
        
        is_relevant = top_score >= self.relevance_threshold
        
        # Check sufficiency: Does top chunk contain substantive guidance for the intent
        intent_words = set(intent.lower().split())
        top_content = (retrieved_chunks[0].get("question", "") + " " + retrieved_chunks[0].get("answer", "")).lower()
        overlap = sum(1 for w in intent_words if w in top_content)
        intent_coverage = overlap / max(1, len(intent_words))
        
        coverage_score = round(0.7 * top_score + 0.3 * intent_coverage, 4)
        is_sufficient = is_relevant and (coverage_score >= self.sufficiency_threshold)
        
        if is_sufficient:
            action = "PROCEED"
            reason = f"Evidence meets relevance ({top_score:.2f} >= {self.relevance_threshold}) and sufficiency criteria."
        elif attempt_number < settings.MAX_RETRIEVAL_ATTEMPTS:
            action = "REFINE"
            reason = f"Evidence coverage ({coverage_score:.2f}) below experimental threshold ({self.sufficiency_threshold}). Triggering corrective pass."
        else:
            action = "EXHAUSTED"
            reason = "Maximum retrieval attempts reached without reaching sufficiency threshold."
            
        return {
            "is_relevant": is_relevant,
            "is_sufficient": is_sufficient,
            "coverage_score": coverage_score,
            "action": action,
            "reason": reason
        }

evidence_evaluator = EvidenceEvaluator()
