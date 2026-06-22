"""
Document Processing Service
Handles PDF, DOCX, and TXT file parsing with page-level text extraction.

Relevance gate uses a risk-scoring approach (fraud-detection pattern):
  - Deterministic rules accumulate a risk score independently.
  - LOW score  → CLEAR tier  → passes immediately, no LLM cost.
  - MID score  → REVIEW tier → escalated to LLM semantic classifier.
  - HIGH score → AUTO_REJECT  → rejected immediately, no LLM cost.
"""
import os
import re
import logging
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime, timezone

import fitz  # PyMuPDF
from docx import Document

logger = logging.getLogger(__name__)

# We use a lazy getter for the developer log to prevent Uvicorn from
# disabling the logger during startup.
def get_relevance_logger() -> logging.Logger:
    logger = logging.getLogger("relevance_gate")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    # Avoid adding handlers multiple times
    if not logger.handlers:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(log_dir, "relevance_gate.log"))
        fh.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(fh)
        
    # Re-enable the logger explicitly on every call in case Uvicorn disabled it
    logger.disabled = False
    return logger

# ── Flat set of all signal keywords used for page relevance scoring ──────────
# Populated by signal_extractor at import time to avoid circular deps.
_SIGNAL_KEYWORDS: frozenset[str] = frozenset()


def register_signal_keywords(keywords: frozenset[str]) -> None:
    global _SIGNAL_KEYWORDS
    _SIGNAL_KEYWORDS = keywords


def score_page_relevance(text: str) -> int:
    """Count unique signal keywords found on a single page."""
    text_lower = text.lower()
    return sum(1 for kw in _SIGNAL_KEYWORDS if kw in text_lower)


# ── Step 1: Risk-scoring data structures ─────────────────────────────────────

class RiskTier(str, Enum):
    CLEAR = "clear"             # low risk — passes immediately
    REVIEW = "review"           # ambiguous — needs LLM verification
    AUTO_REJECT = "auto_reject" # high risk — reject without LLM call


@dataclass
class RuleFlag:
    """A single rule's contribution to the risk assessment, analogous to
    one fraud-detection rule (e.g. 'unusual transaction amount').

    Critically, none of the rule functions reject directly — they only return
    a RuleFlag with risk_points. Rejection decisions are made centrally in
    assess_document_risk(), so each rule is pure and side-effect-free.
    """
    rule_name: str
    triggered: bool
    risk_points: float
    detail: str  # human-readable explanation, used in decision trace


@dataclass
class RelevanceAssessment:
    """Final output of the relevance gate, replacing the old tuple return.

    The `flags` list is the full audit trail — written to the Redis decision
    trace even on PASS so false positives can be debugged later by seeing
    exactly what risk score every document received and why.
    """
    passed: bool
    risk_tier: RiskTier
    total_risk_score: float
    flags: list[RuleFlag] = field(default_factory=list)
    rejection_reason: str | None = None      # machine-readable, e.g. "resume_shape"
    rejection_message: str | None = None     # user-facing message
    llm_review_performed: bool = False
    llm_detected_type: str | None = None
    llm_confidence: float | None = None


def build_user_facing_message(assessment: "RelevanceAssessment") -> str:
    """
    Produces a single, short, plain-English sentence for end users.
    NEVER include: risk scores, point values, rule names, tier names,
    keyword counts/densities, or category counts. This is the ONLY
    function allowed to generate text that reaches the frontend for
    the relevance check step.
    """
    if assessment.passed:
        return "Your document looks like a valid requirements document and is ready for analysis."

    # Map each possible rejection_reason to a plain-English explanation.
    # This list must stay in sync with every rule_name used in Step 2
    # of the previous task (circular_upload, length_ceiling, keyword_density,
    # category_coverage, resume_shape) plus "semantic_mismatch" from the
    # LLM review step.
    reason_messages = {
        "circular_upload": (
            "This file looks like a previously generated report rather than "
            "a requirements document. Please upload your original requirements "
            "document instead."
        ),
        "length_ceiling": (
            "This document is much longer than a typical requirements document "
            "(it looks more like a book or manual). Please upload a focused "
            "requirements or specification document instead."
        ),
        "keyword_density": (
            "This document doesn't appear to contain enough project-requirements "
            "content for us to analyze. Please upload a document describing your "
            "system's requirements."
        ),
        "category_coverage": (
            "This document doesn't appear to cover enough project-requirements "
            "topics for us to analyze. Please upload a document describing your "
            "system's requirements."
        ),
        "resume_shape": (
            "This looks like a resume or CV rather than a project requirements "
            "document. Please upload a document describing your system's "
            "requirements instead."
        ),
        "semantic_mismatch": (
            f"This document appears to be a {assessment.llm_detected_type or 'different type of document'}, "
            f"not a project requirements document. Please upload a document "
            f"describing your system's requirements."
        ),
        "too_short": (
            "This document is too short for us to analyze. Please upload a "
            "more complete requirements document."
        ),
    }

    return reason_messages.get(
        assessment.rejection_reason,
        # Generic fallback — should rarely fire, but never expose raw
        # rejection_reason strings or technical detail if it does.
        "This document doesn't appear to be a project requirements document. "
        "Please upload a document describing your system's requirements."
    )


