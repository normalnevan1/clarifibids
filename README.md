# ClarifiBids: Grounded Intelligence & Procedural Clarification Layer for GePNIC e-Procurement

ClarifiBids is an enterprise AI technical assistance and procedural guidance platform designed specifically for the **Government e-Procurement System of India (GePNIC)** and **Central Public Procurement Portal (CPPP)**.

It resolves critical tender submission blockers (such as DSC token initialization errors, Java JRE version mismatches, BoQ financial template requirements, and role-specific compliance) through **Role-Based Access Control (RBAC)**, an **Adaptive Multi-Strategy Retrieval Engine (Dynamic Vector RAG, Graph RAG, and Corrective RAG / CRAG)**, and **Official Document Page Citations**.

---

## 🏛 System Architecture & Component Diagram

Below is the modular architectural layout of ClarifiBids showing data flow across the 5 primary tiers:

```mermaid
graph TD
    classDef client fill:#e0f2fe,stroke:#0369a1,stroke-width:2px,color:#0f172a,font-size:14px;
    classDef security fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#0f172a,font-size:14px;
    classDef engine fill:#ede9fe,stroke:#6d28d9,stroke-width:2px,color:#0f172a,font-size:14px;
    classDef crag fill:#dcfce7,stroke:#15803d,stroke-width:2px,color:#0f172a,font-size:14px;
    classDef db fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a,font-size:14px;

    UI["💻 React 18 UI<br/>(National NIC/GePNIC Portal)"]:::client
    API["🛡️ FastAPI Gateway<br/>(JWT + RBAC Policy Guard)"]:::security
    CL["🧠 Query Understanding<br/>(Category Centroids + Entity Rules)"]:::engine

    subgraph DynamicRetrieval ["Adaptive Dynamic Retrieval Engine"]
        VR["🔍 Vector RAG<br/>(Dense pgvector Search)"]:::engine
        GR["🕸️ Graph RAG<br/>(Multi-Hop Ontology Traversal)"]:::engine
        Fuse["⚡ Fusion & Deduplication"]:::engine
    end

    CRAG{"⚖️ CRAG Evaluator<br/>(Relevance & Sufficiency)"}:::crag
    SYNTH["🤖 LLM Synthesis<br/>(Groq LPU / Local vLLM)"]:::crag
    POSTGRES[("🗄️ PostgreSQL 18<br/>pgvector + Knowledge Graph + Audit Logs")]:::db

    UI -->|"1. User Query + JWT Role"| API
    API -->|"2. Authenticated Scope"| CL
    CL -->|"Direct Query"| VR
    CL -->|"Procedural / Multi-Hop"| GR
    VR <-->|"Cosine Similarity"| POSTGRES
    GR <-->|"Node & Edge Traversal"| POSTGRES
    VR --> Fuse
    GR --> Fuse
    Fuse -->|"Candidate Chunks"| CRAG
    CRAG -->|"Sufficiency >= 0.70"| SYNTH
    CRAG -.->|"Sufficiency < 0.70 (Refine Query)"| VR
    SYNTH -->|"Verified Guidance + Page Citations"| UI
    API -.->|"Audit Logs & Metrics"| POSTGRES
```

---

## 🔄 End-to-End Project Workflow

The sequence below illustrates the exact request-response lifecycle from query submission to verified page citation rendering:

