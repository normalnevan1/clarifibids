"""
Intelligent Document Ingestion & Role-Based Access Control (RBAC) Classifier.
Handles generic document ingestion (DOCX, PDF, TXT) and uses Groq AI
to classify each chunk into:
  - 'GENERAL' (Accessible to ALL roles: Bidder, Foreign Bidder, Department User)
  - 'Bidder' (Strictly domestic Indian vendors)
  - 'Foreign Bidder' (Strictly overseas/international vendors)
  - 'Department User' (Strictly internal government tender officials)
"""

import os
import hashlib
import logging
from typing import List, Dict, Any, Optional
import docx
from pypdf import PdfReader
from groq import Groq

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import KnowledgeSource, Document, DocumentChunk, DocumentEmbedding
from app.services.embedding.embedding_service import embedding_service
from sqlalchemy import select

logger = logging.getLogger("clarifibids.document_ingestion")


def compute_file_checksum(file_bytes: bytes) -> str:
    """Computes a SHA-256 hash of file content to detect duplicate uploads."""
    return hashlib.sha256(file_bytes).hexdigest()


def extract_chunks_from_file(file_name: str, file_bytes: bytes, chunk_size_words: int = 250) -> List[Dict[str, Any]]:
    """
    Extracts text from DOCX, PDF, or TXT files and splits into logical chunks.
    
    Chunking strategy:
    - DOCX: Preserves Q&A table structures when present, otherwise splits paragraphs.
    - PDF: Extracts text page-by-page and splits on double newlines.
    - TXT/MD: Decodes UTF-8 and breaks into paragraph chunks.
    - Sub-chunking: Any block exceeding `chunk_size_words` is sliced into smaller windows.
    """
    ext = os.path.splitext(file_name)[1].lower()
    raw_paragraphs = []

    if ext == ".docx":
        import io
        doc = docx.Document(io.BytesIO(file_bytes))
        # Handle FAQ-style 2-column tables (Question in row 1, Answer in row 2)
        if doc.tables:
            for idx, table in enumerate(doc.tables, start=1):
                rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                if len(rows) >= 2 and rows[0][0] and rows[1][0]:
                    q, a = rows[0][0], rows[1][0]
                    raw_paragraphs.append({
                        "question": q,
                        "answer": a,
                        "content": f"Question: {q}\nAnswer: {a}"
                    })
        # Also parse normal text paragraphs
        for p in doc.paragraphs:
            text = p.text.strip()
            if text and len(text.split()) > 10:
                raw_paragraphs.append({"content": text})

    elif ext == ".pdf":
        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        for page_idx, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                # Split page into paragraph blocks
                blocks = [b.strip() for b in text.split("\n\n") if len(b.strip().split()) > 10]
                for block in blocks:
                    raw_paragraphs.append({"content": block, "page_number": page_idx})

    elif ext in [".txt", ".md"]:
        text = file_bytes.decode("utf-8", errors="ignore")
        blocks = [b.strip() for b in text.split("\n\n") if len(b.strip().split()) > 10]
        for block in blocks:
            raw_paragraphs.append({"content": block})

    else:
        raise ValueError(f"Unsupported file type: {ext}. Please upload .docx, .pdf, or .txt.")

    chunks = []
    current_idx = 1
    for item in raw_paragraphs:
        content = item["content"].strip()
        words = content.split()
        if len(words) <= chunk_size_words:
            chunks.append({
                "chunk_index": current_idx,
                "content": content,
                "question": item.get("question"),
                "answer": item.get("answer"),
                "page_number": item.get("page_number"),
                "token_count": len(words)
            })
            current_idx += 1
        else:
            # Sub-chunk longer text
            for i in range(0, len(words), chunk_size_words):
                sub_words = words[i:i + chunk_size_words]
                sub_content = " ".join(sub_words)
                chunks.append({
                    "chunk_index": current_idx,
                    "content": sub_content,
                    "question": item.get("question"),
                    "answer": item.get("answer"),
                    "page_number": item.get("page_number"),
                    "token_count": len(sub_words)
                })
                current_idx += 1

    return chunks


