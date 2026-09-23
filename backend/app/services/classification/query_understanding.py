import re
from typing import Dict, Any, List
from app.services.embedding.embedding_service import embedding_service
import numpy as np

# Canonical category definitions & anchor descriptions from dissertation
CATEGORY_DESCRIPTIONS = {
    "Technical Assistance": (
        "Issues related to Digital Signature Certificate DSC token detection, drivers, "
        "Java Runtime Environment JRE configuration, browser settings, operating system, and hardware requirements."
    ),
    "Tender & Bid Information": (
        "Information regarding active tenders, tender notices, bid submission, EMD fee payment, "
        "Bill of Quantities BOQ, corrigendum, covers, packets, and exemption policies."
    ),
    "Portal Usage & User Management": (
        "Bidder enrollment, user registration, account login, password reset, profile management, "
        "and portal navigation."
    ),
    "Security Information": (
        "Encryption standards, digital signature validity, certifying authorities CA, "
        "bid tampering prevention, and data privacy."
    ),
    "Foreign Bidder Information": (
        "Guidelines for international bidders, foreign currency submission, foreign DSC certification, "
        "and country specific procurement policies."
    ),
    "Portal Guidelines & Procurement Terms": (
        "Standard GePNIC procurement terms, portal rules, Indian Standard Time IST reference, "
        "general user features, and procurement lifecycle overviews."
    )
}

ENTITY_RULES = {
    "DSC": ["dsc", "digital signature", "token", "usb token", "crypto", "e-token", "dongle"],
    "JRE": ["jre", "java", "runtime environment", "applet", "java security"],
    "Browser": ["firefox", "chrome", "internet explorer", "edge", "browser"],
    "EMD": ["emd", "earnest money", "bank guarantee", "bg", "exemption", "msme"],
    "BOQ": ["boq", "bill of quantities", "financial bid", "price bid", "rate"],
    "Tender": ["tender", "corrigendum", "closing date", "schedule", "packet", "cover"]
}

class QueryUnderstandingService:
    def __init__(self):
        self._centroids: Dict[str, np.ndarray] = {}
        
    def _init_centroids(self):
        if not self._centroids:
            for cat, desc in CATEGORY_DESCRIPTIONS.items():
                vec = embedding_service.embed_text(desc)
                self._centroids[cat] = np.array(vec, dtype=np.float32)
                
    def extract_entities(self, query: str) -> List[str]:
        q_lower = query.lower()
        extracted = []
        for entity, keywords in ENTITY_RULES.items():
            for kw in keywords:
                if kw in q_lower:
                    extracted.append(entity)
                    break
        return extracted
        
    def determine_depth_level(self, query: str, entities: List[str]) -> str:
        q_lower = query.lower()
        # Direct questions
        if any(w in q_lower for w in ["what is", "where is", "default format", "time format", "ist"]):
            return "Direct"
        # Context-dependent
        if any(w in q_lower for w in ["foreign", "exemption", "msme", "if i am", "department"]):
            return "Context-dependent"
        # Multi-source / Multi-hop
        if len(entities) >= 2 or any(w in q_lower for w in ["failed while", "blocked because", "after", "prerequisite"]):
            return "Multi-source"
        # Procedural
        if any(w in q_lower for w in ["how to", "steps", "procedure", "install", "enroll", "what should i do", "not detected"]):
            return "Procedural"
            
        return "Direct"
        
    def classify_query(self, query: str, user_role: str = "Bidder") -> Dict[str, Any]:
        self._init_centroids()
        q_vec = np.array(embedding_service.embed_text(query), dtype=np.float32)
        
        # Compute cosine similarity with each centroid
        best_cat = "Portal Guidelines & Procurement Terms"
        best_score = -1.0
        
        for cat, centroid in self._centroids.items():
            # Normalized vectors, dot product = cosine similarity
            sim = float(np.dot(q_vec, centroid))
            if sim > best_score:
                best_score = sim
                best_cat = cat
                
        entities = self.extract_entities(query)
        depth_level = self.determine_depth_level(query, entities)
        
        # Out-of-Domain Guard: Check if query has low semantic similarity to all categories and no domain entities
        # Non-procurement questions (e.g., sports, cooking, general trivia) score < 0.55 on BGE centroids and have 0 domain entities.
        if best_score < 0.52 and len(entities) == 0:
            return {
                "category": "Out-of-Domain / Irrelevant Inquiry",
                "subcategory": "Non-Procurement Subject",
                "intent": "Unrelated Inquiry",
                "depth_level": "None",
                "confidence_score": round(best_score, 4),
                "entities": [],
                "is_out_of_domain": True,
                "required_context": {
                    "user_role": user_role,
                    "domain": "External",
                    "extracted_entities": []
                }
            }
        
        # Subcategory & Intent mapping
        subcategory = "General"
        intent = "General Inquiry"
        if "DSC" in entities:
            subcategory = "Digital Signature"
            intent = "DSC Verification & Detection"
        elif "EMD" in entities:
            subcategory = "Tender Fee & EMD"
            intent = "EMD Requirement & Exemption"
        elif "JRE" in entities or "Browser" in entities:
            subcategory = "Client System Prerequisites"
            intent = "Environment Configuration"
            
        return {
            "category": best_cat,
            "subcategory": subcategory,
            "intent": intent,
            "depth_level": depth_level,
            "confidence_score": round(best_score, 4),
            "entities": entities,
            "is_out_of_domain": False,
            "required_context": {
                "user_role": user_role,
                "domain": "GePNIC",
                "extracted_entities": entities
            }
        }

query_understanding_service = QueryUnderstandingService()
