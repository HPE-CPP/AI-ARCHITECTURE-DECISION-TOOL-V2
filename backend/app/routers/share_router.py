"""
GET /api/v1/share/{session_id}
 
Public read-only endpoint — no auth required.
Returns the same analysis result as GET /api/v1/analysis/{id}
but skips all ownership checks so anyone with the link can view it.
 
Only works for COMPLETED analyses — processing/error states return 404
so half-baked results are never exposed publicly.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session as DBSession
 
from app.db.session import get_db
from app.db.models import Session as SessionModel
from app.services import signal_service, recommendation_service, cache_service
from app.services.cost_analysis import generate_cost_analysis
import uuid
 
router = APIRouter()
 
 
@router.get("/share/{session_id}")
def get_shared_analysis(session_id: str, db: DBSession = Depends(get_db)):
    """
    Public read-only analysis result.
    No auth, no ownership check — just fetch and return.
    Only completed analyses are served; everything else returns 404.
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(404, "Analysis not found")
 
    session_row = db.query(SessionModel).filter(
        SessionModel.id == session_uuid
    ).first()
 
    if not session_row:
        raise HTTPException(404, "Analysis not found")
 
    # Only expose completed analyses publicly
    # Only expose completed analyses publicly
    if session_row.status not in ("complete", "completed"):
        raise HTTPException(404, "Analysis not available for sharing")
 
    # Try Redis cache first
    cached = cache_service.get_result(session_id)
    if cached:
        if cached.get("status") == "complete" and cached.get("recommended"):
            cached["cost_analysis"] = generate_cost_analysis(cached)
        return cached
 
    # Load from DB
    signals = signal_service.get_signals(db, session_id)
    result = recommendation_service.get_result(db, session_id, signals)
    if not result:
        raise HTTPException(404, "Analysis result not found")
 
    if result.get("status") == "complete" and result.get("recommended"):
        result["cost_analysis"] = generate_cost_analysis(result)
 
    return result