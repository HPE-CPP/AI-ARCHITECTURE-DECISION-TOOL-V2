"""
Signal Extraction Service
Extracts architecture decision signals from document text using LLM + semantic + heuristics.

Determinism guarantees:
  - LLM extraction uses temperature=0.0 and seed=42 (via generate_deterministic_json).
  - Sentence-aware chunking ensures stable chunk boundaries.
  - Semantic extraction (sentence-transformers) is fully deterministic.
  - Two-pass validation reduces hallucinations for uncertain signals.

Optimizations applied:
  - Page relevance scoring: only pages containing signal keywords are sent to the LLM.
  - Smart context selection: relevant pages are selected (not a blind head-truncation).
  - Parallel chunk extraction: large documents are split into overlapping chunks and
    analysed concurrently with asyncio.gather; highest-confidence signal per chunk wins.
  - In-memory extraction cache: SHA-256 keyed, TTL 1 h — skips LLM entirely on re-upload.
  - Keyword + semantic pre-extraction runs (zero LLM cost) and boosts final confidence.
"""
import asyncio
import json
import logging
import re
import time
from typing import Optional, Any

from services.llm_client import LLMClient
from services.extraction_cache import extraction_cache
from services.document_parser import (
    get_relevant_pages,
    register_signal_keywords,
)

logger = logging.getLogger(__name__)

# ── Tunables ─────────────────────────────────────────────────────────────────
MAX_CONTEXT_CHARS = 8_000   # single-call limit; fits comfortably in 4k-token models
CHUNK_SIZE        = 5_000   # chars per chunk when splitting large docs
CHUNK_OVERLAP     = 500     # overlap so signals spanning chunk boundaries are caught
# ─────────────────────────────────────────────────────────────────────────────

SIGNAL_SCHEMA = {
    "dataset_size": {
        "description": "Volume of data (small/medium/large/very_large)",
        "keywords": ["dataset", "data size", "records", "documents", "entries", "rows", "corpus", "training data", "million", "billion", "terabyte", "gigabyte"],
    },
    "query_volume": {
        "description": "Expected query/request throughput (low/medium/high/very_high)",
        "keywords": ["query", "queries per", "requests", "qps", "throughput", "concurrent", "traffic", "load"],
    },
    "latency_requirement": {
        "description": "Response time needs (relaxed/moderate/strict/ultra_low)",
        "keywords": ["latency", "response time", "real-time", "millisecond", "fast", "speed", "delay", "sla"],
    },
    "data_volatility": {
        "description": "How frequently data changes (static/low/moderate/high)",
        "keywords": ["update", "frequency", "volatile", "dynamic", "refresh", "change", "real-time data", "streaming"],
    },
    "accuracy_requirement": {
        "description": "Accuracy/precision needs (moderate/high/very_high/critical)",
        "keywords": ["accuracy", "precision", "recall", "f1", "quality", "correct", "reliable", "hallucination"],
    },
    "domain_specificity": {
        "description": "How specialized the domain is (general/moderate/specialized/highly_specialized)",
        "keywords": ["domain", "specialized", "expert", "medical", "legal", "financial", "technical", "niche", "industry"],
    },
    "security_level": {
        "description": "Security/privacy requirements (standard/elevated/high/critical)",
        "keywords": ["security", "privacy", "compliance", "gdpr", "hipaa", "pci", "encryption", "classified", "confidential"],
    },
    "cost_sensitivity": {
        "description": "Budget constraints (low/moderate/high/very_high)",
        "keywords": ["cost", "budget", "expensive", "cheap", "affordable", "pricing", "roi", "resource"],
    },
    "deployment_preference": {
        "description": "Where to deploy (cloud/on_premise/hybrid/edge)",
        "keywords": ["deploy", "cloud", "on-premise", "on-prem", "edge", "local", "aws", "azure", "gcp", "self-hosted"],
    },
    "user_scale": {
        "description": "Number of end users (small/medium/large/enterprise)",
        "keywords": ["users", "user base", "scale", "organization", "team", "enterprise", "consumer", "public"],
    },
}

# Flat keyword set — registered with document_parser so it can score pages
_ALL_KEYWORDS: frozenset[str] = frozenset(
    kw for schema in SIGNAL_SCHEMA.values() for kw in schema["keywords"]
)
register_signal_keywords(_ALL_KEYWORDS)

