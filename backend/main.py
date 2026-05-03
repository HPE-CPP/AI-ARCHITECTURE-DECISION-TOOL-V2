"""
ArchGuide Elite v5.0 — main.py
All 14 drawbacks fixed. Smart AI chat with web browsing.
Persistent SQLite storage. Runs without PostgreSQL/Redis.
"""
import os, uuid, json, logging, tempfile
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from config import settings
from services.document_parser import DocumentParser, detect_sections
from services.llm_client import LLMClient, get_llm_client
from services.signal_extractor import SignalExtractor, SIGNAL_SCHEMA
from services.scoring_engine import ScoringEngine, ARCHITECTURE_DESCRIPTIONS
from services.followup_generator import generate_followup_questions, SIGNAL_OPTIONS
from services.extraction_cache import extraction_cache
from services.smart_chat import generate_chat_response
from services.persistent_store import (
    upsert_user, save_analysis, get_analysis as db_get_analysis,
    get_user_analyses, add_chat_message, get_chat_history,
    clear_chat, log_activity, get_user_stats,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version="5.0.0", docs_url="/docs", redoc_url="/redoc")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

doc_parser = DocumentParser()
scoring_engine = ScoringEngine()
analysis_store: dict[str, dict] = {}  # fast in-memory cache; backed by SQLite
project_store: dict[str, dict] = {}
chat_sessions: dict[str, list[dict]] = {}  # per-session in-memory chat history


# ─────────────────────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────────────────────
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
    uid: Optional[str] = None

class FollowUpAnswers(BaseModel):
    analysis_id: str
    answers: dict[str, str]
    uid: Optional[str] = None

class ChatRequest(BaseModel):
    uid: str
    content: str
    analysis_id: Optional[str] = None
    session_id: Optional[str] = None

class UserSync(BaseModel):
    uid: str
    email: Optional[str] = None
    displayName: Optional[str] = None
    photoURL: Optional[str] = None

class ProjectCreate(BaseModel):
    user_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=60)
    description: Optional[str] = Field(default="", max_length=200)

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    analysis_id: Optional[str] = None
    mode: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "5.0.0", "cache_entries": extraction_cache.size,
            "fixes": "all 14 applied — smart chat, persistence, risk, explanation, hybrid"}


# ─────────────────────────────────────────────────────────────────────────────
# USER SYNC
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/v1/users/sync")
async def sync_user(payload: UserSync):
    upsert_user(payload.uid, payload.email or "", payload.displayName or "", payload.photoURL or "")
    log_activity(payload.uid, "login")
    return {"success": True}

@app.get("/api/v1/users/{uid}/stats")
async def user_stats(uid: str):
    return get_user_stats(uid)

@app.get("/api/v1/users/{uid}/analyses")
async def user_analyses(uid: str, limit: int = 50):
    return {"analyses": get_user_analyses(uid, limit)}


