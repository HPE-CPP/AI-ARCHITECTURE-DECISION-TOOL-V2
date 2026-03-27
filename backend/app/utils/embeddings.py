"""
Text chunking + OpenAI embedding utilities.
"""
import logging
from typing import Optional

import numpy as np
import tiktoken

from config import settings

logger = logging.getLogger(__name__)

_enc = tiktoken.get_encoding("cl100k_base")  # works for text-embedding-3-*


def chunk_text(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
) -> list[str]:
    """
    Split `text` into overlapping token-window chunks.
    Returns a list of text strings.
    """
    chunk_size = chunk_size or settings.EMBEDDING_CHUNK_SIZE
    overlap = overlap or settings.EMBEDDING_CHUNK_OVERLAP

    tokens = _enc.encode(text)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(_enc.decode(chunk_tokens))
        if end == len(tokens):
            break
        start += chunk_size - overlap
    return chunks


async def embed_texts(texts: list[str]) -> list[np.ndarray]:
    """
    Generate embeddings for a list of text strings using OpenAI.
    Returns a list of float32 numpy arrays (one per input text).
    Falls back to zero-vectors if OpenAI key is absent.
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY — returning zero-vectors for embeddings.")
        dim = settings.EMBEDDING_DIMENSION
        return [np.zeros(dim, dtype=np.float32) for _ in texts]

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Batch in groups of 100 (OpenAI limit)
    results: list[np.ndarray] = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=batch,
        )
        for item in resp.data:
            results.append(np.array(item.embedding, dtype=np.float32))

    return results
