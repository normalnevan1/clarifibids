import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import DocumentChunk, DocumentEmbedding
from app.services.embedding.embedding_service import embedding_service
from app.services.classification.query_understanding import query_understanding_service
from app.services.evaluation.evidence_evaluator import evidence_evaluator
from app.services.response.prompt_service import build_llm_messages
from app.llm.groq_provider import get_llm_provider
from app.services.retrieval.graph_service import graph_service
from app.core.config import settings

class RAGResult(BaseModel):
    query: str
    user_role: str
    classification: Dict[str, Any]
    retrieved_chunks: List[Dict[str, Any]]
    evaluation: Dict[str, Any]
    response_text: str
    sources: List[Dict[str, Any]]
    latency_ms: float
    strategy: str = "VECTOR_RAG"

class RAGPipeline:
    def __init__(self):
        self.embedding_svc = embedding_service
        self.understanding_svc = query_understanding_service
        self.evaluator = evidence_evaluator
        
    async def retrieve_chunks(
        self, 
        query: str, 
        user_role: str = "Bidder", 
        top_k: int = settings.TOP_K,
        depth_level: str = "Direct"
    ) -> List[Dict[str, Any]]:
        import numpy as np
        query_vec = np.array(self.embedding_svc.embed_text(query), dtype=np.float32)
        norm_q = np.linalg.norm(query_vec)
        if norm_q > 0:
            query_vec = query_vec / norm_q
        
        async with AsyncSessionLocal() as session:
            stmt = (
                select(DocumentChunk, DocumentEmbedding.embedding)
                .join(DocumentEmbedding, DocumentChunk.id == DocumentEmbedding.chunk_id)
            )
            res = await session.execute(stmt)
            rows = res.all()
            
            scored_chunks = []
            for chunk_row, emb_list in rows:
                chunk_role = (chunk_row.metadata_ or {}).get("user_role", "Bidder")
                
                # --- STRICT ROLE-BASED ACCESS CONTROL (RBAC) ---
                # 1. Domestic 'Bidder' CANNOT access 'Foreign Bidder' or 'Department User' sections
                if user_role == "Bidder" and chunk_role in ["Foreign Bidder", "Department User"]:
                    continue
                # 2. 'Foreign Bidder' CANNOT access internal administrative 'Department User' sections
                if user_role == "Foreign Bidder" and chunk_role == "Department User":
                    continue
                # 3. 'Department User' has administrative clearance to inspect Departmental and General Bidder sections
                
                chunk_vec = np.array(emb_list, dtype=np.float32)
                norm_c = np.linalg.norm(chunk_vec)
                if norm_c > 0:
                    chunk_vec = chunk_vec / norm_c
                similarity = float(np.dot(query_vec, chunk_vec))
                
                # Prioritize chunks specifically tailored for the active role
                if chunk_role == user_role and user_role in ["Foreign Bidder", "Department User"]:
                    similarity = min(1.0, similarity * 1.15)
                    
                scored_chunks.append((similarity, chunk_row))
                
            # Sort by descending cosine similarity
            scored_chunks.sort(key=lambda x: x[0], reverse=True)
            
            # Enforce relevance threshold: only admit chunks that meet the minimum similarity cutoff
            valid_matches = [
                (sim, row) for sim, row in scored_chunks 
                if sim >= settings.RELEVANCE_THRESHOLD
            ]
            
            # Compute Adaptive Dynamic K
            if not valid_matches:
                return []
                
            # Depth-based target bounds:
            # - Direct queries (e.g. "default time format"): 2 max (succinct, highly targeted)
            # - Context-dependent queries: 3 max
            # - Procedural / Multi-source queries: up to 5 (needs multi-step / cross-entity evidence)
            depth_max_k = {
                "Direct": 2,
                "Context-dependent": 3,
                "Procedural": 4,
                "Multi-source": 5,
                "None": 2
            }.get(depth_level, 4)
            
            # Adaptive Score Gap Pruning:
            # Drop chunks that are significantly weaker than the top chunk (> 0.12 drop)
            top_score = valid_matches[0][0]
            score_cutoff = max(settings.RELEVANCE_THRESHOLD, top_score - 0.12)
            
            filtered_matches = [
                (sim, row) for sim, row in valid_matches
                if sim >= score_cutoff
            ]
            
            # Keep at least 1-2 chunks if valid, capped at depth_max_k
            effective_k = min(len(filtered_matches), depth_max_k)
            top_matches = filtered_matches[:max(1, effective_k)]
            
            chunks = []
            for similarity, chunk_row in top_matches:
                meta = chunk_row.metadata_ or {}
                page_no = chunk_row.page_number or meta.get("page_number", ((chunk_row.chunk_index - 1) // 4) + 1)
                chunks.append({
                    "chunk_id": str(chunk_row.id),
                    "chunk_index": chunk_row.chunk_index,
                    "question": chunk_row.question,
                    "answer": chunk_row.answer,
                    "content": chunk_row.content,
                    "page_number": page_no,
                    "similarity_score": round(similarity, 4),
                    "metadata": meta
                })
            return chunks

    async def execute(self, query: str, user_role: str = "Bidder") -> RAGResult:
        import time
        t0 = time.time()
        
        # 1. Dynamic Classification
        classification = self.understanding_svc.classify_query(query, user_role=user_role)
        intent = classification.get("intent", "General Inquiry")
        
        # --- ROLE-BASED ACCESS CONTROL (RBAC) PRE-CHECK ---
        q_lower = query.lower()
        if user_role == "Bidder":
            # Bidder trying to access internal department administrative workflows
            if any(k in q_lower for k in ["tender creator", "tender opener", "bid opener", "nodal officer", "auditor role", "create users", "comparative chart", "reject a bidder", "department user"]):
                elapsed_ms = round((time.time() - t0) * 1000, 2)
                return RAGResult(
                    query=query,
                    user_role=user_role,
                    classification=classification,
                    retrieved_chunks=[],
                    evaluation={
                        "is_relevant": False,
                        "is_sufficient": False,
                        "coverage_score": 0.0,
                        "action": "ACCESS_DENIED",
                        "reason": "Access Restricted: The requested procedural evidence is restricted to Department Users / Procuring Authorities. Domestic Bidders do not have authorization to view internal departmental operations."
                    },
                    response_text="**Access Restricted (RBAC Policy)**:\n\nAs a **Domestic Bidder**, you do not have authorization to access internal **Department User / Procuring Entity** administrative procedures (such as tender creation, user creation, bid opener assignments, or comparative evaluation charts). \n\nIf you require departmental access, please switch to the **Department User** role or contact your designated Nodal Officer.",
                    sources=[],
                    latency_ms=elapsed_ms
                )
            # Bidder querying international / foreign bidder policies
            if any(k in q_lower for k in ["foreign bidder", "foreign consultant", "outside india", "out of india", "currencies other than"]):
                elapsed_ms = round((time.time() - t0) * 1000, 2)
                return RAGResult(
                    query=query,
                    user_role=user_role,
                    classification=classification,
                    retrieved_chunks=[],
                    evaluation={
                        "is_relevant": False,
                        "is_sufficient": False,
                        "coverage_score": 0.0,
                        "action": "ACCESS_DENIED",
                        "reason": "Access Restricted: International vendor policies and foreign currency guidelines are restricted to the Foreign Bidder role."
                    },
                    response_text="**Access Restricted (RBAC Policy)**:\n\nThis inquiry pertains specifically to **Foreign Bidder / International Vendor Regulations** (including overseas DSC issuance and foreign currency BoQ submissions). \n\nAs a domestic **Bidder**, standard Indian procurement rules (INR currency, domestic Certifying Authorities) apply to your account. To view international vendor guidelines, please switch your active role to **Foreign Bidder**.",
                    sources=[],
                    latency_ms=elapsed_ms
                )
                
        elif user_role == "Foreign Bidder":
            # Foreign Bidder trying to access internal department administrative workflows
            if any(k in q_lower for k in ["tender creator", "tender opener", "bid opener", "nodal officer", "auditor role", "create users", "comparative chart", "reject a bidder"]):
                elapsed_ms = round((time.time() - t0) * 1000, 2)
                return RAGResult(
                    query=query,
                    user_role=user_role,
                    classification=classification,
                    retrieved_chunks=[],
                    evaluation={
                        "is_relevant": False,
                        "is_sufficient": False,
                        "coverage_score": 0.0,
                        "action": "ACCESS_DENIED",
                        "reason": "Access Restricted: Internal departmental operations are restricted to authenticated Department Users."
                    },
                    response_text="**Access Restricted (RBAC Policy)**:\n\nAs a **Foreign Bidder**, your permissions are strictly limited to international vendor participation and bidding workflows. Internal departmental operations (such as bid opener management and tender creation) are restricted to **Department Users**.",
                    sources=[],
                    latency_ms=elapsed_ms
                )
        
        # --- OUT-OF-DOMAIN / IRRELEVANT QUERY HARDENING ---
        is_ood = classification.get("is_out_of_domain", False)
        if is_ood:
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            eval_result = self.evaluator.evaluate(query, intent, [], attempt_number=2, is_out_of_domain=True)
            return RAGResult(
                query=query,
                user_role=user_role,
                classification=classification,
                retrieved_chunks=[],
                evaluation=eval_result,
                response_text="**Query Out-of-Domain**:\n\nClarifiBids is an assistance system specifically designed for the **GePNIC eProcurement Portal**. Your query does not appear to be related to Indian Government e-procurement guidelines, DSC requirements, bidding procedures, or portal operations.\n\nPlease ask questions related to GePNIC enrollment, tender submission, BoQ preparation, EMD, or administrative portal workflows.",
                sources=[],
                latency_ms=elapsed_ms
            )

        depth_level = classification.get("depth_level", "Direct")
        strategy = "GRAPH_RAG" if depth_level in ["Procedural", "Multi-source"] else "VECTOR_RAG"

        # 2. Candidate Retrieval (Baseline Vector RAG or Graph RAG based on query depth)
        chunks = await self.retrieve_chunks(query, user_role=user_role, top_k=settings.TOP_K, depth_level=depth_level)
        
        # If query is Procedural or Multi-source, augment with Graph RAG traversal
        if strategy == "GRAPH_RAG":
            graph_chunks = await graph_service.retrieve_graph_evidence(
                query=query,
                entities=classification.get("entities", []),
                intent=intent,
                user_role=user_role
            )
            if graph_chunks:
                # Deduplicate by chunk_id
                existing_ids = {c["chunk_id"] for c in chunks}
                for gc in graph_chunks:
                    if gc["chunk_id"] not in existing_ids:
                        chunks.append(gc)
                        existing_ids.add(gc["chunk_id"])

        # 3. Evidence Evaluation (CRAG)
        eval_result = self.evaluator.evaluate(query, intent, chunks, attempt_number=1)
        
        # 4. Corrective Retrieval (if required and candidate chunks were partially found)
        if eval_result["action"] == "REFINE" and len(classification.get("entities", [])) > 0:
            refined_query = f"{query} {intent} {' '.join(classification.get('entities', []))}"
            chunks_pass2 = await self.retrieve_chunks(refined_query, user_role=user_role, top_k=settings.TOP_K, depth_level=depth_level)
            eval_pass2 = self.evaluator.evaluate(refined_query, intent, chunks_pass2, attempt_number=2)
            if eval_pass2["is_sufficient"] or eval_pass2["coverage_score"] > eval_result["coverage_score"]:
                chunks = chunks_pass2
                eval_result = eval_pass2
        elif not chunks:
            # If after retrieval still no chunk meets threshold, mark as IRRELEVANT / INSUFFICIENT
            eval_result = self.evaluator.evaluate(query, intent, [], attempt_number=2)
                
        # 5. Response Synthesis via Groq
        if not chunks:
            response_text = "The available GePNIC knowledge base does not contain verified procedural evidence relevant to this query. ClarifiBids strictly provides answers grounded in official GePNIC portal documentation."
            sources = []
        else:
            messages = build_llm_messages(query, user_role, chunks)
            llm = get_llm_provider()
            try:
                llm_resp = await llm.generate(messages, temperature=0.1, max_tokens=settings.MAX_OUTPUT_TOKENS)
                response_text = llm_resp.content
            except Exception as e:
                response_text = f"Error generating response from LLM provider: {str(e)}"
                
            sources = [
                {
                    "source": c.get("metadata", {}).get("source", "GePNIC FAQ"),
                    "file_name": c.get("metadata", {}).get("file_name", "FAQ.docx"),
                    "item_number": c.get("metadata", {}).get("item_number", c.get("chunk_index")),
                    "page_number": c.get("page_number", c.get("metadata", {}).get("page_number", 1)),
                    "question": c.get("question"),
                    "similarity_score": c.get("similarity_score"),
                    "content_snippet": (c.get("answer") or c.get("content") or "")[:240]
                }
                for c in chunks
            ]
            
        elapsed_ms = round((time.time() - t0) * 1000, 2)
        
        return RAGResult(
            query=query,
            user_role=user_role,
            classification=classification,
            retrieved_chunks=chunks,
            evaluation=eval_result,
            response_text=response_text,
            sources=sources,
            latency_ms=elapsed_ms,
            strategy=strategy
        )

rag_pipeline = RAGPipeline()
