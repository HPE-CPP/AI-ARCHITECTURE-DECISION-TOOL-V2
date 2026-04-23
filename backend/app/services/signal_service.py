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

    # 2. FAISS retrieval to enrich context
    try:
        faiss_context = await retrieve_context(session_id)
        if faiss_context:
            # Prepend retrieved context to the full text for better coverage
            enriched_text = faiss_context + "\n\n" + document_data.get("full_text", "")
            document_data = {**document_data, "full_text": enriched_text[:12000]}
    except Exception as exc:
        logger.warning(f"FAISS retrieval failed, using raw text: {exc}")

    # 3. Extract signals
    llm = get_llm_client(provider)
    extractor = SignalExtractor(llm)
    signals = await extractor.extract_signals(document_data)

    # Anti-hallucination pass
    for key, sig in signals.items():
        if sig.get("confidence", 0) < 0.1:
            sig["value"] = None

    # 4. Persist to PostgreSQL
    try:
        _signals_to_db(db, session_id, signals)
    except Exception as exc:
        logger.error(f"Failed to persist signals to DB: {exc}")

    # 5. Cache
    cache_service.set_signals(session_id, signals)

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
