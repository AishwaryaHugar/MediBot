"""
Per-user test suite for MediBot.

Covers all five demo accounts:
  doctor_user    → role: doctor
  nurse_user     → role: nurse
  billing_user   → role: billing_executive
  tech_user      → role: technician
  admin_user     → role: admin

Run from the project root:
    pytest tests/test_per_user.py -v

These tests are unit / integration tests that do NOT require a running
Qdrant server or Groq API key.  External I/O is monkey-patched via
pytest fixtures defined here.
"""

import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Make sure the backend package is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _groq_response(text: str):
    """Build a minimal Groq-shaped response object."""
    msg = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


# ---------------------------------------------------------------------------
# Auth tests (role-agnostic, but covers every demo account)
# ---------------------------------------------------------------------------

class TestAuthentication:
    """FR-01 / FR-02 — login returns correct role + token per user."""

    @pytest.mark.parametrize("username,expected_role", [
        ("doctor_user",  "doctor"),
        ("nurse_user",   "nurse"),
        ("billing_user", "billing_executive"),
        ("tech_user",    "technician"),
        ("admin_user",   "admin"),
    ])
    def test_correct_credentials_return_role(self, username, expected_role):
        from auth import authenticate
        user = authenticate(username, "password123")
        assert user is not None
        assert user["role"] == expected_role

    @pytest.mark.parametrize("username", [
        "doctor_user", "nurse_user", "billing_user", "tech_user", "admin_user",
    ])
    def test_wrong_password_rejected(self, username):
        from auth import authenticate
        assert authenticate(username, "wrong_password") is None

    def test_unknown_user_rejected(self):
        from auth import authenticate
        assert authenticate("ghost_user", "password123") is None

    @pytest.mark.parametrize("username,role", [
        ("doctor_user",  "doctor"),
        ("nurse_user",   "nurse"),
        ("billing_user", "billing_executive"),
        ("tech_user",    "technician"),
        ("admin_user",   "admin"),
    ])
    def test_token_round_trip(self, username, role):
        from auth import create_token, decode_token
        token = create_token(username, role)
        payload = decode_token(token)
        assert payload["username"] == username
        assert payload["role"] == role

    def test_expired_token_raises(self):
        from auth import decode_token
        import jwt
        from config import SECRET_KEY
        expired = jwt.encode(
            {"username": "x", "role": "doctor", "exp": int(time.time()) - 10},
            SECRET_KEY,
            algorithm="HS256",
        )
        with pytest.raises(ValueError, match="expired"):
            decode_token(expired)

    def test_tampered_token_raises(self):
        from auth import decode_token
        with pytest.raises(ValueError, match="Invalid"):
            decode_token("not.a.real.token")


# ---------------------------------------------------------------------------
# RBAC tests — collection access per role
# ---------------------------------------------------------------------------

class TestRBACCollections:
    """Each role should see exactly its permitted collections and nothing more."""

    EXPECTED = {
        "doctor":            {"clinical", "nursing", "general"},
        "nurse":             {"nursing", "general"},
        "billing_executive": {"billing", "general"},
        "technician":        {"equipment", "general"},
        "admin":             {"clinical", "nursing", "billing", "equipment", "general"},
    }

    @pytest.mark.parametrize("role,expected", EXPECTED.items())
    def test_role_collections(self, role, expected):
        from rbac import get_role_collections
        assert set(get_role_collections(role)) == expected

    def test_unknown_role_returns_empty(self):
        from rbac import get_role_collections
        assert get_role_collections("hacker") == []

    def test_qdrant_filter_must_clause(self):
        from rbac import build_qdrant_filter
        f = build_qdrant_filter("nurse")
        must = f.must
        assert len(must) == 1
        assert must[0].key == "collection"
        assert set(must[0].match.any) == {"nursing", "general"}

    @pytest.mark.parametrize("role,can_sql", [
        ("doctor",            False),
        ("nurse",             False),
        ("billing_executive", True),
        ("technician",        False),
        ("admin",             True),
    ])
    def test_sql_permission(self, role, can_sql):
        from rbac import is_sql_permitted
        assert is_sql_permitted(role) == can_sql

    @pytest.mark.parametrize("role", ["doctor", "nurse", "billing_executive", "technician", "admin"])
    def test_rbac_denial_message_contains_role(self, role):
        from rbac import format_rbac_denial
        msg = format_rbac_denial(role)
        assert role.replace("_", " ").lower() in msg.lower()


