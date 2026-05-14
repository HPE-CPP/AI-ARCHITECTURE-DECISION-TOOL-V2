"""
Signal service — extracts signals, persists them to PostgreSQL,
and caches results in Redis.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from app.db.models import Signal, Session as SessionModel
from app.services import cache_service
from app.services.vector_service import retrieve_context
from services.signal_extractor import SignalExtractor, SIGNAL_SCHEMA
from services.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def _signals_to_db(db: DBSession, session_id_str: str, signals: dict) -> None:
    """Persist extracted signal dicts as Signal ORM rows.

    Deletes any existing rows for this session first to stay idempotent —
    safe to call multiple times without creating duplicates.
    """
    import uuid
    session_uuid = uuid.UUID(session_id_str)
    # Delete stale rows so re-runs don't accumulate duplicates
    db.query(Signal).filter(Signal.session_id == session_uuid).delete(synchronize_session=False)
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
      2. On miss: retrieve semantically relevant text from FAISS
      3. Pass enriched text to SignalExtractor (LLM + keyword)
      4. Persist signals to PostgreSQL
      5. Cache in Redis

    Returns the signals dict.
    """
    # 1. Cache check
    cached = cache_service.get_signals(session_id)
    if cached:
        logger.info(f"Signals cache HIT for session {session_id}")
        return cached

    # 2. FAISS retrieval — pass as separate field so it does not corrupt
    # the full_text used for the extraction cache key and source verification.
    try:
        faiss_context = await retrieve_context(session_id)
        if faiss_context:
            document_data = {**document_data, "retrieved_context": faiss_context}
    except Exception as exc:
        logger.warning(f"FAISS retrieval failed: {exc}")

    # 3. Extract signals
    llm = get_llm_client(provider)
    extractor = SignalExtractor(llm)
    signals = await extractor.extract_signals(document_data)

    pre_ah_count = sum(1 for s in signals.values() if s.get("value"))
    logger.info("Pre-anti-hallucination: %d/%d signals have values", pre_ah_count, len(signals))

    # Anti-hallucination pass
    signals = _apply_anti_hallucination(signals)

    post_ah_count = sum(1 for s in signals.values() if s.get("value"))
    logger.info(
        "Post-anti-hallucination: %d/%d signals retained (threshold=%.1f)",
        post_ah_count, len(signals), 0.3,
    )
    if post_ah_count == 0 and pre_ah_count == 0:
        logger.error(
            "EXTRACTION FAILURE: 0 signals extracted. "
            "LLM may be unreachable. Check Ollama/OpenAI connection."
        )

    # 4. Persist to PostgreSQL
    try:
        _signals_to_db(db, session_id, signals)
    except Exception as exc:
        logger.error(f"Failed to persist signals to DB: {exc}")

    # 5. Cache
    cache_service.set_signals(session_id, signals)

    return signals


def _normalize_value(value: str) -> str:
    """Normalize LLM output value to match scoring rule keys.

    LLMs often return slightly variant spellings:
      "on-premise" → "on_premise", "Very High" → "very_high", etc.
    """
    return value.lower().strip().replace(" ", "_").replace("-", "_")


def _apply_anti_hallucination(signals: dict, threshold: float = 0.3) -> dict:
    """Null out signal values below the confidence threshold OR with invalid values.

    Threshold is intentionally set low (0.3) because source-verification no
    longer penalises confidence.  The primary safety net is the value-validity
    check: any value not in the scoring rules is rejected regardless of
    confidence, so hallucinated labels cannot reach the scoring engine.

    Value normalisation is applied first so that common variant spellings
    (e.g. "on-premise", "Very High") are accepted rather than rejected.
    """
    from services.scoring_engine import SCORING_RULES

    for key, sig in signals.items():
        value = sig.get("value")

        # Normalise first so "on-premise" → "on_premise" passes validation
        if value and isinstance(value, str):
            normalised = _normalize_value(value)
            if normalised != value:
                sig["value"] = normalised
                value = normalised

        if sig.get("confidence", 0) < threshold:
            sig["value"] = None
            continue

        if value and key in SCORING_RULES:
            allowed = set(SCORING_RULES[key].keys())
            if value not in allowed:
                logger.warning(
                    "Anti-hallucination: signal %s has invalid value '%s' "
                    "(allowed: %s). Nulling.",
                    key, value, allowed,
                )
                sig["value"] = None
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
    All deletes and inserts happen inside a single transaction so a concurrent
    reader never sees a window where the signal row is absent.
    """
    import uuid
    session_uuid = uuid.UUID(session_id)

    try:
        for signal_name, value in updates.items():
            if signal_name not in SIGNAL_SCHEMA:
                continue
            db.query(Signal).filter(
                Signal.session_id == session_uuid,
                Signal.signal_name == signal_name,
            ).delete(synchronize_session=False)
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
    except Exception:
        db.rollback()
        raise

    # Invalidate cache so next read gets fresh DB data
    cache_service.delete("signals", session_id)

    return _signals_from_db(db, session_id)