# ─────────────────────────────────────────────────────────────────────────────
# SMART AI CHAT (with web browsing)
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/v1/chat/message")
async def chat_message(req: ChatRequest):
    """Dynamic AI chat — thinks, learns from inputs, browses web for answers."""
    session_key = req.session_id or req.uid
    history = chat_sessions.get(session_key, [])

    # Get analysis context if provided
    analysis_ctx = None
    if req.analysis_id:
        analysis_ctx = analysis_store.get(req.analysis_id)
        if not analysis_ctx:
            stored = db_get_analysis(req.analysis_id)
            if stored: analysis_ctx = stored.get("result", {})

    # Get LLM client (optional — works without one via KB fallback)
    provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama")
    try:
        llm = get_llm_client(provider)
    except Exception:
        llm = None

    # Generate smart response (browses web + LLM + KB)
    result = await generate_chat_response(
        user_message=req.content,
        analysis_result=analysis_ctx,
        history=history,
        llm_client=llm,
        browse_web=True,
    )

    # Update in-memory history
    history.append({"role": "user", "content": req.content})
    history.append({"role": "assistant", "content": result["content"]})
    chat_sessions[session_key] = history[-20:]  # keep last 10 exchanges

    # Persist to SQLite
    add_chat_message(req.uid, "user", req.content, req.analysis_id or "")
    add_chat_message(req.uid, "assistant", result["content"], req.analysis_id or "", result.get("source", ""))

    return {
        "role": "assistant",
        "content": result["content"],
        "source": result.get("source", ""),
        "web_browsed": result.get("web_browsed", False),
        "topic": result.get("topic", "general"),
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/chat/{uid}/history")
async def get_chat(uid: str, limit: int = 50):
    return {"messages": get_chat_history(uid, limit)}

@app.delete("/api/v1/chat/{uid}/clear")
async def clear_chat_history(uid: str, session_id: Optional[str] = Query(default=None)):
    clear_chat(uid)
    key = session_id or uid
    chat_sessions.pop(key, None)
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────────────
# DOCUMENT PROCESSING (background task)
# ─────────────────────────────────────────────────────────────────────────────
async def process_document_task(analysis_id: str, file_path: str, filename: str, provider: str, uid: Optional[str] = None):
    trace: list[dict] = []
    def step(name, status, details=""):
        e = {"step": name, "status": status, "timestamp": datetime.utcnow().isoformat()}
        if details: e["details"] = details
        trace.append(e)

    try:
        step("upload", "complete", f"File: {filename}")
        analysis_store[analysis_id]["status"] = "parsing"
        step("parse", "in_progress")
        doc_data = await doc_parser.parse(file_path, filename)

        if doc_data["word_count"] < 10:
            analysis_store[analysis_id].update({"status": "error", "error": "Document too short."})
            return
        step("parse", "complete", f"{doc_data['word_count']} words / {doc_data['total_pages']} pages")

        analysis_store[analysis_id]["status"] = "detecting_sections"
        sections = detect_sections(doc_data["full_text"])
        step("section_detection", "complete", f"{sum(1 for v in sections.values() if v)} sections")

        analysis_store[analysis_id]["status"] = "extracting_signals"
        step("signal_extraction", "in_progress")
        llm = get_llm_client(provider)
        extractor = SignalExtractor(llm)
        signals = await extractor.extract_signals(doc_data)
        extracted = sum(1 for s in signals.values() if s.get("value"))
        step("signal_extraction", "complete", f"{extracted}/{len(SIGNAL_SCHEMA)} signals")

        analysis_store[analysis_id]["status"] = "validating"
        for key, sig in signals.items():
            if sig.get("confidence", 0) < 0.1: sig["value"] = None
        step("validation", "complete")

        # Edge case: insufficient signals
        valid = sum(1 for s in signals.values() if s.get("value"))
        if valid < 3:
            followups = generate_followup_questions(signals, doc_data.get("full_text", ""))
            analysis_store[analysis_id].update({
                "status": "needs_followup", "signals": signals,
                "followup_questions": followups, "signals_found": valid,
                "signals_missing": len(SIGNAL_SCHEMA) - valid,
                "message": "Document lacks sufficient information. Please answer the follow-up questions.",
                "decision_trace": trace,
            })
            return

        analysis_store[analysis_id]["status"] = "scoring"
        step("scoring", "in_progress")
        result = scoring_engine.score(signals)
        followups = generate_followup_questions(signals, doc_data.get("full_text", ""))
        sensitivity = scoring_engine.sensitivity_analysis(signals)
        step("scoring", "complete", f"Winner: {result['recommended']}")
        step("sensitivity_analysis", "complete", sensitivity.get("warning") or "Stable")
        step("recommend", "complete")

        full = {
            "analysis_id": analysis_id, "status": "complete",
            "signals": signals, "decision_trace": trace,
            "document_info": {"filename": filename, "pages": doc_data["total_pages"], "words": doc_data["word_count"]},
            "followup_questions": followups, "sensitivity": sensitivity,
            **result,
        }
        analysis_store[analysis_id] = full

        if uid:
            save_analysis(analysis_id, uid, f"PDF: {filename}", "document",
                         result["recommended"], result["confidence"], full)
            log_activity(uid, "pdf_analysis", f"{filename} → {result['recommended']}")

    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)
        analysis_store[analysis_id].update({"status": "error", "error": str(e)})
        trace.append({"step": "error", "status": "failed", "details": str(e), "timestamp": datetime.utcnow().isoformat()})
        analysis_store[analysis_id]["decision_trace"] = trace
    finally:
        try:
            if os.path.exists(file_path): os.remove(file_path)
        except Exception: pass


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/v1/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    provider: str = Query(default=getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama")),
    uid: Optional[str] = Query(default=None),
):
    if not file.filename: raise HTTPException(400, "No filename")
    valid, msg = doc_parser.validate_file(file.filename, file.size or 0)
    if not valid: raise HTTPException(400, msg)

    analysis_id = str(uuid.uuid4())
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, file.filename)
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {settings.MAX_FILE_SIZE_MB}MB")
    with open(file_path, "wb") as f: f.write(content)

    analysis_store[analysis_id] = {"analysis_id": analysis_id, "status": "queued",
                                    "created_at": datetime.utcnow().isoformat(), "filename": file.filename}
    background_tasks.add_task(process_document_task, analysis_id, file_path, file.filename, provider, uid)
    if uid: log_activity(uid, "upload", file.filename)
    return {"analysis_id": analysis_id, "status": "queued"}


