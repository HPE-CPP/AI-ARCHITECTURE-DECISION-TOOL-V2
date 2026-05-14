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
from config import settings

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
CRITICAL RULES:
1. DO NOT hallucinate. If a signal is not mentioned in the document, set value to null and confidence to 0.
2. Only extract what is explicitly stated or strongly implied.
3. source_text MUST be a word-for-word copy from the document. Every word in your source_text must appear consecutively in the document. If you cannot find an exact quote, set source_text to "" and confidence to 0.
4. VALUE MUST BE EXACT: Use ONLY the exact option strings listed below — including underscores. For example write "very_high" not "very high", "very_large" not "very large", "on_premise" not "on-premise", "highly_specialized" not "highly specialized". Any value that is not exactly one of the listed options will be REJECTED.
5. Confidence levels:
   - 0.0: Not found at all
   - 0.1-0.3: Weakly implied
   - 0.4-0.6: Moderately implied
   - 0.7-0.8: Strongly implied
   - 0.9-1.0: Explicitly stated with a verbatim source quote

SIGNALS TO EXTRACT:
1. dataset_size: MUST be one of: small, medium, large, very_large — Volume of data
2. query_volume: MUST be one of: low, medium, high, very_high — Expected queries/requests
3. latency_requirement: MUST be one of: relaxed, moderate, strict, ultra_low — Response time needs
4. data_volatility: MUST be one of: static, low, moderate, high — How often data changes
5. accuracy_requirement: MUST be one of: moderate, high, very_high, critical — Accuracy needs
6. domain_specificity: MUST be one of: general, moderate, specialized, highly_specialized — Domain specialization
7. security_level: MUST be one of: standard, elevated, high, critical — Security needs
8. cost_sensitivity: MUST be one of: low, moderate, high, very_high — Budget constraints
9. deployment_preference: MUST be one of: cloud, on_premise, hybrid, edge — Deployment target
10. user_scale: MUST be one of: small, medium, large, enterprise — Number of users

DOCUMENT TEXT:
{document_text}

Respond with a JSON object with signal names as keys, each containing: value, confidence, source_text, page_number.
"""
EXTRACTION_PROMPT_COMPACT = """Extract architecture signals from this document. Return ONLY a JSON object.
 
For each signal return: {{"value": "<exact_option>", "confidence": 0.0-1.0, "source_text": "<verbatim quote>", "page_number": 0}}
Use null for value if not found. Use EXACT option strings with underscores (e.g. very_high not "very high").
 
SIGNALS (use ONLY these exact values):
dataset_size: small | medium | large | very_large
query_volume: low | medium | high | very_high
latency_requirement: relaxed | moderate | strict | ultra_low
data_volatility: static | low | moderate | high
accuracy_requirement: moderate | high | very_high | critical
domain_specificity: general | moderate | specialized | highly_specialized
security_level: standard | elevated | high | critical
cost_sensitivity: low | moderate | high | very_high
deployment_preference: cloud | on_premise | hybrid | edge
user_scale: small | medium | large | enterprise
 
DOCUMENT:
{document_text}
 
