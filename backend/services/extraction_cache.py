"""
P7-005 FIX: Two-tier extraction cache (L1 in-memory + L2 Redis write-through).

Problem:
    The original ExtractionCache was a plain in-memory dict.  Under a
    4-worker uvicorn deployment each worker has its own independent dict,
    giving an effective cache hit rate of ~25% (only the worker that
    originally processed the document can hit the cache).

Solution:
    L1 (in-memory, per-process): fast, zero-latency — same behaviour as before.
    L2 (Redis, shared across all workers): on L1 miss we check Redis; if found
    we populate L1 and return.  On set() we write to both tiers.

    Graceful degradation: if Redis is unavailable (client is None or raises),
    we silently fall back to L1-only behaviour — no crash, no error surfaced.
"""
import hashlib
import json
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 3600  # 1 hour
_REDIS_KEY_PREFIX = "extraction_cache"


class ExtractionCache:
    """Two-tier (in-memory L1 + Redis L2) extraction result cache.

    Thread-safety note: the _store dict is mutated from multiple async
    coroutines that run on the same OS thread (asyncio), so GIL protection
    is sufficient.  No additional lock is needed for the L1 dict.
    """

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL):
        self._store: dict[str, tuple[dict, float]] = {}
        self._ttl = ttl_seconds
        self._redis = self._init_redis()

    # ------------------------------------------------------------------
    # Redis initialisation — deferred so this module can be imported
    # even when Redis env vars are not yet loaded (e.g. in tests).
    # ------------------------------------------------------------------
    @staticmethod
    def _init_redis():
        """Return a Redis client or None if unavailable."""
        try:
            import os, redis as redis_lib
            url = os.getenv("REDIS_URL", "")
            token = os.getenv("REDIS_TOKEN", "")
            if not url:
                return None
            kwargs: dict = {"decode_responses": True}
            if token:
                kwargs["password"] = token
            return redis_lib.Redis.from_url(url, **kwargs)
        except Exception as exc:
            logger.warning("ExtractionCache: Redis init failed — L1-only mode. %s", exc)
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    def _redis_key(self, hash_key: str) -> str:
        return f"{_REDIS_KEY_PREFIX}:{hash_key}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, text: str) -> Optional[dict]:
        key = self._key(text)

        # L1: in-process dict
        entry = self._store.get(key)
        if entry is not None:
            result, ts = entry
            if time.time() - ts < self._ttl:
                logger.info("ExtractionCache L1 hit (key=%s…)", key[:12])
                return result
            # Expired in L1 — remove and fall through to L2
            del self._store[key]

        # L2: Redis
        if self._redis is not None:
            try:
                raw = self._redis.get(self._redis_key(key))
                if raw:
                    result = json.loads(raw)
                    # Populate L1 for the next request on this worker
                    self._store[key] = (result, time.time())
                    logger.info("ExtractionCache L2 (Redis) hit (key=%s…)", key[:12])
                    return result
            except Exception as exc:
                logger.warning("ExtractionCache Redis GET failed (L1-only fallback): %s", exc)

        return None

    def set(self, text: str, result: dict, ttl_seconds: Optional[int] = None) -> None:
        """Cache a result with an optional custom TTL."""
        key = self._key(text)
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl

        # Write to L1
        self._store[key] = (result, now)
        self._evict_expired()

        # Write-through to L2 (Redis)
        if self._redis is not None:
            try:
                self._redis.setex(
                    self._redis_key(key),
                    ttl,
                    json.dumps(result),
                )
            except Exception as exc:
                logger.warning("ExtractionCache Redis SET failed (L1-only stored): %s", exc)

    def _evict_expired(self) -> None:
        now = time.time()
        stale = [k for k, (_, ts) in self._store.items() if now - ts >= self._ttl]
        for k in stale:
            del self._store[k]

    def invalidate(self, text: str) -> None:
        key = self._key(text)
        self._store.pop(key, None)
        if self._redis is not None:
            try:
                self._redis.delete(self._redis_key(key))
            except Exception as exc:
                logger.warning("ExtractionCache Redis DELETE failed: %s", exc)

    def clear(self) -> None:
        """Clear all entries from both L1 and L2 (Redis) tiers."""
        self._store.clear()
        if self._redis is not None:
            try:
                # Flush all keys with our prefix
                keys = self._redis.keys(f"{_REDIS_KEY_PREFIX}:*")
                if keys:
                    self._redis.delete(*keys)
            except Exception as exc:
                logger.warning("ExtractionCache Redis clear failed: %s", exc)

    @property
    def size(self) -> int:
        return len(self._store)


# Module-level singleton shared across all requests within this process
extraction_cache = ExtractionCache()

