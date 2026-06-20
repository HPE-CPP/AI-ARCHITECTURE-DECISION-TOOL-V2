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
import hashlib
import logging
import re
from typing import Optional

from services.llm_client import LLMClient
from services.extraction_cache import extraction_cache
from services.document_parser import (
    get_relevant_pages,
    register_signal_keywords,
)

logger = logging.getLogger(__name__)

# ── Tunables ─────────────────────────────────────────────────────────────────
MAX_CONTEXT_CHARS       = 12_000  # single-call limit — increased to reduce chunking
MAX_TOTAL_CONTEXT_CHARS = 20_000  # hard cap before chunking: 20k → ≤4 chunks → ~14k tokens
CHUNK_SIZE              = 5_000   # chars per chunk when splitting large docs
CHUNK_OVERLAP           = 500     # overlap so signals spanning chunk boundaries are caught
# ─────────────────────────────────────────────────────────────────────────────

SIGNAL_SCHEMA = {
    "dataset_size": {
        "description": "Volume of data",
        "keywords": ["dataset", "data size", "records", "documents", "entries", "rows", "corpus", "training data", "million", "billion", "terabyte", "gigabyte"],
    },
    "query_volume": {
        "description": "Expected query/request throughput",
        "keywords": ["query", "queries per", "requests", "qps", "throughput", "concurrent", "traffic", "load"],
    },
    "latency_requirement": {
        "description": "Response time needs",
        "keywords": ["latency", "response time", "real-time", "millisecond", "fast", "speed", "delay", "sla"],
    },
    "data_volatility": {
        "description": "How frequently data changes",
        "keywords": ["update", "frequency", "volatile", "dynamic", "refresh", "change", "real-time data", "streaming"],
    },
    "accuracy_requirement": {
        "description": "Accuracy/precision needs",
        "keywords": ["accuracy", "precision", "recall", "f1", "quality", "correct", "reliable", "hallucination"],
    },
    "domain_specificity": {
        "description": "How specialized the domain is",
        "keywords": ["domain", "specialized", "expert", "medical", "legal", "financial", "technical", "niche", "industry"],
    },
    "security_level": {
        "description": "Security/privacy requirements",
        "keywords": ["security", "privacy", "compliance", "gdpr", "hipaa", "pci", "encryption", "classified", "confidential"],
    },
    "cost_sensitivity": {
        "description": "Budget constraints",
        "keywords": ["cost", "budget", "expensive", "cheap", "affordable", "pricing", "roi", "resource"],
    },
    "deployment_preference": {
        "description": "Where to deploy",
        "keywords": ["deploy", "cloud", "on-premise", "on-prem", "edge", "local", "aws", "azure", "gcp", "self-hosted"],
    },
    "user_scale": {
        "description": "Number of end users",
        "keywords": ["users", "user base", "scale", "organization", "team", "enterprise", "consumer", "public"],
    },
    "citation_requirement": {
    "description": "How important it is to explain or cite sources for answers",
    "keywords": ["explainability", "explain", "citation", "cite sources", "audit trail", "transparency", "interpretable", "traceable", "reasoning", "justification"],
    },
    "context_size": {
    "description": "How much knowledge/context needs to be available per query",
    "keywords": ["context window", "context size", "knowledge base size", "corpus size", "fits in context", "bounded corpus", "context length"],
    },
}

# Flat keyword set — registered with document_parser so it can score pages
_ALL_KEYWORDS: frozenset[str] = frozenset(
    kw for schema in SIGNAL_SCHEMA.values() for kw in schema["keywords"]
)
register_signal_keywords(_ALL_KEYWORDS)

