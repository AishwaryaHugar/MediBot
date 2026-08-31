import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
# Local disk Qdrant path. Relative values are anchored to BASE_DIR (project root)
# so the same .env works regardless of which subdirectory Python is invoked from.
_qdrant_path_raw = os.getenv("QDRANT_PATH", "qdrant_db")
QDRANT_PATH = str(
    BASE_DIR / _qdrant_path_raw
    if not os.path.isabs(_qdrant_path_raw)
    else Path(_qdrant_path_raw)
)
SECRET_KEY = os.getenv("SECRET_KEY", "medibot-secret-key-change-in-production")
DATABASE_PATH = os.getenv("DATABASE_PATH") or str(BASE_DIR / "db" / "mediassist.db")

COLLECTION_NAME = "mediassist_docs"
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
EMBEDDING_DIM = 384
SPARSE_DIM = 30000
TOP_K_RETRIEVAL = 10
TOP_K_RERANKED = 3
LLM_MODEL = os.getenv("LLM_MODEL") or "openai/gpt-oss-120b"

ROLE_COLLECTIONS: dict[str, list[str]] = {
    "doctor": ["clinical", "nursing", "general"],
    "nurse": ["nursing", "general"],
    "billing_executive": ["billing", "general"],
    "technician": ["equipment", "general"],
    "admin": ["clinical", "nursing", "billing", "equipment", "general"],
}

COLLECTION_ACCESS_ROLES: dict[str, list[str]] = {
    "general": ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical": ["doctor", "admin"],
    "nursing": ["nurse", "doctor", "admin"],
    "billing": ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}

DEMO_USERS: dict[str, dict] = {
    "doctor_user":  {"password": "password123", "role": "doctor"},
    "nurse_user":   {"password": "password123", "role": "nurse"},
    "billing_user": {"password": "password123", "role": "billing_executive"},
    "tech_user":    {"password": "password123", "role": "technician"},
    "admin_user":   {"password": "password123", "role": "admin"},
}

SQL_ROLES: set[str] = {"billing_executive", "admin"}

DOCUMENTS = [
    {"path": str(BASE_DIR / "general"  / "staff_handbook.pdf"),         "collection": "general"},
    {"path": str(BASE_DIR / "general"  / "leave_policy.pdf"),           "collection": "general"},
    {"path": str(BASE_DIR / "general"  / "code_of_conduct.pdf"),        "collection": "general"},
    {"path": str(BASE_DIR / "general"  / "general_faqs.pdf"),           "collection": "general"},
    {"path": str(BASE_DIR / "clinical" / "treatment_protocols.pdf"),    "collection": "clinical"},
    {"path": str(BASE_DIR / "clinical" / "drug_formulary.pdf"),         "collection": "clinical"},
    {"path": str(BASE_DIR / "clinical" / "diagnostic_reference.pdf"),   "collection": "clinical"},
    {"path": str(BASE_DIR / "nursing"  / "icu_nursing_procedures.pdf"), "collection": "nursing"},
    {"path": str(BASE_DIR / "nursing"  / "infection_control.pdf"),      "collection": "nursing"},
    {"path": str(BASE_DIR / "billing"  / "billing_codes.pdf"),          "collection": "billing"},
    {"path": str(BASE_DIR / "billing"  / "claim_submission_guide.md"),  "collection": "billing"},
    {"path": str(BASE_DIR / "equipment"/ "equipment_manual.pdf"),       "collection": "equipment"},
]
