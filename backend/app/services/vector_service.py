"""
Vector service — orchestrates chunking, embedding, and FAISS storage
for uploaded documents. Also provides retrieve helpers for signal
extraction that return the most relevant chunks for a session.

Multi-query retrieval:
  - One semantic retrieval query per signal (via SIGNAL_RETRIEVAL_QUERIES).
  - Focused context retrieval with reduced noise.
  - Isolated context windows per signal for better evidence quality.
"""
import logging
from typing import Optional

from app.utils.embeddings import chunk_text, embed_texts
from app.utils import faiss_store

logger = logging.getLogger(__name__)

# Signal-specific retrieval queries for focused FAISS search
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


async def index_document(
    session_id: str,
    full_text: str,
    pages: list[dict],
) -> int:
    """
    Chunk, embed, and store document text in FAISS.

    Args:
        session_id: Unique identifier for the analysis session.
        full_text:  Complete document text.
        pages:      List of page dicts with 'page_number' and 'text' keys.

    Returns:
        Number of chunks indexed.
    """
    if not full_text.strip():
        logger.warning(f"No text to index for session {session_id}")
        return 0

    # Build chunk → page mapping
    chunks = chunk_text(full_text)
    if not chunks:
        return 0

    # Map each chunk back to an approximate page number
    chunk_pages: list[int] = []
    for chunk in chunks:
        page_num = 0
        for page in pages:
            if chunk[:50] in page.get("text", ""):
                page_num = page.get("page_number", 0)
                break
        chunk_pages.append(page_num)

    # Generate embeddings
    embeddings = await embed_texts(chunks)

    # Store in FAISS
    faiss_store.add_embeddings(
        session_id=session_id,
        embeddings=embeddings,
        chunks=chunks,
        pages=chunk_pages,
    )

    logger.info(f"Indexed {len(chunks)} chunks for session {session_id}")
    return len(chunks)


async def retrieve_context(
    session_id: str,
    query: str = "architecture requirements dataset latency",
    top_k: int = 8,
) -> str:
    """
    Retrieve the most relevant text chunks from FAISS for a session.
    Returns them joined as a single context string for LLM signal extraction.
    """
    query_embeddings = await embed_texts([query])
    if not query_embeddings:
        return ""

    hits = faiss_store.search(session_id, query_embeddings[0], top_k=top_k)
    context = "\n\n".join(h["text"] for h in hits)
    logger.info(f"Retrieved {len(hits)} chunks from FAISS for session {session_id}")
    return context


async def retrieve_context_for_signals(
    session_id: str,
    top_k_per_signal: int = 4,
) -> str:
    """Retrieve context using signal-specific queries for better coverage.

    Runs one FAISS query per signal using SIGNAL_RETRIEVAL_QUERIES, then
    deduplicates and joins the results. This produces higher-quality context
    than a single generic query because each signal gets focused retrieval.

    Args:
        session_id: The analysis session ID.
        top_k_per_signal: Number of chunks to retrieve per signal query.

    Returns:
        Deduplicated context string from all signal-specific queries.
    """
    all_queries = list(SIGNAL_RETRIEVAL_QUERIES.values())
    if not all_queries:
        return ""

    # Batch-embed all signal queries at once for efficiency
    query_embeddings = await embed_texts(all_queries)
    if not query_embeddings:
        return ""

    seen_chunks: set[str] = set()
    ordered_chunks: list[str] = []

    for i, query_name in enumerate(SIGNAL_RETRIEVAL_QUERIES.keys()):
        hits = faiss_store.search(session_id, query_embeddings[i], top_k=top_k_per_signal)
        for hit in hits:
            chunk_text_val = hit.get("text", "")
            if chunk_text_val and chunk_text_val not in seen_chunks:
                seen_chunks.add(chunk_text_val)
                ordered_chunks.append(chunk_text_val)

    context = "\n\n".join(ordered_chunks)
    logger.info(
        "Multi-query FAISS retrieval: %d unique chunks from %d signal queries for session %s",
        len(ordered_chunks), len(all_queries), session_id,
    )
    return context