EXTRACTION_PROMPT = """You are an expert AI architecture analyst. Read the document and extract 10 architecture signals as JSON.

SIGNAL NAMES AND ALLOWED VALUES — you must use EXACTLY these strings for "value":
  dataset_size:          "small" | "medium" | "large" | "very_large"
  query_volume:          "low" | "medium" | "high" | "very_high"
  latency_requirement:   "relaxed" | "moderate" | "strict" | "ultra_low"
  data_volatility:       "static" | "low" | "moderate" | "high"
  accuracy_requirement:  "moderate" | "high" | "very_high" | "critical"
  domain_specificity:    "general" | "moderate" | "specialized" | "highly_specialized"
  security_level:        "standard" | "elevated" | "high" | "critical"
  cost_sensitivity:      "low" | "moderate" | "high" | "very_high"
  deployment_preference: "cloud" | "on_premise" | "hybrid" | "edge"
  user_scale:            "small" | "medium" | "large" | "enterprise"
  citation_requirement:  "low" | "moderate" | "high" | "critical"
  context_size:          "small" | "medium" | "large" | "very_large"

HOW TO PICK THE RIGHT VALUE — infer from context even if not stated word-for-word:
  dataset_size:          GB/TB of documents or millions of records → "large"; hundreds of GBs or billions of records → "very_large"; thousands of records → "small"
  query_volume:          hundreds of daily users / internal tool → "low"; thousands req/day → "medium"; high-traffic / >1000 QPS → "high"
  latency_requirement:   "under 2 seconds" or ">1s acceptable" → "relaxed"; "under 1 second" → "moderate"; "real-time / <100ms" → "strict"; "<50ms" → "ultra_low"
  data_volatility:       "updated daily" or continuous data → "moderate"; "updated weekly/monthly" → "low"; "real-time streaming" → "high"; "historical archive" → "static"
  accuracy_requirement:  "avoid hallucination / cite sources / no wrong answers" → "very_high"; ONLY use "critical" for regulated clinical (FDA/HIPAA), financial-trading (SEC/MiFID), or safety-of-life systems where errors have legal/medical consequences. Customer-facing production → "high"; internal prototype → "moderate". Do NOT pick "critical" just because the doc mentions "compliance" or "reputational risk" — that is "very_high".
  domain_specificity:    Internal company knowledge, support tickets, product manuals, internal procedures, standard industry vocabulary → "specialized" (RAG can retrieve this; no need to over-classify). General Q&A → "general". "highly_specialized" is reserved for domains with PROPRIETARY VOCABULARIES that general LLMs cannot reason over without training: clinical radiology codes, quantitative-finance derivatives terminology, specialised legal precedent. Most "specialized" business domains are NOT "highly_specialized".
  security_level:        "internal procedures / on-premise required" → "elevated"; HIPAA/GDPR/PCI/classified → "high" or "critical"; public data → "standard"
  cost_sensitivity:      "cost efficiency important / budget conscious" → "high"; "strict budget constraints" → "very_high"; unlimited budget → "low"
  deployment_preference: "on-premise / private cloud / self-hosted" → "on_premise"; AWS/GCP/Azure → "cloud"; "both cloud and on-prem" → "hybrid"; IoT/edge devices → "edge"
  user_scale:            "<100 users / small team" → "small"; "100-1000" → "medium"; "1000-10000" → "large"; ">10000 or enterprise-wide" → "enterprise"
  citation_requirement: "audit trail / must cite sources / regulatory traceability" → "critical"; "citations required" → "high"; "some reasoning" → "moderate"; internal tool no explanation needed → "low"
  context_size:               fits in a prompt / bounded corpus → "small"; moderate KB → "medium"; large document corpus → "large"; massive multi-domain corpus → "very_large"

CONFIDENCE SCALE:
  0.0   = signal not mentioned at all (use null for value too)
  0.3   = weakly implied or general context
  0.5   = moderately clear from context
  0.7   = clearly stated
  0.9   = explicitly defined with numbers or keywords

IMPORTANT RULES:
1. For "value": use null ONLY when the document provides absolutely zero signal for that dimension. Otherwise infer.
2. For "source_text": copy one exact sentence from the document. Use "" if no suitable sentence exists.
3. Set confidence >= 0.3 whenever you can infer a reasonable value.
4. Output raw JSON only — no markdown, no explanation, no code blocks.

EXAMPLE OUTPUT (fill in your actual findings from the document):
{"dataset_size": {"value": "large", "confidence": 0.8, "source_text": "The total estimated dataset size is 120 GB", "page_number": 1}, "query_volume": {"value": "low", "confidence": 0.6, "source_text": "500 daily users", "page_number": 1}, "latency_requirement": {"value": "relaxed", "confidence": 0.7, "source_text": "response time must be under 2 seconds", "page_number": 1}, "data_volatility": {"value": "moderate", "confidence": 0.7, "source_text": "Support tickets are added daily", "page_number": 1}, "accuracy_requirement": {"value": "very_high", "confidence": 0.8, "source_text": "avoid hallucinating answers", "page_number": 1}, "domain_specificity": {"value": "specialized", "confidence": 0.7, "source_text": "Internal knowledge base articles", "page_number": 1}, "security_level": {"value": "elevated", "confidence": 0.7, "source_text": "documents contain internal procedures", "page_number": 1}, "cost_sensitivity": {"value": "high", "confidence": 0.6, "source_text": "cost efficiency is important", "page_number": 1}, "deployment_preference": {"value": "on_premise", "confidence": 0.8, "source_text": "prefer on-premise deployment", "page_number": 1}, "user_scale": {"value": "small", "confidence": 0.7, "source_text": "500 daily users", "page_number": 1}}

RETRIEVED CONTEXT (if any):
RETRIEVED_CONTEXT_PLACEHOLDER

DOCUMENT:
DOCUMENT_TEXT_PLACEHOLDER
"""

