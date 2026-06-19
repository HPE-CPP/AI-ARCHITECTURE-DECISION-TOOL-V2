import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.integration
def test_rule_based_extraction_is_repeatable(sample_document_data, mock_llm):
    from services.signal_extractor import SignalExtractor
    from services.extraction_cache import extraction_cache

    extraction_cache.clear()
    extractor = SignalExtractor(mock_llm)

    first = asyncio.run(extractor.extract_signals(sample_document_data))
    second = asyncio.run(extractor.extract_signals(sample_document_data))

    assert first == second


@pytest.mark.integration
def test_rule_based_extraction_prefers_explicit_document_evidence(sample_document_data, mock_llm_hallucinating):
    from services.signal_extractor import SignalExtractor
    from services.extraction_cache import extraction_cache

    extraction_cache.clear()
    extractor = SignalExtractor(mock_llm_hallucinating)
    result = asyncio.run(extractor.extract_signals(sample_document_data))

    assert result["dataset_size"]["value"] == "large"
    assert result["query_volume"]["value"] == "high"
    assert result["latency_requirement"]["value"] == "moderate"
    assert result["data_volatility"]["value"] == "low"
    assert result["security_level"]["value"] == "elevated"
    assert result["deployment_preference"]["value"] == "cloud"
    assert result["user_scale"]["value"] == "enterprise"
    assert result["dataset_size"]["source_verified"] is True
    assert result["deployment_preference"]["source_verified"] is True


@pytest.mark.integration
def test_scoring_confidence_stays_high_for_grounded_explicit_signals(sample_document_data, mock_llm_hallucinating):
    from services.signal_extractor import SignalExtractor
    from services.extraction_cache import extraction_cache
    from services.scoring_engine import ScoringEngine

    extraction_cache.clear()
    extractor = SignalExtractor(mock_llm_hallucinating)
    signals = asyncio.run(extractor.extract_signals(sample_document_data))
    result = ScoringEngine().score(signals)

    assert result["confidence"] >= 0.7
