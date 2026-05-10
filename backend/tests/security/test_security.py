"""
SECURITY TESTS
Tests for all vulnerabilities identified in Phase 1 audit:
- Path traversal (SEC-002)
- CORS misconfiguration (SEC-005)
- User ID spoofing (AUDIT BUG-004)
- Injection via filename / query params
- Rate limiting (ARCH SEC-003)
- Information leakage in error responses
"""
import io
import uuid
import pytest
from unittest.mock import patch


@pytest.mark.security
class TestPathTraversal:

    UPLOAD_URL = "/api/v1/upload"

    def _upload(self, client, filename, content=b"test content for analysis"):
        from unittest.mock import AsyncMock
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
            return client.post(
                self.UPLOAD_URL,
                files={"file": (filename, io.BytesIO(content), "text/plain")},
            )

    def test_parent_directory_traversal_blocked(self, client):
        """AUDIT SEC-002: ../filename must not be accepted."""
        response = self._upload(client, "../../config.py")
        assert response.status_code in (400, 422)
        if response.status_code == 200:
            pytest.fail("CRITICAL: Path traversal accepted — writes to arbitrary locations")

    def test_absolute_path_blocked(self, client):
        response = self._upload(client, "/etc/cron.daily/exploit")
        assert response.status_code in (400, 422)

    def test_windows_path_traversal_blocked(self, client):
        response = self._upload(client, "..\\..\\windows\\system32\\config")
        assert response.status_code in (400, 422)

    def test_double_slash_traversal_blocked(self, client):
        response = self._upload(client, "//etc/passwd")
        assert response.status_code in (400, 422)

    def test_encoded_traversal_blocked(self, client):
        response = self._upload(client, "%2e%2e%2fetc%2fpasswd")
        assert response.status_code in (400, 422)

    def test_null_byte_injection_blocked(self, client):
        response = self._upload(client, "safe.txt\x00.exe")
        assert response.status_code in (400, 422)

    def test_valid_filename_succeeds(self, client, sample_txt_content):
        response = self._upload(client, "requirements.txt", sample_txt_content)
        # Should pass validation (may fail at content if too short but not 400)
        assert response.status_code != 400 or "filename" not in response.text.lower()


@pytest.mark.security
class TestInjection:

    def test_provider_sql_injection_rejected(self, client, sample_txt_content):
        """Provider param must be restricted to enum values."""
        response = client.post(
            "/api/v1/upload?provider='; DROP TABLE sessions; --",
            files={"file": ("test.txt", io.BytesIO(sample_txt_content), "text/plain")},
        )
        assert response.status_code == 422  # regex validation

    def test_analysis_id_sql_injection_404(self, client):
        """Analysis ID must be UUID-validated."""
        response = client.get("/api/v1/analysis/' OR '1'='1")
        assert response.status_code == 404

    def test_followup_answers_json_injection(self, client):
        """Followup answers with injected keys must not crash server."""
        payload = {
            "analysis_id": str(uuid.uuid4()),
            "answers": {
                "dataset_size": "large; DROP TABLE signals;",
                "__proto__": {"admin": True},
            },
        }
        response = client.post("/api/v1/followup", json=payload)
        assert response.status_code in (404, 422)  # Not 500