@app.post("/api/v1/questionnaire")
async def submit_questionnaire(
    input_data: QuestionnaireInput,
    provider: str = Query(default=getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama")),
):
    analysis_id = str(uuid.uuid4())
    trace = [{"step": "questionnaire_input", "status": "complete", "timestamp": datetime.utcnow().isoformat()}]
    uid = input_data.uid

    answers = {k: v for k, v in input_data.model_dump().items() if k != "uid" and v}
    extractor = SignalExtractor(get_llm_client(provider))
    signals = extractor.extract_from_questionnaire(answers)
    trace.append({"step": "signal_extraction", "status": "complete", "timestamp": datetime.utcnow().isoformat(),
                  "details": f"{sum(1 for s in signals.values() if s.get('value'))}/{len(SIGNAL_SCHEMA)} signals"})

    for key, sig in signals.items():
        if sig.get("confidence", 0) < 0.1: sig["value"] = None
    trace.append({"step": "validation", "status": "complete", "timestamp": datetime.utcnow().isoformat()})

    result = scoring_engine.score(signals)
    followups = generate_followup_questions(signals)
    sensitivity = scoring_engine.sensitivity_analysis(signals)

    trace.extend([
        {"step": "scoring", "status": "complete", "timestamp": datetime.utcnow().isoformat(), "details": f"Winner: {result['recommended']}"},
        {"step": "sensitivity_analysis", "status": "complete", "timestamp": datetime.utcnow().isoformat()},
        {"step": "recommend", "status": "complete", "timestamp": datetime.utcnow().isoformat()},
    ])

    response = {"analysis_id": analysis_id, "status": "complete", "signals": signals,
                "followup_questions": followups, "sensitivity": sensitivity,
                "decision_trace": trace, "created_at": datetime.utcnow().isoformat(), **result}
    analysis_store[analysis_id] = response

    if uid:
        save_analysis(analysis_id, uid, f"Questionnaire → {result['recommended']}", "questionnaire",
                     result["recommended"], result["confidence"], response)
        log_activity(uid, "questionnaire", f"→ {result['recommended']}")

    return response


@app.get("/api/v1/analysis/{analysis_id}")
async def get_analysis(analysis_id: str):
    if analysis_id in analysis_store: return analysis_store[analysis_id]
    stored = db_get_analysis(analysis_id)
    if stored:
        result = stored.get("result", {}); result["analysis_id"] = analysis_id; result["status"] = "complete"
        analysis_store[analysis_id] = result; return result
    raise HTTPException(404, "Analysis not found")


@app.post("/api/v1/followup")
async def submit_followup(data: FollowUpAnswers):
    analysis = analysis_store.get(data.analysis_id)
    if not analysis:
        stored = db_get_analysis(data.analysis_id)
        analysis = stored.get("result", {}) if stored else {}
    if not analysis: raise HTTPException(404, "Analysis not found")

    signals = analysis.get("signals", {})
    for signal_name, value in data.answers.items():
        if signal_name in SIGNAL_SCHEMA:
            signals[signal_name] = {"value": value, "confidence": 1.0,
                                    "source_text": "Follow-up answer from user", "page_number": 0, "source_verified": True}

    result = scoring_engine.score(signals)
    sensitivity = scoring_engine.sensitivity_analysis(signals)
    followups = generate_followup_questions(signals)
    analysis.update({"signals": signals, "followup_questions": followups, "sensitivity": sensitivity, **result})
    analysis_store[data.analysis_id] = analysis

    if data.uid:
        save_analysis(data.analysis_id, data.uid, "Follow-up", "followup",
                     result["recommended"], result["confidence"], analysis)
    return analysis


@app.get("/api/v1/questionnaire/options")
async def questionnaire_options():
    return {"signals": {k: {"description": v["description"], "options": SIGNAL_OPTIONS.get(k, []),
                             "required": k in ["dataset_size","data_volatility","accuracy_requirement","latency_requirement","domain_specificity"]}
                        for k, v in SIGNAL_SCHEMA.items()}}

@app.get("/api/v1/architectures")
async def architectures():
    return {"architectures": ARCHITECTURE_DESCRIPTIONS}

@app.get("/api/v1/export/{analysis_id}")
async def export_analysis(analysis_id: str):
    data = analysis_store.get(analysis_id)
    if not data:
        stored = db_get_analysis(analysis_id)
        data = stored.get("result", {}) if stored else {}
    if not data: raise HTTPException(404, "Not found")
    return JSONResponse(content=data, headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.json"})


# ── Projects ──────────────────────────────────────────────────────────────────
@app.post("/api/v1/projects", status_code=201)
async def create_project(data: ProjectCreate):
    pid = str(uuid.uuid4()); now = datetime.utcnow().isoformat()
    p = {"id": pid, "user_id": data.user_id, "name": data.name.strip(),
         "description": (data.description or "").strip(), "status": "empty",
         "analysis_id": None, "mode": None, "created_at": now, "updated_at": now}
    project_store[pid] = p; return p

@app.get("/api/v1/projects")
async def list_projects(user_id: Optional[str] = Query(default=None)):
    ps = list(project_store.values())
    if user_id: ps = [p for p in ps if p.get("user_id") == user_id]
    return {"projects": sorted(ps, key=lambda p: p["updated_at"], reverse=True)}

@app.get("/api/v1/projects/{pid}")
async def get_project(pid: str):
    if pid not in project_store: raise HTTPException(404, "Not found")
    return project_store[pid]

@app.put("/api/v1/projects/{pid}")
async def update_project(pid: str, data: ProjectUpdate):
    if pid not in project_store: raise HTTPException(404, "Not found")
    p = project_store[pid]
    for field in ["name","description","status","analysis_id","mode"]:
        v = getattr(data, field, None)
        if v is not None: p[field] = v.strip() if isinstance(v, str) else v
    p["updated_at"] = datetime.utcnow().isoformat(); return p

@app.delete("/api/v1/projects/{pid}", status_code=204)
async def delete_project(pid: str):
    if pid not in project_store: raise HTTPException(404, "Not found")
    del project_store[pid]




# ─────────────────────────────────────────────────────────────────────────────
# VOICE INPUT — Transcribe audio to text, then run analysis
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/v1/voice/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    uid: Optional[str] = Query(default=None),
):
    """
    Transcribe audio to text using OpenAI Whisper or local fallback.
    Returns transcript + extracted signals from spoken requirements.
    """
    if not audio.filename:
        raise HTTPException(400, "No audio file provided")

    content_bytes = await audio.read()
    if len(content_bytes) == 0:
        raise HTTPException(400, "Empty audio file")

    # Save temp file
    ext = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    tmp_path = os.path.join(tempfile.mkdtemp(), f"voice{ext}")
    with open(tmp_path, "wb") as f:
        f.write(content_bytes)

    transcript = ""

    # ── Try OpenAI Whisper ────────────────────────────────────────────────────
    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            with open(tmp_path, "rb") as f:
                result = await client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    response_format="text",
                )
            transcript = str(result).strip()
            logger.info(f"Whisper transcript: {transcript[:100]}")
        except Exception as e:
            logger.warning(f"Whisper failed: {e}")

    # ── Fallback: Web Speech was used client-side, we just get text ──────────
    if not transcript:
        return JSONResponse(
            status_code=422,
            content={
                "error": "transcription_failed",
                "message": "OpenAI Whisper not configured. Add OPENAI_API_KEY to .env, or use browser-based voice input.",
            }
        )

    # Clean up
    try:
        os.remove(tmp_path)
    except Exception:
        pass

    # Extract signals from the transcript
    from services.fast_extractor import heuristic_extract
    signals = heuristic_extract(transcript)
    valid_signals = sum(1 for s in signals.values() if s.get("value"))

    if uid:
        log_activity(uid, "voice_input", f"Transcript: {transcript[:80]}")

    return {
        "transcript": transcript,
        "signals_extracted": valid_signals,
        "signals": signals,
        "message": f"Extracted {valid_signals} signals from your voice input.",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
