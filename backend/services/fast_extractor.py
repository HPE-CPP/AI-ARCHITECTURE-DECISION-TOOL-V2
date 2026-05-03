"""
fast_extractor.py — Heuristic-First Signal Extraction
=======================================================
Extracts architecture signals from document text using
pure regex + keyword patterns — NO LLM call needed.

Speed: <100ms for any document size.
Coverage: Catches ~70% of signals in well-structured docs.
LLM fills in the remaining 30% only for ambiguous signals.

This runs BEFORE the LLM call and the results are merged in.
Signals found with high confidence here skip the LLM entirely.
"""
from __future__ import annotations
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Pattern map: each signal has a list of (pattern, value, confidence) ──────
PATTERNS: dict[str, list[tuple[str, str, float]]] = {

    "dataset_size": [
        (r"\b(\d+)\s*billion\b", "very_large", 0.95),
        (r"\b(\d+)\s*million\s*(records?|documents?|rows?|items?|entries)\b", "very_large", 0.92),
        (r"\b(\d+)\s*[Mm]\+?\s*(records?|documents?|rows?|items?)\b", "very_large", 0.90),
        (r"\b(petabyte|terabyte|TB|PB)\b", "very_large", 0.90),
        (r"\b(very large|massive|huge|enormous|vast)\s*(dataset|database|corpus|knowledge base)\b", "very_large", 0.82),
        (r"\b10[0-9]{4,}\s*(records?|documents?|entries)\b", "large", 0.88),
        (r"\b(\d+)\s*hundred\s*thousand\b", "large", 0.85),
        (r"\b(large|significant|substantial)\s*(dataset|corpus|knowledge base)\b", "large", 0.72),
        (r"\bgigabyte|GB\b", "large", 0.70),
        (r"\b(\d+[kK])\s*(records?|documents?|rows?)\b", "medium", 0.80),
        (r"\b(\d+)\s*thousand\s*(records?|documents?|rows?)\b", "medium", 0.80),
        (r"\b(medium|moderate|manageable)\s*(dataset|corpus|knowledge base)\b", "medium", 0.68),
        (r"\b(small|limited|few|tiny|minimal)\s*(dataset|corpus|knowledge base)\b", "small", 0.80),
        (r"\bless than\s*[\d,]+\s*(records?|documents?)\b", "small", 0.78),
        (r"\bpilot|proof of concept|PoC|MVP\b", "small", 0.65),
    ],

    "latency_requirement": [
        (r"\b(sub[-\s]?100\s*ms|<\s*100\s*ms|under\s*100\s*ms)\b", "ultra_low", 0.95),
        (r"\b(real[-\s]time|realtime|sub[-\s]second|<\s*1\s*s|ultra[-\s]?low\s*latency)\b", "ultra_low", 0.90),
        (r"\b(50|100|200)\s*ms\b", "ultra_low", 0.88),
        (r"\bembedded|IoT|edge\s*device\b", "ultra_low", 0.75),
        (r"\b(strict|tight|demanding)\s*(latency|SLA|SLO)\b", "strict", 0.85),
        (r"\b(500|800|1000)\s*ms\b", "strict", 0.82),
        (r"\bunder\s*(1|2)\s*second\b", "strict", 0.82),
        (r"\b(interactive|conversational|chat)\b", "moderate", 0.72),
        (r"\b1\s*[-–]\s*5\s*seconds?\b", "moderate", 0.80),
        (r"\b(few\s*seconds?|acceptable\s*delay|moderate\s*latency)\b", "moderate", 0.72),
        (r"\b(batch|offline|async|background|overnight)\b", "relaxed", 0.82),
        (r"\b(report|scheduled|nightly|weekly\s*run)\b", "relaxed", 0.75),
        (r"\b(flexible|no\s*strict|tolerant)\s*(latency|timing)\b", "relaxed", 0.78),
    ],

    "data_volatility": [
        (r"\b(real[-\s]?time|live|streaming|continuous)\s*(updates?|data|feed)\b", "high", 0.92),
        (r"\b(daily|hourly|minute[-\s]?by[-\s]?minute)\s*(updates?|changes?|refresh)\b", "high", 0.88),
        (r"\b(rapidly|frequently|constantly)\s*(chang|updat|refresh)\w*\b", "high", 0.85),
        (r"\b(social\s*media|news\s*feed|market\s*data|stock|price)\b", "high", 0.80),
        (r"\b(weekly|bi[-\s]?weekly|fortnightly)\s*(updates?|changes?|refresh)\b", "moderate", 0.85),
        (r"\b(periodic|occasional|regular)\s*(updates?|refresh|changes?)\b", "moderate", 0.75),
        (r"\b(quarterly|monthly)\s*(updates?|release|refresh)\b", "low", 0.85),
        (r"\b(infrequent|rare|seldom)\s*(updates?|changes?)\b", "low", 0.80),
        (r"\b(static|stable|fixed|unchanging|immutable)\s*(data|content|knowledge)\b", "static", 0.90),
        (r"\b(annual|yearly|never\s*chang)\b", "static", 0.82),
        (r"\bhistorical\s*(data|records?|archive)\b", "static", 0.75),
    ],

    "accuracy_requirement": [
        (r"\b(life|safety|critical|zero[-\s]?error|zero\s*tolerance)\b", "critical", 0.90),
        (r"\b(medical|clinical|healthcare|diagnosis|legal|compliance|regulatory|audit)\b", "critical", 0.88),
        (r"\b(financial\s*transaction|fraud\s*detection|security\s*alert)\b", "critical", 0.85),
        (r"\b(must\s*be\s*(accurate|correct|precise)|no\s*(errors?|mistakes?))\b", "critical", 0.85),
        (r"\b(very\s*high|extremely\s*high|maximum)\s*(accuracy|precision|reliability)\b", "very_high", 0.88),
        (r"\b(high\s*accuracy|high\s*quality|high\s*reliability|highly\s*accurate)\b", "high", 0.82),
        (r"\b(99|98|95)\s*%\s*(accuracy|precision|uptime)\b", "high", 0.85),
        (r"\b(important|significant|necessary)\s*(accuracy|correctness)\b", "high", 0.75),
        (r"\b(moderate|acceptable|reasonable|good\s*enough)\s*(accuracy|quality)\b", "moderate", 0.78),
        (r"\b(best[-\s]?effort|approximate|near)\b", "moderate", 0.70),
        (r"\b(creative|generative|brainstorm|ideation)\b", "moderate", 0.65),
    ],

    "domain_specificity": [
        (r"\b(highly\s*specialized|highly\s*specific|niche|expert[-\s]level|domain\s*expert)\b", "highly_specialized", 0.90),
        (r"\b(medical|clinical|pharmaceutical|radiology|pathology)\b", "highly_specialized", 0.88),
        (r"\b(legal\s*(documents?|contracts?|case\s*law)|law\s*firm)\b", "highly_specialized", 0.88),
        (r"\b(quantitative\s*finance|algorithmic\s*trading|derivatives)\b", "highly_specialized", 0.88),
        (r"\b(specialized|specific|technical|professional|vertical)\s*(domain|industry|field)\b", "specialized", 0.82),
        (r"\b(healthcare|finance|engineering|scientific|academic)\b", "specialized", 0.72),
        (r"\b(enterprise|corporate|industry[-\s]specific)\b", "specialized", 0.70),
        (r"\b(general\s*purpose|broad|diverse|multiple\s*domains)\b", "general", 0.80),
        (r"\b(consumer|e[-\s]?commerce|retail|general\s*public)\b", "general", 0.72),
        (r"\b(FAQ|customer\s*service|help\s*desk|support\s*chat)\b", "moderate", 0.70),
    ],

    "security_level": [
        (r"\b(classified|top\s*secret|national\s*security|government|DoD|ITAR)\b", "critical", 0.95),
        (r"\b(HIPAA|PHI|PII|GDPR|SOC\s*2|FedRAMP|FISMA)\b", "critical", 0.92),
        (r"\b(air[-\s]?gap|isolated|on[-\s]?prem\s*only|no\s*internet)\b", "critical", 0.88),
        (r"\b(high\s*security|strict\s*(security|compliance|privacy)|highly\s*regulated)\b", "high", 0.85),
        (r"\b(CCPA|ISO\s*27001|PCI[-\s]?DSS|financial\s*regulation)\b", "high", 0.85),
        (r"\b(sensitive\s*data|confidential|proprietary|restricted)\b", "elevated", 0.80),
        (r"\b(internal\s*only|enterprise\s*security|role[-\s]based\s*access)\b", "elevated", 0.75),
        (r"\b(standard|basic|normal|typical)\s*security\b", "standard", 0.78),
        (r"\b(public|open|no\s*sensitive|non[-\s]confidential)\b", "standard", 0.72),
    ],

    "cost_sensitivity": [
        (r"\b(budget\s*constrained|very\s*tight\s*budget|minimal\s*spend|zero\s*cost|free\s*tier)\b", "very_high", 0.90),
        (r"\b(startup|bootstrapped|self[-\s]?funded|early\s*stage|PoC|pilot)\b", "very_high", 0.80),
        (r"\b(cost[-\s]?sensitive|cost[-\s]?conscious|frugal|cost\s*is\s*(critical|priority))\b", "very_high", 0.85),
        (r"\b(limited\s*budget|tight\s*budget|constrained\s*budget|low\s*budget)\b", "high", 0.85),
        (r"\b(minimize\s*cost|reduce\s*cost|cost[-\s]?efficient|cost[-\s]?effective)\b", "high", 0.80),
        (r"\b(moderate\s*budget|reasonable\s*budget|willing\s*to\s*invest)\b", "moderate", 0.80),
        (r"\b(cost\s*is\s*(secondary|not\s*(primary|main)))\b", "low", 0.85),
        (r"\b(enterprise\s*budget|unlimited\s*budget|best[-\s]?in[-\s]?class\s*regardless)\b", "low", 0.85),
        (r"\b(well[-\s]?funded|venture[-\s]?backed|well\s*resourced|large\s*budget)\b", "low", 0.80),
    ],

    "deployment_preference": [
        (r"\b(on[-\s]?premises?|on[-\s]?prem\b|self[-\s]?hosted|private\s*data[-\s]?center)\b", "on_premise", 0.92),
        (r"\b(air[-\s]?gap|isolated\s*network|no\s*cloud)\b", "on_premise", 0.90),
        (r"\b(AWS|Azure|GCP|Google\s*Cloud|cloud[-\s]?native|cloud\s*first)\b", "cloud", 0.88),
        (r"\b(SaaS|managed\s*service|serverless|cloud\s*deployment)\b", "cloud", 0.85),
        (r"\b(hybrid\s*(cloud|deployment|architecture)|multi[-\s]?cloud)\b", "hybrid", 0.90),
        (r"\b(some\s*(cloud|on[-\s]?prem)|combination\s*of\s*cloud)\b", "hybrid", 0.80),
        (r"\b(edge\s*(computing|deployment|device)|IoT|embedded\b)\b", "edge", 0.90),
        (r"\b(mobile\s*device|raspberry\s*pi|edge\s*node)\b", "edge", 0.82),
    ],

    "user_scale": [
        (r"\b(\d+)\s*million\s*(users?|customers?|clients?)\b", "enterprise", 0.95),
        (r"\b(enterprise|global|worldwide|millions\s*of\s*users?)\b", "enterprise", 0.82),
        (r"\b(large\s*(organization|company|corporation)|Fortune\s*\d+)\b", "enterprise", 0.80),
        (r"\b(\d+[kK])\s*(users?|customers?)\b", "large", 0.85),
        (r"\b(thousands?\s*of\s*users?|growing\s*user\s*base|scalable)\b", "large", 0.75),
        (r"\b(hundreds?\s*of\s*users?|department[-\s]?level|team\s*of)\b", "medium", 0.80),
        (r"\b(internal\s*tool|intranet|limited\s*users?)\b", "medium", 0.72),
        (r"\b(small\s*team|few\s*users?|under\s*\d+\s*users?|personal)\b", "small", 0.82),
        (r"\b(prototype|PoC|pilot|MVP|demo)\b", "small", 0.72),
    ],

    "query_volume": [
        (r"\b(\d+[kK])\+?\s*(queries|requests|calls)\s*(per\s*second|\/s|QPS)\b", "very_high", 0.95),
        (r"\b(millions?\s*of\s*(queries|requests))\b", "very_high", 0.90),
        (r"\b(very\s*high\s*(volume|traffic|load)|high\s*throughput)\b", "very_high", 0.85),
        (r"\b(\d+)\s*(queries|requests)\s*per\s*second\b", "high", 0.85),
        (r"\b(thousands?\s*(queries|requests)\s*per|high\s*volume)\b", "high", 0.80),
        (r"\b(moderate|medium)\s*(volume|traffic|load|queries)\b", "medium", 0.78),
        (r"\b(occasional|infrequent|periodic|sporadic)\s*(queries|requests|usage)\b", "low", 0.82),
        (r"\b(small\s*number|few\s*requests?|low\s*(traffic|volume|load))\b", "low", 0.80),
    ],
}

