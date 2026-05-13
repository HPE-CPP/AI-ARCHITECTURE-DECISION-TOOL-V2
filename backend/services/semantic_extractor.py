"""
Semantic Signal Extraction Service

Uses sentence-transformers (all-MiniLM-L6-v2) for semantic similarity matching
instead of keyword-only extraction. Provides:
  - Anchor phrase system with multiple semantic anchors per signal.
  - Cosine similarity matching at the sentence level.
  - Evidence sentence retrieval with confidence scoring.
  - Deterministic output (no randomness in the model).
  - CPU inference support, batch embedding, low latency.
"""
import logging
import re
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded model singleton
# ---------------------------------------------------------------------------
_model = None
_model_lock = None


def _get_lock():
    """Lazy-init a threading lock for model loading."""
    global _model_lock
    if _model_lock is None:
        import threading
        _model_lock = threading.Lock()
    return _model_lock


def _get_model():
    """Lazily load the sentence-transformers model (CPU, deterministic)."""
    global _model
    if _model is not None:
        return _model

    lock = _get_lock()
    with lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model: all-MiniLM-L6-v2 ...")
            _model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
            logger.info("Sentence-transformers model loaded successfully.")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Semantic extraction will fall back to keyword-only mode. "
                "Install with: pip install sentence-transformers"
            )
            _model = None
        except Exception as exc:
            logger.error("Failed to load sentence-transformers model: %s", exc)
            _model = None
    return _model


def is_available() -> bool:
    """Check if the semantic extractor model is available."""
    return _get_model() is not None


# ---------------------------------------------------------------------------
# Semantic anchor phrases per signal
# ---------------------------------------------------------------------------
SIGNAL_ANCHORS: dict[str, list[str]] = {
    "dataset_size": [
        "the dataset contains millions of records",
        "processing large volumes of data",
        "small dataset with limited records",
        "data corpus size and scale",
        "terabytes of training data",
        "number of documents in the knowledge base",
        "volume of data to be indexed",
    ],
    "latency_requirement": [
        "response time must be under one second",
        "real-time processing with low latency",
        "strict latency requirements for user queries",
        "millisecond response time needed",
        "performance SLA for query speed",
        "acceptable delay for responses",
    ],
    "query_volume": [
        "thousands of queries per second",
        "expected request throughput and traffic",
        "concurrent users making requests",
        "high volume of API calls",
        "queries per second load capacity",
        "peak traffic and request rates",
    ],
    "user_scale": [
        "millions of active users",
        "enterprise-wide deployment across organization",
        "small team of internal users",
        "public-facing consumer application",
        "number of end users accessing the system",
        "user base size and growth",
    ],
    "security_level": [
        "HIPAA compliance required for health data",
        "SOC2 and security certification needed",
        "classified or confidential information",
        "GDPR compliance for personal data",
        "encryption and access control requirements",
        "data privacy and regulatory compliance",
    ],
    "cost_sensitivity": [
        "strict budget constraints and cost limits",
        "cost-effective solution preferred",
        "budget is flexible for performance",
        "minimize infrastructure spending",
        "return on investment considerations",
        "affordable and resource-efficient",
    ],
    "deployment_preference": [
        "deploy on AWS or cloud infrastructure",
        "on-premise self-hosted deployment required",
        "hybrid cloud architecture",
        "edge computing deployment",
        "data residency requirements",
        "cloud versus local hosting decision",
    ],
    "domain_specificity": [
        "highly specialized medical domain",
        "financial services industry specific",
        "general-purpose knowledge assistant",
        "legal and regulatory domain expertise",
        "proprietary niche industry knowledge",
        "domain-specific terminology and jargon",
    ],
    "data_volatility": [
        "data changes frequently in real-time",
        "static knowledge base rarely updated",
        "streaming data with continuous updates",
        "daily or weekly data refresh cycles",
        "dynamic content that changes hourly",
        "frequency of data updates and changes",
    ],
    "accuracy_requirement": [
        "zero tolerance for incorrect answers",
        "critical accuracy for medical decisions",
        "high precision and recall needed",
        "moderate accuracy acceptable for assistance",
        "hallucination prevention is essential",
        "reliability and correctness requirements",
    ],
}


