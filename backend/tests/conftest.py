"""
Master conftest.py — shared fixtures for all backend test suites.

Provides:
  - app: FastAPI test application (isolated SQLite DB, patched Redis, patched Firebase)
  - client: httpx TestClient with auth bypass
  - auth_client: httpx TestClient that enforces auth (for auth tests)
  - db_session: SQLAlchemy session against in-memory SQLite
  - mock_llm: pre-configured LLM mock that returns deterministic JSON
  - sample_signals / complete_signals: signal dicts for scoring tests
  - sample_document_data: parsed document dict
  - seed_project / seed_session / seed_result: pre-created DB rows
"""
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as DBSession

# ---------------------------------------------------------------------------
# 1. Isolated SQLite engine (in-memory, per-test-session)
# ---------------------------------------------------------------------------
SQLITE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def engine():
    """Create a single in-memory SQLite engine for the test session."""
    from app.db.base import Base
    eng = create_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db_session(engine) -> DBSession:
    """Yield a clean SQLAlchemy session, rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, expire_on_commit=False)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# 2. FastAPI TestClient with DB, Redis, and Firebase Auth overrides
# ---------------------------------------------------------------------------
TEST_USER_UID = "test_firebase_uid_001"


@pytest.fixture
def client(db_session):
    """
    TestClient with:
      - DB dependency overridden to use the test SQLite session
      - Redis disabled (cache_service._client = None)
      - Firebase auth bypassed (returns TEST_USER_UID for all requests)
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from app.db.session import get_db
    from app.core.security import verify_firebase_token

    def override_get_db():
        yield db_session

    def override_verify_firebase_token():
        """Bypass Firebase for tests — return a fixed test UID."""
        return TEST_USER_UID

    with patch("app.services.cache_service._client", None):
        from main import app as fastapi_app
        fastapi_app.dependency_overrides[get_db] = override_get_db
        fastapi_app.dependency_overrides[verify_firebase_token] = override_verify_firebase_token
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield c
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
def auth_client(db_session):
    """
    TestClient WITHOUT auth bypass — tests that require real auth validation.
    Firebase auth will fail with no/invalid token.
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from app.db.session import get_db

    def override_get_db():
        yield db_session

    with patch("app.services.cache_service._client", None):
        from main import app as fastapi_app
        fastapi_app.dependency_overrides[get_db] = override_get_db
        # NOTE: verify_firebase_token is NOT overridden here
        with TestClient(fastapi_app, raise_server_exceptions=False) as c:
            yield c
        fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Mock LLM Client
# ---------------------------------------------------------------------------
MOCK_LLM_RESPONSE = {
    "dataset_size": {
        "value": "large",
        "confidence": 0.9,
        "source_text": "Our system processes over 10 million records daily.",
        "page_number": 2,
    },
    "query_volume": {
        "value": "high",
        "confidence": 0.85,
        "source_text": "Expected throughput is 50,000 queries per day.",
        "page_number": 3,
    },
    "latency_requirement": {
        "value": "strict",
        "confidence": 0.8,
        "source_text": "Response time must be under 1 second.",
        "page_number": 1,
    },
    "data_volatility": {
        "value": "moderate",
        "confidence": 0.75,
        "source_text": "Data is updated weekly from external sources.",
        "page_number": 4,
    },
    "accuracy_requirement": {
        "value": "high",
        "confidence": 0.88,
        "source_text": "High accuracy is required for business decisions.",
        "page_number": 1,
    },
    "domain_specificity": {
        "value": "specialized",
        "confidence": 0.82,
        "source_text": "The platform serves the financial services industry.",
        "page_number": 1,
    },
    "security_level": {
        "value": "high",
        "confidence": 0.92,
        "source_text": "SOC2 and ISO27001 compliance is required.",
        "page_number": 5,
    },
    "cost_sensitivity": {
        "value": "moderate",
        "confidence": 0.7,
        "source_text": "Budget is flexible but cost-efficiency is valued.",
        "page_number": 6,
    },
    "deployment_preference": {
        "value": "cloud",
        "confidence": 0.95,
        "source_text": "Deployment target is AWS us-east-1.",
        "page_number": 1,
    },
    "user_scale": {
        "value": "large",
        "confidence": 0.87,
        "source_text": "100,000+ active users across the enterprise.",
        "page_number": 2,
    },
}


@pytest.fixture
def mock_llm():
    """Mock LLMClient that returns deterministic JSON without real LLM calls."""
    mock = MagicMock()
    mock.provider = "openai"
    mock.generate_json = AsyncMock(return_value=MOCK_LLM_RESPONSE)
    mock.generate = AsyncMock(return_value=json.dumps(MOCK_LLM_RESPONSE))
    return mock


@pytest.fixture
def mock_llm_empty():
    """Mock LLM that returns all nulls — simulates empty document."""
    empty = {k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
             for k in MOCK_LLM_RESPONSE}
    mock = MagicMock()
    mock.provider = "openai"
    mock.generate_json = AsyncMock(return_value=empty)
    mock.generate = AsyncMock(return_value=json.dumps(empty))
    return mock


@pytest.fixture
def mock_llm_hallucinating():
    """Mock LLM that returns values not in the allowed options list."""
    hallucinated = {
        k: {"value": "INVENTED_VALUE", "confidence": 0.99,
            "source_text": "This is totally made up.", "page_number": 1}
        for k in MOCK_LLM_RESPONSE
    }
    mock = MagicMock()
    mock.provider = "openai"
    mock.generate_json = AsyncMock(return_value=hallucinated)
    mock.generate = AsyncMock(return_value=json.dumps(hallucinated))
    return mock


# ---------------------------------------------------------------------------
# 4. Signal fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def complete_signals():
    """All 10 signals with high confidence — deterministic scoring."""
    return {k: dict(v) for k, v in MOCK_LLM_RESPONSE.items()}


@pytest.fixture
def partial_signals():
    """Only 3 signals set — tests incomplete-data scoring behavior."""
    return {
        "dataset_size": {"value": "large", "confidence": 0.9, "source_text": "test", "page_number": 1},
        "data_volatility": {"value": "high", "confidence": 0.8, "source_text": "test", "page_number": 1},
        "latency_requirement": {"value": "ultra_low", "confidence": 0.85, "source_text": "test", "page_number": 1},
        **{k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
           for k in MOCK_LLM_RESPONSE if k not in ["dataset_size", "data_volatility", "latency_requirement"]},
    }


@pytest.fixture
def empty_signals():
    """All signals missing — tests zero-signal edge case."""
    return {k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
            for k in MOCK_LLM_RESPONSE}


# ---------------------------------------------------------------------------
# 5. Document data fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_document_data():
    """Simulates parsed output from DocumentParser.parse()."""
    full_text = (
        "This financial services platform processes over 10 million customer records daily. "
        "Response time must be under 1 second for all queries. "
        "Expected throughput is 50,000 queries per day. "
        "SOC2 and ISO27001 compliance is required. "
        "Deployment target is AWS us-east-1. "
        "Data is updated weekly from external sources. "
        "High accuracy is required for business decisions. "
        "Budget is flexible but cost-efficiency is valued. "
        "100,000+ active users across the enterprise."
    )
    return {
        "filename": "requirements.pdf",
        "format": ".pdf",
        "total_pages": 6,
        "full_text": full_text,
        "char_count": len(full_text),
        "word_count": len(full_text.split()),
        "pages": [
            {"page_number": i + 1, "text": full_text[i * 100:(i + 1) * 100], "char_count": 100}
            for i in range(6)
        ],
    }


@pytest.fixture
def empty_document_data():
    """Simulates a blank/corrupt document."""
    return {
        "filename": "empty.pdf",
        "format": ".pdf",
        "total_pages": 1,
        "full_text": "",
        "char_count": 0,
        "word_count": 0,
        "pages": [{"page_number": 1, "text": "", "char_count": 0}],
    }


@pytest.fixture
def tiny_document_data():
    """Document with too few words — below the 10-word threshold."""
    return {
        "filename": "tiny.txt",
        "format": ".txt",
        "total_pages": 1,
        "full_text": "Hello world.",
        "char_count": 12,
        "word_count": 2,
        "pages": [{"page_number": 1, "text": "Hello world.", "char_count": 12}],
    }


# ---------------------------------------------------------------------------
# 6. Seed database rows
# ---------------------------------------------------------------------------
@pytest.fixture
def seed_project(db_session):
    """Insert and return a Project row in the test DB (owned by TEST_USER_UID)."""
    from app.db.models import Project
    project = Project(
        id=uuid.uuid4(),
        user_id=TEST_USER_UID,   # Must match auth bypass UID
        name="Test Project",
        description="A project for testing",
        status="empty",
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture
def seed_project_other_user(db_session):
    """Insert a Project belonging to a DIFFERENT user — for isolation tests."""
    from app.db.models import Project
    project = Project(
        id=uuid.uuid4(),
        user_id="other_user_uid_999",
        name="Other User Project",
        description="Belongs to a different user",
        status="empty",
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture
def seed_session(db_session, seed_project):
    """Insert and return a completed Session row in the test DB."""
    from app.db.models import Session as SessionModel
    session_row = SessionModel(
        id=uuid.uuid4(),
        project_id=seed_project.id,
        status="completed",
        provider="openai",
        filename="requirements.pdf",
    )
    db_session.add(session_row)
    db_session.commit()
    return session_row


@pytest.fixture
def seed_session_processing(db_session, seed_project):
    """A session stuck in processing state."""
    from app.db.models import Session as SessionModel
    session_row = SessionModel(
        id=uuid.uuid4(),
        project_id=seed_project.id,
        status="processing",
        provider="ollama",
        filename="in_progress.pdf",
    )
    db_session.add(session_row)
    db_session.commit()
    return session_row


@pytest.fixture
def seed_session_error(db_session, seed_project):
    """A session in error state."""
    from app.db.models import Session as SessionModel
    session_row = SessionModel(
        id=uuid.uuid4(),
        project_id=seed_project.id,
        status="error",
        provider="ollama",
        filename="failed.pdf",
    )
    db_session.add(session_row)
    db_session.commit()
    return session_row


@pytest.fixture
def seed_result(db_session, seed_session, complete_signals):
    """Insert a Result row for a completed session."""
    from app.db.models import Result
    from services.scoring_engine import ScoringEngine
    scoring = ScoringEngine()
    score_output = scoring.score(complete_signals)
    sensitivity = scoring.sensitivity_analysis(complete_signals)

    result_row = Result(
        session_id=seed_session.id,
        recommended_architecture=score_output["recommended"],
        confidence_score=score_output["confidence"],
        ranking=score_output["ranking"],
        scores=score_output["scores"],
        decision_breakdown=score_output["factor_breakdown"],
        why_not=score_output["why_not"],
        suitability=score_output["suitability"],
        followup_questions=[],
        sensitivity=sensitivity,
        decision_trace=[],
        architecture_details=score_output["architecture_details"],
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(result_row)
    db_session.commit()
    return result_row


@pytest.fixture
def seed_user(db_session):
    """Insert a User row in the test DB."""
    from app.db.models import User
    user = User(
        id=TEST_USER_UID,
        name="Test User",
        email="testuser@example.com",
        provider="google",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# 7. File upload fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_pdf_bytes():
    """Minimal valid PDF file bytes for upload tests."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R"
        b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        b"4 0 obj<</Length 44>>stream\n"
        b"BT /F1 12 Tf 100 700 Td (Test document.) Tj ET\n"
        b"endstream endobj\n"
        b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"xref\n0 6\n0000000000 65535 f\n"
        b"trailer<</Root 1 0 R/Size 6>>\nstartxref\n0\n%%EOF"
    )


