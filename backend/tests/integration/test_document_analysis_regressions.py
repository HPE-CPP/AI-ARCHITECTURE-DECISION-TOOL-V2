import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _DisabledLLM:
    provider = "openai"

    async def generate_json(self, prompt, **kwargs):
        return {"error": "disabled"}


@pytest.mark.integration
def test_deployment_inference_does_not_match_edge_inside_knowledge():
    from services.signal_extractor import SignalExtractor

    extractor = SignalExtractor(_DisabledLLM())
    inferred = extractor._infer_deployment(
        "The knowledge base is updated daily with new regulatory data."
    )

    assert inferred is None


@pytest.mark.integration
def test_reasonable_document_does_not_collapse_to_zero_confidence_without_llm():
    from services.signal_extractor import SignalExtractor
    from services.scoring_engine import ScoringEngine

    full_text = (
        "Our financial services platform processes over 10 million customer records daily. "
        "The system must handle real-time fraud detection with ultra-low latency requirements of under 100 milliseconds. "
        "The knowledge base is updated daily with new regulatory data. "
        "We require critical accuracy levels with zero tolerance for false negatives in fraud cases. "
        "The domain is highly specialized in financial services and regulatory compliance. "
        "Security level is critical and we must maintain HIPAA and SOC2 compliance at all times. "
        "Cost sensitivity is moderate and quality over cost. "
        "Deployment must be on-premise due to data residency requirements. "
        "User scale is enterprise with 1 million active users."
    )
    doc = {"full_text": full_text, "pages": [{"page_number": 1, "text": full_text}]}

    signals = asyncio.run(SignalExtractor(_DisabledLLM()).extract_signals(doc))
    result = ScoringEngine().score(signals)

    assert signals["deployment_preference"]["value"] == "on_premise"
    assert signals["data_volatility"]["value"] == "low"
    assert result["confidence"] >= 0.7
