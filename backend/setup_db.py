"""
Database Auto-Initializer and Seeder for ClarifiBids.
Checks if the local PostgreSQL database has tables and indexed chunks.
If empty, automatically creates tables, seeds initial roles & categories,
ingests FAQ.docx with embeddings, and populates the Knowledge Graph.
"""
import os
import sys
import logging
from sqlalchemy import select, func

from app.core.database import async_engine, AsyncSessionLocal, Base
from app.models import Role, QueryCategory, DocumentChunk
from app.services.ingestion.faq_parser import parse_faq_docx, compute_checksum
from app.services.embedding.embedding_service import embedding_service
from seed_graph import seed_knowledge_graph

logger = logging.getLogger("clarifibids.init_db")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FAQ_PATH = os.path.join(PROJECT_ROOT, "FAQ.docx")
if not os.path.exists(FAQ_PATH):
    FAQ_PATH = os.path.join(os.path.dirname(__file__), "FAQ.docx")


async def ensure_database_initialized():
    """Run table creation, role seeding, FAQ ingestion & graph seeding if database is empty."""
    logger.info("Verifying database schema and initial indexed chunks...")

    # 1. Ensure all schema tables exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Check if chunks already exist
    async with AsyncSessionLocal() as session:
        count_res = await session.execute(select(func.count(DocumentChunk.id)))
        chunk_count = count_res.scalar() or 0

        # Also seed roles & categories if missing
        role_res = await session.execute(select(func.count(Role.id)))
        role_count = role_res.scalar() or 0
        if role_count == 0:
            logger.info("Seeding initial roles and query categories...")
            roles = [
                Role(name="Bidder", is_business_role=True, description="Standard Indian Domestic Bidder"),
                Role(name="Foreign Bidder", is_business_role=True, description="International Bidder Regulations"),
                Role(name="Department User", is_business_role=True, description="Procuring Entity Official"),
                Role(name="ADMIN", is_business_role=False, description="System Administration"),
            ]
            session.add_all(roles)

            categories = [
                QueryCategory(name="Portal Guidelines & Procurement Terms", description="General terms, standard IST time, basic features"),
                QueryCategory(name="Portal Usage & User Management", description="Bidder enrollment, login, registration, password recovery"),
                QueryCategory(name="Technical Assistance", description="DSC detection, JRE setup, browser, OS, driver configuration"),
                QueryCategory(name="Tender & Bid Information", description="Tender search, bid submission, BOQ, EMD fee, corrigenda, covers"),
                QueryCategory(name="Security Information", description="Digital signatures, encryption, CA validity, tamper prevention"),
                QueryCategory(name="Foreign Bidder Information", description="International vendor guidelines, foreign currency, foreign DSC"),
            ]
            session.add_all(categories)
            await session.commit()
            logger.info("Roles and categories seeded successfully.")

        # Ensure default ADMIN account exists
        from app.models import User, UserRole
        from app.core.auth import hash_password
        admin_check = await session.execute(select(User).where(User.username == "admin"))
        if not admin_check.scalars().first():
            role_q = await session.execute(select(Role).where(Role.name == "ADMIN"))
            admin_role = role_q.scalars().first()
            if admin_role:
                default_admin = User(
                    username="admin",
                    email="admin@gepnic.gov.in",
                    password_hash=hash_password("admin123"),
                    is_active=True
                )
                session.add(default_admin)
                await session.flush()
                session.add(UserRole(user_id=default_admin.id, role_id=admin_role.id))
                await session.commit()
                logger.info("Default admin user created (admin / admin123).")


        if chunk_count > 0:
            logger.info(f"Database is already indexed with {chunk_count} chunks. Skipping ingestion.")
            return

        logger.info(f"No indexed chunks found. Auto-ingesting FAQ from {FAQ_PATH}...")
        if not os.path.exists(FAQ_PATH):
            logger.warning(f"FAQ document not found at {FAQ_PATH}. Skipping auto-ingestion.")
            return

        # 3. Ingest FAQ document chunks and embeddings
        from app.models import KnowledgeSource, Document, DocumentEmbedding

        faq_items = parse_faq_docx(FAQ_PATH)
        checksum = compute_checksum(FAQ_PATH)

        # Knowledge Source
        ks_res = await session.execute(select(KnowledgeSource).where(KnowledgeSource.source_name == "GePNIC FAQ Repository"))
        source = ks_res.scalars().first()
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

        doc = Document(
            source_id=source.id,
            title="GePNIC Frequently Asked Questions",
            document_type="FAQ",
            file_name=os.path.basename(FAQ_PATH),
            checksum=checksum,
            version="1.0",
            status="INDEXING"
        )
        session.add(doc)
        await session.flush()

        logger.info(f"Generating embeddings for {len(faq_items)} FAQ items...")
        texts_to_embed = [item["content"] for item in faq_items]
        embeddings = embedding_service.embed_batch(texts_to_embed)

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
        logger.info(f"Ingested {len(faq_items)} chunks with embeddings successfully.")

    # 4. Seed Knowledge Graph
    logger.info("Seeding domain knowledge graph...")
    await seed_knowledge_graph()
    logger.info("Database auto-initialization complete! Ready to serve queries.")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ensure_database_initialized())