def log_relevance_assessment(session_id: str, filename: str, assessment: "RelevanceAssessment") -> None:
    """
    Full technical detail, for developers only. Never sent to the frontend.
    One JSON line per document for easy grep/parsing later.
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "filename": filename,
        "passed": assessment.passed,
        "risk_tier": assessment.risk_tier.value,
        "total_risk_score": assessment.total_risk_score,
        "rejection_reason": assessment.rejection_reason,
        "llm_review_performed": assessment.llm_review_performed,
        "llm_detected_type": assessment.llm_detected_type,
        "llm_confidence": assessment.llm_confidence,
        "rule_flags": [
            {
                "rule_name": f.rule_name,
                "triggered": f.triggered,
                "risk_points": f.risk_points,
                "detail": f.detail,
            }
            for f in assessment.flags
        ],
    }
    
    # Print the disabled state before retrieving/fixing the logger (User requirement)
    logger_instance = logging.getLogger("relevance_gate")
    print(f">>>> [DIAG] relevance_logger.disabled BEFORE fix: {logger_instance.disabled}", flush=True)
    
    rl = get_relevance_logger()
    
    print(f">>>> [DIAG] relevance_logger.disabled AFTER fix: {rl.disabled}", flush=True)

    rl.info(json.dumps(log_entry))


# ── Step 2: Independent rule functions (each always returns a RuleFlag) ──────
#
# CRITICAL CONSTRAINT: none of these functions return early or raise on
# rejection. They each return a RuleFlag(triggered=True/False, risk_points=N).
# The pass/fail/review decision is made once, centrally, in Step 3.
# This is what makes it a scoring system rather than a chain of hard gates.

# ── Rule 1: Length ceiling ────────────────────────────────────────────────────
MAX_REASONABLE_WORD_COUNT = 15_000   # ~30-40 dense pages; generous for a real spec
EXTREME_WORD_COUNT = 50_000          # textbook-scale; this alone should be near-disqualifying


def rule_length_ceiling(word_count: int) -> RuleFlag:
    """Flags documents that are too long to plausibly be a requirements spec.

    An 800-page textbook naturally contains technical vocabulary spread evenly
    throughout — purely frequency-based checks cannot distinguish it from a
    genuine spec. This rule catches it on size alone.
    """
    if word_count > EXTREME_WORD_COUNT:
        return RuleFlag(
            rule_name="length_ceiling",
            triggered=True,
            risk_points=70,  # high enough to auto-reject alone (see thresholds below)
            detail=(
                f"Document is {word_count:,} words (~{word_count // 500} pages) — "
                f"far beyond typical requirements doc length, resembles a book/manual."
            ),
        )
    if word_count > MAX_REASONABLE_WORD_COUNT:
        return RuleFlag(
            rule_name="length_ceiling",
            triggered=True,
            risk_points=35,
            detail=(
                f"Document is {word_count:,} words, longer than typical requirements docs "
                f"(usually under {MAX_REASONABLE_WORD_COUNT:,})."
            ),
        )
    return RuleFlag(
        rule_name="length_ceiling",
        triggered=False,
        risk_points=0,
        detail="Length within normal range.",
    )


# ── Rule 2: Keyword density (scored signal, not a hard gate) ─────────────────
def rule_keyword_density(text: str, word_count: int, signal_schema: dict) -> RuleFlag:
    """Wraps the existing density calculation as a scored risk signal.

    Unlike the old hard gate (reject if density < 3.0), this contributes
    points to the risk score so a slightly low density document accumulates
    risk but isn't instantly killed — only a combination of weak signals
    reaches rejection threshold.
    """
    text_lower = text.lower()
    total_hits = sum(
        1
        for schema in signal_schema.values()
        for kw in schema.get("keywords", [])
        if kw in text_lower
    )
    density = (total_hits / max(word_count, 1)) * 1000

    if density < 1.5:
        return RuleFlag(
            rule_name="keyword_density",
            triggered=True,
            risk_points=40,
            detail=f"Very low keyword density ({density:.2f}/1000 words).",
        )
    if density < 3.0:
        return RuleFlag(
            rule_name="keyword_density",
            triggered=True,
            risk_points=15,
            detail=f"Below-threshold keyword density ({density:.2f}/1000 words).",
        )
    return RuleFlag(
        rule_name="keyword_density",
        triggered=False,
        risk_points=0,
        detail=f"Healthy keyword density ({density:.2f}/1000 words).",
    )


# ── Rule 3: Category coverage (tightened: require 2+ distinct hits per category) ──
MIN_CATEGORIES_REQUIRED = 5
MIN_UNIQUE_KEYWORDS_PER_CATEGORY = 2


def rule_category_coverage(text: str, signal_schema: dict) -> RuleFlag:
    """Checks how many signal categories have at least 2 distinct keyword hits.

    Tightening from 1-hit-per-category (old gate) to 2-hits means a resume
    that mentions "security" once and "data" once no longer qualifies.
    Requires 5 of 12 categories with 2+ hits (old: 3 of 12 with 1+ hit).
    """
    text_lower = text.lower()
    categories_matched = 0
    for schema in signal_schema.values():
        keywords = schema.get("keywords", [])
        unique_hits = {kw for kw in keywords if kw in text_lower}
        if len(unique_hits) >= MIN_UNIQUE_KEYWORDS_PER_CATEGORY:
            categories_matched += 1

    if categories_matched < 2:
        return RuleFlag(
            rule_name="category_coverage",
            triggered=True,
            risk_points=45,
            detail=(
                f"Only {categories_matched}/12 categories matched — "
                f"touches almost no requirement topics."
            ),
        )
    if categories_matched < MIN_CATEGORIES_REQUIRED:
        return RuleFlag(
            rule_name="category_coverage",
            triggered=True,
            risk_points=20,
            detail=(
                f"Only {categories_matched}/12 categories matched "
                f"(need {MIN_CATEGORIES_REQUIRED}+)."
            ),
        )
    return RuleFlag(
        rule_name="category_coverage",
        triggered=False,
        risk_points=0,
        detail=f"{categories_matched}/12 categories matched.",
    )


# ── Rule 4: Document shape — resume/CV signature ─────────────────────────────
def rule_resume_shape(text: str) -> RuleFlag:
    """Detects structural resume/CV patterns independent of keyword frequency.

    A resume that mentions AWS, scalability, and data pipelines passes keyword
    checks but has a structurally distinct shape: contact info, date ranges,
    short bulleted lines, and no specification/requirements language.
    The spec_hits offset ensures genuine specs with a contact section are
    not falsely flagged.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    word_count = len(text.split())
    text_lower = text.lower()

    resume_section_markers = [
        "work experience", "professional experience", "education",
        "skills", "certifications", "objective", "references available",
        "linkedin.com/in/", "github.com/",
    ]
    marker_hits = sum(1 for m in resume_section_markers if m in text_lower)

    standalone_headers = {"experience", "summary", "profile", "employment"}
    for line in lines:
        if line.lower() in standalone_headers:
            marker_hits += 1

    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
    has_phone = bool(re.search(
        r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
    ))

    date_range_hits = len(re.findall(
        r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?\d{4}\s*[-\u2013\u2014to]+\s*"
        r"(present|current|(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?\d{4})",
        text_lower,
    ))

    short_line_ratio = (
        sum(1 for line in lines if len(line.split()) <= 10) / max(len(lines), 1)
    )

    spec_language_markers = [
        "shall", "must support", "should support", "acceptance criteria",
        "user story", "stakeholder", "scope of work", "deliverable",
        "requirement", "specification", "use case",
    ]
    spec_hits = sum(1 for m in spec_language_markers if m in text_lower)

    resume_score = (
        (2 if marker_hits >= 3 else 0) +
        (1 if has_email and has_phone else 0) +
        (2 if date_range_hits >= 2 else 0) +
        (1 if short_line_ratio > 0.5 else 0) +
        (1 if word_count < 1200 else 0)
    )

    # Spec language presence offsets resume-shape suspicion — a real spec
    # that happens to have a contact section shouldn't be penalized.
    if resume_score >= 4 and spec_hits == 0:
        return RuleFlag(
            rule_name="resume_shape",
            triggered=True,
            risk_points=50,
            detail=(
                f"Strong resume/CV structural signature (score={resume_score}): "
                f"contact info, date ranges, short bulleted lines, no spec language."
            ),
        )
    if resume_score >= 4 and spec_hits > 0:
        return RuleFlag(
            rule_name="resume_shape",
            triggered=True,
            risk_points=15,
            detail=(
                f"Some resume-like structure (score={resume_score}) but spec language "
                f"also present — likely a portfolio/case-study doc, mild suspicion only."
            ),
        )
    return RuleFlag(
        rule_name="resume_shape",
        triggered=False,
        risk_points=0,
        detail="No resume-like structural signature.",
    )


