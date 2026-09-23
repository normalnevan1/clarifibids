from fastapi import FastAPI, Depends, HTTPException, Query as FastAPIQuery
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.services.retrieval.rag_pipeline import rag_pipeline, RAGResult
from app.services.classification.query_understanding import CATEGORY_DESCRIPTIONS

app = FastAPI(
    title="ClarifiBids API",
    description="Intelligent Assistance Layer over GePNIC eProcurement Portal",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatQueryRequest(BaseModel):
    query_text: str = Field(..., min_length=2, max_length=500)
    session_id: str = "default_session"
    user_role: str = Field("Bidder", pattern="^(Bidder|Foreign Bidder|Department User)$")

class ChatQueryResponse(BaseModel):
    query: str
    user_role: str
    classification: Dict[str, Any]
    answer: str
    sources: List[Dict[str, Any]]
    evaluation: Dict[str, Any]
    latency_ms: float
    strategy: str = "VECTOR_RAG"

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "database": "PostgreSQL 18 + pgvector",
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL
    }

from app.core.auth import (
    hash_password, verify_password, create_access_token, get_current_user_optional
)
from app.core.database import AsyncSessionLocal
from app.models import (
    User, Role, UserRole, Query, QueryClassification, QueryCategory,
    RetrievalRun, RetrievedEvidence, EvidenceEvaluation, Response, ResponseEvidence
)
from sqlalchemy import select

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=4)
    role: str = Field("Bidder", pattern="^(Bidder|Foreign Bidder|Department User)$")

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

@app.post("/api/v1/auth/register", response_model=AuthResponse)
async def register_user(req: RegisterRequest):
    async with AsyncSessionLocal() as session:
        # Check existing username
        stmt = select(User).where(User.username == req.username)
        res = await session.execute(stmt)
        if res.scalars().first():
            raise HTTPException(status_code=400, detail="Username already registered")
            
        # Get role record
        role_stmt = select(Role).where(Role.name == req.role)
        role_res = await session.execute(role_stmt)
        role_obj = role_res.scalars().first()
        if not role_obj:
            raise HTTPException(status_code=400, detail=f"Role '{req.role}' not found")
            
        new_user = User(
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
            is_active=True
        )
        session.add(new_user)
        await session.flush()
        
        user_role = UserRole(user_id=new_user.id, role_id=role_obj.id)
        session.add(user_role)
        await session.commit()
        
        token = create_access_token(new_user.id, new_user.username, req.role)
        return AuthResponse(
            access_token=token,
            user={"id": str(new_user.id), "username": new_user.username, "email": new_user.email, "role": req.role}
        )

@app.post("/api/v1/auth/login", response_model=AuthResponse)
async def login_user(req: LoginRequest):
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.username == req.username)
        res = await session.execute(stmt)
        user = res.scalars().first()
        if not user or not verify_password(req.password, user.password_hash or ""):
            raise HTTPException(status_code=401, detail="Invalid username or password")
            
        # Fetch user's assigned role
        ur_stmt = select(Role.name).join(UserRole, Role.id == UserRole.role_id).where(UserRole.user_id == user.id)
        ur_res = await session.execute(ur_stmt)
        role_name = ur_res.scalar_one_or_none() or "Bidder"
        
        token = create_access_token(user.id, user.username, role_name)
        return AuthResponse(
            access_token=token,
            user={"id": str(user.id), "username": user.username, "email": user.email, "role": role_name}
        )

