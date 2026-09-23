import docx
import re
import hashlib
from typing import List, Dict, Any

CATEGORIES = {
    "Technical Assistance": [
        "dsc", "driver", "jre", "java", "browser", "firefox", "chrome", 
        "windows", "pentium", "client machine", "applet", "cryptographic", "token"
    ],
    "Tender & Bid Information": [
        "tender", "bid", "boq", "emd", "corrigendum", "schedule", "fee", 
        "exemption", "covers", "packet", "submission", "bidder enrollment"
    ],
    "Portal Usage & User Management": [
        "login", "account", "enrollment", "register", "password", "user id", 
        "profile", "reset", "forgot"
    ],
    "Security Information": [
        "security", "encryption", "certificate", "ca", "certifying", "validity", 
        "tamper", "class 2", "class 3", "digital signature"
    ],
    "Foreign Bidder Information": [
        "foreign", "currency", "international", "overseas", "country", "passport"
    ],
    "Portal Guidelines & Procurement Terms": [
        "eprocurement", "terms", "guidelines", "standard", "date and time", 
        "ist", "time zone", "features"
    ]
}

def compute_checksum(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def classify_faq_item(question: str, answer: str) -> str:
    text = (question + " " + answer).lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "Portal Guidelines & Procurement Terms"

def determine_applicable_role(question: str, answer: str) -> str:
    text = (question + " " + answer).lower()
    # Check Foreign Bidder first
    if any(k in text for k in ["foreign", "international", "out of india", "outside india", "foreign bidder", "foreign consultant", "other than indian rupees"]):
        return "Foreign Bidder"
    # Check Department User
    if any(k in text for k in ["department user", "tender creator", "tender opener", "bid opener", "nodal officer", "auditor role", "procuring entity", "who will create users", "comparative chart"]):
        return "Department User"
    return "Bidder"

def parse_faq_docx(file_path: str) -> List[Dict[str, Any]]:
    doc = docx.Document(file_path)
    faq_items = []
    
    # FAQ.docx structures each Q&A pair in a 2-row table
    for idx, table in enumerate(doc.tables, start=1):
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        if len(rows) >= 2:
            question = rows[0][0]
            answer = rows[1][0]
            
            if not question or not answer:
                continue
                
            category = classify_faq_item(question, answer)
            role = determine_applicable_role(question, answer)
            
            # Estimate token count (approx 1 token ~= 4 chars or 0.75 words)
            total_text = f"Question: {question}\nAnswer: {answer}"
            token_count = len(total_text.split())
            
            faq_items.append({
                "chunk_index": idx,
                "question": question,
                "answer": answer,
                "content": total_text,
                "category": category,
                "token_count": token_count,
                "user_role": role,
                "metadata": {
                    "source": "GePNIC FAQ Repository",
                    "file_name": "FAQ.docx",
                    "item_number": idx,
                    "category": category,
                    "user_role": role
                }
            })
            
    return faq_items

if __name__ == "__main__":
    items = parse_faq_docx(r"c:\Users\NormalNevan\Desktop\New folder\FAQ.docx")
    print(f"Parsed {len(items)} FAQ items successfully!")
    print("Sample Item 1:", items[0]["question"])
    print("Sample Item 1 Category:", items[0]["category"])