# ── Rule 5: Circular upload detection (original list preserved exactly) ───────
_ARCHGUIDE_MARKERS = [
    "generated by archguide",
    "archguide | architecture recommendation report",
    "archguide architecture recommendation",
    "recommended architecture\nrag",
    "recommended architecture\nfine-tuning",
    "recommended architecture\ncag",
    "recommended architecture\nhybrid",
    "overall score\n0.0 / 100",
    "extracted signals - source traceability",
]


def rule_circular_upload(text: str) -> RuleFlag:
    """Detects ArchGuide-generated reports re-uploaded as input documents.

    These PDFs embed the original source-text snippets, so they pass keyword
    gates but produce 0 LLM signals and meaningless recommendations.
    100 risk points → always AUTO_REJECT regardless of other rules.
    """
    head = text[:1000].lower()
    if any(m in head for m in _ARCHGUIDE_MARKERS):
        return RuleFlag(
            rule_name="circular_upload",
            triggered=True,
            risk_points=100,
            detail=(
                "Document appears to be a previously generated ArchGuide report. "
                "Please upload your original project specification, requirements doc, or "
                "use-case description instead — not the PDF that ArchGuide generated."
            ),
        )
    return RuleFlag(
        rule_name="circular_upload",
        triggered=False,
        risk_points=0,
        detail="No circular-upload markers found.",
    )