JSON:"""
 
# Models known to need the compact prompt (small parameter count, weak instruction following)
_SMALL_MODELS = {"llama3.2", "llama3.2:1b", "llama3.2:3b", "phi", "phi3", "gemma:2b", "qwen:1.8b", "tinyllama"}
 
 
def get_extraction_prompt(model_name: str, document_text: str) -> str:
    """Return the appropriate extraction prompt for the given model size."""
    base_model = model_name.split(":")[0].lower() if ":" in model_name else model_name.lower()
    use_compact = base_model in _SMALL_MODELS or model_name.lower() in _SMALL_MODELS
    template = EXTRACTION_PROMPT_COMPACT if use_compact else EXTRACTION_PROMPT
    if use_compact:
        logger.info("Using compact extraction prompt for small model '%s'", model_name)
    return template.format(document_text=document_text)

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
def _normalize_signal_value(raw: object, allowed: list[str]) -> str | None:
    """
    Normalize and validate a signal value returned by the LLM.
 
    Handles common LLM quirks:
      - Wrong case:          "High"       → "high"
      - Spaces instead of underscores: "very high" → "very_high"
      - Extra whitespace:    "  low  "    → "low"
      - None / empty string: None         → None (caller decides)
 
    Returns the matching allowed value, or None if no match found.
    """
    if not raw:
        return None
 
    # Normalise: lowercase, strip, collapse spaces → underscores
    normalised = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
 
    # Exact match first (fastest path)
    if normalised in allowed:
        return normalised
 
    # Prefix match — handles "very_high_load" matching "very_high"
    for option in allowed:
        if normalised.startswith(option) or option.startswith(normalised):
            return option
 
    return None

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
        if not relevant_pages:
            relevant_pages = pages
            logger.warning("Page filtering removed all pages — using full document")
        else:
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

    async def _llm_extraction(self, text: str) -> dict[str, dict]:
        """Single LLM call for signal extraction."""
        try:
            prompt = get_extraction_prompt(settings.OLLAMA_MODEL if self.llm.provider == "ollama" else "openai", text)
            result = await self.llm.generate_json(prompt=prompt)
 
            # DEBUG: log what the LLM actually returned so you can diagnose issues
            top_keys = list(result.keys())[:5] if isinstance(result, dict) else "NOT A DICT"
            logger.info("LLM raw response top-level keys: %s (total keys: %s)",
                        top_keys, len(result) if isinstance(result, dict) else "?")
 
            if "error" in result:
                logger.warning("LLM extraction returned error: %s", result.get("raw", "")[:200])
                logger.warning("→ Falling back to keyword-only extraction")
                return self._empty_signals()
 

            validated: dict[str, dict] = {}
            for key in SIGNAL_SCHEMA:
                if key in result and isinstance(result[key], dict):
                    sig = result[key]
                    raw_value = sig.get("value")
                    allowed = SIGNAL_OPTIONS.get(key, [])
                    validated_value = _normalize_signal_value(raw_value, allowed)   
                    validated[key] = {
                        "value": sig.get("value"),
                        "confidence": min(1.0, max(0.0, float(sig.get("confidence", 0)))),
                        "source_text": str(sig.get("source_text", ""))[:300],
                        "page_number": int(sig.get("page_number", 0)),
                    }
                if raw_value and not validated_value:
                        logger.warning(
                            "Signal '%s': LLM returned invalid value '%s' (allowed: %s) — discarded",
                            key, raw_value, allowed,
                        )
                        validated[key]["confidence"] = 0.0  
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
        concurrently, then keep the highest-confidence signal from any chunk.
        """
        chunks = self._make_chunks(text)
        logger.info("Parallel extraction: %d chunks (~%d chars each)", len(chunks), CHUNK_SIZE)

        results = await asyncio.gather(
            *[self._llm_extraction(chunk) for chunk in chunks],
            return_exceptions=False,
        )

        # Winner-takes-all per signal: highest confidence across chunks
        merged: dict[str, dict] = self._empty_signals()
        for chunk_result in results:
            for key, sig in chunk_result.items():
                if sig.get("confidence", 0) > merged[key].get("confidence", 0):
                    merged[key] = sig

        return merged
    _VALUE_PATTERNS: dict[str, list[tuple]] = {
        "dataset_size": [
            (r"\b(billion|terabyte|tb|petabyte)\b",                    "very_large", 0.75),
            (r"\b(million|gigabyte|gb|millions of)\b",                 "large",      0.70),
            (r"\b(hundred[s]? thousand|500[,\s]?000|[1-9]\d{5,})\b",  "large",      0.65),
            (r"\b(thousand[s]?|10[,\s]?000|[1-9]\d{3,4}).{0,10}(record|document|row|file|case)\b", "medium", 0.60),
            (r"\b(small dataset|few hundred|28 page|18[,\s]?000 word|handful|single document)\b",   "small",  0.72),
        ],
        "query_volume": [
            (r"\b(million[s]?.{0,15}(request|quer)|50[,\s]?000.{0,20}(hour|day))\b",               "very_high", 0.80),
            (r"\b(15[,\s]?000.{0,20}(hour|day)|thousand[s]?.{0,10}per.{0,10}(second|minute))\b",  "high",      0.75),
            (r"\bnot.{0,15}(high.{0,10}traffic|high.{0,10}volume)\b",                               "low",       0.75),
            (r"\b(800|1[,\s]?200).{0,20}(per day|\/day|studies per)\b",                            "low",       0.70),
            (r"\b(5[\-–]15.{0,10}(question|query|request)|low.{0,10}(traffic|volume))\b",          "low",       0.70),
        ],
        "latency_requirement": [
            (r"\b(sub.{0,5}100\s*ms|ultra.{0,5}low.{0,10}latency|<\s*100\s*ms|200\s*millisecond)\b", "ultra_low", 0.85),
            # Negation FIRST: "real-time NOT required" → relaxed
            (r"\breal.?time.{0,25}not.{0,10}required\b",                                              "relaxed",   0.82),
            (r"\bsub.?second.{0,25}not.{0,10}required\b",                                             "relaxed",   0.82),
            (r"\b(5[\-–]10.{0,10}second.{0,10}(is|are).{0,10}acceptable|relaxed|no.{0,10}sla)\b",   "relaxed",   0.75),
            (r"\b(2.{0,5}second[s]?.{0,20}acceptable|3.{0,5}second)\b",                               "moderate",  0.65),
            (r"\b(real.?time|<\s*1\s*second|under.{0,5}second|1.{0,5}second)\b",                     "strict",    0.68),
        ],
        "data_volatility": [
            (r"\b(update[sd]?.{0,15}(daily|hourly|continuously|real.?time)|change[sd]?.{0,10}(every|daily|frequently))\b", "high",     0.80),
            (r"\b(weekly.{0,15}update|moderate.{0,10}(change|update)|updated.{0,10}weekly)\b",                              "moderate", 0.70),
            (r"\b(rarely.{0,10}change|change[sd]?.{0,10}(annually|yearly|seldom)|low.{0,10}volatility)\b",                 "low",      0.70),
            (r"\b(static|immutable|does not change|never change|fixed.{0,15}(corpus|dataset))\b",                           "static",   0.80),
            (r"\b(reviewed.{0,10}annually|next.{0,15}reviewed|last updated.{0,10}\d+.{0,5}month)\b", "static",   0.72),
        ],
        "accuracy_requirement": [
            (r"\b(patient safety|fda|hipaa|510.?k|material.{0,15}(harm|client harm)|regulatory liability)\b", "critical",  0.85),
            (r"\b(critical.{0,15}(accuracy|correct)|mission.{0,10}critical|zero.{0,10}error)\b",              "critical",  0.80),
            (r"\b(very.{0,5}high.{0,10}accuracy|>?\s*9[05]\%.{0,10}(accuracy|precision))\b",                 "very_high", 0.75),
            # Negation FIRST: "not life-critical", "follow up with HR"
            (r"\bnot.{0,10}life.{0,10}crit\b",                                                                "moderate",  0.78),
            (r"\b(convenience.{0,10}tool|slightly wrong|follow.{0,15}up.{0,15}(with|directly))\b",           "moderate",  0.72),
            (r"\b(high.{0,10}accuracy|incorrect.{0,20}(harm|escalation))\b",                                 "high",      0.70),
        ],
        "domain_specificity": [
            (r"\b(radiology|radiolog|medical.{0,10}(imaging|diagnosis)|bi.?rads|li.?rads)\b",                "highly_specialized", 0.87),
            (r"\b(highly.{0,10}specializ|proprietary.{0,10}(jargon|terminology)|equity.{0,10}(analyst|valuation))\b", "highly_specialized", 0.82),
            (r"\b(specialized.{0,15}(domain|vocabulary|terminology))\b",                                     "specialized",        0.75),
            (r"\b(not.{0,10}highly.{0,10}special|e.?commerce|general.{0,10}purpose)\b",                    "general",            0.68),
            (r"\b(moderate.{0,10}(domain|specializ)|company.{0,10}specific.{0,10}polic)\b",                 "moderate",           0.65),
        ],
        "security_level": [
            (r"\b(hipaa|phi|patient.{0,10}data|air.?gapped|no.{0,15}internet|not.{0,10}leave.{0,15}(hospital|firewall))\b", "critical",  0.85),
            (r"\b(gdpr|pii|sec.{0,10}rule|mifid|audit.{0,10}trail|role.{0,10}based.{0,10}access|sox|soc.{0,5}2)\b",         "high",      0.80),
            (r"\b(elevated.{0,10}security|sensitive.{0,10}data)\b",                                                           "elevated",  0.65),
            (r"\b(standard.{0,10}security|standard.{0,10}cloud|no pii beyond|standard.{0,10}encryption)\b", "standard",  0.72),
        ],
        "cost_sensitivity": [
            (r"\b(\$200.{0,15}month|cannot.{0,10}justify|no.{0,10}budget)\b",                               "very_high", 0.85),
            (r"\b(tight.{0,10}budget|budget.{0,10}constraint|cost.{0,10}sensitive|minimize.{0,10}cost)\b",  "high",      0.75),
            (r"\b(reasonable.{0,10}(budget|engineering)|moderate.{0,10}(cost|budget))\b",                    "moderate",  0.68),
            (r"\b(cost.{0,10}not.{0,10}constraint|cost.{0,10}justif|infrastructure.{0,10}cost.{0,15}not)\b","low",       0.75),
        ],
        "deployment_preference": [
            (r"\b(on.?premise|on.?prem|air.?gapped|within.{0,20}(hospital|firewall|clinical))\b(?!.{0,40}(do not|don.t|not want|avoid))", "on_premise", 0.85),
            # Negation: "do not want to manage on-premise" → cloud preference
            (r"\b(do not|don.t|not want|avoid).{0,30}(on.?premise|on.?prem)\b",                                    "cloud",      0.78),
            (r"\b(hybrid.{0,15}(cloud|deployment|infrastructure)|both.{0,15}(cloud|on.?prem))\b",                  "hybrid",     0.75),
            (r"\b(edge.{0,10}(deploy|computing|inference)|iot|on.?device)\b",                                       "edge",       0.75),
            (r"\b(aws|azure|gcp|google cloud|already use.{0,15}(aws|cloud)|managed service[s]?\s+wherever)\b",     "cloud",      0.72),
        ],
        "user_scale": [
            (r"\b(enterprise|2[,\s]?[0-9]{3}[+]?.{0,10}(user|analyst|employee)|global.{0,10}office[s]?)\b","enterprise", 0.80),
            (r"\b(800[,\s]?000|million[s]?.{0,15}(customer|user)|large.{0,10}user.{0,10}base)\b",           "large",      0.80),
            (r"\b(thousand[s]?.{0,10}user|[1-9]\d{3}.{0,10}(user|customer|employee))\b",                    "medium",     0.65),
            (r"\b(35.{0,10}employee|45.{0,10}radiologist|small.{0,10}team|internal.{0,10}tool)\b",          "small",      0.75),
        ],
    }

    # ── Keyword extraction ────────────────────────────────────────────────────

    def _keyword_extraction(self, text: str, pages: list[dict]) -> dict[str, dict]:
        """Fast keyword scan — no LLM cost, provides fallback source_text."""
        signals = {}
        text_lower = text.lower()

        for signal_name, schema in SIGNAL_SCHEMA.items():
            inferred_value = None
            inferred_conf = 0.0
            inferred_src = ""
 
            for pattern, value, conf in self._VALUE_PATTERNS.get(signal_name, []):
                m = re.search(pattern, text_lower, re.DOTALL | re.IGNORECASE)
                if m:
                    idx = m.start()
                    start = max(0, text.rfind(".", 0, idx) + 1)
                    end = text.find(".", idx)
                    end = min(len(text), idx + 200) if end == -1 else end
                    inferred_value = value
                    inferred_conf = conf
                    inferred_src = text[start:end].strip()[:200]
                    break  # first match wins (patterns ordered most-specific first)
 
            # ── Layer 2: count schema keyword matches for confidence boost ────
            kw_matches = sum(1 for kw in schema["keywords"] if kw in text_lower)
 
            if inferred_value:
                # Boost confidence slightly if many topic keywords also present
                boosted_conf = min(0.75, inferred_conf + kw_matches * 0.02)
                page_num = 0
                for page in pages:
                    if inferred_src[:40].lower() in page.get("text", "").lower():
                        page_num = page.get("page_number", 0)
                        break
                signals[signal_name] = {
                    "value": inferred_value,
                    "confidence": round(boosted_conf, 2),
                    "source_text": inferred_src,
                    "page_number": page_num,
                    "keyword_matches": kw_matches,
                }
            elif kw_matches > 0:
                # Topic detected but value unclear — keep value=None, low confidence
                # This lets source_text still help the LLM merge step
                page_num = 0
                first_kw = next(kw for kw in schema["keywords"] if kw in text_lower)
                idx = text_lower.index(first_kw)
                start = max(0, text.rfind(".", 0, idx) + 1)
                end = text.find(".", idx)
                end = min(len(text), idx + 200) if end == -1 else end
                src = text[start:end].strip()[:200]
                for page in pages:
                    if first_kw in page.get("text", "").lower():
                        page_num = page.get("page_number", 0)
                        break
                signals[signal_name] = {
                    "value": None,
                    "confidence": min(0.3, kw_matches * 0.1),
                    "source_text": src,
                    "page_number": page_num,
                    "keyword_matches": kw_matches,
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
            original_conf = round(sig.get("confidence", 0), 2)
            penalised_conf = round(original_conf * 0.7, 2)
            logger.warning(
                 "Source for '%s' not verified — mild penalty %.2f → %.2f (value='%s' kept)",
                key, original_conf, penalised_conf, sig.get("value"),
            )
            sig["source_verified"] = False
            sig["confidence"] = penalised_conf

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
            (r"\b(?:add|updat|refresh)\w*\s+(?:daily|every\s+day)\b", "moderate", 0.72),
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
            kw  = keyword_signals.get(key, {})
            llm = llm_signals.get(key, {})
 
            kw_val   = kw.get("value")
            llm_val  = llm.get("value")
            kw_conf  = kw.get("confidence", 0.0)
            llm_conf = llm.get("confidence", 0.0)
 
            # ── Choose the best value ────────────────────────────────────────
            if llm_val and llm_conf >= 0.1:
                # LLM gave a valid answer with enough confidence
                value = llm_val
                base_conf = llm_conf
            elif kw_val and kw_conf >= 0.1:
                # LLM failed / was penalised → fall back to keyword inference
                value = kw_val
                base_conf = kw_conf
                logger.debug(
                    "Signal '%s': using keyword value '%s' (conf=%.2f) because LLM "
                    "conf=%.2f was too low (val='%s')",
                    key, kw_val, kw_conf, llm_conf, llm_val,
                )
            else:
                value = None
                base_conf = max(kw_conf, llm_conf)
 
            # ── Boost confidence when both sources agree ─────────────────────
            if kw_val and llm_val and kw_val == llm_val and kw_conf >= 0.1 and llm_conf >= 0.1:
                combined_conf = min(1.0, llm_conf + kw_conf * 0.3)
            else:
                combined_conf = base_conf
 
            # ── Pick best source_text ────────────────────────────────────────
            llm_src      = llm.get("source_text", "")
            llm_verified = llm.get("source_verified", False)
            kw_src       = kw.get("source_text", "")
 
            if llm_src and llm_verified:
                source_text  = llm_src
                page_number  = llm.get("page_number") or kw.get("page_number", 0)
            elif kw_src:
                source_text  = kw_src
                page_number  = kw.get("page_number", 0)
            else:
                source_text  = llm_src
                page_number  = llm.get("page_number") or 0
 
            final_conf = round(combined_conf, 2)
 
            merged[key] = {
                "value":           value if final_conf >= 0.1 else None,
                "confidence":      final_conf,
                "source_text":     source_text,
                "source_verified": bool(llm_verified or (kw_src and source_text == kw_src)),
                "page_number":     page_number,
            }
 
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
