"""
Upload router — POST /api/v1/upload
Handles document upload → parse → embed → extract signals → score → persist.
Uses BackgroundTasks so the endpoint returns immediately and processing
progress is streamed via the session's decision_trace in Redis.
"""
import asyncio
import os
import uuid
import tempfile
import logging
import shutil
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Query, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db, SessionLocal
from app.db.models import Session as SessionModel
from app.services import vector_service, signal_service, recommendation_service, cache_service
from app.core.security import verify_firebase_token
from services.document_parser import (
    DocumentParser, detect_sections, validate_document_relevance,
    build_user_facing_message, log_relevance_assessment
)
from services.signal_extractor import SIGNAL_SCHEMA
from services.llm_client import get_llm_client
from config import settings
from app.limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)
doc_parser = DocumentParser()


def _update_step(session_id: str, step: str, status: str, details: str | None = None) -> None:
    """Write a progress step to Redis so the frontend polling reads it in real time."""
    try:
        trace = cache_service.get("decision_trace", session_id) or []
        trace.append({
            "step": step,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **({"details": details} if details else {}),
        })
        cache_service.set("decision_trace", session_id, trace, ttl=3600)
    except Exception:
        pass


def _process_document_background(session_id: str, file_path: str, safe_filename: str, provider: str) -> None:
    """Run the full processing pipeline as a background task.

    Writes progress to Redis at each stage so the results page polling
    shows real-time steps instead of a fake progress bar.
    """
    print(f"\n>>>> [DIAG] _process_document_background ENTERED for session={session_id} file={safe_filename}\n", flush=True)
    db = SessionLocal()
    try:
        session_row = db.query(SessionModel).get(uuid.UUID(session_id))
        if not session_row:
            return

        # Stage 1: Parse
        _update_step(session_id, "parse", "in_progress")
        doc_data = asyncio.run(doc_parser.parse(file_path, safe_filename))
        _update_step(session_id, "parse", "complete",
                     details=f"Extracted {doc_data['word_count']} words from {doc_data['total_pages']} pages")

        if doc_data["word_count"] < 10:
            session_row.status = "error"
            db.commit()
            _update_step(session_id, "parse", "error", details="Document is empty or contains too little text.")
            return

        # Stage 2: Document relevance gate
        _update_step(session_id, "relevance_check", "in_progress")
        _llm_for_review = get_llm_client(provider)
        
        print(f">>>> [DIAG] About to call validate_document_relevance for session={session_id}", flush=True)
        assessment = asyncio.run(validate_document_relevance(
            doc_data["full_text"],
            doc_data["word_count"],
            SIGNAL_SCHEMA,
            _llm_for_review,
        ))
        print(f">>>> [DIAG] validate_document_relevance RETURNED: passed={assessment.passed} tier={assessment.risk_tier} for session={session_id}", flush=True)

        # 1. Developer log — full detail, file only, never reaches frontend
        log_relevance_assessment(session_id=session_id, filename=safe_filename, assessment=assessment)
        print(f">>>> [DIAG] log_relevance_assessment CALLED for session={session_id}", flush=True)

        # 2. User-facing decision trace — short, plain-English, this is what the frontend shows
        user_message = build_user_facing_message(assessment)
        
        if not assessment.passed:
            _update_step(session_id, "relevance_check", "rejected", details=user_message)
            session_row.status = "error"
            db.commit()
            return
            
        _update_step(session_id, "relevance_check", "complete", details=user_message)

        # Stage 3: Section detection
        _update_step(session_id, "section_detection", "in_progress")
        sections = detect_sections(doc_data["full_text"])
        detected_count = sum(1 for v in sections.values() if v)
        _update_step(session_id, "section_detection", "complete",
                     details=f"Detected {detected_count} document sections")

        # Stage 4: Vector indexing
        _update_step(session_id, "vector_indexing", "in_progress")
        try:
            num_chunks = asyncio.run(vector_service.index_document(
                session_id=session_id,
                full_text=doc_data["full_text"],
                pages=doc_data.get("pages", []),
            ))
            _update_step(session_id, "vector_indexing", "complete",
                         details=f"Indexed {num_chunks} text chunks")
        except Exception as exc:
            logger.warning(f"Vector indexing failed (non-fatal): {exc}")
            _update_step(session_id, "vector_indexing", "skipped",
                         details="Vector indexing unavailable — analysis will continue without semantic retrieval.")

        # Stage 5: Signal extraction
        _update_step(session_id, "signal_extraction", "in_progress")
        # Use run() for the async extraction
        signals = asyncio.run(signal_service.extract_and_persist(
            db=db, session_id=session_id, document_data=doc_data, provider=provider,
        ))
        extracted_count = sum(1 for s in signals.values() if s.get("value"))
        missing_count = sum(1 for s in signals.values() if not s.get("value"))

        if extracted_count == 0:
            _update_step(session_id, "signal_extraction", "error",
                         details="No architecture signals could be extracted from this document.")
            session_row.status = "error"
            db.commit()
            return

        _update_step(session_id, "signal_extraction", "complete",
                     details=f"Extracted {extracted_count}/{len(signals)} signals")

        # Confidence gate
        confident_signals = [
            s for s in signals.values()
            if s.get("value") and s.get("confidence", 0) >= 0.35
        ]
        if len(confident_signals) < 3:
            session_row.status = "error"
            db.commit()
            _update_step(session_id, "confidence_gate", "error",
                         details=f"Only {len(confident_signals)} signals with sufficient confidence (minimum 3 required).")
            return

        # Signal concentration warning
        total_pages = doc_data.get("total_pages", 1)
        if total_pages > 2:
            signal_pages = [
                s.get("page_number", 0) for s in signals.values()
                if s.get("value") and s.get("page_number", 0) > 0
            ]
            if signal_pages and len(set(signal_pages)) == 1:
                _update_step(session_id, "signal_concentration_warning", "warning",
                             details=f"All signals from a single page of {total_pages}")

        # Report missing signals
        if missing_count > 0:
            missing_names = [k.replace("_", " ") for k, s in signals.items() if not s.get("value")]
            _update_step(session_id, "missing_signals", "warning" if extracted_count > 0 else "error",
                         details=f"{missing_count} signals missing: {', '.join(missing_names)}")

        # Stage 6: Scoring
        _update_step(session_id, "scoring", "in_progress")
        trace = cache_service.get("decision_trace", session_id) or []
        result_response = recommendation_service.score_and_persist(
            db=db, session_id=session_id, signals=signals, decision_trace=trace,
        )

        if result_response.get("status") != "complete":
            _update_step(session_id, "scoring", "error", details=result_response.get("error_message"))
            _update_step(session_id, "validating", "skipped", details="Skipped because the document did not contain enough verified signals.")
            session_row.status = "error"
            db.commit()
            return

        _update_step(session_id, "scoring", "complete")

        # Stage 7: Validating — emitted so the live activity log reaches the
        # final stage shown by the progress pipeline.
        _update_step(session_id, "validating", "complete",
                     details="Verified scoring consistency and confidence levels")

        # Attach document info
        result_response["document_info"] = {
            "filename": safe_filename,
            "pages": doc_data["total_pages"],
            "words": doc_data["word_count"],
        }

        # Capture the COMPLETE trace (including the post-scoring steps above) so
        # the final result isn't truncated at the snapshot taken before scoring.
        result_response["decision_trace"] = (
            cache_service.get("decision_trace", session_id) or result_response.get("decision_trace")
        )

        # Mark complete
        session_row.status = "completed"
        db.commit()

        # Write full result to Redis (overwrites the decision_trace-only key)
        cache_service.set_result(session_id, result_response)

    except Exception as exc:
        logger.error(f"Background processing failed for session {session_id}: {exc}")
        _update_step(session_id, "processing", "error", details=str(exc))
        try:
            session_row = db.query(SessionModel).get(uuid.UUID(session_id))
            if session_row:
                session_row.status = "error"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
        cleanup_path = os.path.dirname(file_path) if file_path else None
        if cleanup_path and os.path.exists(cleanup_path):
            shutil.rmtree(cleanup_path, ignore_errors=True)