```mermaid
sequenceDiagram
    autonumber
    actor User as 👤 User / Bidder
    participant UI as 💻 React 18 Portal
    participant API as 🛡️ FastAPI Gateway
    participant Engine as ⚙️ Dynamic Retrieval & CRAG
    participant DB as 🗄️ PostgreSQL 18
    participant LLM as 🤖 Inference LLM
    
    User->>UI: Enters query (e.g. "DSC not detected during bid submission")
    UI->>API: POST /api/v1/chat/query (with Bearer Token & Role)
    
    API->>API: 1. Validate Role-Based Access Control (RBAC)
    API->>Engine: 2. Analyze Intent, Entities & Depth Level
    
    alt Procedural or Multi-hop Query
        Engine->>DB: Graph Traversal (Issues ➔ Procedures ➔ Conditions ➔ Chunks)
        Engine->>DB: Dense Vector Search (BGE-Small pgvector)
        DB-->>Engine: Candidate Evidence Chunks
    else Direct Definition Query
        Engine->>DB: Dense Vector Search (pgvector)
        DB-->>Engine: Top-K Vector Chunks
    end
    
    Engine->>Engine: 3. Corrective RAG (CRAG) Sufficiency Evaluation
    opt Borderline Coverage (0.40 <= Score < 0.70)
        Engine->>DB: Query Expansion using Extracted Entities
        DB-->>Engine: Refined Evidence
    end
    
    Engine->>LLM: 4. Build Role-Constrained Prompt with Evidence
    LLM-->>API: Synthesized Guidance with Source Item & Page Numbers
    API->>DB: 5. Asynchronously Audit Query, Classification & Latency
    API-->>UI: Response Payload (Answer, Item #, Page #, Confidence Score)
    UI-->>User: Renders Verified Answer + Official Document Reference Badge

---

## ⚡ Adaptive Dynamic Retrieval: Vector RAG, Graph RAG & Corrective RAG

ClarifiBids does **not** rely on a static or one-size-fits-all retrieval approach. It analyzes every query's semantic complexity and intent depth to route it dynamically across three distinct paradigms:

| Retrieval Strategy | When Selected | Mechanism | Target Questions |
| :--- | :--- | :--- | :--- |
| **Vector RAG** | `Direct` queries & definition inquiries | Cosine similarity over 384-dimensional dense embeddings (`BAAI/bge-small-en-v1.5`) stored in PostgreSQL `pgvector`. Fast and semantically granular. | *"What is the default date and time format in GePNIC?"*, *"What is the validity period of a DSC?"* |
| **Graph RAG** | `Procedural` & `Multi-source` / `Multi-hop` queries | Multi-hop graph traversal across the GePNIC Domain Knowledge Graph (`GraphNode` & `GraphEdge` tables). Traverses `ISSUES` $\rightarrow$ `TRIGGERS_PROCEDURE` $\rightarrow$ `REQUIRES_PREREQUISITE` $\rightarrow$ `GOVERNED_BY_CONDITION` $\rightarrow$ `SUPPORTS_EVIDENCE` to retrieve connected operational requirements. | *"What should I do if my DSC token is not detected?"*, *"Bid opener name not visible during tender creation"*, *"How to configure Java JRE for e-Procurement?"* |
| **Corrective RAG (CRAG)** | Continuous verification layer across **all** retrievals | Self-evaluates candidate evidence across two criteria: **Relevance** (threshold $\ge 0.65$) and **Sufficiency Coverage** (threshold $\ge 0.70$). If initial evidence is insufficient (`Action: REFINE`), it performs query expansion using extracted entities; if irrelevant, it triggers safe domain-protective fallback. | Prevents hallucinations, flags out-of-domain prompts, and refines complex technical questions. |

---

## 🔐 Deployment, Security & Production Readiness Roadmap

### 1. Cloud-Based Model vs. Air-Gapped / On-Premises Local LLM
- **Current Demo Setup**: For rapid testing, demonstration, and high inference speed without demanding on-prem GPU hardware, the current demonstration runs with **Groq Cloud LPU** (`qwen/qwen3.8-27b` or `llama3-70b-8192`).
- **Production & Air-Gapped Deployment**:
  - In sensitive sovereign government environments (e.g., NIC data centers), the cloud API can be swapped with a **locally hosted open-source LLM** (such as **Llama 3 8B/70B Instruct**, **Mistral**, or **Qwen 2.5**) deployed on an air-gapped on-premise GPU server using **vLLM**, **Ollama**, or **TGI (Text Generation Inference)**.
  - The backend's pluggable LLM provider interface (`app/llm/`) allows changing just one environment variable (`LLM_PROVIDER=local` or `LLM_PROVIDER=vllm`) with zero frontend or pipeline code alterations, ensuring complete data residency and zero external telemetry.

### 2. Enterprise Authentication: Keycloak Integration
- **Current Setup**: Role-based access control (RBAC) with secure hashed credentials and JWT tokens stored in PostgreSQL.
- **Production Enhancement**: The authentication gateway can be bound to **Keycloak (SSO)** via OpenID Connect (OIDC) / OAuth 2.0. This allows seamless federation with existing Indian National Informatics Centre Single Sign-On (NIC SSO / Parichay) and SAML-based enterprise identity providers.

### 3. Secrets Management: HashiCorp Vault Integration
- **Current Setup**: Environment-driven credential configuration (`.env`) guarded by strict `.gitignore` rules.
- **Production Enhancement**: Database credentials, encryption keys, and internal service tokens can be dynamically rotated and fetched from **HashiCorp Vault** using AppRole or Kubernetes service account tokens, eliminating long-lived static secrets in server environments.

---

## 🏛 Key Features

- **Official Government Policy Citations**: Every answer links back directly to the official GePNIC FAQ Manual, displaying the exact Item #, verified policy badge, relevance confidence score, and **Official Document Page Number** (`Page 1`, `Page 2`, etc.).
- **Direct Official Document Download**: In-app download button for `FAQ.docx` so bidders and procurement officers can cross-examine official documentation offline.
- **Role-Based Access Control (RBAC)**:
  - **Bidder**: Domestic Indian procurement workflows, Indian Certifying Authority DSCs, BoQ in INR.
  - **Foreign Bidder**: International vendor compliance, overseas DSC procedures, multi-currency BoQ rules.
  - **Department User**: Procuring entities, tender creators, bid opener role assignment, DSC renewal best practices.
- **Session Thread Isolation**: Chat histories are partitioned cleanly by individual user accounts with in-app "Clear Thread" functionality.
- **Audit-Logged Queries**: All interactions, classifications, and retrieval evaluations are securely audited to PostgreSQL.

---

## 🗄 Database Table Structure & Relational Schema

ClarifiBids uses **PostgreSQL 18** with `pgvector` and standard relational schemas to support vector embeddings, multi-hop knowledge graph queries, RBAC access control, and complete CRAG audit logging:

```mermaid
graph LR
    classDef auth fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#0f172a,font-size:13px;
    classDef docs fill:#e0f2fe,stroke:#0369a1,stroke-width:2px,color:#0f172a,font-size:13px;
    classDef graph fill:#ede9fe,stroke:#6d28d9,stroke-width:2px,color:#0f172a,font-size:13px;
    classDef audit fill:#dcfce7,stroke:#15803d,stroke-width:2px,color:#0f172a,font-size:13px;

    subgraph AuthGroup ["1. Identity & RBAC"]
        U["users<br/>(id, username, password_hash)"]:::auth
        R["roles<br/>(id, name, is_business_role)"]:::auth
        UR["user_roles<br/>(user_id, role_id)"]:::auth
        U --- UR
        R --- UR
    end

    subgraph DocGroup ["2. Knowledge Base & Vector Store"]
        KS["knowledge_sources"]:::docs
        DOC["documents<br/>(title, checksum)"]:::docs
        DC["document_chunks<br/>(question, answer, page_no)"]:::docs
        EMB["document_embeddings<br/>(vector 384-dim)"]:::docs
        KS --> DOC
        DOC --> DC
        DC --> EMB
    end

    subgraph KnowledgeGraph ["3. GePNIC Domain Ontology"]
        GN["graph_nodes<br/>(node_type, name)"]:::graph
        GE["graph_edges<br/>(relationship_type, weight)"]:::graph
        GN -->|"source"| GE
        GE -->|"target"| GN
    end

    subgraph AuditGroup ["4. CRAG & Execution Audit Trail"]
        Q["queries<br/>(query_text, user_role)"]:::audit
        QC["query_classifications<br/>(category, depth_level)"]:::audit
        RR["retrieval_runs<br/>(strategy, latency_ms)"]:::audit
        EE["evidence_evaluations<br/>(action_taken, coverage_score)"]:::audit
        RESP["responses<br/>(response_text, model_name)"]:::audit
        
        Q --> QC
        Q --> RR
        RR --> EE
        Q --> RESP
    end

    U -.->|"initiates"| Q
    DC -.->|"retrieved into"| RR
