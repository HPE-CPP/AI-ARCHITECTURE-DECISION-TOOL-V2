"""
Signal Extraction Service
Extracts architecture decision signals from document text using LLM + heuristics.
Outputs strict schema with confidence scores.
"""
import json
import logging
import re
from typing import Optional, Any

from services.llm_client import LLMClient

logger = logging.getLogger(__name__)

# The 10 core signals we extract
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

EXTRACTION_PROMPT = """You are an expert AI architecture analyst. Analyze the following document text and extract architecture decision signals.

For each signal, provide:
- value: the extracted value (use the provided options, or null if not found)
- confidence: 0.0 to 1.0 (0 if not found, higher if explicitly stated)
- source_text: the exact quote from the document that supports this value (empty string if not found)
- page_number: the page number where the signal was found (0 if not found)

CRITICAL RULES:
1. DO NOT hallucinate. If a signal is not mentioned in the document, set value to null and confidence to 0.
2. Only extract what is explicitly stated or strongly implied.
3. Confidence levels:
   - 0.0: Not found at all
   - 0.1-0.3: Weakly implied
   - 0.4-0.6: Moderately implied
   - 0.7-0.8: Strongly implied
   - 0.9-1.0: Explicitly stated

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


class SignalExtractor:
    """Extracts architecture decision signals from document text."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    async def extract_signals(self, document_data: dict) -> dict[str, dict]:
        """Extract signals from parsed document data."""
        full_text = document_data.get("full_text", "")
        pages = document_data.get("pages", [])

        if not full_text.strip():
            return self._empty_signals()

        # Step 1: Keyword-based pre-extraction
        keyword_signals = self._keyword_extraction(full_text, pages)

        # Step 2: LLM-based extraction
        # Truncate text if too long (keep first 8000 chars for LLM context)
        truncated_text = full_text[:8000] if len(full_text) > 8000 else full_text
        llm_signals = await self._llm_extraction(truncated_text)

        # Step 3: Merge and validate
        merged = self._merge_signals(keyword_signals, llm_signals)

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
                }
            else:
                signals[key] = {
                    "value": None,
                    "confidence": 0.0,
                    "source_text": "",
                    "page_number": 0,
                }
        return signals

    def _keyword_extraction(self, text: str, pages: list[dict]) -> dict[str, dict]:
        """Extract signals using keyword matching."""
        signals = {}
        text_lower = text.lower()

        for signal_name, schema in SIGNAL_SCHEMA.items():
            matches = []
            for keyword in schema["keywords"]:
                if keyword in text_lower:
                    # Find the sentence containing the keyword
                    idx = text_lower.index(keyword)
                    start = max(0, text.rfind(".", 0, idx) + 1)
                    end = text.find(".", idx)
                    if end == -1:
                        end = min(len(text), idx + 200)
                    source = text[start:end].strip()
                    matches.append({
                        "keyword": keyword,
                        "source_text": source,
                    })

            if matches:
                # Find page number
                page_num = 0
                for page in pages:
                    if matches[0]["keyword"] in page.get("text", "").lower():
                        page_num = page.get("page_number", 0)
                        break

                signals[signal_name] = {
                    "value": None,  # Keywords alone can't determine value
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

    async def _llm_extraction(self, text: str) -> dict[str, dict]:
        """Use LLM to extract signals from text."""
        try:
            prompt = EXTRACTION_PROMPT.format(document_text=text)
            result = await self.llm.generate_json(prompt=prompt)

            if "error" in result:
                logger.warning("LLM extraction returned error, falling back to empty signals")
                return self._empty_signals()

            # Validate and normalize each signal
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
            logger.error(f"LLM extraction failed: {e}")
            return self._empty_signals()

    def _merge_signals(self, keyword_signals: dict, llm_signals: dict) -> dict[str, dict]:
        """Merge keyword and LLM signals. LLM takes precedence for values, combined confidence."""
        merged = {}
        for key in SIGNAL_SCHEMA:
            kw = keyword_signals.get(key, {})
            llm = llm_signals.get(key, {})

            # LLM value takes precedence
            value = llm.get("value") if llm.get("value") else kw.get("value")

            # Boost confidence if both agree
            kw_conf = kw.get("confidence", 0)
            llm_conf = llm.get("confidence", 0)
            if kw_conf > 0 and llm_conf > 0:
                combined_conf = min(1.0, llm_conf + (kw_conf * 0.3))
            else:
                combined_conf = max(kw_conf, llm_conf)

            merged[key] = {
                "value": value,
                "confidence": round(combined_conf, 2),
                "source_text": llm.get("source_text") or kw.get("source_text", ""),
                "page_number": llm.get("page_number") or kw.get("page_number", 0),
            }

            # Anti-hallucination: null out low-confidence values
            if merged[key]["confidence"] < 0.1:
                merged[key]["value"] = None

        return merged

    def _empty_signals(self) -> dict[str, dict]:
        """Return all signals with null values and zero confidence."""
        return {
            key: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
            for key in SIGNAL_SCHEMA
        }

    def get_missing_signals(self, signals: dict) -> list[str]:
        """Return list of signal names that are missing or low confidence."""
        missing = []
        for key in SIGNAL_SCHEMA:
            sig = signals.get(key, {})
            if not sig.get("value") or sig.get("confidence", 0) < 0.3:
                missing.append(key)
        return missing
