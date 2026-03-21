"""
AI Architecture Decision Platform - Main FastAPI Application
"""
import os
import sys
import uuid
import json
import logging
import tempfile
import shutil
from datetime import datetime
from typing import Optional, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from services.document_parser import DocumentParser, detect_sections
from services.llm_client import LLMClient, get_llm_client
from services.signal_extractor import SignalExtractor, SIGNAL_SCHEMA
from services.scoring_engine import ScoringEngine, ARCHITECTURE_DESCRIPTIONS
from services.followup_generator import generate_followup_questions, SIGNAL_OPTIONS

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- App ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In memory store (replace with Redis/DB in production) ---
analysis_store: dict[str, dict] = {}

# --- Pydantic Models ---

class QuestionnaireInput(BaseModel):
    dataset_size: Optional[str] = None
    query_volume: Optional[str] = None
    latency_requirement: Optional[str] = None
    data_volatility: Optional[str] = None
    accuracy_requirement: Optional[str] = None
    domain_specificity: Optional[str] = None
    security_level: Optional[str] = None
    cost_sensitivity: Optional[str] = None
    deployment_preference: Optional[str] = None
    user_scale: Optional[str] = None

class FollowUpAnswers(BaseModel):
    analysis_id: str
    answers: dict[str, str]

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    signals: Optional[dict] = None
    scores: Optional[dict] = None
    recommended: Optional[str] = None
    confidence: Optional[float] = None
    ranking: Optional[list] = None
    suitability: Optional[dict] = None
    factor_breakdown: Optional[dict] = None
    why_not: Optional[dict] = None
    architecture_details: Optional[dict] = None
    followup_questions: Optional[list] = None
    sensitivity: Optional[dict] = None
    decision_trace: Optional[list] = None
    created_at: Optional[str] = None

class ProviderSwitch(BaseModel):
    provider: str = Field(..., pattern="^(openai|ollama)$")


# --- Singletons ---
doc_parser = DocumentParser()
scoring_engine = ScoringEngine()


