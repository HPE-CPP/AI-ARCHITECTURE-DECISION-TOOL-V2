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
    Generate embeddings for a list of text strings using the default provider.
    Returns a list of float32 numpy arrays (one per input text).
    """
    provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "ollama").lower()
    
    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            logger.warning("No OPENAI_API_KEY — returning zero-vectors for embeddings.")
            return [np.zeros(settings.EMBEDDING_DIMENSION, dtype=np.float32) for _ in texts]
            
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

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

    elif provider == "ollama":
        import httpx
        results = []
        dim = getattr(settings, "OLLAMA_EMBEDDING_DIMENSION", 768)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            for text in texts:
                try:
                    resp = await client.post(
                        f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                        json={
                            "model": getattr(settings, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
                            "prompt": text
                        }
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    
                    if "embedding" in data:
                        results.append(np.array(data["embedding"], dtype=np.float32))
                    else:
                        results.append(np.zeros(dim, dtype=np.float32))
                except Exception as e:
                    logger.error(f"Ollama embedding error: {e}")
                    results.append(np.zeros(dim, dtype=np.float32))
        return results
        
    else:
        logger.warning(f"Unsupported provider: {provider} — returning zero-vectors.")
        return [np.zeros(settings.EMBEDDING_DIMENSION, dtype=np.float32) for _ in texts]
