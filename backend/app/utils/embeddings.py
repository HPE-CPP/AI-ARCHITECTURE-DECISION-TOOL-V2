"""
Text chunking + embedding utilities.

Sentence-aware chunking:
  - Never splits mid-sentence.
  - Overlapping sentence windows preserve semantic continuity.
  - Deterministic output: identical text always produces identical chunks.
"""
import logging
import re
from typing import Optional

import numpy as np
import tiktoken

from config import settings

logger = logging.getLogger(__name__)

_enc = tiktoken.get_encoding("cl100k_base")  # works for text-embedding-3-*

# Sentence boundary regex — handles common abbreviations gracefully.
# Splits on period/question/exclamation followed by whitespace + uppercase,
# or on newline boundaries.
_SENTENCE_SPLIT_RE = re.compile(
    r'(?<=[.!?])\s+(?=[A-Z])|(?<=\n)\s*(?=\S)'
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences deterministically.

    Falls back to newline splitting if no sentence boundaries are found.
    Preserves original whitespace within sentences.
    """
    if not text.strip():
        return []

    sentences = _SENTENCE_SPLIT_RE.split(text)
    # Filter out empty strings and strip each sentence
    result = [s.strip() for s in sentences if s.strip()]
    return result


def _count_tokens(text: str) -> int:
    """Count tokens using the tiktoken encoder."""
    return len(_enc.encode(text))


def chunk_text(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
) -> list[str]:
    """Split text into overlapping sentence-window chunks.

    Guarantees:
      - Never splits mid-sentence.
      - Overlapping sentence windows (configurable overlap_sentences).
      - Deterministic: identical text always produces identical chunks.
      - Each chunk stays within the token budget (chunk_size tokens).

    Args:
        text: Input text to chunk.
        chunk_size: Maximum tokens per chunk (default from settings).
        overlap: Number of overlap sentences between windows (default 3).

    Returns:
        List of text chunks, each within the token budget.
    """
    chunk_size = chunk_size or settings.EMBEDDING_CHUNK_SIZE
    # overlap is now interpreted as number of overlap sentences
    overlap_sentences = overlap if overlap is not None else 3

    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    i = 0

    while i < len(sentences):
        current_chunk_sentences: list[str] = []
        current_tokens = 0

        # Add sentences until we exceed the token budget
        j = i
        while j < len(sentences):
            sent_tokens = _count_tokens(sentences[j])

            # If a single sentence exceeds chunk_size, include it as its own chunk
            if not current_chunk_sentences and sent_tokens > chunk_size:
                current_chunk_sentences.append(sentences[j])
                j += 1
                break

            if current_tokens + sent_tokens > chunk_size and current_chunk_sentences:
                break

            current_chunk_sentences.append(sentences[j])
            current_tokens += sent_tokens
            j += 1

        if current_chunk_sentences:
            chunks.append(" ".join(current_chunk_sentences))

        # Advance by (sentences consumed - overlap), minimum 1
        sentences_consumed = j - i
        advance = max(1, sentences_consumed - overlap_sentences)
        i += advance

        # Stop if we've consumed everything
        if j >= len(sentences):
            break

    logger.debug(
        "Sentence-aware chunking: %d sentences → %d chunks (budget=%d tokens, overlap=%d sentences)",
        len(sentences), len(chunks), chunk_size, overlap_sentences,
    )
    return chunks


def chunk_text_legacy(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
) -> list[str]:
    """Legacy token-window chunking (kept for backward compatibility).

    Splits on raw token boundaries without sentence awareness.
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
        import asyncio
        from services.llm_client import get_ollama_http_client
        
        dim = getattr(settings, "OLLAMA_EMBEDDING_DIMENSION", 768)
        client = get_ollama_http_client()
        semaphore = asyncio.Semaphore(10)  # B-04 FIX: limit parallel embedding requests to 10

        async def _embed_single(text: str) -> np.ndarray:
            async with semaphore:
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
                        return np.array(data["embedding"], dtype=np.float32)
                except Exception as e:
                    logger.error(f"Ollama embedding error: {e}")
                return np.zeros(dim, dtype=np.float32)

        # B-04 FIX: Parallelize embedding requests instead of serial loop
        results_list = await asyncio.gather(*[_embed_single(t) for t in texts])
        return list(results_list)
        
    else:
        logger.warning(f"Unsupported provider: {provider} — returning zero-vectors.")
        return [np.zeros(settings.EMBEDDING_DIMENSION, dtype=np.float32) for _ in texts]