# --- Background processing ---
async def process_document_task(
    analysis_id: str,
    file_path: str,
    filename: str,
    provider: str,
):
    """Background task to process uploaded document."""
    trace: list[dict] = []
    try:
        # Stage 1: Parse
        trace.append({"step": "upload", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

        analysis_store[analysis_id]["status"] = "parsing"
        trace.append({"step": "parse", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        doc_data = await doc_parser.parse(file_path, filename)
        trace[-1]["status"] = "complete"
        trace[-1]["details"] = f"Extracted {doc_data['word_count']} words from {doc_data['total_pages']} pages"

        if doc_data["word_count"] < 10:
            analysis_store[analysis_id]["status"] = "error"
            analysis_store[analysis_id]["error"] = "Document is empty or contains too little text."
            return

        # Stage 2: Section Detection
        analysis_store[analysis_id]["status"] = "detecting_sections"
        trace.append({"step": "section_detection", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        sections = detect_sections(doc_data["full_text"])
        detected_count = sum(1 for v in sections.values() if v)
        trace[-1]["status"] = "complete"
        trace[-1]["details"] = f"Detected {detected_count} document sections"

        # Stage 3: Signal Extraction
        analysis_store[analysis_id]["status"] = "extracting_signals"
        trace.append({"step": "signal_extraction", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        llm = get_llm_client(provider)
        extractor = SignalExtractor(llm)
        signals = await extractor.extract_signals(doc_data)
        trace[-1]["status"] = "complete"

        extracted_count = sum(1 for s in signals.values() if s.get("value"))
        trace[-1]["details"] = f"Extracted {extracted_count}/{len(SIGNAL_SCHEMA)} signals"

        # Stage 4: Validation
        analysis_store[analysis_id]["status"] = "validating"
        trace.append({"step": "validation", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        # Anti-hallucination: check all confidences
        for key, sig in signals.items():
            if sig.get("confidence", 0) < 0.1:
                sig["value"] = None
        trace[-1]["status"] = "complete"

        # Stage 5: Scoring
        analysis_store[analysis_id]["status"] = "scoring"
        trace.append({"step": "scoring", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        result = scoring_engine.score(signals)
        trace[-1]["status"] = "complete"

        # Stage 6: Follow-up check
        followups = generate_followup_questions(signals, doc_data.get("full_text", ""))

        # Stage 7: Sensitivity
        trace.append({"step": "sensitivity_analysis", "status": "in_progress", "timestamp": datetime.utcnow().isoformat()})
        sensitivity = scoring_engine.sensitivity_analysis(signals)
        trace[-1]["status"] = "complete"

        trace.append({"step": "recommend", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

        # Store results
        analysis_store[analysis_id].update({
            "status": "complete",
            "signals": signals,
            "scores": result["scores"],
            "recommended": result["recommended"],
            "confidence": result["confidence"],
            "ranking": result["ranking"],
            "suitability": result["suitability"],
            "factor_breakdown": result["factor_breakdown"],
            "why_not": result["why_not"],
            "architecture_details": result["architecture_details"],
            "followup_questions": followups,
            "sensitivity": sensitivity,
            "decision_trace": trace,
            "document_info": {
                "filename": filename,
                "pages": doc_data["total_pages"],
                "words": doc_data["word_count"],
            },
        })

    except Exception as e:
        logger.error(f"Document processing failed for {analysis_id}: {e}")
        analysis_store[analysis_id]["status"] = "error"
        analysis_store[analysis_id]["error"] = str(e)
        trace.append({"step": "error", "status": "failed", "details": str(e), "timestamp": datetime.utcnow().isoformat()})
        analysis_store[analysis_id]["decision_trace"] = trace
    finally:
        # Cleanup temp file
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass


# === API ROUTES ===

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.post("/api/v1/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    provider: str = Query(default="ollama", regex="^(openai|ollama)$"),
):
    """Upload a document for analysis."""
    # Validate file
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    valid, msg = doc_parser.validate_file(file.filename, file.size or 0)
    if not valid:
        raise HTTPException(400, msg)

    # Save to temp file
    analysis_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)

    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(400, f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit")
            f.write(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to save file: {str(e)}")

    # Initialize analysis record
    analysis_store[analysis_id] = {
        "analysis_id": analysis_id,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat(),
        "provider": provider,
        "filename": file.filename,
    }

    # Start background processing
    background_tasks.add_task(
        process_document_task,
        analysis_id,
        file_path,
        file.filename,
        provider,
    )

    return {"analysis_id": analysis_id, "status": "queued", "message": "Document uploaded. Processing started."}


@app.post("/api/v1/questionnaire")
async def submit_questionnaire(
    input_data: QuestionnaireInput,
    provider: str = Query(default="ollama", regex="^(openai|ollama)$"),
):
    """Process questionnaire input and return architecture recommendation."""
    analysis_id = str(uuid.uuid4())
    trace: list[dict] = []
    trace.append({"step": "questionnaire_input", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

    # Convert to signals
    answers = input_data.model_dump()
    extractor = SignalExtractor(get_llm_client(provider))
    signals = extractor.extract_from_questionnaire(answers)
    trace.append({"step": "signal_extraction", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

    # Validate
    trace.append({"step": "validation", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

    # Score
    result = scoring_engine.score(signals)
    trace.append({"step": "scoring", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

    # Follow-ups
    followups = generate_followup_questions(signals)

    # Sensitivity
    sensitivity = scoring_engine.sensitivity_analysis(signals)
    trace.append({"step": "sensitivity_analysis", "status": "complete", "timestamp": datetime.utcnow().isoformat()})
    trace.append({"step": "recommend", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

    response_data = {
        "analysis_id": analysis_id,
        "status": "complete",
        "signals": signals,
        "scores": result["scores"],
        "recommended": result["recommended"],
        "confidence": result["confidence"],
        "ranking": result["ranking"],
        "suitability": result["suitability"],
        "factor_breakdown": result["factor_breakdown"],
        "why_not": result["why_not"],
        "architecture_details": result["architecture_details"],
        "followup_questions": followups,
        "sensitivity": sensitivity,
        "decision_trace": trace,
        "created_at": datetime.utcnow().isoformat(),
    }

    analysis_store[analysis_id] = response_data
    return response_data


@app.get("/api/v1/analysis/{analysis_id}")
async def get_analysis(analysis_id: str):
    """Get analysis status and results."""
    if analysis_id not in analysis_store:
        raise HTTPException(404, "Analysis not found")
    return analysis_store[analysis_id]


@app.post("/api/v1/followup")
async def submit_followup(data: FollowUpAnswers):
    """Submit follow-up answers and re-score."""
    if data.analysis_id not in analysis_store:
        raise HTTPException(404, "Analysis not found")

    analysis = analysis_store[data.analysis_id]
    signals = analysis.get("signals", {})

    # Update signals with follow-up answers
    for signal_name, value in data.answers.items():
        if signal_name in SIGNAL_SCHEMA:
            signals[signal_name] = {
                "value": value,
                "confidence": 1.0,
                "source_text": "Follow-up answer from user",
                "page_number": 0,
            }

    # Re-score
    result = scoring_engine.score(signals)
    sensitivity = scoring_engine.sensitivity_analysis(signals)
    followups = generate_followup_questions(signals)

    analysis.update({
        "signals": signals,
        "scores": result["scores"],
        "recommended": result["recommended"],
        "confidence": result["confidence"],
        "ranking": result["ranking"],
        "suitability": result["suitability"],
        "factor_breakdown": result["factor_breakdown"],
        "why_not": result["why_not"],
        "followup_questions": followups,
        "sensitivity": sensitivity,
    })

    return analysis


@app.get("/api/v1/export/{analysis_id}")
async def export_analysis(analysis_id: str):
    """Export analysis results as JSON."""
    if analysis_id not in analysis_store:
        raise HTTPException(404, "Analysis not found")

    analysis = analysis_store[analysis_id]
    return JSONResponse(
        content=analysis,
        headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.json"},
    )


@app.get("/api/v1/questionnaire/options")
async def get_questionnaire_options():
    """Get questionnaire structure with options for each signal."""
    return {
        "signals": {
            key: {
                "description": schema["description"],
                "options": SIGNAL_OPTIONS.get(key, []),
                "required": key in ["dataset_size", "data_volatility", "accuracy_requirement", "latency_requirement", "domain_specificity"],
            }
            for key, schema in SIGNAL_SCHEMA.items()
        }
    }


@app.get("/api/v1/architectures")
async def get_architectures():
    """Get architecture descriptions."""
    return {"architectures": ARCHITECTURE_DESCRIPTIONS}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