EXTRACTION_PROMPT = """You are an expert AI architecture analyst performing STRICT evidence-based signal extraction.

ABSOLUTE RULES — FOLLOW WITHOUT EXCEPTION:
1. NEVER invent, guess, or fabricate values. If a signal is NOT explicitly mentioned or strongly implied in the document, you MUST set value to null and confidence to 0.0.
2. PREFER null over guessing. When uncertain, ALWAYS return null. A missing value is infinitely better than a fabricated one.
3. source_text MUST be a VERBATIM word-for-word copy from the document. Do NOT paraphrase, summarize, or rephrase.
4. confidence > 0.7 is ONLY allowed when you provide an exact verbatim quote from the document as source_text.
5. If you cannot find a direct quote, set confidence ≤ 0.5 regardless of how strongly you believe the signal exists.
6. NEVER assume requirements that are not stated. Do NOT infer from general context.

For each signal, return:
- value: one of the listed options, or null if not found/uncertain
- confidence: 0.0 to 1.0 following the strict scale below
- source_text: EXACT verbatim quote from document (empty string if none found)
- page_number: page where the quote appears (0 if not found)

CONFIDENCE SCALE:
- 0.0: Not found at all — MUST use null value
- 0.1-0.3: Weakly implied, no direct mention — MUST use null value
- 0.4-0.6: Moderately implied, indirect evidence exists
- 0.7-0.8: Strongly implied with supporting verbatim quote
- 0.9-1.0: Explicitly stated with exact verbatim source text

SIGNALS TO EXTRACT (use ONLY these exact values):
1. dataset_size: (small/medium/large/very_large) - Volume of data
2. query_volume: (low/medium/high/very_high) - Expected queries/requests
3. latency_requirement: (relaxed/moderate/strict/ultra_low) - Response time needs
4. data_volatility: (static/low/moderate/high) - How often data changes
5. accuracy_requirement: (moderate/high/very_high/critical) - Accuracy needs
6. domain_specificity: (general/moderate/specialized/highly_specialized) - Domain specialization
7. security_level: (standard/elevated/high/critical) - Security needs
8. cost_sensitivity: (low/moderate/high/very_high) - Budget constraints
9. deployment_preference: (cloud/on_premise/hybrid/edge) - Deployment target
10. user_scale: (small/medium/large/enterprise) - Number of users

DOCUMENT TEXT:
{document_text}

Respond with a JSON object. For EACH signal that lacks clear evidence, use: {{"value": null, "confidence": 0.0, "source_text": "", "page_number": 0}}
"""

SIGNAL_OPTIONS = {
    "dataset_size": [
        {"value": "small", "label": "Small (< 100k records)"},
        {"value": "medium", "label": "Medium (100k - 10M records)"},
        {"value": "large", "label": "Large (10M - 500M records)"},
        {"value": "very_large", "label": "Very Large (> 500M records)"},
    ],
    "query_volume": [
        {"value": "low", "label": "Low (< 10 QPS)"},
        {"value": "medium", "label": "Medium (10 - 100 QPS)"},
        {"value": "high", "label": "High (100 - 1000 QPS)"},
        {"value": "very_high", "label": "Very High (> 1000 QPS)"},
    ],
    "latency_requirement": [
        {"value": "relaxed", "label": "Relaxed (> 1s)"},
        {"value": "moderate", "label": "Moderate (200ms - 1s)"},
        {"value": "strict", "label": "Strict (50ms - 200ms)"},
        {"value": "ultra_low", "label": "Ultra-Low (< 50ms)"},
    ],
    "data_volatility": [
        {"value": "static", "label": "Static (rarely changes)"},
        {"value": "low", "label": "Low (daily/weekly updates)"},
        {"value": "moderate", "label": "Moderate (hourly updates)"},
        {"value": "high", "label": "High (real-time streaming)"},
    ],
    "accuracy_requirement": [
        {"value": "moderate", "label": "Moderate (general assistance)"},
        {"value": "high", "label": "High (professional use)"},
        {"value": "very_high", "label": "Very High (medical/legal)"},
        {"value": "critical", "label": "Critical (zero-hallucination)"},
    ],
    "domain_specificity": [
        {"value": "general", "label": "General Knowledge"},
        {"value": "moderate", "label": "Moderately Specialized"},
        {"value": "specialized", "label": "Highly Specialized"},
        {"value": "highly_specialized", "label": "Proprietary/Niche"},
    ],
    "security_level": [
        {"value": "standard", "label": "Standard (Public data)"},
        {"value": "elevated", "label": "Elevated (Internal data)"},
        {"value": "high", "label": "High (PII/Sensitive data)"},
        {"value": "critical", "label": "Critical (Classified data)"},
    ],
    "cost_sensitivity": [
        {"value": "low", "label": "Low (Performance at any cost)"},
        {"value": "moderate", "label": "Moderate (Balanced)"},
        {"value": "high", "label": "High (Cost optimized)"},
        {"value": "very_high", "label": "Very High (Strict budget)"},
    ],
    "deployment_preference": [
        {"value": "cloud", "label": "Cloud (AWS/GCP/Azure)"},
        {"value": "on_premise", "label": "On-Premise (Self-hosted)"},
        {"value": "hybrid", "label": "Hybrid Cloud"},
        {"value": "edge", "label": "Edge Computing"},
    ],
    "user_scale": [
        {"value": "small", "label": "Small (< 100 users)"},
        {"value": "medium", "label": "Medium (100 - 1000 users)"},
        {"value": "large", "label": "Large (1k - 10k users)"},
        {"value": "enterprise", "label": "Enterprise (> 10k users)"},
    ],
}


