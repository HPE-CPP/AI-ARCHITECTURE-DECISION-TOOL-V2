"""
TEST 12 — CAG recommendation from a 45 MB document.

Verifies that a large (45 MB) requirements document whose content is engineered
to express small-bounded-corpus, low-query-volume, static-data, general-purpose,
and very-tight-budget characteristics produces CAG as the recommended architecture.

Signal targets (all resolved via heuristic extraction — no LLM required):
  dataset_size      = small      ('small bounded corpus',   conf ≥ 0.75)
  query_volume      = low        ('small team',              conf ≥ 0.65)
  latency           = relaxed    ('asynchronous'/'batch',   conf ≥ 0.68)
  data_volatility   = static     ('static'/'rarely changes', conf ≥ 0.74)
  accuracy          = moderate   ('internal tool',           conf ≥ 0.55)
  domain_specificity = general   ('general-purpose',         conf ≥ 0.65)
  security_level    = elevated   ('internal use only',       conf ≥ 0.62)
  cost_sensitivity  = very_high  ('very tight budget',       conf ≥ 0.78)
  deployment        = on_premise ('data center',             conf ≥ 0.82)
  user_scale        = small      ('small team',              conf ≥ 0.65)

CAG synergy bonus (+14 pts) fires because:
  dataset_size=small AND data_volatility=static AND query_volume=low

Expected CAG score: ~90+, well ahead of RAG/FineTuning (~55).
"""
import asyncio
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "services"))

_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "cag_large_document_test_12.txt"
)

# ── Stub LLM — heuristic-only extraction ─────────────────────────────────────


class _DisabledLLM:
    provider = "openai"

    async def generate_json(self, prompt, **kwargs):
        return {"error": "disabled"}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_document(path: str, max_chars: int = 50_000) -> dict:
    """Read the fixture file and build a minimal document_data dict."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read(max_chars)
    pages = [
        {"page_number": i + 1, "text": text[i * 2000 : (i + 1) * 2000]}
        for i in range(len(text) // 2000)
    ]
    return {"full_text": text, "pages": pages}


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_cag_large_document_file_exists():
    """Fixture file must exist and be at least 44 MB."""
    assert os.path.isfile(_FIXTURE_PATH), (
        f"Fixture not found: {_FIXTURE_PATH}. "
        "Run generate_cag_test_document.py to regenerate."
    )
    size_mb = os.path.getsize(_FIXTURE_PATH) / (1024 * 1024)
    assert size_mb >= 44, f"Expected ≥44 MB fixture, got {size_mb:.1f} MB"


@pytest.mark.integration
def test_cag_large_document_heuristic_signals():
    """Heuristic extraction must resolve the four synergy-bonus signals correctly."""
    logging.disable(logging.CRITICAL)
    from services.signal_extractor import SignalExtractor

    doc = _load_document(_FIXTURE_PATH)
    extractor = SignalExtractor(_DisabledLLM())
    signals = asyncio.run(extractor.extract_signals(doc))

    assert signals["dataset_size"]["value"] == "small", (
        f"Expected dataset_size=small, got {signals['dataset_size']['value']}"
    )
    assert signals["query_volume"]["value"] == "low", (
        f"Expected query_volume=low, got {signals['query_volume']['value']}"
    )
    assert signals["data_volatility"]["value"] == "static", (
        f"Expected data_volatility=static, got {signals['data_volatility']['value']}"
    )
    assert signals["cost_sensitivity"]["value"] == "very_high", (
        f"Expected cost_sensitivity=very_high, got {signals['cost_sensitivity']['value']}"
    )


@pytest.mark.integration
def test_cag_large_document_recommends_cag():
    """Scoring engine must recommend CAG from the 45 MB document."""
    logging.disable(logging.CRITICAL)
    from services.signal_extractor import SignalExtractor
    from services.scoring_engine import ScoringEngine

    doc = _load_document(_FIXTURE_PATH)
    extractor = SignalExtractor(_DisabledLLM())
    signals = asyncio.run(extractor.extract_signals(doc))
    result = ScoringEngine().score(signals)

    assert result["recommended"] == "CAG", (
        f"Expected CAG recommendation, got {result['recommended']}. "
        f"Scores: {result['scores']}"
    )
    assert result["scores"]["CAG"] > result["scores"]["RAG"] + 20, (
        f"CAG should lead RAG by >20 pts: CAG={result['scores']['CAG']}, RAG={result['scores']['RAG']}"
    )
    assert result["scores"]["CAG"] >= 80, (
        f"CAG score should be ≥80, got {result['scores']['CAG']}"
    )
