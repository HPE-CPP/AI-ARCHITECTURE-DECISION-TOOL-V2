"""
FAISS index helper — load, save, add embeddings, and search.
Each session gets its own sub-directory inside FAISS_INDEX_PATH.
Metadata (chunk text + page numbers) is stored in a JSON sidecar.
"""
import json
import logging
import os
from pathlib import Path
from typing import Optional

import faiss
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


def _session_dir(session_id: str) -> Path:
    path = Path(settings.FAISS_INDEX_PATH) / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_path(session_id: str) -> Path:
    return _session_dir(session_id) / "index.faiss"


def _meta_path(session_id: str) -> Path:
    return _session_dir(session_id) / "meta.json"


def _get_dim() -> int:
    """Return the embedding dimension for the current provider.

    B-06 FIX: Resolve the dimension at call-time rather than at module import,
    so provider switches (ollama<->openai) pick up the correct dimensionality.
    """
    provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return getattr(settings, "OLLAMA_EMBEDDING_DIMENSION", 768)
    return settings.EMBEDDING_DIMENSION


def _dim_path(session_id: str) -> Path:
    """Path to the file that records the FAISS index dimension for this session."""
    return _session_dir(session_id) / "dim.txt"


def _load_or_create(session_id: str, dim: int) -> faiss.IndexFlatL2:
    """Load an existing FAISS index if the stored dimension matches `dim`.

    B-06 FIX: If the stored dimension doesn't match (e.g. after a provider
    switch), discard the old index and start fresh to avoid a FAISS crash.
    """
    ip = _index_path(session_id)
    dp = _dim_path(session_id)

    if ip.exists() and dp.exists():
        stored_dim = int(dp.read_text().strip())
        if stored_dim == dim:
            return faiss.read_index(str(ip))
        else:
            logger.warning(
                "FAISS dimension mismatch for session %s: stored=%d, requested=%d. "
                "Discarding old index.",
                session_id, stored_dim, dim,
            )
            ip.unlink(missing_ok=True)
            dp.unlink(missing_ok=True)
            _save_meta(session_id, [])  # clear stale metadata

    # Write the dimension so future calls can validate it
    dp.write_text(str(dim))
    return faiss.IndexFlatL2(dim)


def _load_meta(session_id: str) -> list[dict]:
    mp = _meta_path(session_id)
    if mp.exists():
        with open(mp, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_meta(session_id: str, meta: list[dict]) -> None:
    mp = _meta_path(session_id)
    with open(mp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_embeddings(
    session_id: str,
    embeddings: list[np.ndarray],
    chunks: list[str],
    pages: Optional[list[int]] = None,
) -> None:
    """
    Add embeddings (and their text chunks) to the session's FAISS index.

    Args:
        session_id: Unique session identifier.
        embeddings:  List of float32 numpy arrays (shape [dim]).
        chunks:      Corresponding text strings.
        pages:       Optional page numbers for each chunk.
    """
    if not embeddings:
        return

    dim = embeddings[0].shape[0]
    pages = pages or [0] * len(chunks)
    index = _load_or_create(session_id, dim)  # B-06: pass dim for validation
    meta = _load_meta(session_id)

    vectors = np.stack(embeddings).astype(np.float32)
    faiss.normalize_L2(vectors)  # cosine similarity via normalised L2
    index.add(vectors)  # type: ignore[arg-type]

    for i, (chunk, page) in enumerate(zip(chunks, pages)):
        meta.append({
            "chunk_id": len(meta) + i,
            "session_id": session_id,
            "text": chunk,
            "page": page,
        })

    faiss.write_index(index, str(_index_path(session_id)))
    _save_meta(session_id, meta)
    logger.info(f"FAISS: added {len(embeddings)} vectors for session {session_id}")


def search(
    session_id: str,
    query_embedding: np.ndarray,
    top_k: int = 5,
) -> list[dict]:
    """
    Search the session's FAISS index.

    Returns a list of metadata dicts (text, page, chunk_id) for the top-k matches.
    """
    ip = _index_path(session_id)
    if not ip.exists():
        logger.warning(f"FAISS index not found for session {session_id}")
        return []

    index = faiss.read_index(str(ip))
    meta = _load_meta(session_id)

    vec = query_embedding.astype(np.float32).reshape(1, -1)
    faiss.normalize_L2(vec)

    actual_k = min(top_k, index.ntotal)
    if actual_k == 0:
        return []

    _distances, indices = index.search(vec, actual_k)  # type: ignore[arg-type]

    results = []
    for idx in indices[0]:
        if 0 <= idx < len(meta):
            results.append(meta[idx])
    return results


def delete_session_index(session_id: str) -> None:
    """Remove all FAISS data for a session."""
    import shutil
    session_dir = _session_dir(session_id)
    if session_dir.exists():
        shutil.rmtree(session_dir)
        logger.info(f"FAISS: deleted index for session {session_id}")