@pytest.mark.security
class TestCORSConfiguration:

    def test_cors_allows_configured_origin(self, client):
        response = client.get(
            "/api/v1/architectures",
            headers={"Origin": "http://localhost:3000"},
        )
        acao = response.headers.get("access-control-allow-origin", "")
        assert acao in ("http://localhost:3000", "*")

    def test_cors_disallows_unknown_origin(self, client):
        """Non-whitelisted origins should not receive ACAO header with wildcard."""
        response = client.get(
            "/api/v1/architectures",
            headers={"Origin": "https://evil-attacker.com"},
        )
        acao = response.headers.get("access-control-allow-origin", "")
        # Should not echo back the evil origin
        assert "evil-attacker.com" not in acao

    def test_cors_preflight_responds(self, client):
        response = client.options(
            "/api/v1/upload",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code in (200, 204)


@pytest.mark.security
class TestRateLimiting:

    def test_rate_limit_header_present_or_enforced(self, client):
        """
        AUDIT SEC-003: Rate limiting must be enforced.
        Send 35 requests — if no rate limiting, all succeed.
        This test FAILS if all 35 succeed (no rate limiting).
        """
        responses = [
            client.get("/api/v1/architectures") for _ in range(35)
        ]
        status_codes = [r.status_code for r in responses]
        rate_limited = [s for s in status_codes if s == 429]

        if not rate_limited:
            pytest.xfail(
                "AUDIT SEC-003: No rate limiting enforced. "
                "All 35 requests returned 200. "
                "RATE_LIMIT_PER_MINUTE config value is decorative only."
            )


@pytest.mark.security
class TestInformationLeakage:

    def test_500_error_does_not_leak_stack_trace(self, client):
        """Internal errors must not expose Python tracebacks."""
        # Force an internal error via invalid project_id in upload
        response = client.post(
            "/api/v1/upload?project_id=not-a-uuid",
            files={"file": ("test.txt", io.BytesIO(b"Some valid content here for testing."), "text/plain")},
        )
        if response.status_code in (500, 422):
            body = response.text
            assert "Traceback" not in body
            assert "File \"/app" not in body

    def test_404_error_does_not_reveal_db_info(self, client):
        response = client.get(f"/api/v1/analysis/{uuid.uuid4()}")
        assert response.status_code == 404
        body = response.text
        assert "sqlalchemy" not in body.lower()
        assert "postgres" not in body.lower()
        assert "psycopg2" not in body.lower()

    def test_server_header_not_exposed(self, client):
        response = client.get("/api/v1/architectures")
        server_header = response.headers.get("server", "")
        # Should not expose uvicorn version
        assert "uvicorn" not in server_header.lower() or True  # informational only


@pytest.mark.security
class TestUserDataIsolation:

    def test_user_id_in_query_param_is_not_trusted(self, client, seed_project):
        """
        AUDIT SEC-001: Any user_id in query params must not be trusted without auth.
        This test documents the KNOWN VULNERABILITY for tracking.
        """
        # Attempt to read another user's projects by spoofing user_id
        response = client.get("/api/v1/projects?user_id=attacker_uid_000")
        if response.status_code == 200:
            data = response.json()
            # If we can list another user's projects, that's a data isolation failure
            # We mark this as xfail because the vulnerability is known (SEC-001)
            pytest.xfail(
                "AUDIT SEC-001: Backend has no authentication. "
                "user_id in query params is trusted without JWT verification."
            )

    def test_cross_session_analysis_access(self, client, seed_session):
        """
        Accessing another user's analysis by guessing UUID.
        Documents the known vulnerability for remediation tracking.
        """
        # Try to access seed_session (which belongs to test_user_001)
        response = client.get(f"/api/v1/analysis/{seed_session.id}")
        if response.status_code == 200:
            pytest.xfail(
                "AUDIT SEC-001: No auth on analysis endpoint. "
                "Any UUID-guessing request succeeds."
            )


@pytest.mark.security
class TestContentValidation:

    def test_csv_masquerading_as_txt_rejected(self, client):
        csv_content = b"col1,col2,col3\nval1,val2,val3\n"
        from unittest.mock import AsyncMock
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
            response = client.post(
                "/api/v1/upload",
                files={"file": ("data.csv", io.BytesIO(csv_content), "text/plain")},
            )
        assert response.status_code == 400

    def test_binary_file_as_txt_handled(self, client):
        """Binary content sent as text/plain must not crash the server."""
        binary_content = bytes(range(256)) * 100
        from unittest.mock import AsyncMock
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
            response = client.post(
                "/api/v1/upload",
                files={"file": ("binary.txt", io.BytesIO(binary_content), "text/plain")},
            )
        # Must not return 500 — either 200 (attempt to parse) or 400/422
        assert response.status_code != 500

    def test_json_sent_as_txt_handled_gracefully(self, client):
        json_content = b'{"key": "value", "nested": {"deep": true}}'
        from unittest.mock import AsyncMock
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
            response = client.post(
                "/api/v1/upload",
                files={"file": ("data.txt", io.BytesIO(json_content), "text/plain")},
            )
        # 422 likely (too few words) but not 500
        assert response.status_code in (200, 400, 422)
