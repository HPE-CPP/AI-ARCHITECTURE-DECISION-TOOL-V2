"""
Content-Addressable Document Cache

SHA-256 fingerprinting of document content + provider to enable instant
re-processing of identical documents. Caches the full processed result
including signals, scores, and FAISS indexing state.

Cache layers:
  - L1: In-memory dict (per-process, zero latency)
  - L2: Redis (shared across workers, persistent with TTL)

When a cache hit occurs, the system skips:
  - parsing, chunking, embedding, FAISS indexing
  - signal extraction, scoring
  - but still creates an analysis session row for auditability
"""
import hashlib
import json
import logging
import time
from typing import Optional, Any

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 7200  # 2 hours
_REDIS_KEY_PREFIX = "doc_cache"


class DocumentCache:
    """Content-addressable cache for processed document results."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL):
        self._store: dict[str, tuple[dict, float]] = {}
        self._ttl = ttl_seconds
        self._redis = self._init_redis()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _init_redis():
        """Return a Redis client or None if unavailable."""
        try:
            import os
            import redis as redis_lib

            url = os.getenv("REDIS_URL", "")
            token = os.getenv("REDIS_TOKEN", "")
            if not url:
                return None

            kwargs: dict = {"decode_responses": True}
            if token:
                kwargs["password"] = token

            # Handle Upstash rediss:// SSL connections properly
            if url.startswith("rediss://"):
                import ssl
                kwargs["ssl_cert_reqs"] = ssl.CERT_NONE

            client = redis_lib.Redis.from_url(url, **kwargs)
            return client
        except Exception as exc:
            logger.warning("DocumentCache: Redis init failed — L1-only mode. %s", exc)
            return None

    def fingerprint(self, content: bytes, provider: str = "") -> str:
        """Generate SHA-256 fingerprint from document content + provider.

        Including the provider in the fingerprint ensures that results
        cached with OpenAI won't be served for Ollama requests (and vice versa),
        since different models produce different extractions.
        """
        hasher = hashlib.sha256()
        hasher.update(content)
        if provider:
            hasher.update(provider.encode("utf-8"))
        return hasher.hexdigest()

    def get(self, fingerprint: str) -> Optional[dict]:
        """Look up a cached result by document fingerprint.

        Checks L1 (in-memory) first, then L2 (Redis).
        """
        # L1: in-memory
        entry = self._store.get(fingerprint)
        if entry is not None:
            result, ts = entry
            if time.time() - ts < self._ttl:
                self._hits += 1
                logger.info(
                    "DocumentCache L1 HIT (fp=%s…) hits=%d misses=%d",
                    fingerprint[:16], self._hits, self._misses,
                )
                return result
            del self._store[fingerprint]

        # L2: Redis
        if self._redis is not None:
            try:
                raw = self._redis.get(f"{_REDIS_KEY_PREFIX}:{fingerprint}")
                if raw:
                    result = json.loads(raw)
                    self._store[fingerprint] = (result, time.time())
                    self._hits += 1
                    logger.info(
                        "DocumentCache L2 (Redis) HIT (fp=%s…) hits=%d misses=%d",
                        fingerprint[:16], self._hits, self._misses,
                    )
                    return result
            except Exception as exc:
                logger.warning("DocumentCache Redis GET failed: %s", exc)

        self._misses += 1
        return None

    def set(self, fingerprint: str, result: dict, ttl: int = None) -> None:
        """Cache a processed result."""
        ttl = ttl if ttl is not None else self._ttl

        # L1
        self._store[fingerprint] = (result, time.time())
        self._evict_expired()

        # L2: Redis
        if self._redis is not None:
            try:
                self._redis.setex(
                    f"{_REDIS_KEY_PREFIX}:{fingerprint}",
                    ttl,
                    json.dumps(result, default=str),
                )
            except Exception as exc:
                logger.warning("DocumentCache Redis SET failed: %s", exc)

    def _evict_expired(self) -> None:
        """Remove expired entries from L1 cache."""
        now = time.time()
        stale = [k for k, (_, ts) in self._store.items() if now - ts >= self._ttl]
        for k in stale:
            del self._store[k]

    def invalidate(self, fingerprint: str) -> None:
        """Remove a specific entry from both cache tiers."""
        self._store.pop(fingerprint, None)
        if self._redis is not None:
            try:
                self._redis.delete(f"{_REDIS_KEY_PREFIX}:{fingerprint}")
            except Exception as exc:
                logger.warning("DocumentCache Redis DELETE failed: %s", exc)

    @property
    def stats(self) -> dict:
        """Return cache hit/miss statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            "l1_size": len(self._store),
        }


# Module-level singleton
document_cache = DocumentCache()
