"""
In-memory TTL cache for signal extraction results, keyed by document content hash.
"""
import hashlib
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 3600  # 1 hour


class ExtractionCache:
    def __init__(self, ttl_seconds: int = _DEFAULT_TTL):
        self._store: dict[str, tuple[dict, float]] = {}
        self._ttl = ttl_seconds

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()

    def get(self, text: str) -> Optional[dict]:
        key = self._key(text)
        entry = self._store.get(key)
        if entry is None:
            return None
        result, ts = entry
        if time.time() - ts >= self._ttl:
            del self._store[key]
            return None
        logger.info("Extraction cache hit (key=%s…)", key[:12])
        return result

    def set(self, text: str, result: dict) -> None:
        key = self._key(text)
        self._store[key] = (result, time.time())
        self._evict_expired()

    def _evict_expired(self) -> None:
        now = time.time()
        stale = [k for k, (_, ts) in self._store.items() if now - ts >= self._ttl]
        for k in stale:
            del self._store[k]

    def invalidate(self, text: str) -> None:
        self._store.pop(self._key(text), None)

    @property
    def size(self) -> int:
        return len(self._store)


# Module-level singleton shared across all requests
extraction_cache = ExtractionCache()
