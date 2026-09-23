import asyncio
import uuid
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import GraphNode, GraphEdge, DocumentChunk

# GePNIC Domain Ontology definitions from Dissertation (Section 4.5 B & Section 5 b)
NODES_DATA = [
    # ISSUES
    {"name": "DSC Detection Issue", "node_type": "ISSUE", "description": "USB Token or Digital Signature not recognized by the browser during bid submission"},
    {"name": "JRE Applet Blocked", "node_type": "ISSUE", "description": "Java Runtime Environment blocking signing component due to security level"},
    {"name": "EMD Payment Failure", "node_type": "ISSUE", "description": "Earnest Money Deposit payment transaction failure or status not updating"},
    {"name": "BoQ Upload Error", "node_type": "ISSUE", "description": "Validation error or format mismatch when uploading price bid / Bill of Quantities"},
    {"name": "Bid Opener Decryption Failure", "node_type": "ISSUE", "description": "Department user unable to decrypt bids due to missing secondary opener token"},

    # PROCEDURES
    {"name": "DSC Token Configuration Procedure", "node_type": "PROCEDURE", "description": "Steps to install vendor PKI drivers and register token in browser"},
    {"name": "Java Security Configuration Procedure", "node_type": "PROCEDURE", "description": "Steps to add portal URL to Java Exception Site list and verify 32-bit/64-bit JRE"},
    {"name": "Bid Submission Lifecycle Procedure", "node_type": "PROCEDURE", "description": "Complete sequential workflow for bid submission, packet upload, and final ACK"},
    {"name": "EMD Exemption Claim Procedure", "node_type": "PROCEDURE", "description": "Procedure for MSME/NSIC registered vendors to upload exemption certificate"},
    {"name": "Multi-party Bid Decryption Procedure", "node_type": "PROCEDURE", "description": "Department procedure for opening technical and financial bids using 2-of-2 dual keys"},
    {"name": "Foreign Bidder DSC Procurement Procedure", "node_type": "PROCEDURE", "description": "Steps for international vendors to obtain Class-3 DSC from licensed Indian CAs"},

    # CONDITIONS
    {"name": "Valid Class 2 or Class 3 DSC", "node_type": "CONDITION", "description": "Digital Signature Certificate must be active and not expired"},
    {"name": "Compatible Browser and Java Runtime", "node_type": "CONDITION", "description": "JRE 1.8+ installed with permitted browser settings"},
    {"name": "Valid MSME/NSIC Registration", "node_type": "CONDITION", "description": "Valid registration document matching tender category for EMD exemption"},
    {"name": "2-of-2 Bid Opener Quorum", "node_type": "CONDITION", "description": "At least two assigned bid openers must authenticate with DSC tokens to decrypt bids"},

    # RULES
    {"name": "Indian Standard Time Rule", "node_type": "RULE", "description": "All server timestamps and tender deadlines strictly follow IST (GMT+5:30)"},
    {"name": "Foreign Currency BoQ Rule", "node_type": "RULE", "description": "Quotes in non-INR currencies only permitted if explicitly authorized in NIT"}
]

# Structural relationships (Multi-hop chains)
EDGES_DATA = [
    # DSC Detection Issue -> requires prerequisites
    {"source": "DSC Detection Issue", "target": "DSC Token Configuration Procedure", "rel": "TRIGGERS_PROCEDURE"},
    {"source": "DSC Detection Issue", "target": "JRE Applet Blocked", "rel": "REQUIRES_PREREQUISITE"},
    {"source": "DSC Token Configuration Procedure", "target": "Valid Class 2 or Class 3 DSC", "rel": "GOVERNED_BY_CONDITION"},
    {"source": "JRE Applet Blocked", "target": "Java Security Configuration Procedure", "rel": "TRIGGERS_PROCEDURE"},
    {"source": "Java Security Configuration Procedure", "target": "Compatible Browser and Java Runtime", "rel": "GOVERNED_BY_CONDITION"},

    # Bid Submission -> requires DSC + BoQ + EMD
    {"source": "Bid Submission Lifecycle Procedure", "target": "DSC Token Configuration Procedure", "rel": "REQUIRES_PREREQUISITE"},
    {"source": "Bid Submission Lifecycle Procedure", "target": "Indian Standard Time Rule", "rel": "GOVERNED_BY_CONDITION"},
    {"source": "Bid Submission Lifecycle Procedure", "target": "EMD Exemption Claim Procedure", "rel": "SUPPORTS_EVIDENCE"},

    # Department Decryption
    {"source": "Bid Opener Decryption Failure", "target": "Multi-party Bid Decryption Procedure", "rel": "TRIGGERS_PROCEDURE"},
    {"source": "Multi-party Bid Decryption Procedure", "target": "2-of-2 Bid Opener Quorum", "rel": "GOVERNED_BY_CONDITION"},

    # Foreign Bidder
    {"source": "Foreign Bidder DSC Procurement Procedure", "target": "Foreign Currency BoQ Rule", "rel": "SUPPORTS_EVIDENCE"}
]

