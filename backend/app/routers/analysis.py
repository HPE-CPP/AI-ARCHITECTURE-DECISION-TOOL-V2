"""
Analysis router — GET /api/v1/analysis/{id}, POST /followup, GET /export/{id},
GET /architectures, GET /questionnaire/options
"""
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Session as SessionModel, Project
from app.services import signal_service, recommendation_service, cache_service
from app.core.security import verify_firebase_token
from app.limiter import limiter
from app.services.pdf_report import generate_pdf
from app.services.cost_analysis import generate_cost_analysis
from app.services.cost_report_pdf import generate_cost_pdf
from app.schemas.session import AnalysisResponse, FollowUpAnswers
from services.scoring_engine import ARCHITECTURE_DESCRIPTIONS
from services.signal_extractor import SIGNAL_SCHEMA
from services.followup_generator import SIGNAL_OPTIONS

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_project_info(session_row: SessionModel, db: DBSession) -> tuple[Optional[str], Optional[str]]:
    """Return (project_name, project_id) for a session's parent project."""
    if not session_row.project_id:
        return None, None
    project = db.query(Project).filter(Project.id == session_row.project_id).first()
    if project:
        return project.name, str(project.id)
    return None, str(session_row.project_id)


def _inject_project_info(result: dict, session_row: SessionModel, db: DBSession) -> None:
    """Add project_name and project_id to a result dict in-place."""
    name, pid = _get_project_info(session_row, db)
    result["project_name"] = name
    result["project_id"] = pid


def _check_session_ownership(
    session_row: SessionModel,
    uid: Optional[str],
    db: DBSession,
) -> None:
    """Raise 401/403 if the caller does not own this session.

    Rules:
    - Sessions with no project: accessible by anyone (questionnaire guest runs).
    - Sessions whose project is owned by a guest_ user: accessible by anyone.
    - Sessions whose project is owned by an authenticated user: require a
      matching Firebase JWT. Wrong token -> 403. No token -> 401.
    """
    if not session_row.project_id:
        return  # no project attached — allow through

    project = db.query(Project).filter(Project.id == session_row.project_id).first()
    if not project:
        return  # orphaned session — allow through

    owner = project.user_id or ""
    if owner.startswith("guest_"):
        return  # guest project — allow through

    # Authenticated user's project — enforce ownership
    if not uid:
        raise HTTPException(401, "Authentication required to view this analysis")
    if uid != owner:
        raise HTTPException(403, "You do not have permission to view this analysis")


# ---------------------------------------------------------------------------
# SEC-007 FIX: Typed export request schema
# Previously `result: dict` accepted any JSON body of any size/depth, enabling
# DoS via 100 MB payloads or deeply-nested structures that exhaust ReportLab.
# This schema enforces field presence and string length limits at the HTTP layer.
# ---------------------------------------------------------------------------
class ExportRequest(BaseModel):
    """Validated body for PDF export endpoints.

    Mirrors AnalysisResponse so the frontend can POST the full result object
    it already holds. All string fields carry a max_length guard to prevent
    memory exhaustion in the PDF renderer.
    """
    analysis_id: Optional[str] = Field(default=None, max_length=64)
    status: Optional[str] = Field(default=None, max_length=32)
    recommended: Optional[str] = Field(default=None, max_length=100)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Scores, ranking, and breakdown — sent as flat dicts by the frontend
    scores: Optional[dict[str, Any]] = None
    ranking: Optional[list[str]] = Field(default=None, max_length=20)
    suitability: Optional[dict[str, Any]] = None
    factor_breakdown: Optional[dict[str, Any]] = None
    why_not: Optional[dict[str, Any]] = None
    architecture_details: Optional[dict[str, Any]] = None
    sensitivity: Optional[dict[str, Any]] = None
    # Signals and trace
    signals: Optional[dict[str, Any]] = None
    decision_trace: Optional[list[dict[str, Any]]] = Field(default=None, max_length=50)
    # Metadata
    followup_questions: Optional[list[Any]] = Field(default=None, max_length=20)
    document_info: Optional[dict[str, Any]] = None
    cost_analysis: Optional[dict[str, Any]] = None
    created_at: Optional[str] = Field(default=None, max_length=64)