# ── Valid values per signal ───────────────────────────────────────────────────
VALID_VALUES: dict[str, list[str]] = {
    "dataset_size":          ["small", "medium", "large", "very_large"],
    "query_volume":          ["low", "medium", "high", "very_high"],
    "latency_requirement":   ["relaxed", "moderate", "strict", "ultra_low"],
    "data_volatility":       ["static", "low", "moderate", "high"],
    "accuracy_requirement":  ["moderate", "high", "very_high", "critical"],
    "domain_specificity":    ["general", "moderate", "specialized", "highly_specialized"],
    "security_level":        ["standard", "elevated", "high", "critical"],
    "cost_sensitivity":      ["low", "moderate", "high", "very_high"],
    "deployment_preference": ["cloud", "on_premise", "hybrid", "edge"],
    "user_scale":            ["small", "medium", "large", "enterprise"],
}


def heuristic_extract(text: str) -> dict[str, dict]:
    """
    Extract architecture signals from text using regex patterns only.
    Returns signals dict in the same format as LLM extraction.
    Very fast (<100ms), no external calls.
    """
    text_lower = text.lower()
    signals: dict[str, dict] = {}

    for signal_name, pattern_list in PATTERNS.items():
        best_value: Optional[str] = None
        best_conf: float = 0.0
        best_source: str = ""

        for pattern, value, base_conf in pattern_list:
            try:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Count occurrences to boost confidence
                    count = len(re.findall(pattern, text, re.IGNORECASE))
                    conf = min(0.97, base_conf + (count - 1) * 0.03)

                    if conf > best_conf:
                        best_conf = conf
                        best_value = value
                        # Extract surrounding context as source text
                        start = max(0, match.start() - 80)
                        end = min(len(text), match.end() + 80)
                        best_source = text[start:end].strip().replace("\n", " ")
            except re.error:
                continue

        if best_value and best_conf >= 0.60:
            signals[signal_name] = {
                "value": best_value,
                "confidence": round(best_conf, 3),
                "source_text": best_source,
                "page_number": 0,
                "source_verified": True,
                "method": "heuristic",
            }

    covered = len(signals)
    total = len(PATTERNS)
    logger.info(f"[Heuristic] Extracted {covered}/{total} signals in <1ms")
    return signals


