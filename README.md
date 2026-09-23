# ClarifiBids: Grounded Intelligence & Procedural Clarification Layer for GePNIC e-Procurement

ClarifiBids is an AI-powered technical assistance and procedural guidance platform designed specifically for the **Government e-Procurement System of India (GePNIC)** and **Central Public Procurement Portal (CPPP)**.

It solves critical tender submission blockers (such as DSC token initialization errors, Java JRE version mismatches, BoQ financial template requirements, and role-specific compliance) through **Role-Based Access Control (RBAC)**, **Corrective Retrieval-Augmented Generation (CRAG)**, and **Official Document Page Citations**.

---

## 🏛 Key Features

- **Official Government Policy Citations**: Every answer links back directly to the official GePNIC FAQ Manual, displaying the exact Item #, verified policy badge, relevance confidence, and **Document Page Number** (`Page 1`, `Page 2`, etc.).
- **Direct Official Document Download**: In-app download button for `FAQ.docx` so bidders and procurement officers can cross-examine official documentation offline.
- **Role-Based Access Control (RBAC)**:
  - **Bidder**: Domestic Indian procurement workflows, Indian Certifying Authority DSCs, BoQ in INR.
  - **Foreign Bidder**: International vendor compliance, overseas DSC procedures, multi-currency BoQ rules.
  - **Department User**: Procuring entities, tender creators, bid opener role assignment, DSC renewal best practices.
- **Corrective RAG Pipeline (CRAG)**: Evaluates retrieval sufficiency and relevance before generation; prevents hallucinations.
- **Audit-Logged Queries**: All interactions, classifications, and retrieval evaluations are securely audited to PostgreSQL.

---

## 🏗 Technology Architecture

- **Frontend**: React 18, TypeScript, Vite, Lucide Icons, Vanilla CSS (NIC/GePNIC National Portal Design System).
- **Backend API**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy (Asyncpg + Psycopg).
- **Vector Database**: PostgreSQL 18 with `pgvector` extension for semantic embedding search.
- **LLM / Embeddings**:
  - LLM: Groq Cloud API (`qwen/qwen3.8-27b` or Llama 3)
  - Embeddings: HuggingFace SentenceTransformers (`BAAI/bge-small-en-v1.5`, 384 dimensions) running locally.

---

## 🚀 Quick Setup & Installation

### Prerequisites
1. **Node.js** (v18 or higher) and `npm`
2. **Python** (v3.10 to v3.12 recommended)
3. **PostgreSQL 16+** with the **`pgvector`** extension installed
4. **Groq Cloud API Key** (Get one for free at [console.groq.com](https://console.groq.com/keys))

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
   ```
2. *(Windows users: If pgvector is not yet installed on your Postgres, copy the pgvector DLL, control, and SQL files into your PostgreSQL directory or run the included `install_pgvector.bat`)*.

---

### Step 3: Backend Setup & Configuration

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   - **Windows (cmd/powershell)**:
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

5. Ingest the GePNIC Knowledge Base Document:
   - Ensure `FAQ.docx` is present in the project root.
   - Run the ingestion pipeline from the `backend` directory:
     ```bash
     python app/services/ingestion/docx_parser.py
     ```
   *(This extracts the items, computes page numbers, generates 384-dimensional embeddings, and stores them in PostgreSQL).*

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
2. **Explore Grounded Questions**:
   - Click any of the pre-configured role-specific starter queries or type your own question in natural language.
3. **Verify Official Document Pages**:
   - Inspect the returned answer along with the exact citation card showing the GePNIC Item # and Document Page Number.
   - Click **Download Official FAQ** to view the original source `.docx`.
4. **Isolate Session Threads**:
   - Each user account maintains its own isolated conversation history. Click **Clear Thread** anytime to start a fresh workspace.

---

## 🔒 Security & Privacy Notice
Never commit real API keys or database passwords to version control. The repository `.gitignore` ensures that `.env` and virtual environments remain strictly local.