class SignalExtractor:
    """Extracts architecture decision signals from document text."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    # ── Public API ────────────────────────────────────────────────────────────

    async def extract_signals(self, document_data: dict) -> dict[str, dict]:
        """Extract signals with semantic matching, page filtering, caching, and parallel chunks."""
        full_text = document_data.get("full_text", "")
        pages = document_data.get("pages", [])
        extraction_start = time.monotonic()

        if not full_text.strip():
            return self._empty_signals()

        # ── 1. Cache check ────────────────────────────────────────────────────
        cached = extraction_cache.get(full_text)
        if cached is not None:
            logger.info("Extraction cache hit — skipping all extraction steps.")
            return cached

        # ── 2. Keyword pre-extraction (zero LLM cost) ─────────────────────────
        keyword_signals = self._keyword_extraction(full_text, pages)

        # ── 2b. Semantic pre-extraction (zero LLM cost) ──────────────────────
        semantic_signals = self._semantic_extraction(full_text)

        # ── 3. Page filtering: skip pages with no signal keywords ─────────────
        relevant_pages = get_relevant_pages(pages, min_score=1)
        logger.info(
            "Page filtering: %d/%d pages selected as relevant",
            len(relevant_pages), len(pages),
        )

        # ── 4. Build context from relevant pages (document order preserved) ────
        context = self._build_context(relevant_pages)

        # ── 5. LLM extraction — single call or parallel chunks ─────────────────
        if len(context) <= MAX_CONTEXT_CHARS:
            llm_signals = await self._llm_extraction(context)
            logger.info("Single-call extraction (%d chars)", len(context))
        else:
            llm_signals = await self._parallel_chunk_extraction(context)

        # ── 6. Source verification ─────────────────────────────────────────────
        llm_signals = self._verify_sources(llm_signals, full_text, pages)

        # ── 7. Two-pass validation for uncertain signals ──────────────────────
        llm_signals = await self._two_pass_validation(llm_signals, full_text)

        # ── 8. Merge keyword + semantic + LLM results ──────────────────────────
        merged = self._merge_signals(keyword_signals, llm_signals, semantic_signals)

        # ── 9. Cache result ────────────────────────────────────────────────────
        extraction_cache.set(full_text, merged)

        elapsed = time.monotonic() - extraction_start
        logger.info("Signal extraction completed in %.2fs", elapsed)

        return merged

    def extract_from_questionnaire(self, answers: dict) -> dict[str, dict]:
        """Convert questionnaire answers to signal format."""
        signals = {}
        for key in SIGNAL_SCHEMA:
            if key in answers and answers[key]:
                signals[key] = {
                    "value": answers[key],
                    "confidence": 1.0,
                    "source_text": "User questionnaire response",
                    "page_number": 0,
                    "source_verified": True,
                }
            else:
                signals[key] = {
                    "value": None,
                    "confidence": 0.0,
                    "source_text": "",
                    "page_number": 0,
                    "source_verified": False,
                }
        return signals

    # ── Context helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_context(pages: list[dict]) -> str:
        """Concatenate relevant page texts with page-number headers."""
        parts = []
        for p in pages:
            text = p.get("text", "").strip()
            if text:
                parts.append(f"[Page {p.get('page_number', '?')}]\n{text}")
        return "\n\n".join(parts)

    @staticmethod
    def _make_chunks(text: str) -> list[str]:
        """Split text into sentence-aware overlapping chunks.

        Uses the sentence-aware chunker from app.utils.embeddings to ensure
        chunk boundaries never fall mid-sentence.
        """
        try:
            from app.utils.embeddings import chunk_text
            return chunk_text(text, chunk_size=500, overlap=3)
        except ImportError:
            # Fallback to character-based chunking
            chunks = []
            start = 0
            while start < len(text):
                chunks.append(text[start : start + CHUNK_SIZE])
                start += CHUNK_SIZE - CHUNK_OVERLAP
            return chunks

    # ── LLM extraction ────────────────────────────────────────────────────────

    async def _llm_extraction(self, text: str) -> dict[str, dict]:
        """Single deterministic LLM call for signal extraction."""
        try:
            prompt = EXTRACTION_PROMPT.format(document_text=text)
            result = await self.llm.generate_deterministic_json(prompt=prompt)

            if "error" in result:
                logger.warning("LLM extraction returned error, using empty signals")
                return self._empty_signals()

            validated: dict[str, dict] = {}
            for key in SIGNAL_SCHEMA:
                if key in result and isinstance(result[key], dict):
                    sig = result[key]
                    validated[key] = {
                        "value": sig.get("value"),
                        "confidence": min(1.0, max(0.0, float(sig.get("confidence", 0)))),
                        "source_text": str(sig.get("source_text", ""))[:300],
                        "page_number": int(sig.get("page_number", 0)),
                    }
                else:
                    validated[key] = {
                        "value": None,
                        "confidence": 0.0,
                        "source_text": "",
                        "page_number": 0,
                    }
            return validated

        except Exception as e:
            logger.error("LLM extraction failed: %s", e)
            return self._empty_signals()

    async def _parallel_chunk_extraction(self, text: str) -> dict[str, dict]:
        """
        For large documents: split into overlapping chunks, extract from all chunks
        concurrently (bounded by a semaphore), then keep the highest-confidence
        signal from any chunk.
        """
        chunks = self._make_chunks(text)
        logger.info("Parallel extraction: %d chunks (~%d chars each)", len(chunks), CHUNK_SIZE)

        # B-07 FIX: Limit concurrent LLM calls to 5 to prevent OOM / rate-limit crashes.
        # return_exceptions=True ensures a single failed chunk doesn't discard all results.
        semaphore = asyncio.Semaphore(5)

        async def _bounded_extraction(chunk: str) -> dict:
            async with semaphore:
                return await self._llm_extraction(chunk)

        results = await asyncio.gather(
            *[_bounded_extraction(chunk) for chunk in chunks],
            return_exceptions=True,
        )

        # Winner-takes-all per signal: highest confidence across chunks
        merged: dict[str, dict] = self._empty_signals()
        for chunk_result in results:
            # Skip chunks that raised exceptions
            if isinstance(chunk_result, Exception):
                logger.warning("Chunk extraction failed (skipped): %s", chunk_result)
                continue
            for key, sig in chunk_result.items():
                if sig.get("confidence", 0) > merged[key].get("confidence", 0):
                    merged[key] = sig

        return merged

    # ── Keyword extraction ────────────────────────────────────────────────────

    def _keyword_extraction(self, text: str, pages: list[dict]) -> dict[str, dict]:
        """Fast keyword scan — no LLM cost, provides fallback source_text."""
        import re
        signals = {}
        text_lower = text.lower()

        # B-08 FIX: Compile regex patterns once to avoid O(n) text scan per keyword.
        if not hasattr(self, "_keyword_patterns"):
            self._keyword_patterns = {}
            for signal_name, schema in SIGNAL_SCHEMA.items():
                if schema.get("keywords"):
                    # Use \b for word boundaries to avoid partial matches if desired,
                    # but original just used substring match. We keep substring logic 
                    # but combine them into one regex automaton.
                    pattern = "|".join(re.escape(k.lower()) for k in schema["keywords"])
                    self._keyword_patterns[signal_name] = re.compile(pattern)

        for signal_name, schema in SIGNAL_SCHEMA.items():
            matches = []
            pattern = getattr(self, "_keyword_patterns", {}).get(signal_name)
            
            if pattern:
                # Find all unique keywords matched
                found_keywords = set()
                for m in pattern.finditer(text_lower):
                    kw = m.group(0)
                    if kw not in found_keywords:
                        found_keywords.add(kw)
                        idx = m.start()
                        start = max(0, text.rfind(".", 0, idx) + 1)
                        end = text.find(".", idx)
                        if end == -1:
                            end = min(len(text), idx + 200)
                        matches.append({
                            "keyword": kw,
                            "source_text": text[start:end].strip(),
                        })

            if matches:
                page_num = 0
                for page in pages:
                    if matches[0]["keyword"] in page.get("text", "").lower():
                        page_num = page.get("page_number", 0)
                        break

                signals[signal_name] = {
                    "value": None,
                    "confidence": min(0.3, len(matches) * 0.1),
                    "source_text": matches[0]["source_text"][:200],
                    "page_number": page_num,
                    "keyword_matches": len(matches),
                }
            else:
                signals[signal_name] = {
                    "value": None,
                    "confidence": 0.0,
                    "source_text": "",
                    "page_number": 0,
                    "keyword_matches": 0,
                }

        return signals

    # ── Source verification ───────────────────────────────────────────────────

    def _verify_sources(
        self, signals: dict[str, dict], full_text: str, pages: list[dict]
    ) -> dict[str, dict]:
        """
        Verify each LLM-provided source_text actually appears in the document.
        Falls back to fuzzy recovery; penalises confidence on failure.
        """
        text_lower = full_text.lower()

        for key, sig in signals.items():
            src = sig.get("source_text", "").strip()
            if not src:
                sig["source_verified"] = False
                continue

            if src.lower() in text_lower:
                sig["source_verified"] = True
                if not sig.get("page_number"):
                    sig["page_number"] = self._find_page_for_text(src, pages)
                continue

            recovered = self._fuzzy_find_source(src, full_text)
            if recovered:
                sig["source_text"] = recovered
                sig["source_verified"] = True
                sig["page_number"] = self._find_page_for_text(recovered, pages)
                continue

            logger.warning(
                "Source for '%s' not verified — penalising confidence %.2f → %.2f",
                key, sig.get("confidence", 0), sig.get("confidence", 0) * 0.5,
            )
            sig["source_verified"] = False
            sig["confidence"] = round(sig.get("confidence", 0) * 0.5, 2)

        return signals

    @staticmethod
    def _fuzzy_find_source(claimed: str, full_text: str, min_word_ratio: float = 0.6) -> str | None:
        claimed_words = claimed.lower().split()
        if len(claimed_words) < 3:
            return None
        text_lower = full_text.lower()
        for start_len in range(len(claimed_words), max(2, int(len(claimed_words) * min_word_ratio)) - 1, -1):
            fragment = " ".join(claimed_words[:start_len])
            idx = text_lower.find(fragment)
            if idx != -1:
                sent_start = max(0, full_text.rfind(".", 0, idx) + 1)
                sent_end = full_text.find(".", idx + len(fragment))
                if sent_end == -1:
                    sent_end = min(len(full_text), idx + len(fragment) + 100)
                else:
                    sent_end += 1
                return full_text[sent_start:sent_end].strip()
        return None

    @staticmethod
    def _find_page_for_text(text: str, pages: list[dict]) -> int:
        if not text or not pages:
            return 0
        text_lower = text.lower()[:120]
        for page in pages:
            if text_lower in page.get("text", "").lower():
                return page.get("page_number", 0)
        return 0

    # ── Signal merging ────────────────────────────────────────────────────────

    def _merge_signals(
        self, keyword_signals: dict, llm_signals: dict, semantic_signals: dict = None,
    ) -> dict[str, dict]:
        """
        Merge keyword, LLM, and semantic signals.
        LLM value takes precedence; confidence is boosted when multiple sources agree.
        Semantic evidence provides supporting context even without exact keyword matches.
        """
        semantic_signals = semantic_signals or {}
        merged = {}
        for key in SIGNAL_SCHEMA:
            kw = keyword_signals.get(key, {})
            llm = llm_signals.get(key, {})
            sem = semantic_signals.get(key, {})

            value = llm.get("value") if llm.get("value") else kw.get("value")

            kw_conf = kw.get("confidence", 0)
            llm_conf = llm.get("confidence", 0)
            sem_conf = sem.get("confidence", 0)

            # Multi-source confidence merging (deterministic)
            if llm_conf > 0 and kw_conf > 0 and sem_conf > 0:
                combined_conf = min(1.0, llm_conf + kw_conf * 0.2 + sem_conf * 0.15)
            elif llm_conf > 0 and kw_conf > 0:
                combined_conf = min(1.0, llm_conf + kw_conf * 0.3)
            elif llm_conf > 0 and sem_conf > 0:
                combined_conf = min(1.0, llm_conf + sem_conf * 0.2)
            else:
                combined_conf = max(kw_conf, llm_conf)

            llm_src = llm.get("source_text", "")
            llm_verified = llm.get("source_verified", False)
            kw_src = kw.get("source_text", "")
            sem_evidence = sem.get("best_sentence", "")

            if llm_src and llm_verified:
                source_text = llm_src
                page_number = llm.get("page_number") or kw.get("page_number", 0)
            elif kw_src:
                source_text = kw_src
                page_number = kw.get("page_number", 0)
            elif sem_evidence:
                source_text = sem_evidence[:300]
                page_number = 0
            else:
                source_text = llm_src
                page_number = llm.get("page_number") or 0

            merged[key] = {
                "value": value,
                "confidence": round(combined_conf, 2),
                "source_text": source_text,
                "source_verified": bool(llm_verified or (kw_src and source_text == kw_src)),
                "page_number": page_number,
                "semantic_similarity": round(sem.get("best_similarity", 0.0), 3),
            }

            if merged[key]["confidence"] < 0.1:
                merged[key]["value"] = None

        return merged

    # ── Semantic extraction ────────────────────────────────────────────────────

    @staticmethod
    def _semantic_extraction(text: str) -> dict:
        """Run semantic similarity extraction using sentence-transformers.

        Returns a dict of signal_name -> {confidence, evidence_sentences, ...}.
        Gracefully returns empty dict if sentence-transformers is not installed.
        """
        try:
            from services.semantic_extractor import extract_semantic_signals, is_available
            if not is_available():
                logger.info("Semantic extractor not available — skipping semantic extraction.")
                return {}
            result = extract_semantic_signals(text)
            found = sum(1 for v in result.values() if v.get("confidence", 0) > 0)
            logger.info("Semantic extraction found evidence for %d/%d signals", found, len(result))
            return result
        except Exception as exc:
            logger.warning("Semantic extraction failed (non-fatal): %s", exc)
            return {}

    # ── Two-pass validation ────────────────────────────────────────────────────

    async def _two_pass_validation(self, signals: dict, full_text: str) -> dict:
        """Validate uncertain signals (confidence 0.4-0.7) with a verification pass.

        For signals in the uncertain range, re-checks the extracted value against
        the source evidence. Rejects unsupported outputs.

        Returns the signals dict with updated confidences.
        """
        uncertain = {
            k: v for k, v in signals.items()
            if 0.4 <= v.get("confidence", 0) <= 0.7 and v.get("value") is not None
        }

        if not uncertain:
            return signals

        logger.info("Two-pass validation: checking %d uncertain signals", len(uncertain))

        for key, sig in uncertain.items():
            source = sig.get("source_text", "")
            value = sig.get("value", "")

            if not source:
                # No source evidence — reject the value
                signals[key]["value"] = None
                signals[key]["confidence"] = 0.0
                logger.info("Two-pass: rejected '%s' — no source evidence", key)
                continue

            # Check if source text actually exists in document
            if source.lower() not in full_text.lower():
                signals[key]["confidence"] = round(sig["confidence"] * 0.5, 2)
                if signals[key]["confidence"] < 0.4:
                    signals[key]["value"] = None
                logger.info("Two-pass: penalized '%s' — source not found in document", key)

        return signals

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _empty_signals(self) -> dict[str, dict]:
        return {
            key: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
            for key in SIGNAL_SCHEMA
        }

    def get_missing_signals(self, signals: dict) -> list[str]:
        return [
            key for key in SIGNAL_SCHEMA
            if not signals.get(key, {}).get("value")
            or signals[key].get("confidence", 0) < 0.3
        ]