```

### Table Breakdown by Architectural Domain

#### 1. Identity & RBAC Tables
| Table Name | Primary Key | Description & Key Columns |
| :--- | :--- | :--- |
| `users` | `id (UUID)` | Authenticated portal accounts: `username`, `email`, `password_hash`, `is_active`, `created_at`. |
| `roles` | `id (SERIAL)` | Standard roles: `name` (`Bidder`, `Foreign Bidder`, `Department User`, `ADMIN`), `is_business_role`, `description`. |
| `user_roles` | `(user_id, role_id)` | Composite key junction enforcing user-to-role binding. |

#### 2. Vector Store & Knowledge Chunk Tables
| Table Name | Primary Key | Description & Key Columns |
| :--- | :--- | :--- |
| `knowledge_sources` | `id (SERIAL)` | Source metadata: `source_name`, `source_type` (`FAQ`, `MANUAL`), `location`, `version`. |
| `documents` | `id (UUID)` | Document-level tracking: `source_id (FK)`, `title`, `document_type`, `file_name`, `checksum`. |
| `document_chunks` | `id (UUID)` | Partitioned textual chunks: `document_id (FK)`, `chunk_index`, `content`, `question`, `answer`, `page_number`, `token_count`, `metadata (JSONB)` (e.g. `user_role`). |
| `document_embeddings`| `id (UUID)` | 384-dimensional vector store: `chunk_id (FK, UNIQUE)`, `embedding (ARRAY/Vector(384))`, `embedding_model` (`BAAI/bge-small-en-v1.5`). |

#### 3. Procurement Taxonomy & Classification
| Table Name | Primary Key | Description & Key Columns |
| :--- | :--- | :--- |
| `query_categories` | `id (SERIAL)` | Top-level procurement domains: `name` (e.g., *Technical Assistance*, *Security Information*). |
| `query_subcategories`| `id (SERIAL)` | Nested category divisions: `category_id (FK)`, `name` (e.g., *Digital Signature*, *Client System Prerequisites*). |
| `query_intents` | `id (SERIAL)` | Granular operational intent: `subcategory_id (FK)`, `name` (e.g., *DSC Verification & Detection*). |

#### 4. Knowledge Graph Ontology Tables
| Table Name | Primary Key | Description & Key Columns |
| :--- | :--- | :--- |
| `graph_nodes` | `id (UUID)` | Entities and concepts: `node_type` (`ISSUE`, `PROCEDURE`, `CONDITION`, `RULE`, `CHUNK`), `name`, `description`, `metadata (JSONB)`. |
| `graph_edges` | `id (UUID)` | Directed semantic relationships: `source_node_id (FK)`, `target_node_id (FK)`, `relationship_type` (`TRIGGERS_PROCEDURE`, `REQUIRES_PREREQUISITE`, `GOVERNED_BY_CONDITION`, `SUPPORTS_EVIDENCE`), `weight`. |

#### 5. CRAG Execution & Interaction Audit Tables
| Table Name | Primary Key | Description & Key Columns |
| :--- | :--- | :--- |
| `queries` | `id (UUID)` | Audit trail of all queries: `user_id (FK)`, `session_id`, `query_text`, `user_role`, `created_at`. |
| `query_classifications`| `id (UUID)` | Query understanding metadata: `query_id (FK)`, `category_id (FK)`, `depth_level` (`Direct`, `Procedural`, `Multi-source`), `confidence_score`, `entities (JSONB)`. |
| `retrieval_runs` | `id (UUID)` | Retrieval execution passes: `query_id (FK)`, `strategy` (`VECTOR_RAG`, `GRAPH_RAG`), `attempt_number`, `latency_ms`. |
| `retrieved_evidence` | `id (UUID)` | Evidence scoring: `retrieval_run_id (FK)`, `chunk_id (FK)`, `similarity_score`, `rank`, `is_selected`. |
| `evidence_evaluations` | `id (UUID)` | Evaluator metrics: `retrieval_run_id (FK)`, `is_relevant`, `is_sufficient`, `coverage_score`, `action_taken` (`CORRECT`, `REFINE`, `ACCESS_DENIED`), `reason`. |
| `responses` | `id (UUID)` | Synthesized response text: `query_id (FK)`, `retrieval_run_id (FK)`, `response_text`, `model_name`, `provider`, `latency_ms`. |
| `response_evidence` | `id (UUID)` | Grounding links connecting final response to specific evidence items. |

---

## 🏗 Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Lucide Icons, Vanilla CSS (NIC/GePNIC National Portal Design System).
- **Backend API**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy (Asyncpg + Psycopg).
- **Vector Database**: PostgreSQL 18 with `pgvector` extension for semantic embedding search.
- **Knowledge Graph**: Relational Graph Schema (`graph_nodes`, `graph_edges`) modeled after GePNIC procurement ontology with multi-hop recursive traversal.
- **LLM / Embeddings**:
  - LLM: Groq Cloud API (Demo) / Local vLLM (Production)
  - Embeddings: HuggingFace SentenceTransformers (`BAAI/bge-small-en-v1.5`, 384 dimensions) running locally on CPU/GPU.

---

## 🚀 Quick Setup & Installation

### Prerequisites
1. **Node.js** (v18 or higher) and `npm`
2. **Python** (v3.10 to v3.12 recommended)
3. **PostgreSQL 16+** with the **`pgvector`** extension installed
4. **Groq Cloud API Key** (Free at [console.groq.com](https://console.groq.com/keys))

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/normalnevan1/clarifibids.git
cd clarifibids
```