@app.get("/api/v1/auth/me")
async def get_me(user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@app.get("/api/v1/taxonomy/categories")
def get_categories():
    return [
        {"name": name, "description": desc}
        for name, desc in CATEGORY_DESCRIPTIONS.items()
    ]

@app.post("/api/v1/chat/query", response_model=ChatQueryResponse)
async def handle_chat_query(req: ChatQueryRequest):
    try:
        rag_res: RAGResult = await rag_pipeline.execute(
            query=req.query_text,
            user_role=req.user_role
        )

        # Asynchronous DB Audit Persistence
        try:
            async with AsyncSessionLocal() as session:
                # 1. Query record
                db_query = Query(
                    session_id=req.session_id,
                    query_text=rag_res.query,
                    user_role=rag_res.user_role
                )
                session.add(db_query)
                await session.flush()

                # 2. Classification record
                cat_name = rag_res.classification.get("category", "")
                cat_stmt = select(QueryCategory.id).where(QueryCategory.name == cat_name)
                cat_res = await session.execute(cat_stmt)
                cat_id = cat_res.scalar_one_or_none()

                db_class = QueryClassification(
                    query_id=db_query.id,
                    category_id=cat_id,
                    depth_level=rag_res.classification.get("depth_level", "Direct"),
                    confidence_score=rag_res.classification.get("confidence_score", 0.0),
                    entities=rag_res.classification.get("entities", []),
                    required_context=rag_res.classification.get("required_context", {})
                )
                session.add(db_class)

                # 3. Retrieval Run
                db_run = RetrievalRun(
                    query_id=db_query.id,
                    strategy=rag_res.strategy,
                    attempt_number=1,
                    top_k=len(rag_res.retrieved_chunks),
                    latency_ms=rag_res.latency_ms,
                    status="COMPLETED"
                )
                session.add(db_run)
                await session.flush()

                # 4. Retrieved Evidence & Evidence Evaluation
                for idx, c in enumerate(rag_res.retrieved_chunks, 1):
                    c_id_str = c.get("chunk_id")
                    if c_id_str:
                        import uuid
                        db_ev = RetrievedEvidence(
                            retrieval_run_id=db_run.id,
                            chunk_id=uuid.UUID(c_id_str),
                            similarity_score=c.get("similarity_score", 0.0),
                            rank=idx,
                            is_selected=True
                        )
                        session.add(db_ev)

                db_eval = EvidenceEvaluation(
                    retrieval_run_id=db_run.id,
                    is_relevant=rag_res.evaluation.get("is_relevant", False),
                    is_sufficient=rag_res.evaluation.get("is_sufficient", False),
                    coverage_score=rag_res.evaluation.get("coverage_score", 0.0),
                    action_taken=rag_res.evaluation.get("action", "PROCEED"),
                    reason=rag_res.evaluation.get("reason", "")
                )
                session.add(db_eval)

                # 5. Response Record
                db_resp = Response(
                    query_id=db_query.id,
                    retrieval_run_id=db_run.id,
                    response_text=rag_res.response_text,
                    model_name=settings.GROQ_MODEL,
                    provider=settings.LLM_PROVIDER,
                    prompt_version="v1",
                    groundedness_score=rag_res.evaluation.get("coverage_score", 0.0),
                    latency_ms=rag_res.latency_ms
                )
                session.add(db_resp)

                await session.commit()
        except Exception as audit_err:
            # Audit logging failure should not abort client response
            import logging
            logging.error(f"Audit log persistence error: {audit_err}")

        return ChatQueryResponse(
            query=rag_res.query,
            user_role=rag_res.user_role,
            classification=rag_res.classification,
            answer=rag_res.response_text,
            sources=rag_res.sources,
            evaluation=rag_res.evaluation,
            latency_ms=rag_res.latency_ms,
            strategy=rag_res.strategy
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from app.services.evaluation.benchmark_service import benchmark_service

@app.post("/api/v1/evaluation/run-benchmark")
async def trigger_benchmark():
    try:
        report = await benchmark_service.run_benchmark()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/evaluation/results")
async def get_evaluation_history():
    async with AsyncSessionLocal() as session:
        from app.models import EvaluationResult, EvaluationQuery
        stmt = select(EvaluationResult, EvaluationQuery).join(
            EvaluationQuery, EvaluationResult.evaluation_query_id == EvaluationQuery.id
        ).order_by(EvaluationResult.created_at.desc()).limit(20)
        res = await session.execute(stmt)
        history = []
        for r, q in res.all():
            history.append({
                "query": q.query_text,
                "depth_level": q.depth_level,
                "approach": r.approach,
                "precision_at_k": r.precision_at_k,
                "recall_at_k": r.recall_at_k,
                "faithfulness": r.faithfulness,
                "context_completeness": r.context_completeness,
                "latency_ms": r.latency_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None
            })
        return {"total": len(history), "results": history}
