"""
Analysis router — GET /api/v1/analysis/{id}, POST /followup, GET /export/{id},
GET /architectures, GET /questionnaire/options
"""
import logging
import uuid

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Session as SessionModel
from app.services import signal_service, recommendation_service, cache_service
from app.services.pdf_report import generate_pdf
from app.schemas.session import AnalysisResponse, FollowUpAnswers
from services.scoring_engine import ARCHITECTURE_DESCRIPTIONS
from services.signal_extractor import SIGNAL_SCHEMA
from services.followup_generator import SIGNAL_OPTIONS

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GET /api/v1/analysis/{session_id}
# ---------------------------------------------------------------------------
@router.get("/analysis/{session_id}", response_model=AnalysisResponse)
def get_analysis(session_id: str, db: DBSession = Depends(get_db)):
    """Get analysis status and results."""
    # First check Redis
    cached = cache_service.get_result(session_id)
    if cached:
        return cached

    # Check if session exists at all
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(404, "Analysis not found")

    session_row = db.query(SessionModel).filter(SessionModel.id == session_uuid).first()
    if not session_row:
        raise HTTPException(404, "Analysis not found")

    # Session exists but may still be processing
    if session_row.status in ("draft", "processing"):
        return {"analysis_id": session_id, "status": session_row.status}

    if session_row.status == "error":
        return {"analysis_id": session_id, "status": "error"}

    # Load signals + result from DB
    signals = signal_service.get_signals(db, session_id)
    result = recommendation_service.get_result(db, session_id, signals)
    if not result:
        raise HTTPException(404, "Analysis result not found")
    return result


# ---------------------------------------------------------------------------
# POST /api/v1/followup
# ---------------------------------------------------------------------------
@router.post("/followup", response_model=AnalysisResponse)
def submit_followup(data: FollowUpAnswers, db: DBSession = Depends(get_db)):
    """Submit follow-up answers and re-score."""
    try:
        uuid.UUID(data.analysis_id)
    except ValueError:
        raise HTTPException(404, "Analysis not found")

    session_row = db.query(SessionModel).filter(
        SessionModel.id == uuid.UUID(data.analysis_id)
    ).first()
    if not session_row:
        raise HTTPException(404, "Analysis not found")

    # Update signals in DB
    updated_signals = signal_service.update_signals(db, data.analysis_id, data.answers)

    # Re-score and overwrite result
    result = recommendation_service.score_and_persist(
        db=db,
        session_id=data.analysis_id,
        signals=updated_signals,
    )
    return result


# ---------------------------------------------------------------------------
# GET /api/v1/export/{session_id}
# ---------------------------------------------------------------------------
@router.get("/export/{session_id}")
def export_analysis(session_id: str, db: DBSession = Depends(get_db)):
    """Export analysis results as a PDF attachment."""
    result = None
    cached = cache_service.get_result(session_id)
    if cached:
        result = cached
    else:
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(404, "Analysis not found")
        signals = signal_service.get_signals(db, session_id)
        result = recommendation_service.get_result(db, session_id, signals)

    if not result:
        raise HTTPException(404, "Analysis not found")

    pdf_bytes = generate_pdf(result)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ArchGuide_Report_{session_id}.pdf",
        },
    )


# ---------------------------------------------------------------------------
# Static endpoints
# ---------------------------------------------------------------------------
@router.get("/architectures")
def get_architectures():
    return {"architectures": ARCHITECTURE_DESCRIPTIONS}


@router.get("/questionnaire/options")
def get_questionnaire_options():
    return {
        "signals": {
            key: {
                "description": schema["description"],
                "options": SIGNAL_OPTIONS.get(key, []),
                "required": key in [
                    "dataset_size", "data_volatility", "accuracy_requirement",
                    "latency_requirement", "domain_specificity",
                ],
            }
            for key, schema in SIGNAL_SCHEMA.items()
        }
    }