@pytest.fixture
def sample_txt_content():
    """Rich requirement document text for extraction tests."""
    return (
        "Architecture Requirements Document\n\n"
        "System Overview:\n"
        "Our financial services platform processes over 10 million customer records daily. "
        "The system must handle real-time fraud detection with ultra-low latency requirements "
        "of under 100 milliseconds. The knowledge base is updated daily with new regulatory data. "
        "We require critical accuracy levels with zero tolerance for false negatives in fraud cases. "
        "The domain is highly specialized in financial services and regulatory compliance. "
        "Security level is critical — we must maintain HIPAA and SOC2 compliance at all times. "
        "Cost sensitivity is moderate — quality over cost. "
        "Deployment must be on-premise due to data residency requirements. "
        "User scale is enterprise with 1 million+ concurrent sessions.\n"
    ).encode("utf-8")


@pytest.fixture
def corrupted_pdf_bytes():
    """Malformed/truncated PDF for robustness testing."""
    return b"%PDF-1.4\n" + b"\x00\xff\xfe\xfd" * 100 + b"CORRUPT"


@pytest.fixture
def oversized_file_bytes():
    """51MB file to test size limit enforcement."""
    return b"A" * (51 * 1024 * 1024)


@pytest.fixture
def unicode_txt_content():
    """Document with unicode/multilingual content."""
    return (
        "Architecture Requirements — Système de Recommandation d'Architecture IA\n\n"
        "Notre plateforme traite plus de 10 millions d'enregistrements par jour.\n"
        "El sistema debe manejar detección de fraude en tiempo real.\n"
        "Das System muss Hochverfügbarkeit gewährleisten.\n"
        "システムは毎日1000万件以上のレコードを処理します。\n"
        "Требуется строгая безопасность и соответствие стандартам SOC2.\n"
        "We require enterprise-level accuracy with high security compliance for financial data.\n"
        "Deployment target is AWS us-east-1 with global CDN distribution.\n"
        "User scale is 1 million concurrent enterprise sessions across multiple regions.\n"
    ).encode("utf-8")