# Prompt fingerprint — automatically invalidates stale cache entries when the prompt changes.
_PROMPT_FINGERPRINT = hashlib.md5(EXTRACTION_PROMPT.encode()).hexdigest()[:8]

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
    "citation_requirement": [
        {"value": "low",      "label": "Low (No explanation needed)"},
        {"value": "moderate", "label": "Moderate (Some reasoning expected)"},
        {"value": "high",     "label": "High (Citations required)"},
        {"value": "critical", "label": "Critical (Full audit trail mandatory)"},
    ],
    "context_size": [
        {"value": "small",      "label": "Can fit a few documents in memory"},
        {"value": "medium",     "label": "Can fit dozens of documents in memory"},
        {"value": "large",      "label": "Can fit hundreds of documents in memory"},
        {"value": "very_large", "label": "Too much information to keep in memory at once"},
    ],
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
        # Retrieved context from FAISS — supplementary only; NOT used for cache key
        # or source verification so same document always yields the same cache key.
        retrieved_context = document_data.get("retrieved_context", "")

        if not full_text.strip():
            return self._empty_signals()

        # ── 1. Cache check ────────────────────────────────────────────────────
        # Cache key = prompt fingerprint + document text (MD5 of the key string
        # is NOT computed here — the raw string is used as the dict key inside
        # extraction_cache which handles its own hashing).
        # The prompt fingerprint automatically invalidates stale entries when
        # EXTRACTION_PROMPT changes — no manual cache flush required.
        _cache_key = f"p:{_PROMPT_FINGERPRINT}\x00{full_text}"
        cached = extraction_cache.get(_cache_key)
        if cached is not None:
            logger.info("Extraction cache HIT (prompt=%s) — skipping LLM call", _PROMPT_FINGERPRINT)
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

        # Hard cap: prevents too many LLM chunks on large documents.
        # 20k chars → max 4 chunks → ~14k tokens → stays within Groq free-tier TPM limit.
        if len(context) > MAX_TOTAL_CONTEXT_CHARS:
            context = context[:MAX_TOTAL_CONTEXT_CHARS]

        # ── 5. LLM extraction — single call or parallel chunks ─────────────────
        if len(context) <= MAX_CONTEXT_CHARS:
            llm_signals = await self._llm_extraction(context, retrieved_context)
            logger.info("Single-call extraction (%d chars)", len(context))
        else:
            llm_signals = await self._parallel_chunk_extraction(context, retrieved_context)

        # ── 5b. Heuristic fallback ─────────────────────────────────────────────
        # If the LLM returned 0 values (timeout, wrong format, not running),
        # run the regex-based heuristic extractor instead.  Heuristics are
        # transparent and reliable for well-structured requirements documents.
        llm_found = sum(1 for s in llm_signals.values() if s.get("value"))
        if llm_found == 0:
            logger.warning(
                "LLM returned 0 signals — activating heuristic extraction fallback"
            )
            llm_signals = self._heuristic_extraction(full_text, pages)

        # ── 6. Source verification (against original full_text + pages) ────────
        llm_signals = self._verify_sources(llm_signals, full_text, pages)

        # ── 7. Merge keyword + LLM/heuristic results ──────────────────────────
        merged = self._merge_signals(keyword_signals, llm_signals)

        # ── 8. Cache result ───────────────────────────────────────────────────
        extraction_cache.set(_cache_key, merged)

        return merged

    def extract_from_questionnaire(self, answers: dict) -> dict[str, dict]:
        """Convert questionnaire answers to signal format."""
        signals = {}
        for key in SIGNAL_SCHEMA:
            if key in answers and answers[key]:
                signals[key] = {
                    "value": answers[key],
                    # 0.85 rather than 1.0: the user picks the closest option,
                    # not their exact requirement. This lets overall confidence
                    # vary meaningfully with coverage (answered questions).
                    # e.g. 10/10 answered → ~89%, 7/10 → ~80%, 5/10 → ~74%
                    "confidence": 0.85,
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

    async def _llm_extraction(self, text: str, retrieved_context: str = "") -> dict[str, dict]:
        """Single LLM call for signal extraction."""
        try:
            ctx_body = retrieved_context.strip() if retrieved_context else "(none)"

            # Guard: if retrieved_context pushes combined size over MAX_CONTEXT_CHARS,
            # trim it rather than letting the LLM client silently truncate the document.
            overhead = len(EXTRACTION_PROMPT) - len("RETRIEVED_CONTEXT_PLACEHOLDER") - len("DOCUMENT_TEXT_PLACEHOLDER")
            budget = MAX_CONTEXT_CHARS - overhead - len(text)
            if budget < 0:
                # Document itself already exceeds budget — trim it
                text = text[:MAX_CONTEXT_CHARS - overhead - 200]
                ctx_body = "(none)"
            elif len(ctx_body) > budget:
                ctx_body = ctx_body[:budget]

            # Use str.replace() — NOT .format() — because document text may contain
            # literal curly braces (JSON, code, templates) that break str.format().
            prompt = (
                EXTRACTION_PROMPT
                .replace("RETRIEVED_CONTEXT_PLACEHOLDER", ctx_body)
                .replace("DOCUMENT_TEXT_PLACEHOLDER", text)
            )
            result = await self.llm.generate_json(prompt=prompt)

            if "error" in result:
                logger.error(
                    "LLM extraction returned error: %s. "
                    "Check that Ollama/OpenAI is running and the model is loaded.",
                    result.get("error", "unknown"),
                )
                return self._empty_signals()

            # Unwrap if LLM nested signals inside a wrapper key
            # e.g. {"signals": {...}} or {"architecture_signals": {...}}
            if not any(k in result for k in SIGNAL_SCHEMA):
                for wrapper in ("signals", "architecture_signals", "result",
                                "data", "output", "extraction", "analysis"):
                    if wrapper in result and isinstance(result[wrapper], dict):
                        result = result[wrapper]
                        logger.debug("Unwrapped LLM JSON from key '%s'", wrapper)
                        break

            validated: dict[str, dict] = {}
            found_count = 0
            for key in SIGNAL_SCHEMA:
                if key in result and isinstance(result[key], dict):
                    sig = result[key]
                    raw_value = sig.get("value")
                    # Treat JSON null, the string "null", and empty string as absent
                    value = None if raw_value in (None, "null", "", "N/A", "n/a") else raw_value
                    conf = min(1.0, max(0.0, float(sig.get("confidence", 0) or 0)))
                    if value:
                        found_count += 1
                    validated[key] = {
                        "value": value,
                        "confidence": conf,
                        "source_text": str(sig.get("source_text", "") or "")[:300],
                        "page_number": int(sig.get("page_number", 0) or 0),
                    }
                else:
                    validated[key] = {
                        "value": None,
                        "confidence": 0.0,
                        "source_text": "",
                        "page_number": 0,
                    }

            logger.info("LLM extracted %d/%d signals with values", found_count, len(SIGNAL_SCHEMA))
            return validated

        except Exception as e:
            logger.error(
                "LLM extraction failed: %s. "
                "Verify Ollama is running (`ollama serve`) and model is pulled (`ollama pull llama3.2`)",
                e,
            )
            return self._empty_signals()

    async def _parallel_chunk_extraction(self, text: str, retrieved_context: str = "") -> dict[str, dict]:
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

        async def _bounded_extraction(chunk: str, ctx: str = "") -> dict:
            async with semaphore:
                return await self._llm_extraction(chunk, ctx)

        # Pass retrieved_context only to the first chunk to avoid inflating token
        # usage across all parallel calls.
        tasks = [
            _bounded_extraction(chunk, retrieved_context if i == 0 else "")
            for i, chunk in enumerate(chunks)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

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
        Falls back to fuzzy recovery. Does NOT penalise confidence on failure —
        the value itself can be correct even when the exact quote isn't verbatim.
        Penalising confidence here caused valid signals to be nulled downstream
        by the anti-hallucination threshold, dramatically degrading recall.
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

            # Mark unverified but do NOT touch confidence — a slightly paraphrased
            # quote does not invalidate the extracted value.
            logger.debug("Source for '%s' not verified (value kept)", key)
            sig["source_verified"] = False

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

    # ── Heuristic extraction (LLM-independent fallback) ───────────────────────

    # Each entry: (regex_pattern_string, value_or_"NUM", confidence)
    # Patterns are tried in order; first match wins for each signal.
    _HEURISTIC_RULES: dict[str, list] = {
        "dataset_size": [
            (r"\d+(?:\.\d+)?\s*(?:pb|petabyte)", "very_large", 0.75),
            (r"\d+(?:\.\d+)?\s*(?:tb|terabyte)", "very_large", 0.72),
            (r"\b(?:[5-9]\d{2}|\d{4,})(?:\.\d+)?\s*gb\b", "very_large", 0.68),
            (r"\b\d+(?:\.\d+)?\s*gb\b", "large", 0.65),
            (r"billions?\s+of\s+\w+", "very_large", 0.68),
            (r"hundreds?\s+of\s+millions?\s+of\s+\w+", "very_large", 0.65),
            (r"millions?\s+of\s+\w+", "large", 0.65),
            (r"hundreds?\s+of\s+thousands?\s+of\s+\w+", "medium", 0.60),
            (r"tens?\s+of\s+thousands?\s+of\s+\w+", "medium", 0.58),
            (r"thousands?\s+of\s+\w+", "small", 0.55),
            (r"hundreds?\s+of\s+\w+", "small", 0.50),
            # Bounded-corpus indicators — strong CAG signal.
            (r"\bfits?\s+(?:in|within|comfortably\s+(?:in|within))\s+(?:the\s+)?context", "small", 0.78),
            (r"\bbounded\s+corpus\b|\bclosed\s+corpus\b|\bsmall\s+(?:and\s+)?(?:bounded|fixed|well[\s-]?defined)\s+(?:corpus|dataset|knowledge)", "small", 0.75),
            # Numeric template/article counts (typical for legal/SOP docs).
            (r"\b(\d{1,3})\s+(?:standard\s+)?(?:templates?|contracts?|playbooks?|policies)\b", "small", 0.65),
            # Numeric page counts — useful for compact knowledge bases.
            (r"\b(\d+)\s+pages?\b", "NUM_PAGES", 0.60),
        ],
        "query_volume": [
            (r"\d[\d,]*\s*(?:qps|queries?\s+per\s+second|req(?:uests?)?\s+per\s+second)", "NUM_QPS", 0.80),
            # "N queries per minute" — convert to qps via factor 60.
            (r"\b(\d[\d,]*)\s+(?:queries?|requests?|req\w*)\s+per\s+minute\b", "NUM_QPM", 0.78),
            # "N queries/requests/scans per day" (word order: number-noun-perday).
            (r"\b(\d[\d,]*)\s+(?:queries?|requests?|req\w*|scans?|transactions?)\s+per\s+day\b", "NUM_DAILY", 0.72),
            # Original: "per day queries" (less common).
            (r"\b\d[\d,]*\s+(?:daily|per\s+day)\s+(?:users?|queries?|req\w*)", "NUM_DAILY", 0.70),
            (r"\b(?:query\s+)?volume\s+is\s+low\b|\blow[\s-]?volume\b", "low", 0.70),
            (r"\bhigh[\s-]?volume\b", "high", 0.65),
            (r"\bhigh\s+(?:traffic|throughput|load|concurren)", "high", 0.62),
            (r"\bconcurrent\s+(?:users?|sessions?|requests?)", "high", 0.55),
            (r"\bsmall\s+team\b|\binternal\s+(?:tool|use\s+only)\b", "low", 0.58),
            (r"\bfew\s+(?:users?|employees?)\b", "low", 0.55),
        ],
        "latency_requirement": [
            (r"(?:under|less\s+than|within|<)\s*50\s*ms", "ultra_low", 0.85),
            (r"(?:under|less\s+than|within|<)\s*(?:100|150|200)\s*ms", "strict", 0.82),
            (r"(?:under|less\s+than|within|<)\s*(?:0\.5|500\s*ms|half\s+a\s+second)", "strict", 0.78),
            (r"(?:under|less\s+than|within|<)\s*1\s*s(?:ec(?:ond)?)?(?!\d)", "moderate", 0.82),
            (r"(?:under|less\s+than|within|<)\s*[12]\s*s(?:ec(?:ond)?)?(?!\d)", "relaxed", 0.80),
            (r"\breal[\s-]?time\b(?!\s+streaming)", "strict", 0.62),
            (r"\bsub[\s-]?second\b", "strict", 0.72),
            (r"\blow[\s-]?latency\b", "strict", 0.62),
            (r"\bbatch\s+process(?:ing)?\b|\boffline\b|\basynchronous\b", "relaxed", 0.68),
        ],
        "data_volatility": [
            # "feed" → "feeds?" so plural "feeds" matches (was the doc 04 bug).
            (r"\breal[\s-]?time\s+(?:streaming|data|feeds?|updates?|ingestion|market\s+data)\b", "high", 0.78),
            (r"\b(?:continuously?|constantly|frequently)\s+(?:updat|chang|refresh)", "high", 0.68),
            (r"\bstream(?:ing|ed)\s+(?:data|feeds?|updates?)\b", "high", 0.74),
            (r"\b(?:add|updat|refresh)\w*\s+(?:daily|every\s+day)\b", "low", 0.72),
            (r"\b(?:add|updat|refresh)\w*\s+(?:hourly|every\s+hour)\b", "moderate", 0.75),
            (r"\b(?:add|updat|refresh)\w*\s+(?:weekly|every\s+week|each\s+week)\b", "low", 0.72),
            (r"\b(?:add|updat|refresh)\w*\s+(?:monthly|every\s+month)\b", "low", 0.68),
            (r"\b(?:updated|reviewed)\s+(?:and\s+\w+\s+)?(?:annually|yearly|once\s+(?:per|a)\s+year)\b", "static", 0.74),
            (r"\b(?:add|updat|refresh)\w*\s+quarterly\b", "low", 0.68),
            (r"\bstatic\b|\barchiv\w*\b|\bhistorical\s+(?:archive|record|data)\b|\brarely\s+chang", "static", 0.74),
            (r"\bimmutable\b|\bno\s+updates?\b", "static", 0.72),
        ],
        "accuracy_requirement": [
            (r"\bhallucinat\w+\b", "very_high", 0.82),
            (r"\bcite\s+sources?\b|\bsource\s+(?:citation|verification|grounding)\b", "very_high", 0.78),
            (r"\bHIPAA\b|\bGDPR\b|\bPCI\b|\bFDA\b|\bSOX\b|\bSOC\s*2\b", "critical", 0.85),
            (r"\b(?:medical|healthcare|clinical|pharmaceutical)\b", "critical", 0.72),
            (r"\b(?:legal|law\s+firm|litigation|jurisprudence)\b", "critical", 0.72),
            (r"\bfinancial\s+(?:compliance|regulation|audit)\b", "critical", 0.70),
            (r"\bhigh\s+accuracy\b|\bprecise\s+answers\b|\bfactually?\s+correct\b", "high", 0.68),
            (r"\bcustomer[\s-]?facing\b|\bproduction[\s-]?grade\b", "high", 0.62),
            (r"\binternal\s+(?:tool|use\s+only|prototype)\b", "moderate", 0.55),
        ],
        "domain_specificity": [
            (r"\b(?:medical|healthcare|clinical|pharmaceutical|biotech)\b", "highly_specialized", 0.78),
            (r"\b(?:legal|law|jurisprudence|compliance\s+regulation)\b", "highly_specialized", 0.75),
            (r"\bproprietary\s+(?:knowledge|data|information)\b", "highly_specialized", 0.72),
            (r"\binternal\s+(?:knowledge\s+base|procedures?|documentation|support)\b", "specialized", 0.70),
            (r"\bsupport\s+(?:tickets?|cases?|documentation)\b", "specialized", 0.65),
            (r"\bcompany[\s-]?(?:specific|internal|proprietary)\b", "specialized", 0.65),
            (r"\bdomain[\s-]?specific\b|\bspecializ\w+\b|\bniche\b", "specialized", 0.62),
            (r"\bgeneral[\s-]?purpose\b|\bgeneral\s+(?:knowledge|assistant|chat)\b", "general", 0.65),
        ],
        "security_level": [
            (r"\bHIPAA\b|\bGDPR\b|\bPCI[\s-]?DSS\b|\bFedRAMP\b|\bITAR\b|\btop\s+secret\b|\bclassified\b", "critical", 0.88),
            (r"\bPII\b|\bpersonal(?:ly\s+identifiable)?\s+(?:information|data)\b|\bsensitive\s+data\b", "high", 0.78),
            (r"\bconfidential\b|\brestricted\s+(?:data|access)\b", "high", 0.72),
            (r"\bon[\s-]?premise\b|\bprivate\s+cloud\b|\bself[\s-]?hosted\b", "elevated", 0.65),
            (r"\binternal\s+(?:procedures?|documents?|use\s+only|data)\b", "elevated", 0.62),
            (r"\bpublic\s+(?:data|information|api|dataset)\b|\bopen\s+(?:source|data)\b", "standard", 0.62),
        ],
        "cost_sensitivity": [
            (r"\bvery\s+(?:tight|limited|strict)\s+budget\b|\bno\s+budget\b|\bminimal\s+cost\b", "very_high", 0.78),
            (r"\bcost[\s-]?(?:effective|efficient|optimization|sensitive|important|conscious)\b", "high", 0.72),
            (r"\bbudget[\s-]?(?:conscious|constrained|limited)\b|\baffordab\w+\b", "high", 0.70),
            (r"\bROI\b|\breturn\s+on\s+investment\b|\bcost\s+reduction\b", "high", 0.65),
            (r"\bbalanced\b.{0,30}(?:cost|budget)\b|\bmoderate\s+(?:cost|budget)\b", "moderate", 0.60),
            (r"\bperformance\s+at\s+any\s+cost\b|\bunlimited\s+budget\b|\benterprise[\s-]?grade\s+budget\b", "low", 0.72),
        ],
        "deployment_preference": [
            (r"\bhybrid\s+cloud\b|\bboth\s+cloud\s+and\s+on[\s-]?prem|\bon[\s-]?prem\w*\s+(?:and|or)\s+cloud", "hybrid", 0.82),
            (r"\bself[\s-]?hosted\b|\bon[\s-]?premise\b|\bon[\s-]?prem\b|\bdata\s+cent(?:er|re)\b", "on_premise", 0.82),
            (r"\bprivate\s+cloud\b|\bsecure\s+(?:private\s+)?cloud\b", "on_premise", 0.72),
            (r"\bAWS\b|\bAmazon\s+Web\s+Services\b|\bGoogle\s+Cloud\b|\bGCP\b|\bAzure\b|\bMicrosoft\s+Azure\b", "cloud", 0.85),
            (r"\bcloud[\s-]?native\b|\bSaaS\b|\bmanaged\s+cloud\b", "cloud", 0.72),
            (r"\bedge\s+(?:computing|devices?|deployment|inference)\b|\bIoT\b|\bembedded\b|\boffline\s+device", "edge", 0.82),
        ],
        "user_scale": [
            (r"\b(\d[\d,]*)\s*k?\s+(?:daily\s+)?(?:active\s+)?users?\b", "NUM_USERS", 0.78),
            (r"\b(\d[\d,]*)\s+(?:enterprise\s+)?(?:analysts?|associates?|radiologists?|agents?|managers?|specialists?|consultants?|operators?|employees?)\b", "NUM_USERS", 0.72),
            (r"\benterprise[\s-]?wide\b|\bcompany[\s-]?wide\b|\borganization[\s-]?wide\b", "enterprise", 0.75),
            (r"\bFortune\s+500\b|\bmultinational\b|\bglobal\s+(?:org|organization|company|workforce)\b", "enterprise", 0.78),
            (r"\blarge\s+(?:organization|company|enterprise|corporation)\b", "large", 0.65),
            (r"\bsmall\s+(?:team|company|startup)\b|\bfew\s+(?:users?|employees?|people)\b", "small", 0.65),
            (r"\bpilot\b|\bprototype\b|\bproof\s+of\s+concept\b|\bPoC\b", "small", 0.58),
        ],
        "citation_requirement": [
    (r"\baudit\s+trail\b|\bfull\s+(?:audit|traceability)\b|\bregulatory\s+(?:audit|compliance)\b", "critical", 0.82),
    (r"\bcite\s+sources?\b|\bsource\s+citation\b|\btraceab\w+\b|\bverif\w+\s+sources?\b", "high", 0.78),
    (r"\bexplain\w*\s+(?:the\s+)?(?:answer|reasoning|decision)\b|\btransparent\b|\binterpretab\w+\b", "high", 0.72),
    (r"\bsome\s+(?:reasoning|explanation)\b|\bjustif\w+\b", "moderate", 0.62),
    (r"\bno\s+(?:explanation|citation)\s+(?:needed|required)\b|\binternal\s+tool\b", "low", 0.58),
],
"context_size": [
    (r"\bfits?\s+(?:in|within)\s+(?:the\s+)?(?:context|prompt)\b|\bbounded\s+corpus\b|\bsmall\s+(?:and\s+)?(?:bounded|fixed)\s+(?:corpus|dataset)\b", "small", 0.80),
    (r"\bmassive\s+(?:corpus|knowledge\s+base|dataset)\b|\bmulti[\s-]?domain\b", "very_large", 0.75),
    (r"\blarge\s+(?:corpus|knowledge\s+base|document\s+set)\b", "large", 0.72),
    (r"\bmoderate[\s-]?sized?\s+(?:corpus|knowledge\s+base)\b", "medium", 0.65),
],
    }

    # Compiled once at class-definition time
    _COMPILED_HEURISTICS: dict[str, list] = {}

    @classmethod
    def _get_compiled_heuristics(cls) -> dict[str, list]:
        if not cls._COMPILED_HEURISTICS:
            cls._COMPILED_HEURISTICS = {
                sig: [(re.compile(pat, re.IGNORECASE), val, conf) for pat, val, conf in rules]
                for sig, rules in cls._HEURISTIC_RULES.items()
            }
        return cls._COMPILED_HEURISTICS

    # Words that, when appearing within NEGATION_WINDOW chars before a
    # matched pattern, invalidate that match. Without this guard the extractor
    # converts "no real-time streaming requirement" into volatility=high and
    # "no expectation of high concurrency" into query_volume=high.
    _NEGATION_PREFIXES = re.compile(
        r"\b(?:no|not|never|without|zero|none|n['o]t|nor|cannot|can'?t|won'?t)\s+"
        r"(?:\w+\s+){0,3}$",
        re.IGNORECASE,
    )
    _NEGATION_WINDOW = 60  # chars to look back

    def _is_negated(self, text: str, match_start: int) -> bool:
        """True if a negation word appears within the lookback window."""
        window_start = max(0, match_start - self._NEGATION_WINDOW)
        prefix = text[window_start:match_start]
        return bool(self._NEGATION_PREFIXES.search(prefix))

    def _heuristic_extraction(self, text: str, pages: list[dict]) -> dict[str, dict]:
        """
        Regex/pattern-based signal extraction — runs as a fallback when the LLM
        returns 0 signals (e.g., Ollama not running, wrong JSON format, timeout).

        Returns values with moderate confidence (0.4-0.85) derived from explicit
        text patterns.  Much cheaper than an LLM call and surprisingly accurate for
        well-structured requirements documents.
        """
        compiled = self._get_compiled_heuristics()
        signals: dict[str, dict] = {}

        for sig, rules in compiled.items():
            matched_value: Optional[str] = None
            matched_conf: float = 0.0
            matched_src: str = ""

            for pattern, value_template, conf in rules:
                # Find first non-negated match. A raw .search() ignores
                # surrounding context, so "no real-time" still matches
                # "real-time" — we iterate and skip negated occurrences.
                m = None
                for candidate in pattern.finditer(text):
                    if not self._is_negated(text, candidate.start()):
                        m = candidate
                        break
                if not m:
                    continue

                # Resolve numeric sentinel values
                value: Optional[str] = None
                if value_template == "NUM_QPS":
                    num_str = re.sub(r"[,\s]", "", m.group(0).split()[0])
                    try:
                        qps = float(num_str)
                        if qps >= 1000:
                            value = "very_high"
                        elif qps >= 100:
                            value = "high"
                        elif qps >= 10:
                            value = "medium"
                        else:
                            value = "low"
                    except ValueError:
                        continue

                elif value_template == "NUM_QPM":
                    raw = re.sub(r",", "", m.group(1)) if m.lastindex and m.group(1) else "0"
                    try:
                        qpm = float(raw)
                        qps = qpm / 60.0
                        if qps >= 1000:
                            value = "very_high"
                        elif qps >= 100:
                            value = "high"
                        elif qps >= 10:
                            value = "medium"
                        else:
                            value = "low"
                    except ValueError:
                        continue

                elif value_template == "NUM_DAILY":
                    raw = re.sub(r",", "", m.group(1)) if m.lastindex and m.group(1) else re.sub(r"[,\s]", "", m.group(0).split()[0])
                    try:
                        daily = float(raw)
                        # daily volume → bucket on absolute daily count.
                        if daily >= 1_000_000:
                            value = "very_high"
                        elif daily >= 10_000:
                            value = "high"
                        elif daily >= 500:
                            value = "medium"
                        else:
                            value = "low"
                    except ValueError:
                        continue

                elif value_template == "NUM_PAGES":
                    raw = re.sub(r",", "", m.group(1)) if m.lastindex and m.group(1) else ""
                    try:
                        pages_count = int(raw) if raw else 0
                        if pages_count <= 2000:
                            value = "small"
                        elif pages_count <= 50_000:
                            value = "medium"
                        else:
                            value = "large"
                    except ValueError:
                        continue

                elif value_template == "NUM_USERS":
                    raw = re.sub(r",", "", m.group(1)) if m.lastindex and m.group(1) else re.sub(r"[,\s]", "", m.group(0).split()[0])
                    try:
                        n = float(raw)
                        if "k" in m.group(0).lower():
                            n *= 1000
                        if n > 10_000:
                            value = "enterprise"
                        elif n > 1_000:
                            value = "large"
                        elif n >= 100:
                            value = "medium"
                        else:
                            value = "small"
                    except ValueError:
                        continue
                else:
                    value = value_template

                if value and conf > matched_conf:
                    matched_value = value
                    matched_conf = conf
                    # Extract surrounding sentence as source
                    idx = m.start()
                    sent_start = max(0, text.rfind(".", 0, idx) + 1)
                    sent_end = text.find(".", idx + len(m.group(0)))
                    if sent_end == -1:
                        sent_end = min(len(text), idx + 200)
                    matched_src = text[sent_start:sent_end].strip()[:250]
                    break  # first (highest-priority) match wins

            if matched_value:
                page_num = self._find_page_for_text(matched_src, pages)
                signals[sig] = {
                    "value": matched_value,
                    "confidence": matched_conf,
                    "source_text": matched_src,
                    "page_number": page_num,
                    "source_verified": True,
                }
            else:
                signals[sig] = {
                    "value": None,
                    "confidence": 0.0,
                    "source_text": "",
                    "page_number": 0,
                    "source_verified": False,
                }

        found = sum(1 for s in signals.values() if s.get("value"))
        logger.info("Heuristic extraction: %d/%d signals found", found, len(SIGNAL_SCHEMA))
        return signals

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

    def _infer_deployment(self, text: str) -> str | None:
        """
        Infer deployment_preference from text using heuristics alone.
        Returns the value string (e.g. "on_premise") or None if no match.
        Used by regression tests to verify specific heuristic patterns.
        """
        compiled = self._get_compiled_heuristics()
        rules = compiled.get("deployment_preference", [])
        for pattern, value, _conf in rules:
            m = None
            for candidate in pattern.finditer(text):
                if not self._is_negated(text, candidate.start()):
                    m = candidate
                    break
            if m:
                return value
        return None

    def get_missing_signals(self, signals: dict) -> list[str]:
        return [
            key for key in SIGNAL_SCHEMA
            if not signals.get(key, {}).get("value")
            or signals[key].get("confidence", 0) < 0.3
        ]
