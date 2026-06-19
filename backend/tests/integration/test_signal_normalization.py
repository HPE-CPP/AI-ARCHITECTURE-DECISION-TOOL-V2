import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.integration
def test_normalize_signal_value_maps_common_aliases():
    from services.signal_extractor import normalize_signal_value

    assert normalize_signal_value("deployment_preference", "on-premise") == "on_premise"
    assert normalize_signal_value("latency_requirement", "ultra low") == "ultra_low"
    assert normalize_signal_value("query_volume", "very high") == "very_high"


@pytest.mark.integration
def test_retrieved_context_does_not_change_cache_key_behavior(sample_document_data, mock_llm):
    from services.extraction_cache import extraction_cache
    from services.signal_extractor import SignalExtractor

    extraction_cache.clear()
    extractor = SignalExtractor(mock_llm)

    baseline = copy.deepcopy(sample_document_data)
    with_context = {
        **copy.deepcopy(sample_document_data),
        "retrieved_context": "Deployment target is AWS us-east-1.\n\nExpected throughput is 50,000 queries per day.",
    }

    first = __import__("asyncio").run(extractor.extract_signals(baseline))
    second = __import__("asyncio").run(extractor.extract_signals(with_context))

    assert first == second
