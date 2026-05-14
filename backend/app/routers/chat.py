"""
Chat router — POST /api/v1/chat
Answers user questions about a completed analysis using the full result context.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Session as SessionModel, Result, Signal
from app.core.security import verify_firebase_token

router = APIRouter()
logger = logging.getLogger(__name__)

ARCH_LABELS = {
    "RAG": "Retrieval-Augmented Generation (RAG)",
    "FineTuning": "Fine-Tuning",
    "CAG": "Context-Augmented Generation (CAG)",
    "Hybrid": "Hybrid (RAG + Fine-Tuning)",
}

SIGNAL_LABELS = {
    "dataset_size": "Dataset Size",
    "query_volume": "Query Volume",
    "latency_requirement": "Latency Requirement",
    "data_volatility": "Data Volatility",
    "accuracy_requirement": "Accuracy Requirement",
    "domain_specificity": "Domain Specificity",
    "security_level": "Security Level",
    "cost_sensitivity": "Cost Sensitivity",
    "deployment_preference": "Deployment Preference",
    "user_scale": "User Scale",
}


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    analysis_id: str = Field(..., max_length=64)
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    response: str
    analysis_id: str


def _build_context(session: SessionModel, result: Result, signals: list[Signal]) -> str:
    rec = result.recommended_architecture
    conf = result.confidence_score
    scores = result.scores or {}
    why_not = result.why_not or {}
    suitability = result.suitability or {}
    arch_details = result.architecture_details or {}

    lines = [
        f"RECOMMENDED ARCHITECTURE: {ARCH_LABELS.get(rec, rec)}",
        f"CONFIDENCE: {round(conf * 100)}%",
        "",
        "ARCHITECTURE SCORES (higher = better fit):",
    ]
    for arch, score in sorted(scores.items(), key=lambda x: -x[1]):
        label = ARCH_LABELS.get(arch, arch)
        lines.append(f"  - {label}: {score:.1f}/100")

    lines += ["", "EXTRACTED SIGNALS FROM DOCUMENT:"]
    sig_map = {s.signal_name: s for s in signals}
    for key, label in SIGNAL_LABELS.items():
        s = sig_map.get(key)
        if s and s.value:
            lines.append(f"  - {label}: {s.value} (confidence: {round(s.confidence * 100)}%)")
        else:
            lines.append(f"  - {label}: not detected")

    if suitability:
        lines += ["", "SUITABILITY DESCRIPTIONS:"]
        for arch, desc in suitability.items():
            lines.append(f"  [{ARCH_LABELS.get(arch, arch)}] {desc}")

    if why_not:
        lines += ["", "WHY OTHER ARCHITECTURES WERE NOT RECOMMENDED:"]
        for arch, reason in why_not.items():
            if arch != rec:
                lines.append(f"  [{ARCH_LABELS.get(arch, arch)}] {reason}")

    if rec in arch_details:
        det = arch_details[rec]
        lines += ["", f"DETAILS ABOUT {ARCH_LABELS.get(rec, rec)}:"]
        if det.get("description"):
            lines.append(f"  Description: {det['description']}")
        if det.get("strengths"):
            lines.append(f"  Strengths: {', '.join(det['strengths'][:4])}")
        if det.get("weaknesses"):
            lines.append(f"  Weaknesses: {', '.join(det['weaknesses'][:3])}")

    if session.filename:
        lines += ["", f"DOCUMENT: {session.filename}"]

    return "\n".join(lines)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    uid: Optional[str] = Depends(verify_firebase_token),
    db: DBSession = Depends(get_db),
):
    try:
        session_uuid = uuid.UUID(body.analysis_id)
    except ValueError:
        raise HTTPException(404, "Analysis not found")

    session = db.query(SessionModel).filter(
        SessionModel.id == session_uuid
    ).first()
    if not session:
        raise HTTPException(404, "Analysis not found")
    if session.status != "completed":
        raise HTTPException(400, "Analysis is not yet complete")

    result = session.result
    if not result:
        raise HTTPException(404, "No result found for this analysis")

    signals = session.signals or []
    context = _build_context(session, result, signals)

    system_prompt = f"""You are ArchGuide, an expert AI architecture advisor. A user is asking about their specific project analysis. \
You have the full analysis context below. Every answer MUST cite concrete values from this context — never give generic advice.

ANALYSIS CONTEXT:
{context}

HOW TO ANSWER:
- Always reference the actual signal values (e.g. "your dataset is large at ~500GB", "your strict latency requirement of <200ms", "your critical accuracy need").
- When explaining WHY, trace it back to 2-3 specific signals from the context above.
- When comparing architectures, use the actual scores (e.g. "RAG scored 78 vs FineTuning's 91 because...").
- For cost questions, reference cost_sensitivity and the suitability descriptions if available.
- Be direct and specific — 3-6 sentences is ideal. No bullet points unless listing more than 3 items.
- Never say "I don't know" - use the context to give the best answer possible.
- Never invent data not in the context.
- Write plain prose only. No asterisks, no bold, no italic, no markdown of any kind.
- No em dashes or en dashes. Use a plain hyphen (-) or comma if you need a pause.
- No bullet points, no numbered lists, no headers. Just clear sentences and paragraphs."""

    from services.llm_client import LLMClient
    from fastapi import HTTPException as _HTTPException

    llm = LLMClient()

    # Build a proper multi-turn messages list so the model tracks full conversation context.
    # history already contains all previous turns (NOT the current message — frontend
    # sends messages state before appending the new userMsg).
    ollama_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in body.history[-12:]:          # keep last 12 turns (6 exchanges) for context
        ollama_messages.append({"role": msg.role, "content": msg.content})
    ollama_messages.append({"role": "user", "content": body.message})

    try:
        response_text = await llm.generate_chat(
            messages=ollama_messages,
            temperature=0.25,
            max_tokens=768,
        )
    except _HTTPException:
        raise
    except Exception as e:
        logger.error("LLM chat error: %s", e, exc_info=True)
        detail = str(e)
        if "connection" in detail.lower() or "connect" in detail.lower():
            raise HTTPException(503, "Cannot reach the LLM service. Make sure Ollama is running.")
        raise HTTPException(503, f"Chat failed: {detail}")

    # Strip any role prefix the LLM might echo back
    response_text = response_text.strip()
    for prefix in ("ArchGuide:", "Assistant:", "AI:"):
        if response_text.startswith(prefix):
            response_text = response_text[len(prefix):].strip()

    import re, unicodedata

    # Normalise unicode so fancy dashes (U+2014, U+2013, U+2012, etc.) are caught
    response_text = unicodedata.normalize("NFKC", response_text)

    # Remove every kind of dash that isn't a plain hyphen-minus
    response_text = re.sub(r'[‒–—―﹘﹣－]', '-', response_text)

    # Strip ALL asterisks (bold/italic markers) — no paired matching needed
    response_text = re.sub(r'\*+', '', response_text)

    # Strip markdown headers (##, ###, etc.)
    response_text = re.sub(r'(?m)^#{1,6}\s*', '', response_text)

    # Strip trailing colons left behind after header removal, e.g. "Mitigation:"
    # — keep them if they're mid-sentence; only strip lone "Word:" at line start
    # (don't over-strip — colons in context like "RAG: 91/100" are fine)

    # Collapse 3+ consecutive newlines to 2
    response_text = re.sub(r'\n{3,}', '\n\n', response_text)

    response_text = response_text.strip()

    return ChatResponse(response=response_text, analysis_id=body.analysis_id)
