"""
Upload router — POST /api/v1/upload
Handles document upload → parse → embed → extract signals → score → persist.
"""
import os
import uuid
import tempfile
import logging
import shutil
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Query, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Session as SessionModel
from app.services import vector_service, signal_service, recommendation_service
from app.schemas.session import AnalysisResponse
from app.core.security import verify_firebase_token
from services.document_parser import DocumentParser, detect_sections
from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)
doc_parser = DocumentParser()


@router.post("/upload", response_model=AnalysisResponse)
async def upload_document(
    file: UploadFile = File(...),
    provider: str = Query(default=getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama"), regex="^(openai|ollama)$"),
    project_id: str | None = Query(default=None),
    db: DBSession = Depends(get_db),
    uid: str = Depends(verify_firebase_token),
):
    """Upload a document for architecture analysis."""

    # --- Validate ---
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    # SEC-3.1 FIX: Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(file.filename.replace("\\", "/"))
    if not safe_filename or "\x00" in safe_filename or ".." in safe_filename:
        raise HTTPException(400, "Invalid filename")

    content = await file.read()
    file_size = len(content)

    valid, msg = doc_parser.validate_file(safe_filename, file_size)
    if not valid:
        raise HTTPException(400, msg)

    if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit")

    p_uuid = None
    if project_id:
        try:
            p_uuid = uuid.UUID(project_id)
            from app.db.models import Project
            project_exists = db.query(Project).filter(Project.id == p_uuid).first()
            if not project_exists:
                raise HTTPException(404, "Project not found. It may have been deleted.")
            # SEC-002 FIX: Ensure the user owns the project they are uploading to
            if project_exists.user_id != uid:
                raise HTTPException(403, "You do not have permission to upload to this project.")
        except ValueError:
            pass

    # --- Create Session row ---
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

    trace: list[dict] = [
        {"step": "upload", "status": "complete", "timestamp": datetime.utcnow().isoformat()}
    ]

    # --- Save to temp file ---
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, safe_filename)
    try:
        with open(file_path, "wb") as f:
            f.write(content)

        # Stage 1: Parse
        trace.append({"step": "parse", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        doc_data = await doc_parser.parse(file_path, safe_filename)
        trace[-1]["status"] = "complete"
        trace[-1]["details"] = f"Extracted {doc_data['word_count']} words from {doc_data['total_pages']} pages"

        if doc_data["word_count"] < 10:
            _mark_session_error(db, session_row, "Document is empty or contains too little text.")
            raise HTTPException(422, "Document is empty or contains too little text.")

        # Stage 2: Section detection (unchanged)
        trace.append({"step": "section_detection", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        sections = detect_sections(doc_data["full_text"])
        detected_count = sum(1 for v in sections.values() if v)
        trace[-1]["status"] = "complete"
        trace[-1]["details"] = f"Detected {detected_count} document sections"

        # Stage 3: FAISS indexing
        trace.append({"step": "vector_indexing", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        try:
            num_chunks = await vector_service.index_document(
                session_id=session_id,
                full_text=doc_data["full_text"],
                pages=doc_data.get("pages", []),
            )
            trace[-1]["status"] = "complete"
            trace[-1]["details"] = f"Indexed {num_chunks} text chunks"
        except Exception as exc:
            logger.warning(f"Vector indexing failed (non-fatal): {exc}")
            trace[-1]["status"] = "skipped"
            trace[-1]["details"] = str(exc)

        # Stage 4: Signal extraction (DB + Redis)
        trace.append({"step": "signal_extraction", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        signals = await signal_service.extract_and_persist(
            db=db,
            session_id=session_id,
            document_data=doc_data,
            provider=provider,
        )
        extracted_count = sum(1 for s in signals.values() if s.get("value"))
        missing_count = sum(1 for s in signals.values() if not s.get("value"))
        trace[-1]["status"] = "complete"
        trace[-1]["details"] = f"Extracted {extracted_count}/10 signals"

        # Stage 4b: Report missing signals
        if missing_count > 0:
            missing_names = [k.replace("_", " ") for k, s in signals.items() if not s.get("value")]
            trace.append({
                "step": "missing_signals",
                "status": "complete",
                "timestamp": datetime.utcnow().isoformat(),
                "details": f"{missing_count} signals missing: {', '.join(missing_names)}",
            })

        # Stage 5: Sensitivity analysis is embedded inside scoring
        trace.append({"step": "scoring", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        trace.append({"step": "recommend", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

        # Stage 6: Score + persist Result
        result_response = recommendation_service.score_and_persist(
            db=db,
            session_id=session_id,
            signals=signals,
            decision_trace=trace,
        )
        trace[-2]["status"] = "complete"

        # Mark session complete
        session_row.status = "completed"
        db.commit()

        # Attach document info
        result_response["document_info"] = {
            "filename": safe_filename,
            "pages": doc_data["total_pages"],
            "words": doc_data["word_count"],
        }
        return result_response

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Document processing failed: {exc}")
        _mark_session_error(db, session_row, str(exc))
        if "Failed to parse" in str(exc) or "Unsupported" in str(exc):
            raise HTTPException(422, f"Invalid or unreadable document: {str(exc)}")
        raise HTTPException(500, f"Processing failed: {str(exc)}")
    finally:
        # SEC-3.9 FIX: use shutil.rmtree to ensure complete cleanup even if parser created subfiles
        shutil.rmtree(temp_dir, ignore_errors=True)


def _mark_session_error(db: DBSession, session_row: SessionModel, error: str) -> None:
    try:
        session_row.status = "error"
        db.commit()
    except Exception:
        pass
