"""
Upload router — POST /api/v1/upload
Handles document upload → parse → embed → extract signals → score → persist.
"""
import os
import uuid
import tempfile
import logging
import shutil
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Query, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Session as SessionModel
from app.services import vector_service, signal_service, recommendation_service
from app.schemas.session import AnalysisResponse
from app.core.security import verify_firebase_token
from services.document_parser import DocumentParser, detect_sections, validate_document_relevance
from config import settings
from app.limiter import limiter

router = APIRouter()
logger = logging.getLogger(__name__)
doc_parser = DocumentParser()


@router.post("/upload", response_model=AnalysisResponse)
@limiter.limit("4/minute")  # 1 upload every 15 s — unlimited total, just not rapid-fire
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    provider: str = Query(default=getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama"), pattern="^(openai|ollama)$"),
    project_id: str | None = Query(default=None),
    db: DBSession = Depends(get_db),
    uid: Optional[str] = Depends(verify_firebase_token),
):
    """Upload a document for architecture analysis.

    Guest uploads are allowed: if no Firebase token is provided, the session
    is created without a project owner and remains accessible to anyone with
    the analysis_id (matching the questionnaire guest-run behaviour).
    """
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

    p_uuid = None
    if project_id:
        try:
            p_uuid = uuid.UUID(project_id)
            from app.db.models import Project
            project_exists = db.query(Project).filter(Project.id == p_uuid).first()
            if not project_exists:
                raise HTTPException(404, "Project not found. It may have been deleted.")
            # SEC-002 FIX: Ensure the user owns the project they are uploading to
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

    trace: list[dict] = [
        {"step": "upload", "status": "complete", "timestamp": datetime.now(timezone.utc).isoformat()}
    ]

    # --- Save to temp file ---
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, safe_filename)
    try:
        with open(file_path, "wb") as f:
            f.write(content)

        # Stage 1: Parse
        trace.append({"step": "parse", "status": "in_progress", "timestamp": datetime.now(timezone.utc).isoformat()})
        doc_data = await doc_parser.parse(file_path, safe_filename)
        trace[-1]["status"] = "complete"
        trace[-1]["details"] = f"Extracted {doc_data['word_count']} words from {doc_data['total_pages']} pages"

        if doc_data["word_count"] < 10:
            _mark_session_error(db, session_row, "Document is empty or contains too little text.")
            raise HTTPException(422, "Document is empty or contains too little text.")

        # Stage 1b: Document relevance gate
        # Rejects random PDFs (cost reports, screenshots, invoices, etc.) before
        # spending LLM tokens on them.
        trace.append({"step": "relevance_check", "status": "in_progress", "timestamp": datetime.now(timezone.utc).isoformat()})
        is_relevant, issue_type, relevance_msg = validate_document_relevance(
            doc_data["full_text"], doc_data.get("pages", [])
        )
        if not is_relevant:
            trace[-1]["status"] = "rejected"
            trace[-1]["details"] = relevance_msg
            _mark_session_error(db, session_row, relevance_msg)
            raise HTTPException(422, relevance_msg)
        trace[-1]["status"] = "complete"
        trace[-1]["details"] = f"Document passes relevance check ({doc_data['word_count']} words)"

        # Stage 2: Section detection (unchanged)
        trace.append({"step": "section_detection", "status": "in_progress", "timestamp": datetime.now(timezone.utc).isoformat()})
        sections = detect_sections(doc_data["full_text"])
        detected_count = sum(1 for v in sections.values() if v)
        trace[-1]["status"] = "complete"
        trace[-1]["details"] = f"Detected {detected_count} document sections"

        # Stage 3: FAISS indexing
        trace.append({"step": "vector_indexing", "status": "in_progress", "timestamp": datetime.now(timezone.utc).isoformat()})
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
            trace[-1]["details"] = "Vector indexing unavailable — analysis will continue without semantic retrieval."

        # Stage 4: Signal extraction (DB + Redis)
        trace.append({"step": "signal_extraction", "status": "in_progress", "timestamp": datetime.now(timezone.utc).isoformat()})
        signals = await signal_service.extract_and_persist(
            db=db,
            session_id=session_id,
            document_data=doc_data,
            provider=provider,
        )
        extracted_count = sum(1 for s in signals.values() if s.get("value"))
        missing_count = sum(1 for s in signals.values() if not s.get("value"))

        if extracted_count == 0:
            trace[-1]["status"] = "error"
            trace[-1]["details"] = (
                "No architecture signals could be extracted from this document. "
                "Ensure the document contains requirements, specifications, or use-case descriptions."
            )
        else:
            trace[-1]["status"] = "complete"
            trace[-1]["details"] = f"Extracted {extracted_count}/10 signals"

        # Post-extraction quality gate ─────────────────────────────────────────
        # 1. Confidence gate: if fewer than 3 signals extracted with real
        #    confidence, the document almost certainly wasn't a requirements doc
        #    that slipped past the keyword gate (e.g. a glossary or FAQ page
        #    that happens to mention "data" and "users").
        confident_signals = [
            s for s in signals.values()
            if s.get("value") and s.get("confidence", 0) >= 0.35
        ]
        if len(confident_signals) < 3:
            _mark_session_error(
                db, session_row,
                "Insufficient signal confidence — document does not appear to be a requirements specification."
            )
            raise HTTPException(
                422,
                f"Only {len(confident_signals)} architecture signal(s) could be extracted with sufficient "
                f"confidence (minimum 3 required). This document may not be a system requirements or "
                f"specification document. Please upload a document describing an AI/software system's "
                f"requirements, data sources, scale, latency needs, and deployment constraints."
            )

        # 2. Signal concentration warning: if the document has multiple pages
        #    but all extracted signals point to a single page, the recommendation
        #    is based on one paragraph — flag this to the user.
        total_pages = doc_data.get("total_pages", 1)
        if total_pages > 2:
            signal_pages = [
                s.get("page_number", 0) for s in signals.values()
                if s.get("value") and s.get("page_number", 0) > 0
            ]
            if signal_pages:
                unique_pages = set(signal_pages)
                if len(unique_pages) == 1:
                    sole_page = next(iter(unique_pages))
                    trace.append({
                        "step": "signal_concentration_warning",
                        "status": "warning",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "details": (
                            f"All {extracted_count} signals were extracted from a single page "
                            f"(page {sole_page} of {total_pages}). "
                            f"The recommendation is based on limited context. "
                            f"Consider uploading a more detailed requirements document."
                        ),
                    })
                    logger.warning(
                        "Signal concentration: all signals from page %d of %d-page document (session %s)",
                        sole_page, total_pages, session_id,
                    )

        # Stage 4b: Report missing signals
        if missing_count > 0:
            missing_names = [k.replace("_", " ") for k, s in signals.items() if not s.get("value")]
            trace.append({
                "step": "missing_signals",
                "status": "warning" if extracted_count > 0 else "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": f"{missing_count} signals missing: {', '.join(missing_names)}",
            })

        # Stage 5: Sensitivity analysis is embedded inside scoring
        trace.append({"step": "scoring", "status": "in_progress", "timestamp": datetime.now(timezone.utc).isoformat()})
        trace.append({"step": "recommend", "status": "complete", "timestamp": datetime.now(timezone.utc).isoformat()})

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
        msg = str(exc)
        if "Unable to read" in msg or "Unsupported" in msg or "corrupt" in msg.lower():
            raise HTTPException(422, msg)
        raise HTTPException(500, "Document processing failed. Please try again or contact support.")
    finally:
        # SEC-3.9 FIX: use shutil.rmtree to ensure complete cleanup even if parser created subfiles
        shutil.rmtree(temp_dir, ignore_errors=True)


def _mark_session_error(db: DBSession, session_row: SessionModel, error: str) -> None:
    try:
        session_row.status = "error"
        db.commit()
    except Exception:
        pass
