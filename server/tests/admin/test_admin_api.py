"""
Tests for Admin API endpoints (cache management).
"""

from unittest.mock import AsyncMock, patch


class TestAdminAPI:
    """Test suite for Admin API endpoints."""

    def test_cache_invalidate_no_redis(self, client):
        """Test cache invalidation when Redis is unavailable."""
        mock_invalidate = AsyncMock(
            return_value={
                "status": "ok",
                "message": "No cache configured.",
            }
        )
        with patch("server.api.admin.routes._invalidate_cache", mock_invalidate):
            response = client.post("/api/v1/admin/cache/invalidate")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "no cache" in data["message"].lower()
        mock_invalidate.assert_awaited_once()

    def test_cache_stats_no_redis(self, client):
        """Test cache stats when Redis is unavailable."""
        mock_stats = AsyncMock(return_value={"backend": "none", "stats": {}})
        with patch("server.api.admin.routes._get_cache_stats", mock_stats):
            response = client.get("/api/v1/admin/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "none"
        assert data["stats"] == {}
        mock_stats.assert_awaited_once()

    def test_cache_invalidate_success(self, client):
        """Test successful cache invalidation."""
        mock_invalidate = AsyncMock(
            return_value={
                "status": "ok",
                "message": "Skill cache cleared (5 keys removed).",
            }
        )
        with patch("server.api.admin.routes._invalidate_cache", mock_invalidate):
            response = client.post("/api/v1/admin/cache/invalidate")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "5 keys" in data["message"]
        mock_invalidate.assert_awaited_once()

    def test_cache_stats_success(self, client):
        """Test successful cache stats retrieval."""
        mock_stats = AsyncMock(
            return_value={
                "backend": "redis",
                "stats": {"skill_keys": 5, "ttl_seconds": 3600},
            }
        )
        with patch("server.api.admin.routes._get_cache_stats", mock_stats):
            response = client.get("/api/v1/admin/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "redis"
        assert data["stats"]["skill_keys"] == 5
        assert data["stats"]["ttl_seconds"] == 3600
        mock_stats.assert_awaited_once()

    def test_cache_invalidate_error(self, client):
        """Test cache invalidation when the backend returns an error."""
        mock_invalidate = AsyncMock(
            return_value={
                "status": "error",
                "message": "Connection refused",
            }
        )
        with patch("server.api.admin.routes._invalidate_cache", mock_invalidate):
            response = client.post("/api/v1/admin/cache/invalidate")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert "connection" in data["message"].lower()
        mock_invalidate.assert_awaited_once()

    def test_cache_stats_unexpected_error(self, client):
        """Test cache stats response when the backend is unreachable."""
        mock_stats = AsyncMock(
            return_value={
                "backend": "redis",
                "stats": {"error": "Timeout connecting to Redis"},
            }
        )
        with patch("server.api.admin.routes._get_cache_stats", mock_stats):
            response = client.get("/api/v1/admin/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "redis"
        assert "error" in data["stats"]
        assert "timeout" in data["stats"]["error"].lower()
        mock_stats.assert_awaited_once()
