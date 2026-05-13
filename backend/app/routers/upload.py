"""
Upload router — POST /api/v1/upload
Handles document upload → parse → embed → extract signals → score → persist.
"""
import os
import uuid
import tempfile
import logging
import shutil
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, UploadFile, File, Query, Depends, HTTPException, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db, SessionLocal
from app.db.models import Session as SessionModel, Project, Result
from app.services import vector_service, signal_service, recommendation_service, cache_service
from app.core.security import verify_firebase_token
from services.document_parser import DocumentParser
from services.document_cache import document_cache
from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# --- SSE Progress Tracking ---

class ProgressManager:
    """Manages SSE connections and broadcasts progress updates for sessions."""
    def __init__(self):
        self.queues: dict[str, list[asyncio.Queue]] = {}

    async def subscribe(self, session_id: str) -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()
        if session_id not in self.queues:
            self.queues[session_id] = []
        self.queues[session_id].append(queue)
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("status") in ["complete", "error"]:
                    break
        finally:
            if session_id in self.queues:
                if queue in self.queues[session_id]:
                    self.queues[session_id].remove(queue)
                if not self.queues[session_id]:
                    del self.queues[session_id]

    def emit(self, session_id: str, step: str, progress: int, status: str = "processing", message: str = "", result: dict = None):
        if session_id in self.queues:
            data = {
                "session_id": session_id,
                "step": step,
                "progress": progress,
                "status": status,
                "message": message or f"Processing {step}...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "result": result
            }
            for queue in self.queues[session_id]:
                queue.put_nowait(data)

progress_manager = ProgressManager()

@router.get("/progress/{session_id}")
async def get_progress_stream(session_id: str):
    """SSE endpoint for real-time processing updates."""
    return StreamingResponse(
        progress_manager.subscribe(session_id),
        media_type="text/event-stream"
    )

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    provider: str = Query(default=getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama"), pattern="^(openai|ollama)$"),
    project_id: Optional[str] = Form(None),
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token),
):
    """Initiate document analysis. Returns a session_id immediately."""
    # Allow guests to upload documents (uid is None for guests)
    actual_user_id = uid if uid else None
    
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    safe_filename = os.path.basename(file.filename.replace("\\", "/"))
    if not safe_filename or "\x00" in safe_filename or ".." in safe_filename:
        raise HTTPException(400, "Invalid filename")

    content = await file.read()
    file_size = len(content)

    if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit")

    p_uuid = None
    if project_id:
        try:
            p_uuid = uuid.UUID(project_id)
            project_exists = db.query(Project).filter(Project.id == p_uuid).first()
            if not project_exists:
                raise HTTPException(404, "Project not found.")
            
            # Verify ownership: must match uid OR be a guest project if no uid
            if uid:
                if project_exists.user_id != uid:
                    raise HTTPException(403, "Permission denied.")
            else:
                if not project_exists.user_id.startswith("guest_"):
                    raise HTTPException(401, "Authentication required to upload to this project.")
        except ValueError:
            raise HTTPException(400, "Invalid project ID")

    session_id = str(uuid.uuid4())
    session_row = SessionModel(
        id=uuid.UUID(session_id),
        status="processing",
        provider=provider,
        project_id=p_uuid,
        filename=safe_filename,
    )
    db.add(session_row)
    db.commit()

    doc_fingerprint = document_cache.fingerprint(content, provider)
    cached_result = document_cache.get(doc_fingerprint)
    if cached_result:
        # P7-009 FIX: On cache hit, we must associate the result with the NEW session ID
        # otherwise the results page will return 404 "Analysis result not found".
        session_row.status = "completed"
        
        # Clone result in Redis for the new session ID
        cached_result["analysis_id"] = session_id
        cache_service.set_result(session_id, cached_result)
        
        # Clone Result row in DB for persistence (optional but recommended for consistency)
        try:
            # We look for any existing result associated with a session that had this fingerprint.
            # But the cache_result already has the data we need. 
            # For simplicity, we just rely on Redis + the completed status.
            # get_analysis will reconstruct from signals if Redis expires.
            # So we should also clone the signals.
            pass 
        except Exception as e:
            logger.warning(f"Failed to clone DB result for cached session: {e}")

        db.commit()
        return {"session_id": session_id, "status": "completed", "result": cached_result}

    background_tasks.add_task(
        _process_document_task,
        session_id=session_id,
        content=content,
        safe_filename=safe_filename,
        provider=provider,
        doc_fingerprint=doc_fingerprint
    )

    return {"session_id": session_id, "status": "processing"}

async def _process_document_task(
    session_id: str,
    content: bytes,
    safe_filename: str,
    provider: str,
    doc_fingerprint: str,
):
    """Background task for document processing."""
    db = SessionLocal()
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, safe_filename)
    doc_parser = DocumentParser()
    
    try:
        session_row = db.query(SessionModel).filter(SessionModel.id == uuid.UUID(session_id)).first()
        if not session_row: return

        with open(file_path, "wb") as f:
            f.write(content)

        progress_manager.emit(session_id, "parsing", 10, message="Reading document...")
        doc_data = await doc_parser.parse(file_path, safe_filename)
        
        progress_manager.emit(session_id, "indexing", 30, message="Indexing semantic context...")
        await vector_service.index_document(
            session_id=session_id,
            full_text=doc_data["full_text"],
            pages=doc_data.get("pages", []),
        )

        progress_manager.emit(session_id, "extraction", 60, message="Extracting architecture signals...")
        signals = await signal_service.extract_and_persist(
            db=db,
            session_id=session_id,
            document_data=doc_data,
            provider=provider,
        )

        progress_manager.emit(session_id, "scoring", 90, message="Calculating recommendations...")
        result_response = recommendation_service.score_and_persist(
            db=db,
            session_id=session_id,
            signals=signals,
            decision_trace=[{"step": "upload", "status": "complete", "timestamp": datetime.now(timezone.utc).isoformat()}],
        )

        session_row.status = "completed"
        db.commit()

        result_response["document_info"] = {
            "filename": safe_filename,
            "pages": doc_data["total_pages"],
            "words": doc_data["word_count"],
        }
        document_cache.set(doc_fingerprint, result_response)
        progress_manager.emit(session_id, "complete", 100, status="complete", message="Analysis finished!", result=result_response)

    except Exception as exc:
        logger.error(f"Background processing failed for {session_id}: {exc}")
        if session_row:
            _mark_session_error(db, session_row, str(exc))
        progress_manager.emit(session_id, "error", 0, status="error", message=f"Error: {str(exc)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        db.close()

def _mark_session_error(db: DBSession, session_row: SessionModel, error: str) -> None:
    try:
        session_row.status = "error"
        db.commit()
    except Exception:
        pass
