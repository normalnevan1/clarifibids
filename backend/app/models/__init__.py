import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey, UniqueConstraint, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    Vector = None
    HAS_PGVECTOR = False
from app.core.database import Base

# 1. ROLES & USERS
class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False) # 'Bidder', 'Foreign Bidder', 'Department User', 'ADMIN'
    is_business_role = Column(Boolean, nullable=False, default=True)
    description = Column(Text, nullable=True)

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class UserRole(Base):
    __tablename__ = "user_roles"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

# 2. TAXONOMY
class QueryCategory(Base):
    __tablename__ = "query_categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    subcategories = relationship("QuerySubcategory", back_populates="category", cascade="all, delete-orphan")

class QuerySubcategory(Base):
    __tablename__ = "query_subcategories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("query_categories.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_category_subcategory"),)
    
    category = relationship("QueryCategory", back_populates="subcategories")
    intents = relationship("QueryIntent", back_populates="subcategory", cascade="all, delete-orphan")

class QueryIntent(Base):
    __tablename__ = "query_intents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subcategory_id = Column(Integer, ForeignKey("query_subcategories.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    
    __table_args__ = (UniqueConstraint("subcategory_id", "name", name="uq_subcategory_intent"),)
    
    subcategory = relationship("QuerySubcategory", back_populates="intents")

# 3. KNOWLEDGE SOURCE & DOCUMENT MODEL
class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(150), unique=True, nullable=False)
    source_type = Column(String(50), nullable=False) # 'FAQ', 'SUPPORT_KB', 'PORTAL_MANUAL'
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    version = Column(String(20), default="1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    documents = relationship("Document", back_populates="source", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(Integer, ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False) # 'DOCX', 'PDF', 'TEXT'
    file_name = Column(String(255), nullable=False)
    checksum = Column(String(64), nullable=False)
    version = Column(String(20), default="1.0")
    status = Column(String(50), default="INDEXED")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    source = relationship("KnowledgeSource", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)
    section_title = Column(String(255), nullable=True)
    token_count = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    document = relationship("Document", back_populates="chunks")
    embedding = relationship("DocumentEmbedding", uselist=False, back_populates="chunk", cascade="all, delete-orphan")

class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), unique=True, nullable=False)
    embedding = Column(ARRAY(Float), nullable=False)
    embedding_model = Column(String(100), default="BAAI/bge-small-en-v1.5")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    chunk = relationship("DocumentChunk", back_populates="embedding")

# 4. GRAPH ENTITIES & EDGES (Phase 12+)
class GraphNode(Base):
    __tablename__ = "graph_nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_type = Column(String(50), nullable=False) # 'ISSUE', 'PROCEDURE', 'CONDITION', 'RULE', 'CHUNK'
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)