# ── Step 3: Central risk aggregation and tier decision ────────────────────────
#
# Thresholds — named constants so they can be tuned based on real traffic
# without code changes. Scattered magic numbers are forbidden.
AUTO_REJECT_THRESHOLD = 70   # score ≥ this → reject without LLM review
REVIEW_THRESHOLD = 25        # score ≥ this (but < auto-reject) → LLM review
# score < REVIEW_THRESHOLD → CLEAR, passes immediately, no LLM cost


def assess_document_risk(
    text: str,
    word_count: int,
    signal_schema: dict,
) -> tuple[RiskTier, float, list[RuleFlag]]:
    """Run all rules and aggregate risk score. This is the ONLY place where
    a tier decision is made — the rule functions themselves are pure and
    side-effect-free, mirroring fraud-detection rule engines.

    Why additive scoring works:
    - A single mid-severity rule (15 pts) won't kill a document.
    - Multiple mid-severity rules compound: 15+20+15 = 50 → REVIEW.
    - One severe rule (circular_upload=100, extreme_length=70) → AUTO_REJECT alone.
    """
    flags = [
        rule_circular_upload(text),
        rule_length_ceiling(word_count),
        rule_keyword_density(text, word_count, signal_schema),
        rule_category_coverage(text, signal_schema),
        rule_resume_shape(text),
    ]

    total_risk = sum(f.risk_points for f in flags if f.triggered)

    if total_risk >= AUTO_REJECT_THRESHOLD:
        tier = RiskTier.AUTO_REJECT
    elif total_risk >= REVIEW_THRESHOLD:
        tier = RiskTier.REVIEW
    else:
        tier = RiskTier.CLEAR

    return tier, total_risk, flags


