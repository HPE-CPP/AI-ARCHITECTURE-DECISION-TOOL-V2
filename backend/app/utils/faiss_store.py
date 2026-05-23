"""
Qdrant vector store — persistent cloud storage replacing FAISS.
Preserves the same public API: add_embeddings(), search(), delete_session_index()
"""
import logging
import uuid
from typing import Optional

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, FilterSelector,
)

from config import settings

logger = logging.getLogger(__name__)

_client: Optional[QdrantClient] = None


def _get_client() -> QdrantClient:
    global _client
    if _client is not None:
        return _client

    url = (settings.QDRANT_URL or "").strip()
    api_key = settings.QDRANT_API_KEY or None

    # Explicit in-memory mode — useful for local dev without a Qdrant server
    if url in (":memory:", "memory", ""):
        _client = QdrantClient(":memory:")
        logger.info("Qdrant: using in-memory mode (data won't persist across restarts)")
        return _client

    # Try to connect to configured URL (local or cloud)
    try:
        candidate = QdrantClient(url=url, api_key=api_key)
        candidate.get_collections()  # connection probe
        _client = candidate
        logger.info("Qdrant: connected to %s", url)
    except Exception as exc:
        logger.warning(
            "Qdrant: cannot connect to %s (%s) — falling back to in-memory mode. "
            "Document embeddings won't persist across restarts. "
            "Set QDRANT_URL=:memory: in .env to silence this warning, "
            "or configure a real Qdrant instance for persistence.",
            url, exc,
        )
        _client = QdrantClient(":memory:")

    return _client


def _get_dim() -> int:
    provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return getattr(settings, "OLLAMA_EMBEDDING_DIMENSION", 768)
    return settings.EMBEDDING_DIMENSION


def _ensure_collection(client: QdrantClient, dim: int) -> None:
    collection = settings.QDRANT_COLLECTION
    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        logger.info("Qdrant: created collection '%s' dim=%d", collection, dim)


def add_embeddings(
    session_id: str,
    embeddings: list[np.ndarray],
    chunks: list[str],
    pages: Optional[list[int]] = None,
) -> None:
    if not embeddings:
        return

    dim = embeddings[0].shape[0]
    pages = pages or [0] * len(chunks)

    client = _get_client()
    _ensure_collection(client, dim)

    # Delete any existing vectors for this session before re-uploading
    try:
        client.delete(
            collection_name=settings.QDRANT_COLLECTION,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
                )
            ),
        )
    except Exception:
        pass

    points = []
    for i, (embedding, chunk, page) in enumerate(zip(embeddings, chunks, pages)):
        vec = embedding.astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vec.tolist(),
            payload={
                "session_id": session_id,
                "text": chunk,
                "page": page,
                "chunk_index": i,
            },
        ))

    for i in range(0, len(points), 100):
        client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=points[i:i + 100],
        )

    logger.info("Qdrant: upserted %d vectors for session %s", len(points), session_id)


def search(
    session_id: str,
    query_embedding: np.ndarray,
    top_k: int = 5,
) -> list[dict]:
    client = _get_client()

    existing = {c.name for c in client.get_collections().collections}
    if settings.QDRANT_COLLECTION not in existing:
        logger.warning("Qdrant: collection not found for session %s", session_id)
        return []

    vec = query_embedding.astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    results = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=vec.tolist(),
        query_filter=Filter(
            must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
        ),
        limit=top_k,
        with_payload=True,
    )

    hits = [
        {
            "text": r.payload.get("text", ""),
            "page": r.payload.get("page", 0),
            "chunk_id": r.payload.get("chunk_index", 0),
            "session_id": session_id,
        }
        for r in results
        if r.payload
    ]

    logger.info("Qdrant: retrieved %d chunks for session %s", len(hits), session_id)
    return hits


def delete_session_index(session_id: str) -> None:
    client = _get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.QDRANT_COLLECTION not in existing:
        return
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]
            )
        ),
    )
    logger.info("Qdrant: deleted vectors for session %s", session_id)


def cleanup_old_indexes(max_age_days: int = 7) -> int:
    """No-op: Qdrant is persistent, no local file cleanup needed."""
    return 0
