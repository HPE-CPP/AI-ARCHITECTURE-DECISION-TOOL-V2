"""
Signal Extraction Service
Extracts architecture decision signals from document text using LLM + heuristics.

Optimizations applied:
  - Page relevance scoring: only pages containing signal keywords are sent to the LLM.
  - Smart context selection: relevant pages are selected (not a blind head-truncation).
  - Parallel chunk extraction: large documents are split into overlapping chunks and
    analysed concurrently with asyncio.gather; highest-confidence signal per chunk wins.
  - In-memory extraction cache: SHA-256 keyed, TTL 1 h — skips LLM entirely on re-upload.
  - Keyword pre-extraction still runs (zero LLM cost) and boosts final confidence.
"""
import asyncio
import json
import logging
import re
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

EXTRACTION_PROMPT = """You are an expert AI architecture analyst. Analyze the following document text and extract architecture decision signals.

For each signal, provide:
- value: the extracted value (MUST be one of the listed options, or null if not found)
- confidence: 0.0 to 1.0 (0 if not found, higher if explicitly stated)
- source_text: a VERBATIM quote copied exactly from the document that supports this value. Do NOT paraphrase, summarize, or rephrase. Copy the exact sentence or phrase as it appears in the document. If not found, use an empty string.
- page_number: the page number where the source_text appears (0 if not found)

CRITICAL RULES:
1. DO NOT hallucinate. If a signal is not mentioned in the document, set value to null and confidence to 0.
2. Only extract what is explicitly stated or strongly implied.
3. source_text MUST be a word-for-word copy from the document. Every word in your source_text must appear consecutively in the document. If you cannot find an exact quote, set source_text to "" and confidence to 0.
4. Confidence levels:
   - 0.0: Not found at all
   - 0.1-0.3: Weakly implied
   - 0.4-0.6: Moderately implied
   - 0.7-0.8: Strongly implied
   - 0.9-1.0: Explicitly stated with a verbatim source quote

SIGNALS TO EXTRACT:
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

Respond with a JSON object with signal names as keys, each containing: value, confidence, source_text, page_number.
"""

SIGNAL_OPTIONS = {
    "dataset_size": ["small", "medium", "large", "very_large"],
    "query_volume": ["low", "medium", "high", "very_high"],
    "latency_requirement": ["relaxed", "moderate", "strict", "ultra_low"],
    "data_volatility": ["static", "low", "moderate", "high"],
    "accuracy_requirement": ["moderate", "high", "very_high", "critical"],
    "domain_specificity": ["general", "moderate", "specialized", "highly_specialized"],
    "security_level": ["standard", "elevated", "high", "critical"],
    "cost_sensitivity": ["low", "moderate", "high", "very_high"],
    "deployment_preference": ["cloud", "on_premise", "hybrid", "edge"],
    "user_scale": ["small", "medium", "large", "enterprise"],
}


class SignalExtractor:
    """Extracts architecture decision signals from document text."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    # ── Public API ────────────────────────────────────────────────────────────

    async def extract_signals(self, document_data: dict) -> dict[str, dict]:
        """Extract signals with page filtering, caching, and parallel chunk analysis."""
        full_text = document_data.get("full_text", "")
        pages = document_data.get("pages", [])

        if not full_text.strip():
            return self._empty_signals()

        # ── 1. Cache check ────────────────────────────────────────────────────
        cached = extraction_cache.get(full_text)
        if cached is not None:
            return cached

        # ── 2. Keyword pre-extraction (zero LLM cost) ─────────────────────────
        keyword_signals = self._keyword_extraction(full_text, pages)

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

        # ── 7. Merge keyword + LLM results ─────────────────────────────────────
        merged = self._merge_signals(keyword_signals, llm_signals)

        # ── 8. Cache result ────────────────────────────────────────────────────
        extraction_cache.set(full_text, merged)

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
        """Split text into overlapping chunks of CHUNK_SIZE chars."""
        chunks = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + CHUNK_SIZE])
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    # ── LLM extraction ────────────────────────────────────────────────────────

    async def _llm_extraction(self, text: str) -> dict[str, dict]:
        """Single LLM call for signal extraction."""
        try:
            prompt = EXTRACTION_PROMPT.format(document_text=text)
            result = await self.llm.generate_json(prompt=prompt)

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

    def _merge_signals(self, keyword_signals: dict, llm_signals: dict) -> dict[str, dict]:
        """
        Merge keyword and LLM signals.
        LLM value takes precedence; confidence is boosted when both agree.
        Source falls back to keyword when LLM source fails verification.
        """
        merged = {}
        for key in SIGNAL_SCHEMA:
            kw = keyword_signals.get(key, {})
            llm = llm_signals.get(key, {})

            value = llm.get("value") if llm.get("value") else kw.get("value")

            kw_conf = kw.get("confidence", 0)
            llm_conf = llm.get("confidence", 0)
            if kw_conf > 0 and llm_conf > 0:
                combined_conf = min(1.0, llm_conf + kw_conf * 0.3)
            else:
                combined_conf = max(kw_conf, llm_conf)

            llm_src = llm.get("source_text", "")
            llm_verified = llm.get("source_verified", False)
            kw_src = kw.get("source_text", "")

            if llm_src and llm_verified:
                source_text = llm_src
                page_number = llm.get("page_number") or kw.get("page_number", 0)
            elif kw_src:
                source_text = kw_src
                page_number = kw.get("page_number", 0)
            else:
                source_text = llm_src
                page_number = llm.get("page_number") or 0

            merged[key] = {
                "value": value,
                "confidence": round(combined_conf, 2),
                "source_text": source_text,
                "source_verified": bool(llm_verified or (kw_src and source_text == kw_src)),
                "page_number": page_number,
            }

            if merged[key]["confidence"] < 0.1:
                merged[key]["value"] = None

        return merged

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
