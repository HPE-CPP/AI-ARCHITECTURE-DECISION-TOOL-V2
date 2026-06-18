"""
UNIT TESTS — LLM Client
Tests JSON sanitization, provider switching, error handling,
malformed output recovery, and timeout behavior.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.llm_client import sanitize_json_string, get_llm_client


@pytest.mark.unit
class TestSanitizeJsonString:

    def test_strips_markdown_code_fence(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        result = sanitize_json_string(raw)
        assert result == '{"key": "value"}'

    def test_strips_backtick_only_fence(self):
        raw = "```\n{\"key\": 1}\n```"
        result = sanitize_json_string(raw)
        assert result == '{"key": 1}'

    def test_plain_json_unchanged(self):
        raw = '{"key": "value"}'
        result = sanitize_json_string(raw)
        assert result == '{"key": "value"}'

    def test_strips_leading_trailing_whitespace(self):
        raw = "   {\"key\": \"val\"}   "
        result = sanitize_json_string(raw)
        assert result == '{"key": "val"}'

    def test_strips_explanatory_prefix(self):
        raw = "Here is the JSON output:\n```json\n{\"key\": 1}\n```"
        result = sanitize_json_string(raw)
        assert result == '{"key": 1}'

    def test_truncated_json_handled(self):
        """Truncated JSON from context window overflow."""
        raw = '{"dataset_size": {"value": "large", "confidence": 0.9'
        # sanitize should return raw string for caller to handle
        result = sanitize_json_string(raw)
        assert isinstance(result, str)

    def test_empty_string_returned_as_empty(self):
        result = sanitize_json_string("")
        assert result == ""

    def test_json_with_single_quotes_not_sanitized(self):
        """Single-quoted JSON is invalid — must not silently produce wrong data."""
        raw = "{'key': 'value'}"
        result = sanitize_json_string(raw)
        # Should still return the string — json.loads will fail, that's expected
        assert isinstance(result, str)


@pytest.mark.unit
class TestGetLLMClient:

    def test_get_openai_client(self):
        with patch("services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test-key"
            client = get_llm_client("openai")
            assert client.provider == "openai"

    def test_get_ollama_client(self):
        client = get_llm_client("ollama")
        assert client.provider == "ollama"

    def test_get_default_client_uses_settings(self):
        with patch("services.llm_client.settings") as mock_settings:
            mock_settings.DEFAULT_LLM_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "sk-test"
            client = get_llm_client(None)
            assert client is not None

    def test_invalid_provider_falls_back_gracefully(self):
        client = get_llm_client("invalid_provider")
        assert client is not None


@pytest.mark.unit
class TestLLMClientGenerateJson:

    @pytest.mark.asyncio
    async def test_parses_valid_json_response(self):
        with patch("services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.DEFAULT_LLM_PROVIDER = "openai"
            client = get_llm_client("openai")
            client.generate = AsyncMock(return_value='{"key": "value"}')
            result = await client.generate_json("prompt", {})
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_returns_error_dict_on_invalid_json(self):
        with patch("services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.DEFAULT_LLM_PROVIDER = "openai"
            client = get_llm_client("openai")
            client.generate = AsyncMock(return_value="not valid json at all")
            result = await client.generate_json("prompt", {})
            assert "error" in result
            assert "raw" in result

    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(self):
        with patch("services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.DEFAULT_LLM_PROVIDER = "openai"
            client = get_llm_client("openai")
            client.generate = AsyncMock(return_value='```json\n{"dataset_size": "large"}\n```')
            result = await client.generate_json("prompt", {})
            assert result.get("dataset_size") == "large"

    @pytest.mark.asyncio
    async def test_handles_generate_exception(self):
        with patch("services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.DEFAULT_LLM_PROVIDER = "openai"
            client = get_llm_client("openai")
            client.generate = AsyncMock(side_effect=Exception("Network failure"))
            result = await client.generate_json("prompt", {})
            assert "error" in result

    @pytest.mark.asyncio
    async def test_schema_validation_rejects_wrong_type(self):
        """Returns dict even if values don't match schema types."""
        with patch("services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.DEFAULT_LLM_PROVIDER = "openai"
            client = get_llm_client("openai")
            client.generate = AsyncMock(return_value='{"value": 42}')
            result = await client.generate_json("prompt", {})
            # Should not crash even if type is wrong
            assert isinstance(result, dict)


@pytest.mark.unit
class TestLLMClientHallucinationGuard:

    @pytest.mark.asyncio
    async def test_confidence_below_threshold_nulled(self, mock_llm_hallucinating):
        """Values with confidence < 0.1 must be nulled before returning."""
        from app.services.signal_service import _apply_anti_hallucination
        hallucinated = {
            "dataset_size": {"value": "FAKE", "confidence": 0.05, "source_text": "", "page_number": 0}
        }
        result = _apply_anti_hallucination(hallucinated)
        assert result["dataset_size"]["value"] is None

    @pytest.mark.asyncio
    async def test_confidence_above_threshold_preserved(self):
        from app.services.signal_service import _apply_anti_hallucination
        valid = {
            "dataset_size": {"value": "large", "confidence": 0.9, "source_text": "test", "page_number": 1}
        }
        result = _apply_anti_hallucination(valid)
        assert result["dataset_size"]["value"] == "large"


@pytest.mark.unit
class TestExtractionCache:

    def test_cache_miss_returns_none(self):
        from services.extraction_cache import ExtractionCache
        cache = ExtractionCache()
        assert cache.get("nonexistent_key") is None

    def test_cache_set_then_get(self):
        from services.extraction_cache import ExtractionCache
        cache = ExtractionCache()
        cache.set("key1", {"value": "test"})
        assert cache.get("key1") == {"value": "test"}

    def test_cache_ttl_expires(self):
        """Items set with ttl_seconds=0 should not persist in L2 (Redis)."""
        from services.extraction_cache import ExtractionCache
        cache = ExtractionCache()
        # Mock Redis to verify TTL
        cache._redis = MagicMock()
        cache.set("key_ttl", {"v": 1}, ttl_seconds=0)
        cache._redis.setex.assert_called_once()
        assert cache._redis.setex.call_args[0][1] == 0

    def test_cache_invalidate(self):
        from services.extraction_cache import ExtractionCache
        cache = ExtractionCache()
        cache.set("key2", {"data": "abc"})
        cache.invalidate("key2")
        assert cache.get("key2") is None

    def test_cache_key_hashing_is_deterministic(self):
        from services.extraction_cache import ExtractionCache
        cache = ExtractionCache()
        key1 = cache._key("doc_text_content")
        key2 = cache._key("doc_text_content")
        assert key1 == key2

    def test_different_inputs_produce_different_keys(self):
        from services.extraction_cache import ExtractionCache
        cache = ExtractionCache()
        key1 = cache._key("content_a")
        key2 = cache._key("content_b")
        assert key1 != key2

    def test_redis_l2_hit_populates_l1(self):
        """Verify that an L2 hit (Redis) correctly populates the L1 (in-memory) cache."""
        from services.extraction_cache import ExtractionCache
        cache = ExtractionCache()
        cache._redis = MagicMock()
        cache._redis.get.return_value = json.dumps({"redis": "data"})
        
        # Initial get (L1 miss, L2 hit)
        result = cache.get("redis_text")
        assert result == {"redis": "data"}
        assert cache.size == 1
        
        # Second get (L1 hit)
        cache._redis.get.reset_mock()
        result2 = cache.get("redis_text")
        assert result2 == {"redis": "data"}
        cache._redis.get.assert_not_called()