def classify_role_with_groq(text: str, groq_client: Optional[Groq] = None) -> str:
    """
    Intelligently classifies procurement chunk text into one of 4 access roles:
    - GENERAL: Portal login, password, date & time (IST), common browser rules, general navigation
    - Bidder: Domestic Indian bidder procedures, EMD exemption, MSME/NSIC, domestic bank gateway
    - Foreign Bidder: Cross-border, international bidder, foreign currency, overseas DSC, RBI rules
    - Department User: Procuring entity official, tender creator, bid opener, dual-key 2-of-2 opening
    """
    # 1. Fast heuristic checks to save latency
    lower = text.lower()
    if any(k in lower for k in ["tender creator", "bid opener", "nodal officer", "who will create users", "comparative chart", "department user", "opener name"]):
        return "Department User"
    if any(k in lower for k in ["foreign bidder", "foreign consultant", "outside india", "out of india", "currencies other than indian rupees", "international firm", "foreign dsc"]):
        return "Foreign Bidder"

    # 2. Use Groq AI for intelligent disambiguation
    if not settings.GROQ_API_KEY:
        return "GENERAL"

    try:
        if groq_client is None:
            groq_client = Groq(api_key=settings.GROQ_API_KEY)

        prompt = (
            "You are an expert e-Procurement Access Control Classifier. "
            "Analyze the text chunk below and classify its audience into strictly one of these 4 categories:\n"
            "- GENERAL: Universal portal rules, system requirements, login, passwords, IST time format, general FAQs applicable to everyone.\n"
            "- Bidder: Procedures, fees, EMD exemption specifically for domestic Indian bidders.\n"
            "- Foreign Bidder: Procedures, currencies, DSC specifically for foreign or international bidders.\n"
            "- Department User: Internal government officials, tender creation, bid opening, administrative management.\n\n"
            f"Chunk Text:\n\"\"\"{text[:1000]}\"\"\"\n\n"
            "Respond ONLY with one of the exact names: GENERAL, Bidder, Foreign Bidder, or Department User."
        )

        response = groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=15
        )
        prediction = (response.choices[0].message.content or "").strip()
        for valid_role in ["Foreign Bidder", "Department User", "Bidder", "GENERAL"]:
            if valid_role.lower() in prediction.lower():
                return valid_role
    except Exception as e:
        logger.warning(f"Groq classification fallback: {e}")

def validate_document_domain(sample_text: str, groq_client: Optional[Groq] = None) -> bool:
    """
    Validates whether the uploaded document belongs to the domain of e-Procurement,
    tendering, bidding, portal guidelines, or technical compliance.
    Rejects completely random/unrelated documents (e.g. cooking recipes, movie scripts, poetry).
    """
    # 1. Fast domain keyword check
    domain_keywords = [
        "procurement", "tender", "bid", "bidder", "eprocurement", "gepnic",
        "portal", "dsc", "digital signature", "boq", "emd", "corrigendum",
        "contract", "vendor", "technical bid", "financial bid", "evaluation",
        "certifying authority", "token", "pki", "exception site", "java",
        "department", "nodal", "government", "solicitation", "proposal"
    ]
    lower = sample_text.lower()
    matches = sum(1 for kw in domain_keywords if kw in lower)
    if matches >= 2:
        return True

    # 2. If keywords are scarce, check with Groq AI
    if not settings.GROQ_API_KEY or groq_client is None:
        return matches >= 1

    try:
        prompt = (
            "You are a gatekeeper for an e-Procurement knowledge repository (ClarifiBids / GePNIC). "
            "Examine this sample excerpt from an uploaded document:\n\n"
            f"\"\"\"{sample_text[:1200]}\"\"\"\n\n"
            "Is this document related to procurement, bidding, tendering, public contracts, vendor guidelines, "
            "portal user instructions, security, or technical assistance for portals?\n"
            "Answer strictly with either 'ACCEPT' or 'REJECT'."
        )
        response = groq_client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10
        )
        decision = (response.choices[0].message.content or "").strip().upper()
        return "ACCEPT" in decision
    except Exception as e:
        logger.warning(f"Domain validation AI fallback: {e}")
        return matches >= 1


