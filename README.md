# ClarifiBids: Grounded Intelligence & Procedural Clarification Layer for GePNIC e-Procurement

ClarifiBids is an enterprise AI technical assistance and procedural guidance platform designed specifically for the **Government e-Procurement System of India (GePNIC)** and **Central Public Procurement Portal (CPPP)**.

It resolves critical tender submission blockers (such as DSC token initialization errors, Java JRE version mismatches, BoQ financial template requirements, and role-specific compliance) through **Role-Based Access Control (RBAC)**, an **Adaptive Multi-Strategy Retrieval Engine (Dynamic Vector RAG, Graph RAG, and Corrective RAG / CRAG)**, and **Official Document Page Citations**.

---

## 🏛 System Architecture & Retrieval Flowchart

Below is the complete architectural layout illustrating how user inquiries are authenticated, routed dynamically between Vector and Graph search, evaluated via Corrective RAG (CRAG), and synthesized:

```mermaid
flowchart TD
    %% User and Client Layer
    subgraph ClientLayer ["1. Client Interaction Layer (React 18 + Vite)"]
        User(["User / Bidder"])
        UI["National NIC/GePNIC UI Workspace"]
        AuthModal["Role-Based Authentication (Bidder / Foreign Bidder / Dept User)"]
    end

    %% API and Security Layer
    subgraph APILayer ["2. API & Security Gateway (FastAPI)"]
        JWT["Bearer Token & Session Auth"]
        RBACFilter{"Role RBAC Guard"}
        AuditLog[("PostgreSQL Audit Log")]
    end

    %% Query Classification
    subgraph UnderstandingLayer ["3. Intent Classification & Depth Routing"]
        Classifier["Query Understanding Engine"]
        Centroids["BGE Centroids (6 Procurement Categories)"]
        EntityRules["Regex Entity Extractor (DSC, JRE, EMD, BoQ)"]
        DepthRouter{"Depth Level Decision"}
    end

    %% Dynamic Retrieval Engine
    subgraph RetrievalLayer ["4. Adaptive Dynamic Retrieval Engine"]
        VectorEngine["Vector RAG (Dense Embedding Search)\nBAAI/bge-small-en-v1.5 + pgvector"]
        GraphEngine["Graph RAG (Ontology Multi-Hop Traversal)\nIssues -> Procedures -> Conditions -> Chunks"]
        HybridMerge["Context Fusion & Chunk Deduplication"]
    end

    %% Corrective RAG Evaluator
    subgraph CRAGLayer ["5. Corrective RAG (CRAG) Engine"]
        Evaluator{"Evidence Evaluator\n(Relevance >= 0.65 & Sufficiency >= 0.70)"}
        PassAction["Action: CORRECT\nProceed to Generation"]
        RefineAction["Action: REFINE\nDecompose & Re-query with Extracted Entities"]
        DenyAction["Action: INCORRECT / OOD\nSafe Fallback Notification"]
    end

    %% Synthesis & Knowledge Layer
    subgraph SynthesisLayer ["6. LLM Synthesis & Official Grounding"]
        PromptBuilder["Role-Constrained Prompt Construction"]
        LLM["Groq LPU Engine (Qwen 2.5 27B / Llama 3)"]
        CitationEngine["Official Document Page Citation Builder\n(Item #, Verified Badge, Page Reference)"]
    end

    %% Data Stores
    subgraph StorageLayer ["7. Knowledge Base & Storage (PostgreSQL 18)"]
        DocDB[("Document Chunks & pgvector (384-dim)")]
        GraphDB[("Graph Nodes & Edges (GePNIC Ontology)")]
        DocFile[("Official Manual: FAQ.docx")]
    end

    %% Connections
    User --> UI
    UI --> AuthModal
    AuthModal --> JWT
    JWT --> RBACFilter

    RBACFilter -- "Unauthorized Role" --> DenyAction
    RBACFilter -- "Authorized" --> Classifier
    Classifier <--> Centroids
    Classifier <--> EntityRules
    Classifier --> DepthRouter

    DepthRouter -- "Direct / Context-dependent" --> VectorEngine
    DepthRouter -- "Procedural / Multi-source Multi-hop" --> GraphEngine
    DepthRouter -- "Hybrid" --> VectorEngine & GraphEngine

    VectorEngine <--> DocDB
    GraphEngine <--> GraphDB

    VectorEngine --> HybridMerge
    GraphEngine --> HybridMerge
    HybridMerge --> Evaluator

    Evaluator -- "Sufficiency >= 0.70" --> PassAction
    Evaluator -- "0.40 <= Sufficiency < 0.70" --> RefineAction
    RefineAction --> VectorEngine
    Evaluator -- "Sufficiency < 0.40" --> DenyAction

    PassAction --> PromptBuilder
    PromptBuilder --> LLM
    LLM --> CitationEngine
    CitationEngine --> UI
    DocFile -.-> UI
    Classifier -.-> AuditLog
    Evaluator -.-> AuditLog
```

---

## ⚡ Adaptive Dynamic Retrieval: Vector RAG, Graph RAG & Corrective RAG

ClarifiBids does **not** rely on a static or one-size-fits-all retrieval approach. It analyzes every query's semantic complexity and intent depth to route it dynamically across three distinct paradigms:

| Retrieval Strategy | When Selected | Mechanism | Target Questions |
| :--- | :--- | :--- | :--- |
| **Vector RAG** | `Direct` queries & definition inquiries | Cosine similarity over 384-dimensional dense embeddings (`BAAI/bge-small-en-v1.5`) stored in PostgreSQL `pgvector`. Fast and semantically granular. | *"What is the default date and time format in GePNIC?"*, *"What is the validity period of a DSC?"* |
| **Graph RAG** | `Procedural` & `Multi-source` / `Multi-hop` queries | Multi-hop graph traversal across the GePNIC Domain Knowledge Graph (`GraphNode` & `GraphEdge` tables). Traverses `ISSUES` $\rightarrow$ `TRIGGERS_PROCEDURE` $\rightarrow$ `REQUIRES_PREREQUISITE` $\rightarrow$ `GOVERNED_BY_CONDITION` $\rightarrow$ `SUPPORTS_EVIDENCE` to retrieve connected operational requirements. | *"What should I do if my DSC token is not detected?"*, *"Bid opener name not visible during tender creation"*, *"How to configure Java JRE for e-Procurement?"* |
| **Corrective RAG (CRAG)** | Continuous verification layer across **all** retrievals | Self-evaluates candidate evidence across two criteria: **Relevance** (threshold $\ge 0.65$) and **Sufficiency Coverage** (threshold $\ge 0.70$). If initial evidence is insufficient (`Action: REFINE`), it performs query expansion using extracted entities; if irrelevant, it triggers safe domain-protective fallback. | Prevents hallucinations, flags out-of-domain prompts, and refines complex technical questions. |

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

## 🏗 Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Lucide Icons, Vanilla CSS (NIC/GePNIC National Portal Design System).
- **Backend API**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy (Asyncpg + Psycopg).
- **Vector Database**: PostgreSQL 18 with `pgvector` extension for semantic embedding search.
- **Knowledge Graph**: Relational Graph Schema (`graph_nodes`, `graph_edges`) modeled after GePNIC procurement ontology with multi-hop recursive traversal.
- **LLM / Embeddings**:
  - LLM: Groq Cloud API (`qwen/qwen3.8-27b` or `llama3-70b-8192`)
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
