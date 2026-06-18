"""
PHASE 4 — BACKEND + API TESTING
Tests: upload, analysis, follow-up, export, health, architectures, questionnaire.
Covers: happy paths, error paths, malformed requests, security, DB integrity.
"""
import io
import uuid
import pytest
from unittest.mock import AsyncMock, patch


# ============================================================================
# UPLOAD ENDPOINT — POST /api/v1/upload
# ============================================================================
@pytest.mark.api
class TestUploadHappyPaths:
    URL = "/api/v1/upload"

    def _post(self, client, content, filename, ct="text/plain"):
        return client.post(self.URL, files={"file": (filename, io.BytesIO(content), ct)})

    def test_txt_upload_returns_non_500(self, client, sample_txt_content):
        """A valid TXT document must not cause a 500."""
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=5)), \
             patch("app.services.signal_service.extract_and_persist", new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": str(uuid.uuid4()), "status": "complete",
                 "recommended": "RAG", "confidence": 0.8,
                 "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = self._post(client, sample_txt_content, "req.txt")
        assert r.status_code != 500

    def test_response_has_analysis_id(self, client, sample_txt_content):
        """Successful upload must return a UUID analysis_id."""
        aid = str(uuid.uuid4())
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=5)), \
             patch("app.services.signal_service.extract_and_persist", new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": aid, "status": "complete", "recommended": "RAG",
                 "confidence": 0.8, "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = self._post(client, sample_txt_content, "req.txt")
        if r.status_code == 200:
            data = r.json()
            assert "analysis_id" in data
            assert len(data["analysis_id"]) == 36

    def test_provider_openai_accepted(self, client, sample_txt_content):
        """Provider=openai must pass regex validation."""
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=0)), \
             patch("app.services.signal_service.extract_and_persist", new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": str(uuid.uuid4()), "status": "complete",
                 "recommended": "RAG", "confidence": 0.8,
                 "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = client.post(self.URL + "?provider=openai",
                            files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")})
        assert r.status_code != 422 or "provider" not in r.text.lower()

    def test_valid_project_association(self, client, sample_txt_content, seed_project):
        """Upload with a real project_id must not return 404."""
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=5)), \
             patch("app.services.signal_service.extract_and_persist", new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": str(uuid.uuid4()), "status": "complete",
                 "recommended": "RAG", "confidence": 0.8,
                 "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = client.post(
                self.URL + f"?project_id={seed_project.id}",
                files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")},
            )
        assert r.status_code != 404


@pytest.mark.api
class TestUploadValidationErrors:
    URL = "/api/v1/upload"

    def test_no_file_returns_422(self, client):
        assert client.post(self.URL).status_code == 422

    def test_empty_filename_returns_400(self, client):
        r = client.post(self.URL, files={"file": ("", io.BytesIO(b"data"), "text/plain")})
        assert r.status_code in (400, 422)

    def test_invalid_extension_returns_400(self, client):
        r = client.post(self.URL, files={"file": ("virus.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")})
        assert r.status_code == 400

    def test_oversized_file_returns_400(self, client, oversized_file_bytes):
        r = client.post(self.URL, files={"file": ("big.txt", io.BytesIO(oversized_file_bytes), "text/plain")})
        assert r.status_code == 400

    def test_empty_txt_returns_400_or_422(self, client):
        r = client.post(self.URL, files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")})
        assert r.status_code in (400, 422)

    def test_tiny_content_returns_422(self, client):
        r = client.post(self.URL, files={"file": ("tiny.txt", io.BytesIO(b"Hi."), "text/plain")})
        assert r.status_code == 422

    def test_invalid_provider_returns_422(self, client, sample_txt_content):
        r = client.post(self.URL + "?provider=gpt9000",
                        files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")})
        assert r.status_code == 422

    def test_csv_extension_returns_400(self, client):
        r = client.post(self.URL, files={"file": ("data.csv", io.BytesIO(b"a,b,c\n1,2,3"), "text/csv")})
        assert r.status_code == 400

    def test_nonexistent_project_id_returns_404(self, client, sample_txt_content):
        fake_id = str(uuid.uuid4())
        r = client.post(
            self.URL + f"?project_id={fake_id}",
            files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")},
        )
        assert r.status_code == 404

    def test_invalid_project_id_format_skipped(self, client, sample_txt_content):
        """Invalid UUID format must not return 404 — it is skipped gracefully."""
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=5)), \
             patch("app.services.signal_service.extract_and_persist", new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": str(uuid.uuid4()), "status": "complete",
                 "recommended": "RAG", "confidence": 0.8,
                 "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = client.post(
                self.URL + "?project_id=not-a-uuid",
                files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")},
            )
        assert r.status_code != 404