# ── Step 4: LLM semantic review (the "manual review" step) ───────────────────
RELEVANCE_CLASSIFIER_PROMPT = """You are a strict document classifier. Determine if the following document excerpt is a SOFTWARE/AI PROJECT REQUIREMENTS DOCUMENT — i.e., a document describing what a team needs to build, including things like data characteristics, expected scale, performance needs, or system constraints.

It is NOT a requirements document if it is instead: a resume/CV, a textbook or educational material, a legal contract, a financial report, a slide deck export, marketing copy, a research paper, news article, or general documentation unrelated to a specific project's requirements.

Respond with ONLY this JSON, no other text, no markdown code fences:
{{"is_requirements_doc": true/false, "actual_document_type": "<your best guess, 2-4 words>", "confidence": 0.0-1.0}}

Document excerpt:
---
{excerpt}
---
"""


async def llm_relevance_review(text: str, llm_client) -> dict:
    """
    The 'manual review' step in the fraud-detection analogy: only called for
    documents that scored into the REVIEW tier. Makes the final semantic
    judgment call that frequency-based rules structurally cannot make.

    FAIL OPEN: if the LLM call or parsing fails, the document is allowed through.
    This matches the existing codebase precedent (e.g. relevance gate passes
    through if the keyword registry hasn't loaded at import time). Layers 1-5
    (rules) already filtered the highest-confidence rejections; this is a
    precision improvement, not the only line of defense.
    """
    start = text[:2000]
    mid_point = len(text) // 2
    middle = text[mid_point:mid_point + 1000]
    excerpt = f"{start}\n...\n[EXCERPT FROM MIDDLE OF DOCUMENT]\n...\n{middle}"

    prompt = RELEVANCE_CLASSIFIER_PROMPT.format(excerpt=excerpt)

    try:
        # Use generate_json — the same interface used for signal extraction.
        # It handles JSON parsing and sanitization internally; returns {"error": ...}
        # on failure so callers always get a dict, never an exception.
        result = await llm_client.generate_json(prompt=prompt)

        if result.get("error"):
            logger.warning(
                "LLM relevance review returned error: %s — failing open.",
                result["error"],
            )
            return {
                "is_requirements_doc": True,
                "detected_type": "unknown",
                "confidence": 0.0,
                "error": result["error"],
            }

        return {
            "is_requirements_doc": bool(result.get("is_requirements_doc", True)),
            "detected_type": str(result.get("actual_document_type", "unknown")),
            "confidence": float(result.get("confidence", 0.0)),
            "error": None,
        }
    except Exception as exc:
        logger.warning("LLM relevance review failed (%s) — failing open.", exc)
        return {
            "is_requirements_doc": True,
            "detected_type": "unknown",
            "confidence": 0.0,
            "error": str(exc),
        }