# ---------------------------------------------------------------------------
# Doctor tests
# ---------------------------------------------------------------------------

class TestDoctorUser:
    """doctor_user — accesses clinical + nursing + general; no SQL."""

    ROLE = "doctor"

    def test_accessible_collections(self):
        from auth import get_accessible_collections
        cols = set(get_accessible_collections(self.ROLE))
        assert "clinical" in cols
        assert "nursing" in cols
        assert "general" in cols
        assert "billing" not in cols
        assert "equipment" not in cols

    def test_non_analytical_query_routes_hybrid(self):
        from chat import is_analytical
        assert not is_analytical("What is the treatment protocol for sepsis?")

    def test_analytical_query_not_sql_permitted(self):
        from chat import is_analytical
        from rbac import is_sql_permitted
        q = "How many patients were admitted last month?"
        assert is_analytical(q)
        assert not is_sql_permitted(self.ROLE)

    def test_orchestrate_knowledge_question(self):
        fake_chunks = [
            {
                "text": "Use broad-spectrum antibiotics for sepsis.",
                "collection": "clinical",
                "section_title": "Sepsis Protocol",
                "source_document": "treatment_protocols.pdf",
                "reranker_score": 0.95,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="Use broad-spectrum antibiotics."):
            from chat import orchestrate
            resp = orchestrate("What is the treatment for sepsis?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"
        assert resp.role == self.ROLE
        assert len(resp.sources) == 1
        assert resp.sources[0].collection == "clinical"

    def test_no_results_returns_denial(self):
        with patch("chat.hybrid_retrieve", return_value=[]):
            from chat import orchestrate
            resp = orchestrate("Tell me about billing codes.", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"
        assert "access" in resp.answer.lower() or "limited" in resp.answer.lower()


# ---------------------------------------------------------------------------
# Nurse tests
# ---------------------------------------------------------------------------

class TestNurseUser:
    """nurse_user — accesses nursing + general only; no clinical; no SQL."""

    ROLE = "nurse"

    def test_accessible_collections(self):
        from auth import get_accessible_collections
        cols = set(get_accessible_collections(self.ROLE))
        assert "nursing" in cols
        assert "general" in cols
        assert "clinical" not in cols
        assert "billing" not in cols
        assert "equipment" not in cols

    def test_sql_not_permitted(self):
        from rbac import is_sql_permitted
        assert not is_sql_permitted(self.ROLE)

    def test_orchestrate_nursing_question(self):
        fake_chunks = [
            {
                "text": "ICU hand hygiene steps: wash 30 seconds …",
                "collection": "nursing",
                "section_title": "Infection Control",
                "source_document": "infection_control.pdf",
                "reranker_score": 0.9,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="Follow standard hand hygiene."):
            from chat import orchestrate
            resp = orchestrate("What is the ICU hand hygiene protocol?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"
        assert resp.sources[0].collection == "nursing"

    def test_clinical_question_returns_denial(self):
        with patch("chat.hybrid_retrieve", return_value=[]):
            from chat import orchestrate
            resp = orchestrate("What drug formulary applies to sepsis?", self.ROLE)
        assert "limited" in resp.answer.lower() or "access" in resp.answer.lower()

    def test_analytical_query_falls_back_to_hybrid(self):
        """Nurse asking an analytical question falls through to hybrid RAG (not SQL)."""
        fake_chunks = [
            {
                "text": "Staff handbook section on scheduling …",
                "collection": "general",
                "section_title": "Scheduling",
                "source_document": "staff_handbook.pdf",
                "reranker_score": 0.7,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="Scheduling information here."):
            from chat import orchestrate
            resp = orchestrate("How many shifts are scheduled this month?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"


# ---------------------------------------------------------------------------
# Billing Executive tests
# ---------------------------------------------------------------------------

class TestBillingUser:
    """billing_user — accesses billing + general; SQL-permitted."""

    ROLE = "billing_executive"

    def test_accessible_collections(self):
        from auth import get_accessible_collections
        cols = set(get_accessible_collections(self.ROLE))
        assert "billing" in cols
        assert "general" in cols
        assert "clinical" not in cols
        assert "nursing" not in cols
        assert "equipment" not in cols

    def test_sql_permitted(self):
        from rbac import is_sql_permitted
        assert is_sql_permitted(self.ROLE)

    @pytest.mark.parametrize("question", [
        "How many claims were submitted last month?",
        "What is the total approved amount?",
        "Show all pending claims.",
        "What is the average claim value?",
        "List all insurers.",
    ])
    def test_analytical_questions_detected(self, question):
        from chat import is_analytical
        assert is_analytical(question)

    def test_orchestrate_analytical_routes_to_sql(self):
        with patch("chat.sql_rag_chain", return_value="There were 42 claims in July."):
            from chat import orchestrate
            resp = orchestrate("How many claims were submitted last month?", self.ROLE)
        assert resp.retrieval_type == "sql_rag"
        assert "42" in resp.answer
        assert resp.sources == []

    def test_sql_failure_falls_back_to_hybrid(self):
        fake_chunks = [
            {
                "text": "Billing codes guide …",
                "collection": "billing",
                "section_title": "Codes",
                "source_document": "billing_codes.pdf",
                "reranker_score": 0.8,
            }
        ]
        with patch("chat.sql_rag_chain", side_effect=Exception("DB error")), \
             patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="Billing codes are …"):
            from chat import orchestrate
            resp = orchestrate("How many claims are pending?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"

    def test_knowledge_question_uses_hybrid(self):
        fake_chunks = [
            {
                "text": "Submit claims within 30 days …",
                "collection": "billing",
                "section_title": "Submission Guide",
                "source_document": "claim_submission_guide.md",
                "reranker_score": 0.88,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="Claims must be submitted within 30 days."):
            from chat import orchestrate
            resp = orchestrate("What is the claim submission deadline?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"
        assert resp.sources[0].collection == "billing"


# ---------------------------------------------------------------------------
# Technician tests
# ---------------------------------------------------------------------------

class TestTechUser:
    """tech_user — accesses equipment + general only; no SQL."""

    ROLE = "technician"

    def test_accessible_collections(self):
        from auth import get_accessible_collections
        cols = set(get_accessible_collections(self.ROLE))
        assert "equipment" in cols
        assert "general" in cols
        assert "clinical" not in cols
        assert "nursing" not in cols
        assert "billing" not in cols

    def test_sql_not_permitted(self):
        from rbac import is_sql_permitted
        assert not is_sql_permitted(self.ROLE)

    def test_orchestrate_equipment_question(self):
        fake_chunks = [
            {
                "text": "MRI calibration steps: power off, align, …",
                "collection": "equipment",
                "section_title": "MRI Calibration",
                "source_document": "equipment_manual.pdf",
                "reranker_score": 0.92,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="MRI calibration procedure …"):
            from chat import orchestrate
            resp = orchestrate("How do I calibrate the MRI machine?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"
        assert resp.sources[0].collection == "equipment"

    def test_clinical_question_returns_denial(self):
        with patch("chat.hybrid_retrieve", return_value=[]):
            from chat import orchestrate
            resp = orchestrate("What is the treatment protocol for sepsis?", self.ROLE)
        assert "limited" in resp.answer.lower() or "access" in resp.answer.lower()

    def test_analytical_falls_back_to_hybrid(self):
        """Technician asking analytical question — SQL not permitted → hybrid fallback."""
        fake_chunks = [
            {
                "text": "Maintenance schedule …",
                "collection": "equipment",
                "section_title": "Maintenance",
                "source_document": "equipment_manual.pdf",
                "reranker_score": 0.75,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="Maintenance info …"):
            from chat import orchestrate
            resp = orchestrate("How many maintenance tickets are open?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"


# ---------------------------------------------------------------------------
# Admin tests
# ---------------------------------------------------------------------------

class TestAdminUser:
    """admin_user — accesses ALL collections; SQL-permitted."""

    ROLE = "admin"

    def test_accessible_collections(self):
        from auth import get_accessible_collections
        cols = set(get_accessible_collections(self.ROLE))
        assert cols == {"clinical", "nursing", "billing", "equipment", "general"}

    def test_sql_permitted(self):
        from rbac import is_sql_permitted
        assert is_sql_permitted(self.ROLE)

    def test_orchestrate_analytical_sql_path(self):
        with patch("chat.sql_rag_chain", return_value="Total approved: $1,200,000."):
            from chat import orchestrate
            resp = orchestrate("What is the total approved amount?", self.ROLE)
        assert resp.retrieval_type == "sql_rag"
        assert "1,200,000" in resp.answer

    def test_orchestrate_clinical_question(self):
        fake_chunks = [
            {
                "text": "Diagnostic reference for hypertension …",
                "collection": "clinical",
                "section_title": "Hypertension",
                "source_document": "diagnostic_reference.pdf",
                "reranker_score": 0.97,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="Hypertension diagnostic criteria …"):
            from chat import orchestrate
            resp = orchestrate("What are the diagnostic criteria for hypertension?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"
        assert resp.sources[0].collection == "clinical"

    def test_orchestrate_equipment_question(self):
        fake_chunks = [
            {
                "text": "Ventilator alarm codes …",
                "collection": "equipment",
                "section_title": "Alarms",
                "source_document": "equipment_manual.pdf",
                "reranker_score": 0.89,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="Alarm code list …"):
            from chat import orchestrate
            resp = orchestrate("What do the ventilator alarm codes mean?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"
        assert resp.sources[0].collection == "equipment"

    def test_orchestrate_billing_question(self):
        fake_chunks = [
            {
                "text": "CPT code 99213 applies to …",
                "collection": "billing",
                "section_title": "CPT Codes",
                "source_document": "billing_codes.pdf",
                "reranker_score": 0.91,
            }
        ]
        with patch("chat.hybrid_retrieve", return_value=fake_chunks), \
             patch("chat.rerank", return_value=fake_chunks), \
             patch("chat.answer_with_context", return_value="CPT code 99213 details …"):
            from chat import orchestrate
            resp = orchestrate("What is CPT code 99213?", self.ROLE)
        assert resp.retrieval_type == "hybrid_rag"
        assert resp.sources[0].collection == "billing"

    def test_qdrant_filter_covers_all_collections(self):
        from rbac import build_qdrant_filter
        f = build_qdrant_filter(self.ROLE)
        allowed = set(f.must[0].match.any)
        assert allowed == {"clinical", "nursing", "billing", "equipment", "general"}


# ---------------------------------------------------------------------------
# SQL RAG unit tests (billing + admin paths)
# ---------------------------------------------------------------------------

class TestSqlRag:
    """Unit tests for clean_sql helper — no DB or LLM calls required."""

    def test_clean_sql_strips_markdown_fence(self):
        from sql_rag import clean_sql
        raw = "```sql\nSELECT COUNT(*) FROM claims;\n```"
        result = clean_sql(raw)
        assert result.startswith("SELECT")
        assert "```" not in result

    def test_clean_sql_adds_semicolon(self):
        from sql_rag import clean_sql
        result = clean_sql("SELECT * FROM claims")
        assert result.endswith(";")

    def test_clean_sql_preserves_existing_semicolon(self):
        from sql_rag import clean_sql
        result = clean_sql("SELECT * FROM claims;")
        assert result.count(";") == 1

    def test_clean_sql_strips_prose(self):
        from sql_rag import clean_sql
        raw = "Here is the query:\nSELECT COUNT(*) FROM claims WHERE status='pending';"
        result = clean_sql(raw)
        assert result.startswith("SELECT")


# ---------------------------------------------------------------------------
# is_analytical keyword coverage
# ---------------------------------------------------------------------------

class TestAnalyticalDetection:

    @pytest.mark.parametrize("question", [
        "How many claims were filed?",
        "What is the total amount approved?",
        "Show all pending tickets.",
        "What is the average claim value?",
        "List all departments.",
        "What is the maximum claim amount?",
        "What is the minimum approved amount?",
        "Give me a breakdown by insurer.",
        "How much was spent last month?",
        "What percentage of claims are denied?",
        "What are the top 5 insurers?",
    ])
    def test_analytical_detected(self, question):
        from chat import is_analytical
        assert is_analytical(question)

    @pytest.mark.parametrize("question", [
        "What is the sepsis treatment protocol?",
        "Describe ICU hand hygiene steps.",
        "Explain the claim submission process.",
        "What does CPT code 99213 mean?",
        "How do I calibrate the MRI machine?",
    ])
    def test_non_analytical_not_detected(self, question):
        from chat import is_analytical
        assert not is_analytical(question)
