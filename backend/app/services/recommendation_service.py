"""
Recommendation service — runs the scoring engine, persists the Result
row to PostgreSQL, and caches it in Redis.
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from app.db.models import Result, Session as SessionModel
from app.services import cache_service
from services.scoring_engine import ScoringEngine
from services.followup_generator import generate_followup_questions

logger = logging.getLogger(__name__)

_scoring_engine = ScoringEngine()


def _result_to_response(session_id: str, result: Result, signals: dict) -> dict:
    """Serialise a Result ORM row into the AnalysisResponse dict shape."""
    return {
        "analysis_id": session_id,
        "status": "complete",
        "signals": signals,
        "scores": result.scores,
        "recommended": result.recommended_architecture,
        "confidence": result.confidence_score,
        "ranking": result.ranking,
        "suitability": result.suitability,
        "factor_breakdown": result.decision_breakdown,
        "why_not": result.why_not,
        "architecture_details": result.architecture_details,
        "followup_questions": result.followup_questions,
        "sensitivity": result.sensitivity,
        "decision_trace": result.decision_trace,
        "created_at": result.created_at.isoformat(),
    }


def score_and_persist(
    db: DBSession,
    session_id: str,
    signals: dict,
    decision_trace: list | None = None,
) -> dict:
    """
    Run the scoring engine, persist the Result row, and cache.

    Returns the full AnalysisResponse dict.
    """
    decision_trace = decision_trace or []

    # Score
    scoring_result = _scoring_engine.score(signals)
    sensitivity = _scoring_engine.sensitivity_analysis(signals)
    followups = generate_followup_questions(signals)

    session_uuid = uuid.UUID(session_id)

    # Upsert Result (delete existing if present)
    existing = db.query(Result).filter(Result.session_id == session_uuid).first()
    if existing:
        db.delete(existing)
        db.flush()

    result_row = Result(
        session_id=session_uuid,
        recommended_architecture=scoring_result["recommended"],
        confidence_score=scoring_result["confidence"],
        ranking=scoring_result["ranking"],
        scores=scoring_result["scores"],
        decision_breakdown=scoring_result["factor_breakdown"],
        why_not=scoring_result["why_not"],
        suitability=scoring_result["suitability"],
        followup_questions=followups,
        sensitivity=sensitivity,
        decision_trace=decision_trace,
        architecture_details=scoring_result["architecture_details"],
        created_at=datetime.utcnow(),
    )
    db.add(result_row)
    db.commit()
    db.refresh(result_row)

    response = _result_to_response(session_id, result_row, signals)
    cache_service.set_result(session_id, response)
    return response


def get_result(db: DBSession, session_id: str, signals: dict | None = None) -> dict | None:
    """
    Fetch result — Redis first, then reconstruct from PostgreSQL.
    Returns None if no result exists yet.
    """
    cached = cache_service.get_result(session_id)
    if cached:
        return cached

    session_uuid = uuid.UUID(session_id)
    result_row = db.query(Result).filter(Result.session_id == session_uuid).first()
    if not result_row:
        return None

    response = _result_to_response(session_id, result_row, signals or {})
    cache_service.set_result(session_id, response)
    return response