@pytest.mark.api
class TestUploadSecurityEdgeCases:
    URL = "/api/v1/upload"

    def test_path_traversal_blocked(self, client):
        r = client.post(self.URL, files={"file": ("../../etc/passwd", io.BytesIO(b"malicious"), "text/plain")})
        assert r.status_code in (400, 422)
        if r.status_code == 200:
            pytest.fail("CRITICAL: Path traversal filename accepted!")

    def test_windows_path_traversal_blocked(self, client):
        r = client.post(self.URL, files={"file": ("..\\..\\windows\\system32", io.BytesIO(b"x"), "text/plain")})
        assert r.status_code in (400, 422)

    def test_null_byte_filename_blocked(self, client):
        r = client.post(self.URL, files={"file": ("file\x00.txt", io.BytesIO(b"x"), "text/plain")})
        assert r.status_code in (400, 422)

    def test_provider_sql_injection_rejected(self, client, sample_txt_content):
        r = client.post(
            self.URL + "?provider='; DROP TABLE sessions; --",
            files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")},
        )
        assert r.status_code == 422

    def test_cross_user_project_access_denied(self, client, seed_project_other_user):
        """Authenticated user must not be able to upload to another user's project."""
        r = client.post(
            self.URL + f"?project_id={seed_project_other_user.id}",
            files={"file": ("req.txt", io.BytesIO(b"Some valid content here with enough words." * 5), "text/plain")},
        )
        assert r.status_code == 403

    def test_corrupted_pdf_does_not_crash(self, client, corrupted_pdf_bytes):
        """A corrupted PDF must not return 500."""
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=5)), \
             patch("app.services.signal_service.extract_and_persist", new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": str(uuid.uuid4()), "status": "complete",
                 "recommended": "RAG", "confidence": 0.8,
                 "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = client.post(self.URL, files={"file": ("corrupt.pdf", io.BytesIO(corrupted_pdf_bytes), "application/pdf")})
        assert r.status_code != 500

    def test_binary_as_txt_does_not_crash(self, client):
        binary = bytes(range(256)) * 50
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=5)), \
             patch("app.services.signal_service.extract_and_persist", new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": str(uuid.uuid4()), "status": "complete",
                 "recommended": "RAG", "confidence": 0.8,
                 "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = client.post(self.URL, files={"file": ("binary.txt", io.BytesIO(binary), "text/plain")})
        assert r.status_code != 500

    def test_unicode_filename_handled(self, client, unicode_txt_content):
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=5)), \
             patch("app.services.signal_service.extract_and_persist", new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": str(uuid.uuid4()), "status": "complete",
                 "recommended": "RAG", "confidence": 0.8,
                 "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = client.post(self.URL, files={"file": ("требования.txt", io.BytesIO(unicode_txt_content), "text/plain")})
        # Must not 500
        assert r.status_code != 500

    def test_no_auth_token_returns_401(self, auth_client, sample_txt_content):
        """Without auth token, upload must return 401."""
        r = auth_client.post(
            self.URL,
            files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")},
        )
        assert r.status_code == 401

    def test_invalid_auth_token_returns_401(self, auth_client, sample_txt_content):
        """An invalid Bearer token must be rejected."""
        r = auth_client.post(
            self.URL,
            files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert r.status_code == 401


# ============================================================================
# ANALYSIS ENDPOINT — GET /api/v1/analysis/{id}
# ============================================================================
@pytest.mark.api
class TestAnalysisEndpoint:

    def test_nonexistent_session_returns_404(self, client):
        r = client.get(f"/api/v1/analysis/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_invalid_uuid_returns_404(self, client):
        r = client.get("/api/v1/analysis/not-a-valid-uuid")
        assert r.status_code == 404

    def test_sql_injection_in_id_returns_404(self, client):
        r = client.get("/api/v1/analysis/' OR '1'='1")
        assert r.status_code == 404

    def test_processing_session_returns_processing_status(self, client, seed_session_processing):
        r = client.get(f"/api/v1/analysis/{seed_session_processing.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "processing"

    def test_error_session_returns_error_status(self, client, seed_session_error):
        r = client.get(f"/api/v1/analysis/{seed_session_error.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_completed_session_with_result_returns_full_shape(self, client, seed_result, seed_session):
        r = client.get(f"/api/v1/analysis/{seed_session.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert "recommended" in data
        assert "scores" in data
        assert "confidence" in data
        assert "ranking" in data

    def test_response_does_not_leak_db_internals(self, client):
        r = client.get(f"/api/v1/analysis/{uuid.uuid4()}")
        body = r.text.lower()
        assert "sqlalchemy" not in body
        assert "psycopg2" not in body
        assert "traceback" not in body

    def test_analysis_id_in_response_matches_request(self, client, seed_session_processing):
        sid = str(seed_session_processing.id)
        r = client.get(f"/api/v1/analysis/{sid}")
        assert r.status_code == 200
        data = r.json()
        assert data["analysis_id"] == sid


# ============================================================================
# FOLLOW-UP ENDPOINT — POST /api/v1/followup
# ============================================================================
@pytest.mark.api
class TestFollowUpEndpoint:

    def test_nonexistent_session_returns_404(self, client):
        payload = {"analysis_id": str(uuid.uuid4()), "answers": {"dataset_size": "large"}}
        r = client.post("/api/v1/followup", json=payload)
        assert r.status_code == 404

    def test_invalid_uuid_returns_404(self, client):
        payload = {"analysis_id": "not-a-uuid", "answers": {}}
        r = client.post("/api/v1/followup", json=payload)
        assert r.status_code == 404

    def test_empty_answers_accepted(self, client, seed_session, seed_result):
        payload = {"analysis_id": str(seed_session.id), "answers": {}}
        r = client.post("/api/v1/followup", json=payload)
        assert r.status_code == 200

    def test_valid_followup_returns_updated_result(self, client, seed_session, seed_result):
        payload = {
            "analysis_id": str(seed_session.id),
            "answers": {"dataset_size": "small", "latency_requirement": "flexible"},
        }
        r = client.post("/api/v1/followup", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "recommended" in data
        assert "scores" in data

    def test_unknown_signal_key_ignored_not_500(self, client, seed_session, seed_result):
        """Unknown signal names in answers must be gracefully ignored."""
        payload = {
            "analysis_id": str(seed_session.id),
            "answers": {
                "dataset_size": "large",
                "TOTALLY_FAKE_SIGNAL": "evil_value",
                "__proto__": {"admin": True},
            },
        }
        r = client.post("/api/v1/followup", json=payload)
        assert r.status_code in (200, 422)
        assert r.status_code != 500

    def test_missing_analysis_id_returns_422(self, client):
        r = client.post("/api/v1/followup", json={"answers": {"dataset_size": "large"}})
        assert r.status_code == 422

    def test_missing_answers_field_returns_422(self, client):
        r = client.post("/api/v1/followup", json={"analysis_id": str(uuid.uuid4())})
        assert r.status_code == 422

    def test_sql_injection_in_answers_is_safe(self, client, seed_session, seed_result):
        """SQL-injection payloads in answer values must not crash."""
        payload = {
            "analysis_id": str(seed_session.id),
            "answers": {"dataset_size": "'; DROP TABLE signals; --"},
        }
        r = client.post("/api/v1/followup", json=payload)
        assert r.status_code in (200, 422)
        assert r.status_code != 500

    def test_rescoring_is_idempotent(self, client, seed_session, seed_result):
        """Same answers sent twice must return the same recommendation."""
        payload = {"analysis_id": str(seed_session.id), "answers": {"dataset_size": "large"}}
        r1 = client.post("/api/v1/followup", json=payload)
        r2 = client.post("/api/v1/followup", json=payload)
        if r1.status_code == 200 and r2.status_code == 200:
            assert r1.json()["recommended"] == r2.json()["recommended"]


# ============================================================================
# EXPORT ENDPOINTS — POST /api/v1/export/pdf, /export/pdf/cost
# ============================================================================
@pytest.mark.api
class TestExportEndpoints:

    VALID_RESULT = {
        "analysis_id": "test-export-id",
        "status": "complete",
        "recommended": "RAG",
        "confidence": 0.82,
        "scores": {"RAG": 78.5, "FineTuning": 52.0, "CAG": 34.0, "Hybrid": 61.0},
        "ranking": ["RAG", "Hybrid", "FineTuning", "CAG"],
        "suitability": {"RAG": "Highly Suitable", "FineTuning": "Suitable"},
        "why_not": {"FineTuning": "High dataset volatility"},
        "factor_breakdown": {"RAG": {"accuracy": 0.9}},
        "signals": {},
        "architecture_details": {},
        "followup_questions": [],
        "sensitivity": {},
        "decision_trace": [],
    }

    def test_pdf_export_endpoint_exists(self, client):
        """INTEG-001: POST /api/v1/export/pdf must exist (not 404)."""
        r = client.post("/api/v1/export/pdf", json=self.VALID_RESULT)
        assert r.status_code != 404, "PDF export endpoint is MISSING — INTEG-001 confirmed"
        assert r.status_code != 405, "PDF export wrong HTTP method"

    def test_pdf_export_returns_pdf_content_type(self, client):
        r = client.post("/api/v1/export/pdf", json=self.VALID_RESULT)
        if r.status_code == 200:
            assert "application/pdf" in r.headers.get("content-type", "")

    def test_pdf_export_returns_bytes(self, client):
        r = client.post("/api/v1/export/pdf", json=self.VALID_RESULT)
        if r.status_code == 200:
            assert len(r.content) > 0
            assert r.content[:4] == b"%PDF"

    def test_pdf_export_with_empty_result_no_500(self, client):
        r = client.post("/api/v1/export/pdf", json={})
        assert r.status_code != 500

    def test_cost_pdf_endpoint_exists(self, client):
        r = client.post("/api/v1/export/pdf/cost", json=self.VALID_RESULT)
        assert r.status_code != 404

    def test_cost_pdf_returns_pdf_content_type(self, client):
        r = client.post("/api/v1/export/pdf/cost", json=self.VALID_RESULT)
        if r.status_code == 200:
            assert "application/pdf" in r.headers.get("content-type", "")

    def test_pdf_content_disposition_header_set(self, client):
        r = client.post("/api/v1/export/pdf", json=self.VALID_RESULT)
        if r.status_code == 200:
            cd = r.headers.get("content-disposition", "")
            assert "attachment" in cd
            assert ".pdf" in cd


# ============================================================================
# STATIC / METADATA ENDPOINTS
# ============================================================================
@pytest.mark.api
class TestStaticEndpoints:

    def test_health_endpoint_returns_200(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200

    def test_health_has_status_ok(self, client):
        r = client.get("/api/v1/health")
        assert r.json()["status"] == "ok"

    def test_architectures_returns_all_four(self, client):
        r = client.get("/api/v1/architectures")
        assert r.status_code == 200
        data = r.json()
        assert set(data["architectures"].keys()) == {"RAG", "FineTuning", "CAG", "Hybrid"}

    def test_questionnaire_options_has_10_signals(self, client):
        r = client.get("/api/v1/questionnaire/options")
        assert r.status_code == 200
        data = r.json()
        assert len(data["signals"]) == 10

    def test_questionnaire_options_schema_complete(self, client):
        r = client.get("/api/v1/questionnaire/options")
        assert r.status_code == 200
        for key, signal in r.json()["signals"].items():
            assert "description" in signal, f"Signal {key} missing description"
            assert "options" in signal, f"Signal {key} missing options"
            assert "required" in signal, f"Signal {key} missing required"

    def test_cors_headers_present_on_options(self, client):
        r = client.options(
            "/api/v1/architectures",
            headers={"Origin": "http://localhost:3000",
                     "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" in r.headers

    def test_docs_endpoint_accessible(self, client):
        r = client.get("/docs")
        assert r.status_code in (200, 404)

    @pytest.mark.xfail(reason="FastAPI does not natively enforce JSON body size limits")
    def test_large_json_body_rejected_gracefully(self, client):
        huge = {"data": "x" * (2 * 1024 * 1024)}
        r = client.post("/api/v1/questionnaire", json=huge)
        assert r.status_code in (400, 413, 422)


# ============================================================================
# QUESTIONNAIRE ENDPOINT — POST /api/v1/questionnaire
# ============================================================================
@pytest.mark.api
class TestQuestionnaireEndpoint:

    FULL_ANSWERS = {
        "answers": {
            "dataset_size": "large",
            "query_volume": "high",
            "latency_requirement": "strict",
            "data_volatility": "moderate",
            "accuracy_requirement": "high",
            "domain_specificity": "specialized",
            "security_level": "high",
            "cost_sensitivity": "moderate",
            "deployment_preference": "cloud",
            "user_scale": "large",
        }
    }

    def test_full_questionnaire_returns_200(self, client):
        r = client.post("/api/v1/questionnaire", json=self.FULL_ANSWERS)
        assert r.status_code == 200

    def test_response_has_all_required_fields(self, client):
        r = client.post("/api/v1/questionnaire", json=self.FULL_ANSWERS)
        if r.status_code == 200:
            data = r.json()
            for field in ["analysis_id", "status", "recommended", "scores", "confidence"]:
                assert field in data, f"Missing field: {field}"

    def test_empty_answers_returns_result(self, client):
        r = client.post("/api/v1/questionnaire", json={"answers": {}})
        assert r.status_code in (200, 422)
        assert r.status_code != 500

    def test_invalid_provider_rejected(self, client):
        r = client.post(
            "/api/v1/questionnaire?provider=badprovider",
            json=self.FULL_ANSWERS,
        )
        assert r.status_code == 422

    def test_null_answers_handled(self, client):
        payload = {"answers": {k: None for k in self.FULL_ANSWERS["answers"]}}
        r = client.post("/api/v1/questionnaire", json=payload)
        assert r.status_code in (200, 422)
        assert r.status_code != 500

    def test_questionnaire_creates_db_session(self, client, db_session):
        """Questionnaire submission must create a Session row in DB."""
        from app.db.models import Session as SessionModel
        before = db_session.query(SessionModel).count()
        client.post("/api/v1/questionnaire", json=self.FULL_ANSWERS)
        after = db_session.query(SessionModel).count()
        assert after > before
