"""
INTEGRATION TESTS — Signal Service + Cache Service
Tests the full extract_and_persist flow including DB writes,
Redis cache interactions (mocked), and FAISS retrieval (mocked).
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.integration
class TestExtractAndPersist:

    @pytest.mark.asyncio
    async def test_extract_and_persist_writes_to_db(self, db_session, sample_document_data, mock_llm):
        """Full extraction pipeline persists all signals to the DB."""
        from app.services import signal_service
        session_id = str(uuid.uuid4())

        # Insert a session row first
        from app.db.models import Session as SessionModel
        s = SessionModel(id=uuid.UUID(session_id), status="processing", provider="openai")
        db_session.add(s)
        db_session.commit()

        with patch("app.services.signal_service.retrieve_context", new_callable=AsyncMock) as mock_faiss, \
             patch("app.services.signal_service.get_llm_client", return_value=mock_llm), \
             patch("app.services.cache_service._client", None):
            mock_faiss.return_value = ""
            signals = await signal_service.extract_and_persist(
                db=db_session,
                session_id=session_id,
                document_data=sample_document_data,
                provider="openai",
            )

        assert signals is not None
        from app.db.models import Signal
        db_signals = db_session.query(Signal).filter(
            Signal.session_id == uuid.UUID(session_id)
        ).all()
        assert len(db_signals) == 12  # all 12 signals written

    @pytest.mark.asyncio
    async def test_extract_and_persist_uses_cache_on_second_call(self, db_session, sample_document_data, mock_llm):
        """Second extraction for the same session must come from cache, not LLM."""
        from app.services import signal_service
        session_id = str(uuid.uuid4())

        mock_cache = {session_id: {"dataset_size": {"value": "large", "confidence": 0.9,
                                                     "source_text": "cached", "page_number": 1}}}

        with patch("app.services.cache_service.get_signals", return_value=mock_cache.get(session_id)), \
             patch("app.services.signal_service.get_llm_client", return_value=mock_llm):
            signals = await signal_service.extract_and_persist(
                db=db_session,
                session_id=session_id,
                document_data=sample_document_data,
                provider="openai",
            )

        # LLM should NOT have been called
        mock_llm.generate_json.assert_not_called()
        assert "dataset_size" in signals

    @pytest.mark.asyncio
    async def test_extract_handles_faiss_failure_gracefully(self, db_session, sample_document_data, mock_llm):
        """If FAISS retrieval fails, pipeline continues with raw text."""
        from app.services import signal_service
        session_id = str(uuid.uuid4())

        from app.db.models import Session as SessionModel
        s = SessionModel(id=uuid.UUID(session_id), status="processing", provider="openai")
        db_session.add(s)
        db_session.commit()

        with patch("app.services.signal_service.retrieve_context",
                   side_effect=Exception("FAISS unavailable")), \
             patch("app.services.signal_service.get_llm_client", return_value=mock_llm), \
             patch("app.services.cache_service._client", None):
            # Should not raise — FAISS failure is non-fatal
            signals = await signal_service.extract_and_persist(
                db=db_session,
                session_id=session_id,
                document_data=sample_document_data,
                provider="openai",
            )
        assert signals is not None

    @pytest.mark.asyncio
    async def test_anti_hallucination_applied_after_extraction(self, db_session, mock_llm_hallucinating):
        """Low-confidence hallucinated values must be nulled before persisting."""
        # Patch the hallucinating LLM to return 0.05 confidence
        low_conf_response = {
            k: {"value": "HALLUCINATED", "confidence": 0.05, "source_text": "", "page_number": 0}
            for k in ["dataset_size", "data_volatility", "latency_requirement",
                      "query_volume", "accuracy_requirement", "domain_specificity",
                      "security_level", "cost_sensitivity", "deployment_preference", "user_scale",
                      "citation_requirement", "context_size"]
        }
        mock_llm_hallucinating.generate_json = AsyncMock(return_value=low_conf_response)

        from app.services import signal_service
        session_id = str(uuid.uuid4())

        from app.db.models import Session as SessionModel
        s = SessionModel(id=uuid.UUID(session_id), status="processing", provider="openai")
        db_session.add(s)
        db_session.commit()

        # Use minimal text with no keywords to prevent heuristic override
        blank_doc = {
            "filename": "blank.txt",
            "format": ".txt",
            "total_pages": 1,
            "full_text": "This is a placeholder document.",
            "char_count": 31,
            "word_count": 6,
            "pages": [{"page_number": 1, "text": "This is a placeholder document.", "char_count": 31}],
        }

        with patch("app.services.signal_service.retrieve_context", new_callable=AsyncMock, return_value=""), \
             patch("app.services.signal_service.get_llm_client", return_value=mock_llm_hallucinating), \
             patch("app.services.cache_service._client", None):
            signals = await signal_service.extract_and_persist(
                db=db_session,
                session_id=session_id,
                document_data=blank_doc,
                provider="openai",
            )

        for key, sig in signals.items():
            assert sig["value"] is None, f"Signal {key} was not nulled (confidence 0.05)"


@pytest.mark.integration
class TestUpdateSignals:

    def test_update_signals_overwrites_existing_db_row(self, db_session, seed_session):
        """Follow-up answers must replace old signal rows, not append."""
        from app.services import signal_service
        from app.db.models import Signal

        # Pre-insert a signal
        sid = seed_session.id
        original = Signal(session_id=sid, signal_name="dataset_size", value="small",
                          confidence=0.5, source_text="original", page_number=1)
        db_session.add(original)
        db_session.commit()

        with patch("app.services.cache_service.delete"):
            _ = signal_service.update_signals(
                db=db_session,
                session_id=str(sid),
                updates={"dataset_size": "large"},
            )

        rows = db_session.query(Signal).filter(
            Signal.session_id == sid,
            Signal.signal_name == "dataset_size",
        ).all()
        # Must have exactly 1 row after update (not 2)
        assert len(rows) == 1
        assert rows[0].value == "large"
        assert rows[0].confidence == 0.85
        assert rows[0].source_verified is True

    def test_update_signals_unknown_key_ignored(self, db_session, seed_session):
        from app.services import signal_service
        with patch("app.services.cache_service.delete"):
            result = signal_service.update_signals(
                db=db_session,
                session_id=str(seed_session.id),
                updates={"totally_invalid_signal": "value"},
            )
        # No crash, unknown key skipped
        assert isinstance(result, dict)

    def test_update_signals_invalidates_cache(self, db_session, seed_session):
        from app.services import signal_service
        with patch("app.services.cache_service.delete") as mock_delete:
            signal_service.update_signals(
                db=db_session,
                session_id=str(seed_session.id),
                updates={"dataset_size": "medium"},
            )
        mock_delete.assert_called_once_with("signals", str(seed_session.id))


@pytest.mark.integration
class TestRecommendationService:

    def test_score_and_persist_creates_result_row(self, db_session, seed_session, complete_signals):
        from app.services import recommendation_service
        from app.db.models import Result
        with patch("app.services.cache_service.set_result"):
            result = recommendation_service.score_and_persist(
                db=db_session,
                session_id=str(seed_session.id),
                signals=complete_signals,
            )

        assert result["status"] == "complete"
        assert result["recommended"] in ("RAG", "FineTuning", "CAG", "Hybrid")

        row = db_session.query(Result).filter(
            Result.session_id == seed_session.id
        ).first()
        assert row is not None
        assert row.recommended_architecture == result["recommended"]

    def test_score_and_persist_rejects_empty_signals(self, db_session, seed_session):
        from app.services import recommendation_service
        from app.db.models import Result

        sparse_signals = {
            k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0, "source_verified": False}
            for k in [
                "dataset_size",
                "query_volume",
                "latency_requirement",
                "data_volatility",
                "accuracy_requirement",
                "domain_specificity",
                "security_level",
                "cost_sensitivity",
                "deployment_preference",
                "user_scale",
                "citation_requirement",
                "context_size",
            ]
        }

        with patch("app.services.cache_service.set_result"):
            result = recommendation_service.score_and_persist(
                db=db_session,
                session_id=str(seed_session.id),
                signals=sparse_signals,
            )

        assert result["status"] == "error"
        assert "Couldn't find enough signals" in result["error_message"]
        assert db_session.query(Result).filter(Result.session_id == seed_session.id).count() == 0

    def test_score_and_persist_upserts_on_re_score(self, db_session, seed_session, seed_result, complete_signals):
        """Re-scoring must replace the existing result row, not create a duplicate."""
        from app.services import recommendation_service
        from app.db.models import Result
        with patch("app.services.cache_service.set_result"):
            recommendation_service.score_and_persist(
                db=db_session,
                session_id=str(seed_session.id),
                signals=complete_signals,
            )

        count = db_session.query(Result).filter(
            Result.session_id == seed_session.id
        ).count()
        assert count == 1  # Not 2

    def test_get_result_returns_from_db_when_cache_empty(self, db_session, seed_session, seed_result, complete_signals):
        from app.services import recommendation_service
        with patch("app.services.cache_service.get_result", return_value=None):
            result = recommendation_service.get_result(
                db=db_session,
                session_id=str(seed_session.id),
                signals=complete_signals,
            )
        assert result is not None
        assert result["recommended"] is not None

    def test_get_result_returns_from_cache_when_available(self, db_session, seed_session):
        from app.services import recommendation_service
        cached_result = {"status": "complete", "recommended": "RAG", "analysis_id": str(seed_session.id)}
        with patch("app.services.cache_service.get_result", return_value=cached_result):
            result = recommendation_service.get_result(
                db=db_session,
                session_id=str(seed_session.id),
            )
        assert result == cached_result

    def test_get_result_returns_none_when_no_result_exists(self, db_session):
        from app.services import recommendation_service
        with patch("app.services.cache_service.get_result", return_value=None):
            result = recommendation_service.get_result(
                db=db_session,
                session_id=str(uuid.uuid4()),
            )
        assert result is None


@pytest.mark.integration
class TestCacheService:

    def test_get_returns_none_when_client_is_none(self):
        from app.services import cache_service
        with patch.object(cache_service, "_client", None):
            result = cache_service.get("signals", "test_session")
        assert result is None

    def test_set_is_noop_when_client_is_none(self):
        from app.services import cache_service
        with patch.object(cache_service, "_client", None):
            # Must not raise
            cache_service.set("signals", "test_session", {"data": 1})

    def test_get_signals_convenience_wrapper(self):
        from app.services import cache_service
        mock_value = {"dataset_size": {"value": "large"}}
        with patch.object(cache_service, "_client") as mock_client:
            mock_client.get.return_value = '{"dataset_size": {"value": "large"}}'
            result = cache_service.get_signals("test_session")
        assert result == mock_value

    def test_set_signals_uses_signals_prefix(self):
        from app.services import cache_service
        with patch.object(cache_service, "_client") as mock_client:
            cache_service.set_signals("sess_123", {"test": "data"})
            mock_client.setex.assert_called_once()
            call_args = mock_client.setex.call_args[0]
            assert "signals:sess_123" in call_args[0]

    def test_invalidate_session_deletes_both_keys(self):
        from app.services import cache_service
        with patch.object(cache_service, "_client") as mock_client:
            cache_service.invalidate_session("sess_abc")
            assert mock_client.delete.call_count == 2
            calls = [str(c) for c in mock_client.delete.call_args_list]
            assert any("signals" in c for c in calls)
            assert any("result" in c for c in calls)