# ── Step 5: New validate_document_relevance() ─────────────────────────────────
async def validate_document_relevance(
    text: str,
    word_count: int,
    signal_schema: dict,
    llm_client,
) -> RelevanceAssessment:
    """
    Production-grade relevance gate using risk-scoring (fraud-detection pattern).

    Replaces the old hard-gate `validate_document_relevance(full_text, pages)`
    tuple return with a rich RelevanceAssessment object that carries a full
    audit trail (flags list) for the Redis decision trace.

    Flow:
      0. Minimum word count (80) → immediate AUTO_REJECT if too short.
      1. If signal_schema not yet populated → graceful CLEAR (fail open).
      2. Run 5 independent rule checks → accumulate risk score.
      3. AUTO_REJECT (score ≥ 70): reject immediately, no LLM cost.
      4. REVIEW (score 25-69): escalate to LLM semantic classifier.
      5. CLEAR (score < 25): pass immediately, no LLM cost.

    The full flags list is ALWAYS returned in the assessment so the caller can
    log it to the decision trace for every document — both passes and rejects.
    """
    # Minimum word count floor — preserved from the original gate
    if word_count < 80:
        return RelevanceAssessment(
            passed=False,
            risk_tier=RiskTier.AUTO_REJECT,
            total_risk_score=100.0,
            flags=[
                RuleFlag(
                    rule_name="min_word_count",
                    triggered=True,
                    risk_points=100,
                    detail=(
                        f"Document is too short ({word_count} words, minimum 80). "
                        f"Please upload a requirements document, product specification, "
                        f"or use-case description."
                    ),
                )
            ],
            rejection_reason="too_short",
            rejection_message=(
                f"The document is too short ({word_count} words). "
                f"Please upload a requirements document, product specification, "
                f"or use-case description."
            ),
        )

    # Graceful skip if the signal keyword registry hasn't been populated yet
    # (happens only when signal_extractor import is still in progress at startup).
    if not signal_schema:
        return RelevanceAssessment(
            passed=True,
            risk_tier=RiskTier.CLEAR,
            total_risk_score=0.0,
            flags=[],
        )

    tier, total_risk, flags = assess_document_risk(text, word_count, signal_schema)

    if tier == RiskTier.AUTO_REJECT:
        primary = max(
            (f for f in flags if f.triggered),
            key=lambda f: f.risk_points,
        )
        return RelevanceAssessment(
            passed=False,
            risk_tier=tier,
            total_risk_score=total_risk,
            flags=flags,
            rejection_reason=primary.rule_name,
            rejection_message=_build_rejection_message(primary, flags),
        )

    if tier == RiskTier.REVIEW:
        llm_result = await llm_relevance_review(text, llm_client)
        if not llm_result["is_requirements_doc"] and llm_result["error"] is None:
            return RelevanceAssessment(
                passed=False,
                risk_tier=tier,
                total_risk_score=total_risk,
                flags=flags,
                rejection_reason="semantic_mismatch",
                rejection_message=(
                    f"This document appears to be a {llm_result['detected_type']}, "
                    f"not a project requirements document."
                ),
                llm_review_performed=True,
                llm_detected_type=llm_result["detected_type"],
                llm_confidence=llm_result["confidence"],
            )
        # LLM either confirmed relevance or failed open
        return RelevanceAssessment(
            passed=True,
            risk_tier=tier,
            total_risk_score=total_risk,
            flags=flags,
            llm_review_performed=llm_result.get("error") is None,
            llm_detected_type=llm_result.get("detected_type"),
            llm_confidence=llm_result.get("confidence"),
        )

    # CLEAR tier — passes immediately, no LLM cost
    return RelevanceAssessment(
        passed=True,
        risk_tier=tier,
        total_risk_score=total_risk,
        flags=flags,
    )


def _build_rejection_message(
    primary_flag: RuleFlag,
    all_flags: list[RuleFlag],
) -> str:
    """User-facing rejection message.

    Leads with the primary (highest risk_points) triggered flag detail.
    The full all_flags list is logged separately via the decision trace.
    """
    triggered_details = [
        f.detail for f in all_flags if f.triggered and f.rule_name != primary_flag.rule_name
    ]
    if triggered_details:
        return f"{primary_flag.detail} Additional flags: {'; '.join(triggered_details)}"
    return primary_flag.detail


# ── Page relevance helpers ───────────────────────────────────────────────────
def get_relevant_pages(pages: list[dict], min_score: int = 1, max_pages: int = 20) -> list[dict]:
    """
    Return the top `max_pages` most-relevant pages (by keyword score) in document order.
    Falls back to the first max_pages pages if none pass the threshold.

    Capping at max_pages prevents huge LLM contexts on large documents, which
    would otherwise generate dozens of parallel Groq chunks and hit TPM rate limits.
    """
    scored = [(page, score_page_relevance(page.get("text", ""))) for page in pages]
    relevant = [(p, s) for p, s in scored if s >= min_score]
    if not relevant:
        return pages[:max_pages]
    # Take top max_pages by score, then restore document order for coherent narrative
    top_ids = {id(p) for p, _ in sorted(relevant, key=lambda x: x[1], reverse=True)[:max_pages]}
    return [p for p in pages if id(p) in top_ids]


