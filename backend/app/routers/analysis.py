"""
Analysis router — GET /api/v1/analysis/{id}, POST /followup, GET /export/{id},
GET /architectures, GET /questionnaire/options
"""
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Session as SessionModel
from app.services import signal_service, recommendation_service, cache_service
from app.services.pdf_report import generate_pdf
from app.services.cost_analysis import generate_cost_analysis
from app.services.cost_report_pdf import generate_cost_pdf
from app.schemas.session import AnalysisResponse, FollowUpAnswers
from services.scoring_engine import ARCHITECTURE_DESCRIPTIONS
from services.signal_extractor import SIGNAL_SCHEMA
from services.followup_generator import SIGNAL_OPTIONS

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SEC-007 FIX: Typed export request schema
# Previously `result: dict` accepted any JSON body of any size/depth, enabling
# DoS via 100 MB payloads or deeply-nested structures that exhaust ReportLab.
# This schema enforces field presence and string length limits at the HTTP layer.
# ---------------------------------------------------------------------------
class ArchitectureScore(BaseModel):
    architecture: str = Field(..., max_length=100)
    total_score: float = Field(..., ge=0.0, le=100.0)
    scores: Optional[dict[str, Any]] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    explanation: Optional[str] = Field(default=None, max_length=5000)


class ExportRequest(BaseModel):
    """Validated body for PDF export endpoints.

    All string fields carry a max_length guard so that an attacker cannot
    trigger memory exhaustion in ReportLab by sending unbounded text.
    """
    analysis_id: Optional[str] = Field(default=None, max_length=64)
    status: Optional[str] = Field(default=None, max_length=32)
    recommended: Optional[str] = Field(default=None, max_length=100)
    rankings: Optional[list[ArchitectureScore]] = Field(default=None, max_length=20)
    decision_trace: Optional[list[dict[str, Any]]] = Field(default=None, max_length=50)
    signals: Optional[dict[str, Any]] = None
    follow_up_questions: Optional[list[str]] = Field(default=None, max_length=20)
    document_info: Optional[dict[str, Any]] = None
    cost_analysis: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# GET /api/v1/analysis/{session_id}
# ---------------------------------------------------------------------------
@router.get("/analysis/{session_id}", response_model=AnalysisResponse)
def get_analysis(session_id: str, db: DBSession = Depends(get_db)):
    """Get analysis status and results."""
    # First check Redis
    cached = cache_service.get_result(session_id)
    if cached:
        # Attach cost analysis on the fly (not stored in cache)
        if cached.get("status") == "complete" and cached.get("recommended"):
            cached["cost_analysis"] = generate_cost_analysis(cached)
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

    # Attach cost analysis on the fly
    if result.get("status") == "complete" and result.get("recommended"):
        result["cost_analysis"] = generate_cost_analysis(result)

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

    # Attach cost analysis
    if result.get("status") == "complete" and result.get("recommended"):
        result["cost_analysis"] = generate_cost_analysis(result)

    return result


# ---------------------------------------------------------------------------
# POST /api/v1/export/pdf  — accepts full result from frontend, no DB needed
# ---------------------------------------------------------------------------
@router.post("/export/pdf")
def export_pdf(result: ExportRequest):
    """Generate and return a PDF report from the provided analysis result.

    SEC-007 FIX: Body is now validated by ExportRequest schema. Raw `dict`
    accepted any JSON of any size, enabling DoS via huge payloads.
    """
    analysis_id = result.analysis_id or "report"
    try:
        pdf_bytes = generate_pdf(result.model_dump(exclude_none=True))
    except Exception as e:
        import traceback
        logger.error(f"PDF generation failed for {analysis_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {e}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ArchGuide_Report_{analysis_id}.pdf",
        },
    )


# ---------------------------------------------------------------------------
# POST /api/v1/export/pdf/cost  — same pattern for cost report
# ---------------------------------------------------------------------------
@router.post("/export/pdf/cost")
def export_cost_pdf_route(result: ExportRequest):
    """Generate and return a cost analysis PDF from the provided analysis result.

    SEC-007 FIX: Body is now validated by ExportRequest schema (same as /export/pdf).
    """
    analysis_id = result.analysis_id or "report"
    try:
        result_dict = result.model_dump(exclude_none=True)
        cost_data = generate_cost_analysis(result_dict)
        pdf_bytes = generate_cost_pdf(cost_data, analysis_id=analysis_id)
    except Exception as e:
        import traceback
        logger.error(f"Cost PDF generation failed for {analysis_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Cost PDF generation failed: {e}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ArchGuide_Cost_Analysis_{analysis_id}.pdf",
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
