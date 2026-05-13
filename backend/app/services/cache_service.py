"""
Redis cache service — wraps Upstash Redis (or any Redis) with
a simple get/set/delete API using JSON serialisation.

SSL/TLS:
  - Automatically handles rediss:// (Upstash) connections.
  - Sets ssl_cert_reqs=CERT_NONE for Upstash compatibility.
  - Graceful fallback when Redis is unavailable.
"""
import json
import logging
from typing import Any, Optional

import redis as redis_lib

from config import settings

logger = logging.getLogger(__name__)

# Build Redis client once at module load time.
_redis_kwargs: dict = {"decode_responses": True}
if settings.REDIS_TOKEN:
    _redis_kwargs["password"] = settings.REDIS_TOKEN

# Fix Redis SSL for Upstash rediss:// URLs
if settings.REDIS_URL.startswith("rediss://"):
    import ssl
    _redis_kwargs["ssl_cert_reqs"] = ssl.CERT_NONE
    logger.info("Redis SSL mode enabled for rediss:// URL.")

try:
    _client = redis_lib.Redis.from_url(settings.REDIS_URL, **_redis_kwargs)
    # Verify connectivity with a non-blocking test
    try:
        _client.ping()
        logger.info("Redis connection verified successfully.")
    except Exception as ping_exc:
        logger.warning("Redis ping failed — caching may be unavailable: %s", ping_exc)
        # Keep the client — it may recover on next operation
except Exception as exc:
    logger.warning(f"Redis client creation failed — caching disabled. Reason: {exc}")
    _client = None  # type: ignore[assignment]


def _key(prefix: str, session_id: str) -> str:
    return f"{prefix}:{session_id}"


def get(prefix: str, session_id: str) -> Optional[Any]:
    """Return cached value or None if missing / Redis down."""
    if _client is None:
        return None
    try:
        raw = _client.get(_key(prefix, session_id))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning(f"Redis GET failed: {exc}")
        return None


def set(prefix: str, session_id: str, value: Any, ttl: int = 600) -> None:
    """Cache a JSON-serialisable value with a TTL (seconds)."""
    if _client is None:
        return
    try:
        _client.setex(_key(prefix, session_id), ttl, json.dumps(value))
    except Exception as exc:
        logger.warning(f"Redis SET failed: {exc}")


def delete(prefix: str, session_id: str) -> None:
    """Evict a cache key."""
    if _client is None:
        return
    try:
        _client.delete(_key(prefix, session_id))
    except Exception as exc:
        logger.warning(f"Redis DELETE failed: {exc}")


# Convenience wrappers for the two main cache namespaces
SIGNALS_TTL = 600   # 10 min
RESULT_TTL  = 900   # 15 min


def get_signals(session_id: str) -> Optional[dict]:
    return get("signals", session_id)


def set_signals(session_id: str, signals: dict) -> None:
    set("signals", session_id, signals, ttl=SIGNALS_TTL)


def get_result(session_id: str) -> Optional[dict]:
    return get("result", session_id)


def set_result(session_id: str, result: dict) -> None:
    set("result", session_id, result, ttl=RESULT_TTL)


def invalidate_session(session_id: str) -> None:
    """Purge all cache entries related to a session."""
    delete("signals", session_id)
    delete("result", session_id)
