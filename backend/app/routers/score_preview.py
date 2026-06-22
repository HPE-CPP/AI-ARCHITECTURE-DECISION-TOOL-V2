"""
POST /api/v1/score-preview
 
Accepts a flat dict of signal_name -> value_string and returns live
architecture scores + recommended architecture.  Used by the What-If
Signal Editor on the frontend — no DB writes, no auth required.
 
This file is SELF-CONTAINED.  It imports only from services/ which already
exist.  No changes to any other file are needed to register this router.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
 
from services.scoring_engine import ScoringEngine, SCORING_RULES
from services.signal_extractor import SIGNAL_SCHEMA
 
router = APIRouter()
_engine = ScoringEngine()
 
 
# ── Request / Response schemas ────────────────────────────────────────────────
 
class ScorePreviewRequest(BaseModel):
    """
    signals: { "latency_requirement": "strict", "dataset_size": "large", ... }
    Only the keys you send are scored; others are skipped (confidence=0).
    """
    signals: dict[str, str]
 
 
class ScorePreviewResponse(BaseModel):
    scores: dict[str, float]          # { "RAG": 72.4, "FineTuning": 85.1, ... }
    recommended: str                   # "FineTuning"
    ranking: list[str]                 # ["FineTuning", "RAG", "Hybrid", "CAG"]
    factor_breakdown: dict[str, dict[str, float]]   # same shape as analysis result
 
 
# ── Endpoint ─────────────────────────────────────────────────────────────────
 
@router.post("/score-preview", response_model=ScorePreviewResponse)
def score_preview(body: ScorePreviewRequest):
    """
    Pure scoring — no LLM, no DB, instant response (<5 ms).
    Converts flat { signal: value } into the signal dict shape the engine expects,
    using confidence=1.0 for every signal the user explicitly set.
    """
    # Build signal dict in the format ScoringEngine.score() expects
    signal_dict: dict[str, dict] = {}
    for signal_name in SIGNAL_SCHEMA:
        value = body.signals.get(signal_name)
        if value and value in SCORING_RULES.get(signal_name, {}):
            signal_dict[signal_name] = {"value": value, "confidence": 1.0}
        else:
            signal_dict[signal_name] = {"value": None, "confidence": 0.0}
 
    result = _engine.score(signal_dict)

    if not result.get("data_sufficient", False):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Couldn't find enough signals. "
                f"At least {result.get('min_signals_to_show_results', 5)} signals are required before showing results."
            ),
        )
 
    raw_scores: dict[str, float] = result.get("scores", {})
    ranking: list[str] = result.get("ranking", [])
    factor_breakdown: dict[str, dict[str, float]] = result.get("factor_breakdown", {})
 
    recommended = ranking[0] if ranking else max(raw_scores, key=lambda k: raw_scores[k])
 
    return ScorePreviewResponse(
        scores=raw_scores,
        recommended=recommended,
        ranking=ranking,
        factor_breakdown=factor_breakdown,
    )