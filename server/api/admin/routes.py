import logging

from fastapi import APIRouter

from server.core.llm_cache import (
    get_cache_stats as _get_cache_stats,
)
from server.core.llm_cache import (
    invalidate_cache as _invalidate_cache,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/cache/invalidate")
async def admin_invalidate_cache():
    """Invalidate the skill response cache.

    Useful after deploying new skills or if cached data is suspected stale.
    This clears all cached skill responses (SPARQL queries, HPI data, etc.).
    """
    result = await _invalidate_cache()
    return result


@router.get("/cache/stats")
async def admin_cache_stats():
    """Return statistics about the skill response cache backend."""
    stats = await _get_cache_stats()
    return stats