---

### Step 2: Database Setup (PostgreSQL + pgvector)

1. Open `psql` or pgAdmin as your PostgreSQL superuser (e.g. `postgres`):
   ```sql
   CREATE DATABASE clarifibids_db;
   \c clarifibids_db
   CREATE EXTENSION IF NOT EXISTS vector;
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   ```
2. *(Windows users: If pgvector is not yet installed on your Postgres, copy the pgvector DLL, control, and SQL files into your PostgreSQL directory or run the included `install_pgvector.bat`)*.

3. Seed initial database roles and query categories:
   ```bash
   cd backend
   python seed_db.py
   ```

---

### Step 3: Backend Setup & Configuration

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   - **Windows**:
     ```bash
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure Environment Variables:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env     # Linux / Mac
     copy .env.example .env   # Windows
     ```
   - Edit `backend/.env` with your actual credentials:
     ```env
     DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@127.0.0.1:5432/clarifibids_db
     SYNC_DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@127.0.0.1:5432/clarifibids_db
     GROQ_API_KEY=gsk_your_groq_api_key_here
     GROQ_MODEL=qwen/qwen3.8-27b
     ```

5. Ingest Knowledge Base and Seed Knowledge Graph:
   - Ingest `FAQ.docx` into PostgreSQL with 384-dimensional vector embeddings and page markers:
     ```bash
     python ingest_faq.py
     ```
   - Seed the GePNIC Domain Knowledge Graph nodes, edges, and procedural associations:
     ```bash
     python seed_graph.py
     ```