class GraphEdge(Base):
    __tablename__ = "graph_edges"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id = Column(UUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(UUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(100), nullable=False)
    weight = Column(Float, default=1.0)
    metadata_ = Column("metadata", JSONB, default=dict)

# 5. QUERIES, RUNS, EVALUATIONS & RESPONSES
class Query(Base):
    __tablename__ = "queries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(100), nullable=False)
    query_text = Column(Text, nullable=False)
    user_role = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    classification = relationship("QueryClassification", uselist=False, back_populates="query", cascade="all, delete-orphan")
    retrieval_runs = relationship("RetrievalRun", back_populates="query", cascade="all, delete-orphan")
    response = relationship("Response", uselist=False, back_populates="query", cascade="all, delete-orphan")

class QueryClassification(Base):
    __tablename__ = "query_classifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), unique=True, nullable=False)
    category_id = Column(Integer, ForeignKey("query_categories.id"), nullable=True)
    subcategory_id = Column(Integer, ForeignKey("query_subcategories.id"), nullable=True)
    intent_id = Column(Integer, ForeignKey("query_intents.id"), nullable=True)
    depth_level = Column(String(50), nullable=False) # 'Direct', 'Procedural', 'Context-dependent', 'Multi-source'
    confidence_score = Column(Float, nullable=True)
    entities = Column(JSONB, default=list)
    required_context = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    query = relationship("Query", back_populates="classification")
    category = relationship("QueryCategory")
    subcategory = relationship("QuerySubcategory")
    intent = relationship("QueryIntent")

class RetrievalRun(Base):
    __tablename__ = "retrieval_runs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False)
    parent_run_id = Column(UUID(as_uuid=True), ForeignKey("retrieval_runs.id", ondelete="SET NULL"), nullable=True)
    strategy = Column(String(50), nullable=False) # 'VECTOR_RAG', 'GRAPH_RAG', 'CORRECTIVE_PASS'
    attempt_number = Column(Integer, default=1)
    top_k = Column(Integer, default=4)
    latency_ms = Column(Float, nullable=True)
    status = Column(String(50), default="COMPLETED")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    query = relationship("Query", back_populates="retrieval_runs")
    parent_run = relationship("RetrievalRun", remote_side=[id])
    evidence_items = relationship("RetrievedEvidence", back_populates="retrieval_run", cascade="all, delete-orphan")
    evaluation = relationship("EvidenceEvaluation", uselist=False, back_populates="retrieval_run", cascade="all, delete-orphan")

class RetrievedEvidence(Base):
    __tablename__ = "retrieved_evidence"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    retrieval_run_id = Column(UUID(as_uuid=True), ForeignKey("retrieval_runs.id", ondelete="CASCADE"), nullable=False)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    similarity_score = Column(Float, nullable=True)
    rank = Column(Integer, nullable=True)
    is_selected = Column(Boolean, default=True)
    
    retrieval_run = relationship("RetrievalRun", back_populates="evidence_items")
    chunk = relationship("DocumentChunk")

class EvidenceEvaluation(Base):
    __tablename__ = "evidence_evaluations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    retrieval_run_id = Column(UUID(as_uuid=True), ForeignKey("retrieval_runs.id", ondelete="CASCADE"), unique=True, nullable=False)
    is_relevant = Column(Boolean, nullable=False)
    is_sufficient = Column(Boolean, nullable=False)
    coverage_score = Column(Float, nullable=False)
    action_taken = Column(String(50), nullable=False) # 'PROCEED', 'REFINE', 'EXHAUSTED'
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    retrieval_run = relationship("RetrievalRun", back_populates="evaluation")

class Response(Base):
    __tablename__ = "responses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), unique=True, nullable=False)
    retrieval_run_id = Column(UUID(as_uuid=True), ForeignKey("retrieval_runs.id"), nullable=True)
    response_text = Column(Text, nullable=False)
    model_name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    prompt_version = Column(String(20), default="v1")
    groundedness_score = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    query = relationship("Query", back_populates="response")
    retrieval_run = relationship("RetrievalRun")
    evidence_links = relationship("ResponseEvidence", back_populates="response", cascade="all, delete-orphan")

class ResponseEvidence(Base):
    __tablename__ = "response_evidence"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    response_id = Column(UUID(as_uuid=True), ForeignKey("responses.id", ondelete="CASCADE"), nullable=False)
    retrieved_evidence_id = Column(UUID(as_uuid=True), ForeignKey("retrieved_evidence.id", ondelete="CASCADE"), nullable=False)
    
    __table_args__ = (UniqueConstraint("response_id", "retrieved_evidence_id", name="uq_response_retrieved_evidence"),)
    
    response = relationship("Response", back_populates="evidence_links")
    retrieved_evidence = relationship("RetrievedEvidence")

# 6. EVALUATION BENCHMARKING (Phase 16+)
class EvaluationQuery(Base):
    __tablename__ = "evaluation_queries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    query_text = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("query_categories.id"), nullable=True)
    depth_level = Column(String(50), nullable=False)
    user_role = Column(String(50), nullable=False)
    expected_evidence_chunks = Column(JSONB, default=list)
    reference_answer = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)

class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_query_id = Column(Integer, ForeignKey("evaluation_queries.id", ondelete="CASCADE"), nullable=False)
    approach = Column(String(50), nullable=False) # 'KEYWORD', 'VECTOR_RAG', 'GRAPH_RAG'
    precision_at_k = Column(Float, nullable=True)
    recall_at_k = Column(Float, nullable=True)
    answer_correctness = Column(Float, nullable=True)
    answer_relevance = Column(Float, nullable=True)
    faithfulness = Column(Float, nullable=True)
    context_completeness = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    config_snapshot = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
