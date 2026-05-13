"""
Signal service — extracts signals, persists them to PostgreSQL,
and caches results in Redis.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from app.db.models import Signal, Session as SessionModel
from app.services import cache_service
from services.signal_extractor import SignalExtractor, SIGNAL_SCHEMA
from services.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def _signals_to_db(db: DBSession, session_id_str: str, signals: dict) -> None:
    """Persist extracted signal dicts as Signal ORM rows."""
    import uuid
    session_uuid = uuid.UUID(session_id_str)
    for signal_name, data in signals.items():
        row = Signal(
            session_id=session_uuid,
            signal_name=signal_name,
            value=data.get("value"),
            confidence=float(data.get("confidence", 0.0)),
            source_text=str(data.get("source_text", ""))[:2000],
            page_number=int(data.get("page_number", 0)),
            source_verified=bool(data.get("source_verified", False)),
        )
        db.add(row)
    db.commit()


def _signals_from_db(db: DBSession, session_id_str: str) -> dict:
    """Reload signal rows from PostgreSQL and convert to dict format."""
    import uuid
    session_uuid = uuid.UUID(session_id_str)
    rows = db.query(Signal).filter(Signal.session_id == session_uuid).all()
    signals: dict = {}
    for row in rows:
        signals[row.signal_name] = {
            "value": row.value,
            "confidence": row.confidence,
            "source_text": row.source_text,
            "page_number": row.page_number,
            "source_verified": getattr(row, "source_verified", False),
        }
    return signals


async def extract_and_persist(
    db: DBSession,
    session_id: str,
    document_data: dict,
    provider: str = None,
) -> dict:
    """
    Extract signals from a parsed document, persist to DB, and cache.

    Flow:
      1. Check Redis cache
      2. On miss: retrieve signal-specific context from FAISS (multi-query)
      3. Pass enriched text to SignalExtractor (LLM + semantic + keyword)
      4. Apply strict anti-hallucination pipeline
      5. Persist signals to PostgreSQL
      6. Cache in Redis

    Returns the signals dict.
    """
    # 1. Cache check
    cached = cache_service.get_signals(session_id)
    if cached:
        logger.info(f"Signals cache HIT for session {session_id}")
        return cached

    # 2. Multi-query FAISS retrieval for signal-specific context
    try:
        from app.services.vector_service import retrieve_context_for_signals
        faiss_context = await retrieve_context_for_signals(session_id)
        if faiss_context:
            # Prepend retrieved context to the full text for better coverage
            enriched_text = faiss_context + "\n\n" + document_data.get("full_text", "")
            document_data = {**document_data, "full_text": enriched_text[:12000]}
            logger.info("Enriched context with %d chars from multi-query FAISS retrieval", len(faiss_context))
    except Exception as exc:
        logger.warning(f"FAISS retrieval failed, using raw text: {exc}")

    # 3. Extract signals
    llm = get_llm_client(provider)
    extractor = SignalExtractor(llm)
    signals = await extractor.extract_signals(document_data)

    # 4. Strict anti-hallucination pass
    signals = _apply_anti_hallucination(signals)

    # 5. Persist to PostgreSQL
    try:
        _signals_to_db(db, session_id, signals)
    except Exception as exc:
        logger.error(f"Failed to persist signals to DB: {exc}")

    # 6. Cache
    cache_service.set_signals(session_id, signals)

    return signals


# Hallucination confidence threshold — signals below this are nullified
HALLUCINATION_THRESHOLD = 0.55


def _apply_anti_hallucination(signals: dict) -> dict:
    """Strict anti-hallucination pipeline.

    Validates signals through multiple checks:
      1. Confidence threshold (0.55) — below this, value is nullified.
      2. Allowlist validation — values must be in SCORING_RULES.
      3. Source verification — unverified sources penalize confidence.
      4. Hallucination risk scoring — risk level added to each signal.

    Risk levels:
      - confirmed: source_verified=True and confidence >= 0.7
      - low: source_verified=True and confidence >= THRESHOLD
      - medium: confidence >= THRESHOLD but source not verified
      - high: confidence < THRESHOLD or invalid value
    """
    from services.scoring_engine import SCORING_RULES

    for key, sig in signals.items():
        confidence = sig.get("confidence", 0)
        value = sig.get("value")
        source_verified = sig.get("source_verified", False)

        # Check 1: Confidence threshold
        if confidence < HALLUCINATION_THRESHOLD:
            sig["value"] = None
            sig["hallucination_risk"] = "high"
            continue

        # Check 2: Allowlist validation
        if value and key in SCORING_RULES:
            allowed = set(SCORING_RULES[key].keys())
            if value not in allowed:
                logger.warning(
                    "Anti-hallucination: signal %s has invalid value '%s' "
                    "(allowed: %s). Nulling.",
                    key, value, allowed,
                )
                sig["value"] = None
                sig["hallucination_risk"] = "high"
                continue

        # Check 3: Source verification penalty
        if not source_verified and value:
            sig["confidence"] = round(confidence * 0.7, 2)
            if sig["confidence"] < HALLUCINATION_THRESHOLD:
                sig["value"] = None
                sig["hallucination_risk"] = "high"
                continue

        # Check 4: Assign hallucination risk level
        if source_verified and sig.get("confidence", 0) >= 0.7:
            sig["hallucination_risk"] = "confirmed"
        elif source_verified:
            sig["hallucination_risk"] = "low"
        elif sig.get("confidence", 0) >= HALLUCINATION_THRESHOLD:
            sig["hallucination_risk"] = "medium"
        else:
            sig["hallucination_risk"] = "high"

    return signals


def get_signals(db: DBSession, session_id: str) -> dict:
    """Fetch signals for a session — Redis first, then PostgreSQL."""
    cached = cache_service.get_signals(session_id)
    if cached:
        return cached
    signals = _signals_from_db(db, session_id)
    if signals:
        cache_service.set_signals(session_id, signals)
    return signals


def update_signals(db: DBSession, session_id: str, updates: dict[str, str]) -> dict:
    """
    Apply follow-up answer overrides to existing signals.
    Deletes old rows for updated signals and inserts new ones.
    """
    import uuid
    session_uuid = uuid.UUID(session_id)

    for signal_name, value in updates.items():
        if signal_name not in SIGNAL_SCHEMA:
            continue
        # Delete existing row for this signal
        db.query(Signal).filter(
            Signal.session_id == session_uuid,
            Signal.signal_name == signal_name,
        ).delete(synchronize_session=False)
        # Insert updated row
        db.add(Signal(
            session_id=session_uuid,
            signal_name=signal_name,
            value=value,
            confidence=1.0,
            source_text="Follow-up answer from user",
            page_number=0,
            source_verified=True,
        ))
    db.commit()

    # Invalidate cache so next read gets fresh DB data
    cache_service.delete("signals", session_id)

    return _signals_from_db(db, session_id)
