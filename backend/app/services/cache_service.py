"""
Redis cache service — wraps Upstash Redis (or any Redis) with
a simple get/set/delete API using JSON serialisation.
"""
import json
import logging
from typing import Any, Optional

import redis as redis_lib

from config import settings

logger = logging.getLogger(__name__)

# Build Redis client once at module load time.
# Upstash requires SSL; the URL starts with rediss://
_redis_kwargs: dict = {"decode_responses": True}
if settings.REDIS_TOKEN:
    # Upstash REST-style auth: password = token
    # (SSL is automatically inferred from the rediss:// URL schema)
    _redis_kwargs["password"] = settings.REDIS_TOKEN

try:
    _client = redis_lib.Redis.from_url(settings.REDIS_URL, **_redis_kwargs)
    _client.ping()
    logger.info("Redis connected successfully.")
except Exception as exc:
    logger.warning(f"Redis unavailable — caching disabled. Reason: {exc}")
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
