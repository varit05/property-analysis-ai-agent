"""
Skill Response Cache — caches results from external data source calls
(SPARQL queries, HPI API requests) in Redis.

Unlike the previous LangChain LLM cache, this module caches the *output*
of skill function calls (e.g. ``price_paid_transactions``, ``regional_hpi``,
``sparql_query``). This is far more effective because:
  - The same postcode district or region is frequently queried multiple times.
  - External API calls are expensive (200–500 ms each).
  - It does not block streaming — the LLM pipeline is never intercepted.

Usage::

    from server.core.llm_cache import invalidate_cache, get_cache_stats, \
        get_cached_skill_result, set_cached_skill_result

    # Check before calling an external API
    result = await get_cached_skill_result(
        "price_paid_transactions",
        {"postcode": "GU1"}
    )
    if result is None:
        result = await price_paid_transactions(postcode="GU1")
        await set_cached_skill_result(
            "price_paid_transactions", {"postcode": "GU1"},
            result
        )

Redis connection is lazily established on the first cache operation and is
non-blocking beyond the initial ``ping()`` validation.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from server.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy Redis client
# ---------------------------------------------------------------------------

_redis_client = None
_redis_available = False


async def _get_redis_client():
    """Return the shared Redis client, initialising it on first call.

    Returns ``None`` if Redis is not configured or unreachable.
    """
    global _redis_client, _redis_available

    if _redis_available:
        return _redis_client

    if _redis_client is None:
        if not settings.REDIS_URL:
            logger.info("No REDIS_URL set — caching disabled")
            return None

        try:
            import redis.asyncio as aioredis

            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await _redis_client.ping()
            _redis_available = True
            logger.info("Skill cache connected to Redis at %s", settings.REDIS_URL)
        except Exception:
            logger.warning(
                "Redis unavailable (%s) — caching disabled",
                settings.REDIS_URL,
                exc_info=True,
            )
            _redis_client = None
            _redis_available = False

    return _redis_client if _redis_available else None


# ---------------------------------------------------------------------------
# Cache key helpers
# ---------------------------------------------------------------------------


def _make_cache_key(function_name: str, params: dict[str, Any]) -> str:
    """Build a deterministic cache key from a function name and its arguments.

    Example::

        skill:price_paid_transactions:9b2a8c1d5e6f
    """
    # Sort params so the key is deterministic regardless of dict ordering
    param_str = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(
        param_str.encode("utf-8"), usedforsecurity=False
    ).hexdigest()
    return f"skill:{function_name}:{param_hash}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_cached_skill_result(
    function_name: str, params: dict[str, Any]
) -> Any | None:
    """Retrieve a cached skill result from Redis.

    Args:
        function_name: The name of the skill function (e.g. ``"sparql_query"``).
        params: The parameters the function was called with.

    Returns the cached JSON-decoded result, or ``None`` if no cache entry
    exists or Redis is unavailable.
    """
    client = await _get_redis_client()
    if client is None:
        return None

    key = _make_cache_key(function_name, params)
    try:
        raw = await client.get(key)
        if raw is not None:
            logger.info("Cache HIT for %s", key)
            return json.loads(raw)
        logger.info("Cache MISS for %s", key)
        return None
    except Exception:
        logger.exception("Failed to read cache key '%s'", key)
        return None


async def set_cached_skill_result(
    function_name: str,
    params: dict[str, Any],
    result: Any,
    ttl: int | None = None,
) -> None:
    """Store a skill result in Redis with a TTL.

    Args:
        function_name: The name of the skill function.
        params: The parameters the function was called with.
        result: The result to cache (must be JSON-serialisable).
        ttl: Time-to-live in seconds. Defaults to ``settings.LLM_CACHE_TTL``.
    """
    client = await _get_redis_client()
    if client is None:
        return

    if ttl is None:
        ttl = settings.LLM_CACHE_TTL

    key = _make_cache_key(function_name, params)
    try:
        serialised = json.dumps(result, default=str)
        await client.setex(key, ttl, serialised)
        logger.info("Cached %s (TTL=%ds)", key, ttl)
    except Exception:
        logger.exception("Failed to write cache key '%s'", key)


async def invalidate_cache() -> dict:
    """Clear all skill cache entries from Redis.

    Returns a dict with status information.
    """
    client = await _get_redis_client()
    if client is None:
        return {"status": "ok", "message": "No cache configured."}

    try:
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match="skill:*", count=100)
            if keys:
                await client.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        logger.info("Cache invalidated — %d keys removed", deleted)
        return {
            "status": "ok",
            "message": f"Skill cache cleared ({deleted} keys removed).",
        }
    except Exception as exc:
        logger.exception("Failed to clear skill cache")
        return {"status": "error", "message": str(exc)}


async def get_cache_stats() -> dict:
    """Return statistics about the current cache backend."""
    client = await _get_redis_client()
    if client is None:
        return {"backend": "none", "stats": {}}

    try:
        # Count skill keys
        cursor = 0
        count = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match="skill:*", count=5000)
            count += len(keys)
            if cursor == 0:
                break

        return {
            "backend": "redis",
            "stats": {
                "skill_keys": count,
                "ttl_seconds": settings.LLM_CACHE_TTL,
            },
        }
    except Exception as exc:
        return {"backend": "redis", "stats": {"error": str(exc)}}