# FAQ chunk associations (Item numbers in GePNIC FAQ knowledge base)
CHUNK_ASSOCIATIONS = [
    {"concept": "DSC Token Configuration Procedure", "item_numbers": [1, 2, 8]},
    {"concept": "Java Security Configuration Procedure", "item_numbers": [3, 43]},
    {"concept": "Indian Standard Time Rule", "item_numbers": [4, 5]},
    {"concept": "Bid Submission Lifecycle Procedure", "item_numbers": [26, 27, 28, 29]},
    {"concept": "EMD Exemption Claim Procedure", "item_numbers": [28, 30]},
    {"concept": "Multi-party Bid Decryption Procedure", "item_numbers": [48, 49, 50]},
    {"concept": "Foreign Bidder DSC Procurement Procedure", "item_numbers": [44, 45, 46]}
]

async def seed_knowledge_graph():
    print("Seeding GePNIC Knowledge Graph in PostgreSQL...")
    async with AsyncSessionLocal() as session:
        # 1. Create or fetch Concept Nodes
        node_map = {}
        for n_data in NODES_DATA:
            stmt = select(GraphNode).where(GraphNode.name == n_data["name"])
            res = await session.execute(stmt)
            existing = res.scalars().first()
            if not existing:
                node = GraphNode(
                    name=n_data["name"],
                    node_type=n_data["node_type"],
                    description=n_data["description"],
                    metadata_={"domain": "GePNIC"}
                )
                session.add(node)
                await session.flush()
                node_map[n_data["name"]] = node.id
            else:
                node_map[n_data["name"]] = existing.id

        # 2. Create Concept-to-Concept Edges
        for e_data in EDGES_DATA:
            src_id = node_map.get(e_data["source"])
            tgt_id = node_map.get(e_data["target"])
            if src_id and tgt_id:
                edge_stmt = select(GraphEdge).where(
                    GraphEdge.source_node_id == src_id,
                    GraphEdge.target_node_id == tgt_id,
                    GraphEdge.relationship_type == e_data["rel"]
                )
                e_res = await session.execute(edge_stmt)
                if not e_res.scalars().first():
                    edge = GraphEdge(
                        source_node_id=src_id,
                        target_node_id=tgt_id,
                        relationship_type=e_data["rel"],
                        weight=1.0,
                        metadata_={"domain": "GePNIC"}
                    )
                    session.add(edge)

        # 3. Create Chunk Nodes & Chunk-to-Concept Supporting Edges
        for assoc in CHUNK_ASSOCIATIONS:
            concept_name = assoc["concept"]
            concept_id = node_map.get(concept_name)
            if not concept_id:
                continue

            for item_num in assoc["item_numbers"]:
                chunk_node_name = f"Evidence_Item_{item_num}"
                c_stmt = select(GraphNode).where(GraphNode.name == chunk_node_name)
                c_res = await session.execute(c_stmt)
                chunk_node = c_res.scalars().first()
                if not chunk_node:
                    chunk_node = GraphNode(
                        name=chunk_node_name,
                        node_type="CHUNK",
                        description=f"Supporting evidence from GePNIC FAQ Item #{item_num}",
                        metadata_={"item_number": item_num, "source": "GePNIC FAQ"}
                    )
                    session.add(chunk_node)
                    await session.flush()

                # Edge from concept to chunk
                edge_stmt = select(GraphEdge).where(
                    GraphEdge.source_node_id == concept_id,
                    GraphEdge.target_node_id == chunk_node.id,
                    GraphEdge.relationship_type == "SUPPORTS_EVIDENCE"
                )
                e_res = await session.execute(edge_stmt)
                if not e_res.scalars().first():
                    edge = GraphEdge(
                        source_node_id=concept_id,
                        target_node_id=chunk_node.id,
                        relationship_type="SUPPORTS_EVIDENCE",
                        weight=1.0,
                        metadata_={"item_number": item_num}
                    )
                    session.add(edge)

        await session.commit()
        print("Knowledge Graph seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_knowledge_graph())