@router.post("/upload", status_code=202)
@limiter.limit("4/minute")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    provider: str = Query(default=getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama"), pattern="^(openai|ollama)$"),
    project_id: str | None = Query(default=None),
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token),
):
    """Upload a document — returns immediately (202) and processes in the background.

    Frontend should poll GET /api/v1/analysis/{session_id} for status and decision_trace.
    """
    # --- Validate ---
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    safe_filename = os.path.basename(file.filename.replace("\\", "/"))
    if not safe_filename or "\x00" in safe_filename or ".." in safe_filename:
        raise HTTPException(400, "Invalid filename")

    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise HTTPException(400, "File is empty — nothing to process")

    valid, msg = doc_parser.validate_file(safe_filename, file_size)
    if not valid:
        raise HTTPException(400, msg)

    # Minimum content check for plain text only.
    # PDF/DOCX are binary — decoding 50 MB of binary as UTF-8 is wasteful and
    # produces garbage "words". Real content checks happen during background parsing.
    ext = os.path.splitext(safe_filename)[1].lower()
    if ext == ".txt":
        text_preview = content.decode("utf-8", errors="replace").strip()
        if len(text_preview.split()) < 10:
            raise HTTPException(422, "Document is too short. Please upload a document with more content.")

    p_uuid = None
    if project_id:
        try:
            p_uuid = uuid.UUID(project_id)
            from app.db.models import Project
            project_exists = db.query(Project).filter(Project.id == p_uuid).first()
            if not project_exists:
                raise HTTPException(404, "Project not found. It may have been deleted.")
            if uid:
                if project_exists.user_id != uid:
                    raise HTTPException(403, "You do not have permission to upload to this project.")
            else:
                if not project_exists.user_id.startswith("guest_"):
                    raise HTTPException(401, "Authentication required to upload to this project.")
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

    # Save file to temp and start background processing
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, safe_filename)
    with open(file_path, "wb") as f:
        f.write(content)

    background_tasks.add_task(
        _process_document_background,
        session_id, file_path, safe_filename, provider,
    )

    return JSONResponse(
        status_code=202,
        content={"analysis_id": session_id, "status": "processing"},
    )


def _mark_session_error(db: DBSession, session_row: SessionModel, error: str) -> None:
    try:
        session_row.status = "error"
        db.commit()
    except Exception:
        pass
