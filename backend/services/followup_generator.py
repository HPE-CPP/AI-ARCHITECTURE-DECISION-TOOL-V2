"""
Follow-Up Question Generator
Generates contextual follow-up questions for missing or low-confidence signals.
"""
import logging
from typing import Optional
from services.signal_extractor import SIGNAL_SCHEMA

logger = logging.getLogger(__name__)

# Pre-defined multiple-choice options for each signal
SIGNAL_OPTIONS: dict[str, list[dict[str, str]]] = {
    "dataset_size": [
        {"value": "small", "label": "Small (< 10K documents/records)"},
        {"value": "medium", "label": "Medium (10K - 1M documents/records)"},
        {"value": "large", "label": "Large (1M - 100M documents/records)"},
        {"value": "very_large", "label": "Very Large (100M+ documents/records)"},
    ],
    "query_volume": [
        {"value": "low", "label": "Low (< 100 queries/day)"},
        {"value": "medium", "label": "Medium (100 - 10K queries/day)"},
        {"value": "high", "label": "High (10K - 1M queries/day)"},
        {"value": "very_high", "label": "Very High (1M+ queries/day)"},
    ],
    "latency_requirement": [
        {"value": "relaxed", "label": "Relaxed (> 5 seconds acceptable)"},
        {"value": "moderate", "label": "Moderate (1 - 5 seconds)"},
        {"value": "strict", "label": "Strict (< 1 second)"},
        {"value": "ultra_low", "label": "Ultra Low (< 100ms)"},
    ],
    "data_volatility": [
        {"value": "static", "label": "Static (rarely or never changes)"},
        {"value": "low", "label": "Low (updates monthly or less)"},
        {"value": "moderate", "label": "Moderate (updates weekly)"},
        {"value": "high", "label": "High (updates daily or real-time)"},
    ],
    "accuracy_requirement": [
        {"value": "moderate", "label": "Moderate (good enough for most cases)"},
        {"value": "high", "label": "High (important for business decisions)"},
        {"value": "very_high", "label": "Very High (mission-critical accuracy)"},
        {"value": "critical", "label": "Critical (zero error tolerance, e.g., medical/legal)"},
    ],
    "domain_specificity": [
        {"value": "general", "label": "General (common knowledge domain)"},
        {"value": "moderate", "label": "Moderate (some industry-specific terms)"},
        {"value": "specialized", "label": "Specialized (deep technical domain)"},
        {"value": "highly_specialized", "label": "Highly Specialized (e.g., medical, legal, scientific)"},
    ],
    "security_level": [
        {"value": "standard", "label": "Standard (basic security practices)"},
        {"value": "elevated", "label": "Elevated (data encryption, access controls)"},
        {"value": "high", "label": "High (compliance requirements: SOC2, etc.)"},
        {"value": "critical", "label": "Critical (regulated: HIPAA, GDPR, classified)"},
    ],
    "cost_sensitivity": [
        {"value": "low", "label": "Low (budget is flexible)"},
        {"value": "moderate", "label": "Moderate (cost-conscious but flexible)"},
        {"value": "high", "label": "High (tight budget constraints)"},
        {"value": "very_high", "label": "Very High (minimal budget available)"},
    ],
    "deployment_preference": [
        {"value": "cloud", "label": "Cloud (AWS, Azure, GCP)"},
        {"value": "on_premise", "label": "On-Premise (private infrastructure)"},
        {"value": "hybrid", "label": "Hybrid (cloud + on-premise mix)"},
        {"value": "edge", "label": "Edge (devices, IoT, local processing)"},
    ],
    "user_scale": [
        {"value": "small", "label": "Small (< 100 users)"},
        {"value": "medium", "label": "Medium (100 - 10K users)"},
        {"value": "large", "label": "Large (10K - 1M users)"},
        {"value": "enterprise", "label": "Enterprise (1M+ users, multi-tenant)"},
    ],
}

QUESTION_TEMPLATES: dict[str, str] = {
    "dataset_size": "What is the approximate size of your dataset or knowledge base?",
    "query_volume": "How many queries or requests do you expect per day?",
    "latency_requirement": "What are your response time requirements?",
    "data_volatility": "How frequently does your underlying data change?",
    "accuracy_requirement": "How critical is accuracy for your use case?",
    "domain_specificity": "How specialized is your domain?",
    "security_level": "What level of security and compliance do you need?",
    "cost_sensitivity": "What are your budget constraints?",
    "deployment_preference": "What is your preferred deployment environment?",
    "user_scale": "How many end users will use the system?",
}

MAX_FOLLOWUP_QUESTIONS = 5


def generate_followup_questions(
    signals: dict[str, dict],
    document_context: Optional[str] = None,
    max_questions: int = MAX_FOLLOWUP_QUESTIONS,
) -> list[dict]:
    """Generate follow-up questions for missing or low-confidence signals.

    Returns list of question objects with:
    - signal: signal name
    - question: human-readable question text
    - context: document reference if available
    - options: list of {value, label} choices
    - required: whether this is a critical signal
    """
    missing = []
    for signal_name in SIGNAL_SCHEMA:
        sig = signals.get(signal_name, {})
        value = sig.get("value")
        confidence = sig.get("confidence", 0.0)

        if not value or confidence < 0.3:
            priority = _get_signal_priority(signal_name)
            missing.append((signal_name, confidence, priority))

    # Sort by priority (higher first), then by confidence (lower first)
    missing.sort(key=lambda x: (-x[2], x[1]))

    questions = []
    for signal_name, confidence, priority in missing[:max_questions]:
        question_text = QUESTION_TEMPLATES.get(signal_name, f"Please specify: {signal_name}")

        # Add document context reference if available
        context = ""
        sig = signals.get(signal_name, {})
        source = sig.get("source_text", "")
        if source:
            # AI-5.4 FIX: Only append ellipsis when the source is actually truncated.
            # Previously "..." was always appended even for texts shorter than 150 chars.
            truncated = source[:150]
            suffix = "..." if len(source) > 150 else ""
            context = f'From your document: "{truncated}{suffix}"'

        questions.append({
            "signal": signal_name,
            "question": question_text,
            "context": context,
            "options": SIGNAL_OPTIONS.get(signal_name, []),
            "required": priority >= 3,
            "current_value": sig.get("value"),
            "current_confidence": confidence,
        })

    return questions


def _get_signal_priority(signal_name: str) -> int:
    """Get importance priority of a signal (1-5, 5=most important)."""
    priorities = {
        "dataset_size": 5,
        "data_volatility": 5,
        "accuracy_requirement": 4,
        "latency_requirement": 4,
        "domain_specificity": 4,
        "query_volume": 3,
        "security_level": 3,
        "cost_sensitivity": 2,
        "deployment_preference": 2,
        "user_scale": 2,
    }
    return priorities.get(signal_name, 1)
