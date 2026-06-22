"""
Questionnaire router — POST /api/v1/questionnaire
Converts user answers to signals, scores, persists, caches.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Depends, Request
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Session as SessionModel, Signal
from app.services import recommendation_service
from app.services import cache_service
from app.schemas.session import QuestionnaireInput, AnalysisResponse
from app.core.security import verify_firebase_token
from services.signal_extractor import SignalExtractor
from services.llm_client import get_llm_client
from config import settings
from app.limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/questionnaire", response_model=AnalysisResponse)
@limiter.limit("10/minute")
def submit_questionnaire(
    request: Request,
    input_data: QuestionnaireInput,
    provider: str = Query(default=getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama"), pattern="^(openai|ollama)$"),
    project_id: str | None = Query(default=None),
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token),
):
    """Process questionnaire input and return architecture recommendation."""
    session_id = str(uuid.uuid4())
    session_uuid = uuid.UUID(session_id)
    trace: list[dict] = []

    # Parse project ID safely
    p_uuid = None
    if project_id:
        try:
            p_uuid = uuid.UUID(project_id)
        except ValueError:
            pass

    # Create session row
    session_row = SessionModel(
        id=session_uuid,
        status="processing",
        provider=provider,
        project_id=p_uuid,
        filename=None,
    )
    db.add(session_row)
    db.commit()

    trace.append({"step": "questionnaire_input", "status": "complete", "timestamp": datetime.now(timezone.utc).isoformat()})

    # Convert answers to signals using existing extractor
    extractor = SignalExtractor(get_llm_client(provider))
    answers = input_data.model_dump()
    signals = extractor.extract_from_questionnaire(answers)

    extracted_count = sum(1 for s in signals.values() if s.get("value"))
    missing_count = sum(1 for s in signals.values() if not s.get("value"))

    trace.append({
        "step": "signal_extraction",
        "status": "complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": f"Extracted {extracted_count}/{len(signals)} signals",
    })

    if missing_count > 0:
        missing_names = [k.replace("_", " ") for k, s in signals.items() if not s.get("value")]
        trace.append({
            "step": "missing_signals",
            "status": "complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": f"{missing_count} signals missing: {', '.join(missing_names)}",
        })

    trace.append({"step": "validation", "status": "complete", "timestamp": datetime.now(timezone.utc).isoformat()})

    # Persist signals
    for signal_name, data in signals.items():
        db.add(Signal(
            session_id=session_uuid,
            signal_name=signal_name,
            value=data.get("value"),
            confidence=float(data.get("confidence", 0.0)),
            source_text=str(data.get("source_text", ""))[:2000],
            page_number=int(data.get("page_number", 0)),
        ))
    db.commit()

    trace.append({"step": "scoring", "status": "complete", "timestamp": datetime.now(timezone.utc).isoformat()})
    trace.append({"step": "sensitivity_analysis", "status": "complete", "timestamp": datetime.now(timezone.utc).isoformat()})
    trace.append({"step": "recommend", "status": "complete", "timestamp": datetime.now(timezone.utc).isoformat()})

    # Score + persist result
    result = recommendation_service.score_and_persist(
        db=db,
        session_id=session_id,
        signals=signals,
        decision_trace=trace,
    )

    if result.get("status") != "complete":
        cache_service.set("decision_trace", session_id, result.get("decision_trace", trace), ttl=3600)
        session_row.status = "error"
        db.commit()
        return result

    # Mark session complete
    session_row.status = "completed"
    db.commit()

    return result
