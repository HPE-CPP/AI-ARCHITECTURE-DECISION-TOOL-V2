"""
Vector service — orchestrates chunking, embedding, and FAISS storage
for uploaded documents. Also provides a retrieve() helper for signal
extraction that returns the most relevant chunks for a session.
"""
import logging
from typing import Optional

from app.utils.embeddings import chunk_text, embed_texts
from app.utils import faiss_store

logger = logging.getLogger(__name__)


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
    query: str = (
        "dataset size records volume latency response time query throughput "
        "data volatility updates accuracy security compliance cost budget "
        "deployment cloud on-premise users scale domain specialized"
    ),
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