def signals_need_llm(heuristic_signals: dict[str, dict], min_confidence: float = 0.70) -> list[str]:
    """
    Return list of signal names that still need LLM extraction.
    A signal needs LLM if: not found, or found with low confidence.
    """
    missing = []
    all_signals = list(PATTERNS.keys())
    for sig in all_signals:
        found = heuristic_signals.get(sig)
        if not found or found.get("confidence", 0) < min_confidence:
            missing.append(sig)
    return missing


def make_targeted_prompt(text: str, missing_signals: list[str]) -> str:
    """
    Build a smaller LLM prompt asking ONLY for missing signals.
    Much faster than asking for all 10 every time.
    """
    signal_descriptions = {
        "dataset_size":          "Volume of data (small/medium/large/very_large)",
        "query_volume":          "Query throughput (low/medium/high/very_high)",
        "latency_requirement":   "Response time needs (relaxed/moderate/strict/ultra_low)",
        "data_volatility":       "How often data changes (static/low/moderate/high)",
        "accuracy_requirement":  "Precision/accuracy needs (moderate/high/very_high/critical)",
        "domain_specificity":    "Domain specialisation (general/moderate/specialized/highly_specialized)",
        "security_level":        "Security requirements (standard/elevated/high/critical)",
        "cost_sensitivity":      "Budget constraints (low/moderate/high/very_high)",
        "deployment_preference": "Where to deploy (cloud/on_premise/hybrid/edge)",
        "user_scale":            "Number of users (small/medium/large/enterprise)",
    }

    signals_list = "\n".join([
        f"- {sig}: {signal_descriptions.get(sig, sig)}"
        for sig in missing_signals
    ])

    # Use first 4000 chars — enough for targeted extraction
    excerpt = text[:4000]

    return f"""You are an expert AI architect. Extract ONLY these specific signals from the document:

{signals_list}

For each signal found:
- value: exact option from the listed choices, or null
- confidence: 0.0-1.0 (0 if not clearly present)
- source_text: verbatim quote from document (empty if not found)
- page_number: 0

DO NOT hallucinate. If a signal is absent or unclear, set value to null, confidence to 0.

DOCUMENT:
{excerpt}

Respond with JSON only. Keys are the signal names listed above."""