# ---------------------------------------------------------------------------
# GET /api/v1/analysis/{session_id}
# ---------------------------------------------------------------------------
@router.get("/analysis/{session_id}", response_model=AnalysisResponse)
@limiter.limit("30/minute")  # polling loop — generous limit, blocks bots
def get_analysis(
    request: Request,
    session_id: str,
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token),
):
    """Get analysis status and results.

    SEC-008 FIX: Ownership is now verified before returning any data.
    The DB session lookup always runs first so we can check project ownership,
    even when the result is cached in Redis (cache does not store user_id).
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(404, "Analysis not found")

    # Always load the session row first — needed for ownership check
    session_row = db.query(SessionModel).filter(SessionModel.id == session_uuid).first()
    if not session_row:
        raise HTTPException(404, "Analysis not found")

    # Ownership gate — raises 401/403 for unauthorized callers
    _check_session_ownership(session_row, uid, db)

    # Ownership confirmed — now serve from Redis cache if available
    cached = cache_service.get_result(session_id)
    if cached:
        if cached.get("status") == "complete" and cached.get("recommended"):
            cached["cost_analysis"] = generate_cost_analysis(cached)
        _inject_project_info(cached, session_row, db)
        return cached

    # Session still processing or errored
    if session_row.status in ("draft", "processing"):
        trace = cache_service.get("decision_trace", session_id)
        resp = {
            "analysis_id": session_id,
            "status": session_row.status,
            "decision_trace": trace or [],
        }
        _inject_project_info(resp, session_row, db)
        return resp

    if session_row.status == "error":
        trace = cache_service.get("decision_trace", session_id)
        error_msg = None
        if trace:
            error_steps = [s for s in trace if s.get("status") in ("error", "rejected")]
            if error_steps:
                error_msg = error_steps[-1].get("details")
        return {
            "analysis_id": session_id,
            "status": "error",
            "error_message": error_msg or "Processing failed. Please try uploading your document again.",
        }

    # Load signals + result from DB
    signals = signal_service.get_signals(db, session_id)
    result = recommendation_service.get_result(db, session_id, signals)
    if not result:
        raise HTTPException(404, "Analysis result not found")

    if result.get("status") == "complete" and result.get("recommended"):
        result["cost_analysis"] = generate_cost_analysis(result)

    _inject_project_info(result, session_row, db)
    return result


# ---------------------------------------------------------------------------
# POST /api/v1/followup
# ---------------------------------------------------------------------------
@router.post("/followup", response_model=AnalysisResponse)
@limiter.limit("10/minute")
def submit_followup(
    request: Request,
    data: FollowUpAnswers,
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token),
):
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

    _check_session_ownership(session_row, uid, db)

    # Update signals in DB
    updated_signals = signal_service.update_signals(db, data.analysis_id, data.answers)

    # Re-score and overwrite result
    result = recommendation_service.score_and_persist(
        db=db,
        session_id=data.analysis_id,
        signals=updated_signals,
    )

    if result.get("status") != "complete":
        session_row.status = "error"
        db.commit()
        _inject_project_info(result, session_row, db)
        return result

    # Attach cost analysis
    if result.get("status") == "complete" and result.get("recommended"):
        result["cost_analysis"] = generate_cost_analysis(result)

    _inject_project_info(result, session_row, db)
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


# ---------------------------------------------------------------------------
# POST /api/v1/admin/cache/clear  — dev-only cache flush
# ---------------------------------------------------------------------------
@router.post("/admin/cache/clear")
def clear_extraction_cache():
    """Clear the in-memory and Redis extraction cache.

    Use after code changes to signal extraction so that previously cached
    results for the same document are re-computed with the new logic.
    Only intended for development use.
    """
    from config import settings
    if not getattr(settings, "DEBUG", False):
        raise HTTPException(403, "Cache clear is only available in DEBUG mode")
    from services.extraction_cache import extraction_cache
    extraction_cache.clear()
    logger.info("Extraction cache cleared via admin endpoint")
    return {"cleared": True, "message": "Extraction cache cleared successfully"}


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
                    "user_scale", "citation_requirement", "context_size",
                ],
            }
            for key, schema in SIGNAL_SCHEMA.items()
        }
    }
