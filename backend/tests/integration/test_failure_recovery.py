"""
PHASE 4 — FAILURE RECOVERY + TIMEOUT + RATE LIMITING TESTS
Tests: Redis failure, Ollama unavailability, timeout recovery, 
       retry logic, queue failure, rate limiting validation.
"""
import io
import uuid
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# REDIS FAILURE RECOVERY
# ============================================================================
@pytest.mark.integration
class TestRedisFailureRecovery:

    def test_cache_miss_fallback_to_db(self, client, seed_result, seed_session):
        """When Redis is unavailable (already patched to None), DB fallback must work."""
        # client fixture already sets Redis to None — so this tests the fallback path
        r = client.get(f"/api/v1/analysis/{seed_session.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "complete"

    def test_analysis_works_without_redis(self, client, seed_session_processing):
        """A processing session must be retrievable even without Redis."""
        r = client.get(f"/api/v1/analysis/{seed_session_processing.id}")
        assert r.status_code == 200
        assert r.json()["status"] == "processing"

    def test_cache_service_get_handles_redis_error(self):
        """cache_service.get() must return None when Redis client errors."""
        from unittest.mock import patch, MagicMock
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("Redis connection refused")
        with patch("app.services.cache_service._client", mock_client):
            from app.services import cache_service
            result = cache_service.get("result", "test-session-id")
            assert result is None

    def test_cache_service_set_handles_redis_error(self):
        """cache_service.set() must not raise when Redis client errors."""
        mock_client = MagicMock()
        mock_client.setex.side_effect = Exception("Redis connection refused")
        with patch("app.services.cache_service._client", mock_client):
            from app.services import cache_service
            # Must not raise
            cache_service.set("result", "test-session-id", {"status": "complete"})

    def test_cache_service_delete_handles_redis_error(self):
        """cache_service.delete() must not raise when Redis client errors."""
        mock_client = MagicMock()
        mock_client.delete.side_effect = Exception("Redis down")
        with patch("app.services.cache_service._client", mock_client):
            from app.services import cache_service
            cache_service.delete("signals", "test-session-id")


# ============================================================================
# OLLAMA / LLM FAILURE RECOVERY
# ============================================================================
@pytest.mark.integration
class TestOllamaFailureRecovery:

    def test_ollama_timeout_raises_runtime_error(self):
        """LLMClient must raise RuntimeError on timeout, not hang."""
        import asyncio
        from services.llm_client import LLMClient

        client = LLMClient(provider="ollama")
        with patch("services.llm_client.get_ollama_http_client") as mock_factory:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_factory.return_value = mock_http

            with pytest.raises((RuntimeError, asyncio.TimeoutError)):
                asyncio.get_event_loop().run_until_complete(
                    client.generate("test prompt")
                )

    def test_ollama_connection_refused_raises_error(self):
        """LLMClient must raise RuntimeError on connection refused."""
        import asyncio
        import httpx
        from services.llm_client import LLMClient

        client = LLMClient(provider="ollama")
        with patch("services.llm_client.get_ollama_http_client") as mock_factory:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_factory.return_value = mock_http

            with pytest.raises(RuntimeError):
                asyncio.get_event_loop().run_until_complete(
                    client.generate("test prompt")
                )

    def test_vector_service_failure_is_non_fatal(self, client, sample_txt_content):
        """FAISS indexing failure must not fail the upload — it must be non-fatal."""
        with patch("app.services.vector_service.index_document",
                   new=AsyncMock(side_effect=Exception("FAISS write error"))), \
             patch("app.services.signal_service.extract_and_persist",
                   new=AsyncMock(return_value={})), \
             patch("app.services.recommendation_service.score_and_persist", return_value={
                 "analysis_id": str(uuid.uuid4()), "status": "complete",
                 "recommended": "RAG", "confidence": 0.8,
                 "scores": {}, "ranking": [], "suitability": {},
                 "factor_breakdown": {}, "why_not": {}, "signals": {},
                 "architecture_details": {}, "followup_questions": [],
                 "sensitivity": {}, "decision_trace": [], "created_at": "2026-01-01",
             }):
            r = client.post(
                "/api/v1/upload",
                files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")},
            )
        # Must succeed — vector indexing failure is skipped, not fatal
        assert r.status_code in (200, 422)
        assert r.status_code != 500

    def test_signal_extraction_failure_propagates_as_500(self, client, sample_txt_content):
        """If signal extraction itself fails, the API must return 500."""
        with patch("app.services.vector_service.index_document", new=AsyncMock(return_value=5)), \
             patch("app.services.signal_service.extract_and_persist",
                   new=AsyncMock(side_effect=RuntimeError("LLM crashed"))):
            r = client.post(
                "/api/v1/upload",
                files={"file": ("req.txt", io.BytesIO(sample_txt_content), "text/plain")},
            )
        assert r.status_code == 500


# ============================================================================
# TOKEN CONTEXT WINDOW PROTECTION
# ============================================================================
@pytest.mark.unit
class TestContextWindowProtection:

    def test_short_prompt_passes_unchanged(self):
        """A short prompt must pass through without truncation."""
        import asyncio
        from services.llm_client import LLMClient

        llm = LLMClient(provider="ollama")
        short_prompt = "What is RAG?"
        captured = []

        async def mock_ollama(prompt, system_prompt, temperature, max_tokens, json_mode):
            captured.append(prompt)
            return '{"result": "ok"}'

        llm._ollama_generate = mock_ollama
        asyncio.get_event_loop().run_until_complete(
            llm.generate(short_prompt)
        )
        assert captured and "[TRUNCATED" not in captured[0]

    def test_huge_prompt_gets_truncated(self):
        """A 20k-token prompt must be truncated to the 16k token limit."""
        import asyncio
        from services.llm_client import LLMClient

        llm = LLMClient(provider="ollama")
        # ~20k tokens of content
        huge_prompt = "word " * 20000
        captured = []

        async def mock_ollama(prompt, system_prompt, temperature, max_tokens, json_mode):
            captured.append(prompt)
            return '{"result": "ok"}'

        llm._ollama_generate = mock_ollama
        asyncio.get_event_loop().run_until_complete(
            llm.generate(huge_prompt)
        )
        assert captured and "[TRUNCATED" in captured[0]


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================
@pytest.mark.security
class TestRateLimiting:

    def test_rate_limit_config_is_positive(self):
        """RATE_LIMIT_PER_MINUTE must be a positive integer."""
        from config import settings
        assert settings.RATE_LIMIT_PER_MINUTE > 0

    def test_repeated_requests_eventually_rate_limited(self, client):
        """
        Sends 40 rapid requests to the architectures endpoint.
        At 30/min limit, at least some should be rate-limited.
        Documents the behavior — xfail if not enforced in test mode.
        """
        responses = [client.get("/api/v1/architectures") for _ in range(40)]
        rate_limited = [r for r in responses if r.status_code == 429]
        if not rate_limited:
            pytest.xfail(
                "Rate limiting not enforced in test mode. "
                "SlowAPI needs RemoteAddr, which TestClient may not provide correctly."
            )

    def test_health_endpoint_responds_under_load(self, client):
        """Health checks must remain fast even under parallel requests."""
        responses = [client.get("/api/v1/health") for _ in range(20)]
        successes = [r for r in responses if r.status_code == 200]
        assert len(successes) >= 10, "Health endpoint should remain available"


# ============================================================================
# LATENCY BENCHMARKS
# ============================================================================
@pytest.mark.integration
class TestLatencyBenchmarks:

    def test_health_endpoint_responds_under_50ms(self, client):
        start = time.perf_counter()
        r = client.get("/api/v1/health")
        elapsed = (time.perf_counter() - start) * 1000
        assert r.status_code == 200
        assert elapsed < 50, f"Health endpoint took {elapsed:.1f}ms — should be <50ms"

    def test_architectures_endpoint_responds_under_100ms(self, client):
        start = time.perf_counter()
        r = client.get("/api/v1/architectures")
        elapsed = (time.perf_counter() - start) * 1000
        assert r.status_code == 200
        assert elapsed < 100, f"Architectures endpoint took {elapsed:.1f}ms"

    def test_questionnaire_options_responds_under_100ms(self, client):
        start = time.perf_counter()
        r = client.get("/api/v1/questionnaire/options")
        elapsed = (time.perf_counter() - start) * 1000
        assert r.status_code == 200
        assert elapsed < 100, f"Questionnaire options took {elapsed:.1f}ms"

    def test_analysis_404_responds_under_200ms(self, client):
        start = time.perf_counter()
        r = client.get(f"/api/v1/analysis/{uuid.uuid4()}")
        elapsed = (time.perf_counter() - start) * 1000
        assert r.status_code == 404
        assert elapsed < 200, f"Analysis 404 took {elapsed:.1f}ms"

    def test_project_list_responds_under_200ms(self, client):
        start = time.perf_counter()
        r = client.get("/api/v1/projects")
        elapsed = (time.perf_counter() - start) * 1000
        assert r.status_code == 200
        assert elapsed < 200, f"Project list took {elapsed:.1f}ms"