6. Start the FastAPI Backend Server:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   FastAPI will start at `http://127.0.0.1:8000`. You can inspect the interactive docs at `http://127.0.0.1:8000/docs`.

---

### Step 4: Frontend Setup

1. Open a new terminal window and navigate to `frontend`:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to:
   ```
   http://localhost:5173
   ```

---

## 📖 Using ClarifiBids

1. **Register / Login**:
   - Create an account by choosing a username, email, password (min 4 characters), and your role (**Bidder**, **Foreign Bidder**, or **Department User**).
2. **Explore Adaptive RAG**:
   - Click any role-specific starter query or type natural language questions.
   - For direct questions, **Vector RAG** executes immediate semantic lookup.
   - For procedural or issue-driven queries (e.g., token detection failures), **Graph RAG** traverses procedural prerequisites.
   - **Corrective RAG** continuously validates sufficiency before generation.
3. **Verify Official Document Pages**:
   - Check the citation card showing the GePNIC Item # and Document Page Number.
   - Click **Download Official FAQ** to inspect the source manual.
4. **Isolate Session Threads**:
   - Click **Clear Thread** anytime to start a fresh workspace for your active role.

---

## 🔒 Security & Privacy Notice
Never commit real API keys or database passwords to version control. The repository `.gitignore` ensures that `.env` and virtual environments remain strictly local.