# ── Document parser ───────────────────────────────────────────────────────────
class DocumentParser:
    """Multi-format document parser with page-level extraction."""

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    def __init__(self):
        self.supported_formats = {
            ".pdf": self._parse_pdf,
            ".docx": self._parse_docx,
            ".txt": self._parse_txt,
        }

    def validate_file(self, filename: str, file_size: int) -> tuple[bool, str]:
        """Validate file extension and size."""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type: {ext}. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}"
        if file_size > self.MAX_FILE_SIZE:
            return False, f"File too large ({file_size / 1024 / 1024:.1f}MB). Max: {self.MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
        return True, "OK"

    async def parse(self, file_path: str, filename: str) -> dict:
        """Parse a document and return structured text with page numbers."""
        ext = os.path.splitext(filename)[1].lower()
        parser = self.supported_formats.get(ext)
        if not parser:
            raise ValueError(f"Unsupported file format: {ext}")

        pages = parser(file_path)
        full_text = "\n\n".join([p["text"] for p in pages if p["text"].strip()])

        return {
            "filename": filename,
            "format": ext,
            "total_pages": len(pages),
            "pages": pages,
            "full_text": full_text,
            "char_count": len(full_text),
            "word_count": len(full_text.split()),
        }

    def _parse_pdf(self, file_path: str) -> list[dict]:
        """Extract text from PDF with page numbers."""
        pages = []
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                pages.append({
                    "page_number": page_num + 1,
                    "text": text.strip(),
                    "char_count": len(text.strip()),
                })
            doc.close()
        except Exception as e:
            logger.error("PDF parse error: %s", e)
            raise RuntimeError(
                "Unable to read this PDF. The file may be corrupted, "
                "password-protected, or in an unsupported format."
            )
        return pages

    def _parse_docx(self, file_path: str) -> list[dict]:
        """Extract text from DOCX. Treats the whole document as one page."""
        try:
            doc = Document(file_path)
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text.strip())
            full_text = "\n\n".join(paragraphs)
            return [{
                "page_number": 1,
                "text": full_text,
                "char_count": len(full_text),
            }]
        except Exception as e:
            logger.error("DOCX parse error: %s", e)
            raise RuntimeError(
                "Unable to read this Word document. The file may be corrupted "
                "or in an unsupported format."
            )

    def _parse_txt(self, file_path: str) -> list[dict]:
        """Extract text from TXT file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            return [{
                "page_number": 1,
                "text": text.strip(),
                "char_count": len(text.strip()),
            }]
        except Exception as e:
            logger.error("TXT parse error: %s", e)
            raise RuntimeError("Unable to read this text file.")


# ── Section Detection ─────────────────────────────────────────────────────────
SECTION_KEYWORDS = {
    "overview": ["overview", "introduction", "background", "summary", "purpose", "scope", "objective"],
    "functional_requirements": ["functional", "features", "use case", "user story", "capability", "functionality"],
    "non_functional_requirements": ["non-functional", "nfr", "performance", "scalability", "reliability", "availability"],
    "data_description": ["data", "dataset", "database", "schema", "data source", "data model", "corpus"],
    "constraints": ["constraint", "limitation", "restriction", "boundary", "assumption"],
    "performance": ["performance", "latency", "throughput", "response time", "speed", "sla"],
    "security": ["security", "privacy", "compliance", "gdpr", "hipaa", "encryption", "authentication", "authorization"],
}


def detect_sections(text: str) -> dict[str, list[str]]:
    """Detect document sections using keyword heuristics.
    Returns dict mapping section type to list of relevant text chunks.
    """
    lines = text.split("\n")
    sections: dict[str, list[str]] = {key: [] for key in SECTION_KEYWORDS}
    current_section: Optional[str] = None
    current_buffer: list[str] = []

    for line in lines:
        line_lower = line.lower().strip()
        detected = None
        for section, keywords in SECTION_KEYWORDS.items():
            if any(kw in line_lower for kw in keywords):
                # Check if this looks like a heading (short line with keyword)
                if len(line_lower.split()) <= 8:
                    detected = section
                    break

        if detected:
            # Save previous buffer
            if current_section and current_buffer:
                sections[current_section].append("\n".join(current_buffer))
            current_section = detected
            current_buffer = [line.strip()]
        elif current_section:
            current_buffer.append(line.strip())

    # Flush last buffer
    if current_section and current_buffer:
        sections[current_section].append("\n".join(current_buffer))

    return sections
