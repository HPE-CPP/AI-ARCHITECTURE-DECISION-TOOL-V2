import pytest


@pytest.mark.integration
def test_partial_but_strong_signals_do_not_yield_artificially_low_confidence(partial_signals):
    """Strong evidence should not be drowned out by unrelated missing signals."""
    from services.scoring_engine import ScoringEngine

    for signal in partial_signals.values():
        if signal["value"]:
            signal["source_verified"] = True

    result = ScoringEngine().score(partial_signals)

    assert result["confidence"] >= 0.7