# ---------------------------------------------------------------------------
# Sentence splitting (shared with embeddings module)
# ---------------------------------------------------------------------------
_SENTENCE_SPLIT_RE = re.compile(
    r'(?<=[.!?])\s+(?=[A-Z])|(?<=\n)\s*(?=\S)'
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences deterministically."""
    if not text.strip():
        return []
    sentences = _SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in sentences if s.strip()]


# ---------------------------------------------------------------------------
# Core semantic extraction
# ---------------------------------------------------------------------------

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def extract_semantic_signals(
    text: str,
    min_similarity: float = 0.35,
    top_k_evidence: int = 3,
) -> dict[str, dict]:
    """Extract signals using semantic similarity against anchor phrases.

    For each signal:
      1. Embed all anchor phrases for that signal.
      2. Embed every sentence in the document.
      3. Find the top-k most similar (sentence, anchor) pairs.
      4. Compute a confidence score based on max similarity.
      5. Return the best evidence sentence.

    Args:
        text: Full document text.
        min_similarity: Minimum cosine similarity to consider a match.
        top_k_evidence: Number of evidence sentences to retain per signal.

    Returns:
        Dict mapping signal_name -> {confidence, evidence_sentences, best_sentence}.
    """
    model = _get_model()
    if model is None:
        logger.warning("Semantic model not available — returning empty signals.")
        return {}

    sentences = _split_sentences(text)
    if not sentences:
        return {}

    # Batch-embed all document sentences (deterministic)
    sentence_embeddings = model.encode(
        sentences,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True,
    )

    results: dict[str, dict] = {}

    for signal_name, anchors in SIGNAL_ANCHORS.items():
        # Embed anchor phrases
        anchor_embeddings = model.encode(
            anchors,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        # Compute similarity matrix: [num_sentences x num_anchors]
        # With normalized embeddings, cosine similarity = dot product
        similarity_matrix = np.dot(sentence_embeddings, anchor_embeddings.T)

        # Find top-k (sentence_idx, anchor_idx) pairs by similarity
        flat_indices = np.argsort(similarity_matrix.ravel())[::-1]
        top_pairs = []
        seen_sentences = set()

        for flat_idx in flat_indices:
            if len(top_pairs) >= top_k_evidence:
                break
            sent_idx = int(flat_idx // len(anchors))
            anchor_idx = int(flat_idx % len(anchors))
            sim = float(similarity_matrix[sent_idx, anchor_idx])

            if sim < min_similarity:
                break
            if sent_idx in seen_sentences:
                continue

            seen_sentences.add(sent_idx)
            top_pairs.append({
                "sentence": sentences[sent_idx],
                "sentence_idx": sent_idx,
                "anchor": anchors[anchor_idx],
                "similarity": round(sim, 4),
            })

        if top_pairs:
            max_sim = top_pairs[0]["similarity"]
            # Map similarity to confidence: [min_similarity, 1.0] -> [0.1, 0.6]
            # Semantic confidence caps at 0.6 — LLM validation pushes it higher
            confidence = round(
                0.1 + (max_sim - min_similarity) / (1.0 - min_similarity) * 0.5,
                3,
            )
            confidence = min(0.6, max(0.1, confidence))

            results[signal_name] = {
                "confidence": confidence,
                "evidence_sentences": [p["sentence"] for p in top_pairs],
                "best_sentence": top_pairs[0]["sentence"],
                "best_similarity": max_sim,
                "anchor_matched": top_pairs[0]["anchor"],
            }
        else:
            results[signal_name] = {
                "confidence": 0.0,
                "evidence_sentences": [],
                "best_sentence": "",
                "best_similarity": 0.0,
                "anchor_matched": "",
            }

    return results


# ---------------------------------------------------------------------------
# Signal-specific FAISS retrieval queries
# ---------------------------------------------------------------------------
SIGNAL_RETRIEVAL_QUERIES: dict[str, str] = {
    "dataset_size": "data size volume records documents corpus training data scale",
    "latency_requirement": "response time latency performance speed milliseconds SLA real-time",
    "query_volume": "queries per second throughput requests traffic concurrent load QPS",
    "user_scale": "number of users scale enterprise consumer team organization",
    "security_level": "security privacy compliance HIPAA GDPR SOC2 encryption classified",
    "cost_sensitivity": "budget cost pricing ROI affordable resource efficiency spending",
    "deployment_preference": "deploy cloud on-premise hybrid edge AWS Azure GCP self-hosted",
    "domain_specificity": "domain specialized expert medical legal financial technical niche",
    "data_volatility": "data update frequency volatile dynamic refresh streaming real-time changes",
    "accuracy_requirement": "accuracy precision recall quality hallucination reliable correct critical",
}