async def ingest_document_file(
    file_name: str,
    file_bytes: bytes,
    source_name: str = "Uploaded Knowledge Document",
    source_description: str = "Administrator uploaded reference document."
) -> Dict[str, Any]:
    """
    Ingests, validates domain relevance, intelligently chunks, classifies roles via Groq AI,
    computes BAAI embeddings, and stores in PostgreSQL.
    """
    checksum = compute_file_checksum(file_bytes)
    chunks_data = extract_chunks_from_file(file_name, file_bytes)
    if not chunks_data:
        raise ValueError("Could not extract any readable text chunks from the uploaded document.")

    groq_client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None

    # Step: Domain Relevance Validation (Reject random / unrelated files)
    sample_text = " ".join([c["content"] for c in chunks_data[:5]])
    is_valid_domain = validate_document_domain(sample_text, groq_client)
    if not is_valid_domain:
        raise ValueError(
            "Document rejected: The uploaded file does not appear to be related to e-Procurement, "
            "tendering, portal guidelines, or bidding. Please upload relevant procurement reference material."
        )

    # Classify each chunk's role intelligently
    classified_chunks = []
    role_counts = {"GENERAL": 0, "Bidder": 0, "Foreign Bidder": 0, "Department User": 0}

    for ch in chunks_data:
        role = classify_role_with_groq(ch["content"], groq_client)
        ch["user_role"] = role
        ch["metadata"] = {
            "source": source_name,
            "file_name": file_name,
            "chunk_index": ch["chunk_index"],
            "user_role": role,
            "applicable_role": role
        }
        role_counts[role] = role_counts.get(role, 0) + 1
        classified_chunks.append(ch)

    # Compute Embeddings
    texts_to_embed = [c["content"] for c in classified_chunks]
    embeddings = embedding_service.embed_batch(texts_to_embed)

    async with AsyncSessionLocal() as session:
        # 1. Knowledge source
        source_stmt = select(KnowledgeSource).where(KnowledgeSource.source_name == source_name)
        res = await session.execute(source_stmt)
        source = res.scalars().first()
        if not source:
            source = KnowledgeSource(
                source_name=source_name,
                source_type="ADMIN_UPLOAD",
                description=source_description,
                location=file_name,
                version="1.0"
            )
            session.add(source)
            await session.flush()

        # 2. Document record
        doc = Document(
            source_id=source.id,
            title=file_name,
            document_type=os.path.splitext(file_name)[1].replace(".", "").upper(),
            file_name=file_name,
            checksum=checksum,
            version="1.0",
            status="INDEXED"
        )
        session.add(doc)
        await session.flush()

        # 3. Store chunks and embeddings
        for ch, emb in zip(classified_chunks, embeddings):
            chunk_rec = DocumentChunk(
                document_id=doc.id,
                chunk_index=ch["chunk_index"],
                content=ch["content"],
                question=ch.get("question"),
                answer=ch.get("answer"),
                page_number=ch.get("page_number"),
                section_title=f"{ch['user_role']} Section",
                token_count=ch.get("token_count"),
                metadata_=ch["metadata"]
            )
            session.add(chunk_rec)
            await session.flush()

            doc_emb = DocumentEmbedding(
                chunk_id=chunk_rec.id,
                embedding=emb,
                embedding_model="BAAI/bge-small-en-v1.5"
            )
            session.add(doc_emb)

        await session.commit()

    return {
        "document_id": str(doc.id),
        "file_name": file_name,
        "total_chunks": len(classified_chunks),
        "role_breakdown": role_counts,
        "status": "INDEXED"
    }
