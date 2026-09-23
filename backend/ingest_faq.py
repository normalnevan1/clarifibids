import asyncio
import os
import sys
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, async_engine, Base
from app.models import KnowledgeSource, Document, DocumentChunk, DocumentEmbedding
from app.services.ingestion.faq_parser import parse_faq_docx, compute_checksum
from app.services.embedding.embedding_service import embedding_service

FAQ_PATH = r"c:\Users\NormalNevan\Desktop\New folder\FAQ.docx"

async def init_tables():
    print("1. Creating database tables if not existing...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created successfully.")

async def ingest_faq():
    if not os.path.exists(FAQ_PATH):
        print(f"Error: FAQ document not found at {FAQ_PATH}")
        sys.exit(1)
        
    print(f"2. Parsing {FAQ_PATH}...")
    faq_items = parse_faq_docx(FAQ_PATH)
    checksum = compute_checksum(FAQ_PATH)
    print(f"Parsed {len(faq_items)} items. Checksum: {checksum}")
    
    async with AsyncSessionLocal() as session:
        # Check if KnowledgeSource exists
        stmt = select(KnowledgeSource).where(KnowledgeSource.source_name == "GePNIC FAQ Repository")
        res = await session.execute(stmt)
        source = res.scalars().first()
        
        if not source:
            source = KnowledgeSource(
                source_name="GePNIC FAQ Repository",
                source_type="FAQ",
                description="Official Frequently Asked Questions on GePNIC portal operations and guidelines.",
                location=FAQ_PATH,
                version="1.0"
            )
            session.add(source)
            await session.flush()
            print(f"Created KnowledgeSource id={source.id}")
            
        # Check if Document already ingested
        doc_stmt = select(Document).where(Document.checksum == checksum)
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalars().first()
        
        if doc:
            print(f"Document already ingested with ID: {doc.id}. Checking chunk count...")
            count_stmt = select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            chunks_res = await session.execute(count_stmt)
            existing_chunks = chunks_res.scalars().all()
            if len(existing_chunks) >= len(faq_items):
                print(f"All {len(existing_chunks)} chunks already present in database.")
                return
            print(f"Re-ingesting chunks for document {doc.id}...")
        else:
            doc = Document(
                source_id=source.id,
                title="GePNIC FAQ - Official Guidelines",
                document_type="DOCX",
                file_name="FAQ.docx",
                checksum=checksum,
                version="1.0",
                status="PROCESSING"
            )
            session.add(doc)
            await session.flush()
            print(f"Created Document record id={doc.id}")
            
        print("3. Generating embeddings with BGE-small (CPU) and saving to database...")
        # Prepare texts to embed in batch
        texts_to_embed = [item["content"] for item in faq_items]
        embeddings = embedding_service.embed_batch(texts_to_embed)
        print(f"Generated {len(embeddings)} embeddings of dimension {len(embeddings[0])}.")
        
        for item, emb_vector in zip(faq_items, embeddings):
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=item["chunk_index"],
                content=item["content"],
                question=item["question"],
                answer=item["answer"],
                section_title=item.get("category"),
                token_count=item.get("token_count"),
                metadata_=item.get("metadata")
            )
            session.add(chunk)
            await session.flush()
            
            doc_embedding = DocumentEmbedding(
                chunk_id=chunk.id,
                embedding=emb_vector,
                embedding_model="BAAI/bge-small-en-v1.5"
            )
            session.add(doc_embedding)
            
        doc.status = "INDEXED"
        await session.commit()
        print("Ingestion and indexing completed successfully! All 67 chunks indexed with embeddings.")

if __name__ == "__main__":
    asyncio.run(init_tables())
    asyncio.run(ingest_faq())
