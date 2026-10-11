"""
Evidence Evaluator Module
=========================
Evaluates retrieved candidate chunks against the user's intent to determine if:
1. The evidence is statistically relevant (exceeds semantic similarity threshold).
2. The evidence is sufficient (contains substantive keywords answering the intent).
3. The RAG pipeline should PROCEED to answer generation, REFINE the search query,
   or flag the query as OUT_OF_DOMAIN / IRRELEVANT.
"""

from typing import List, Dict, Any
from app.core.config import settings


class EvidenceEvaluator:
    """
    Evaluates retrieval quality dynamically to guard against hallucination.
    Decides whether the retrieved documents provide enough factual backing
    before feeding them into the Large Language Model.
    """

    def __init__(
        self, 
        relevance_threshold: float = settings.RELEVANCE_THRESHOLD,
        sufficiency_threshold: float = settings.SUFFICIENCY_THRESHOLD
    ):
        # Minimum cosine/dot similarity score required for the top retrieved chunk (e.g., 0.65)
        self.relevance_threshold = relevance_threshold
        # Combined score threshold (relevance + lexical coverage) to allow answer generation (e.g., 0.70)
        self.sufficiency_threshold = sufficiency_threshold
        
    def evaluate(
        self, 
        query: str, 
        intent: str, 
        retrieved_chunks: List[Dict[str, Any]], 
        attempt_number: int = 1,
        is_out_of_domain: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluate candidate evidence chunks against the query and intent.
        
        Args:
            query: The raw question asked by the user.
            intent: The parsed operational intent (e.g., 'DSC token configuration').
            retrieved_chunks: List of retrieved chunks with similarity scores.
            attempt_number: Current iteration (1, 2, etc.) of the retrieval loop.
            is_out_of_domain: Whether query classifier marked this outside GePNIC.
            
        Returns:
            Dict containing:
            - is_relevant: bool
            - is_sufficient: bool
            - coverage_score: float (0.0 to 1.0)
            - action: 'PROCEED' | 'REFINE' | 'EXHAUSTED' | 'OUT_OF_DOMAIN' | 'IRRELEVANT_QUERY'
            - reason: Human-readable diagnostic message explaining the decision.
        """
        # Step 1: Check if the user query was already classified as out-of-domain
        if is_out_of_domain:
            return {
                "is_relevant": False,
                "is_sufficient": False,
                "coverage_score": 0.0,
                "action": "OUT_OF_DOMAIN",
                "reason": "Query is outside the procedural domain of the GePNIC eProcurement portal."
            }

        # Step 2: Check if any chunks matched the role & threshold filters
        if not retrieved_chunks:
            return {
                "is_relevant": False,
                "is_sufficient": False,
                "coverage_score": 0.0,
                # If we still have retry attempts left, ask pipeline to refine query; otherwise mark irrelevant
                "action": "IRRELEVANT_QUERY" if attempt_number >= settings.MAX_RETRIEVAL_ATTEMPTS else "REFINE",
                "reason": f"No candidate chunks satisfied the minimum relevance threshold ({self.relevance_threshold})."
            }
            
        # Top chunk's dense embedding similarity score
        top_score = retrieved_chunks[0].get("similarity_score", 0.0)
        
        # Check relevance: Top chunk must meet or exceed minimum threshold
        is_relevant = top_score >= self.relevance_threshold
        
        # Step 3: Check Sufficiency (Intent Overlap)
        # Verify if the top retrieved chunk contains actual keywords addressing the user's intent
        intent_words = set(intent.lower().split())
        top_content = (retrieved_chunks[0].get("question", "") + " " + retrieved_chunks[0].get("answer", "")).lower()
        overlap = sum(1 for w in intent_words if w in top_content)
        intent_coverage = overlap / max(1, len(intent_words))
        
        # Step 4: Calculate Weighted Coverage Score
        # 70% weight on dense semantic vector similarity + 30% weight on intent keyword overlap
        coverage_score = round(0.7 * top_score + 0.3 * intent_coverage, 4)
        is_sufficient = is_relevant and (coverage_score >= self.sufficiency_threshold)
        
        # Step 5: Determine next pipeline action
        if is_sufficient:
            # Evidence is strong enough; proceed to LLM generation
            action = "PROCEED"
            reason = f"Evidence meets relevance ({top_score:.2f} >= {self.relevance_threshold}) and sufficiency criteria."
        elif attempt_number < settings.MAX_RETRIEVAL_ATTEMPTS:
            # Evidence is insufficient but attempts remain; trigger a query refinement pass
            action = "REFINE"
            reason = f"Evidence coverage ({coverage_score:.2f}) below threshold ({self.sufficiency_threshold}). Triggering corrective pass."
        else:
            # Exhausted all retrieval retry attempts without passing sufficiency
            action = "EXHAUSTED"
            reason = "Maximum retrieval attempts reached without reaching sufficiency threshold."
            
        return {
            "is_relevant": is_relevant,
            "is_sufficient": is_sufficient,
            "coverage_score": coverage_score,
            "action": action,
            "reason": reason
        }


# Singleton instance for easy import across the application
evidence_evaluator = EvidenceEvaluator()

