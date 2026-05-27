"""
Tests for Properties API endpoints.

Since the service now runs Properties analysis in a background task, the
POST /analyze endpoint returns immediately with status "running".
Background execution is mocked to avoid side effects.
"""

from unittest.mock import AsyncMock, patch

import pytest

from server.api.properties.schemas import (
    ANALYSIS_STATUS_ACCEPTED,
    ANALYSIS_STATUS_PENDING_REVIEW,
    ANALYSIS_STATUS_REJECTED,
    ANALYSIS_STATUS_RUNNING,
)

# Module-level in-memory store dict shared between the mock and tests
_in_memory_store: dict = {}


class _MockStore:
    """In-memory store that mimics AnalysisStore interface."""

    async def get(self, analysis_id):
        return _in_memory_store.get(analysis_id)

    async def upsert(self, analysis_id, data):
        if analysis_id in _in_memory_store:
            _in_memory_store[analysis_id].update(data)
        else:
            _in_memory_store[analysis_id] = data
        return _in_memory_store[analysis_id]

    async def list(self, query_filter=None, skip=0, limit=100):
        items = list(_in_memory_store.values())
        if query_filter:
            q = query_filter.lower()
            items = [r for r in items if q in r.get("query", "").lower()]
        total = len(items)
        return items[skip : skip + limit], total


def _upsert_sync(analysis_id, data):
    """Helper to upsert into the mock store synchronously."""
    if analysis_id in _in_memory_store:
        _in_memory_store[analysis_id].update(data)
    else:
        _in_memory_store[analysis_id] = data


@pytest.fixture(autouse=True)
def mock_deps():
    """Replace the real file-backed store & background task for all tests."""
    _in_memory_store.clear()
    mock_store = _MockStore()

    with (
        patch("server.api.properties.service.get_store", return_value=mock_store),
        patch("server.api.properties.routes.get_store", return_value=mock_store),
        patch("server.api.properties.service.DeepAgent") as mock_agent_cls,
    ):
        # Mock DeepAgent directly instead of the removed _get_agent —
        # each background task now creates a fresh DeepAgent instance.
        # Default mock agent that does nothing — tests override as needed
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = {
            "research_note": "",
            "charts": [],
            "trace": [],
            "iterations": 1,
        }
        mock_agent_cls.return_value = mock_agent_instance
        yield


class TestPropertiesAPI:
    """Test suite for Properties API endpoints."""

    def test_get_analysis_not_found(self, client):
        """Test getting a non-existent analysis."""
        response = client.get("/api/v1/properties/analyses/non-existent-id")
        assert response.status_code == 404

    def test_trigger_analysis_returns_running_status(self, client):
        """Test that POST /analyze returns immediately with status 'running'."""
        response = client.post(
            "/api/v1/properties/analyze",
            json={"query": "Analyse property price trends in GU1"},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == ANALYSIS_STATUS_RUNNING
        assert data["query"] == "Analyse property price trends in GU1"
        assert data["result"] is None
        assert data["error"] is None
        assert "id" in data
        assert "created_at" in data

    def test_trigger_analysis_with_additional_context(self, client):
        """Test that additional_context appears in the response."""
        response = client.post(
            "/api/v1/properties/analyze",
            json={
                "query": "Analyse property prices in GU1",
                "additional_context": "Focus on detached houses",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == ANALYSIS_STATUS_RUNNING
        assert data["additional_context"] == "Focus on detached houses"

    def test_trigger_analysis_invalid_request_empty_query(self, client):
        """Test validation error for empty query."""
        response = client.post(
            "/api/v1/properties/analyze",
            json={"query": ""},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_trigger_analysis_invalid_request_missing_query(self, client):
        """Test validation error for missing query field."""
        response = client.post(
            "/api/v1/properties/analyze",
            json={},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_trigger_analysis_invalid_request_type(self, client):
        """Test validation error for wrong type."""
        response = client.post(
            "/api/v1/properties/analyze",
            json={"query": 12345},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    # ------------------------------------------------------------------
    # Review tests
    # ------------------------------------------------------------------

    def test_review_analysis_not_found(self, client):
        """Test reviewing a non-existent analysis returns 404."""
        response = client.post(
            "/api/v1/properties/analyses/non-existent-id/review",
            json={"action": "accept"},
        )
        assert response.status_code == 404

    def test_review_analysis_accept(self, client):
        """Test accepting a completed (pending_review) analysis."""
        _upsert_sync(
            "review-accept-test",
            {
                "id": "review-accept-test",
                "query": "test",
                "additional_context": None,
                "status": ANALYSIS_STATUS_PENDING_REVIEW,
                "result": {
                    "research_note": "Analysis complete.",
                    "charts": [],
                    "trace": [],
                },
                "error": None,
                "trace_steps": [],
                "created_at": "2026-01-01T00:00:00",
                "completed_at": "2026-01-01T00:01:00",
                "reviewed_at": None,
            },
        )

        response = client.post(
            "/api/v1/properties/analyses/review-accept-test/review",
            json={"action": "accept"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["analysis"]["status"] == ANALYSIS_STATUS_ACCEPTED
        assert "accepted" in data["message"]
        assert data["analysis"]["reviewed_at"] is not None

    def test_review_analysis_reject(self, client):
        """Test rejecting a pending analysis."""
        _upsert_sync(
            "review-reject-test",
            {
                "id": "review-reject-test",
                "query": "test",
                "additional_context": None,
                "status": ANALYSIS_STATUS_PENDING_REVIEW,
                "result": {
                    "research_note": "Analysis complete.",
                    "charts": [],
                    "trace": [],
                },
                "error": None,
                "trace_steps": [],
                "created_at": "2026-01-01T00:00:00",
                "completed_at": "2026-01-01T00:01:00",
                "reviewed_at": None,
            },
        )

        response = client.post(
            "/api/v1/properties/analyses/review-reject-test/review",
            json={"action": "reject", "reason": "Not relevant"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["analysis"]["status"] == ANALYSIS_STATUS_REJECTED
        assert "rejected" in data["message"]
        assert data["analysis"]["reviewed_at"] is not None

    def test_review_analysis_already_reviewed(self, client):
        """Test that double-reviewing returns 409 Conflict."""
        _upsert_sync(
            "already-reviewed",
            {
                "id": "already-reviewed",
                "query": "test",
                "status": ANALYSIS_STATUS_ACCEPTED,
                "result": None,
                "error": None,
                "trace_steps": [],
                "created_at": "2026-01-01T00:00:00",
            },
        )

        response = client.post(
            "/api/v1/properties/analyses/already-reviewed/review",
            json={"action": "accept"},
        )
        assert response.status_code == 409
        data = response.json()
        assert "already" in data.get("error", "").lower()

    def test_review_analysis_wrong_status(self, client):
        """Test that reviewing a running analysis returns 409."""
        _upsert_sync(
            "still-running",
            {
                "id": "still-running",
                "query": "test",
                "status": ANALYSIS_STATUS_RUNNING,
                "result": None,
                "error": None,
                "trace_steps": [],
                "created_at": "2026-01-01T00:00:00",
            },
        )

        response = client.post(
            "/api/v1/properties/analyses/still-running/review",
            json={"action": "accept"},
        )
        assert response.status_code == 409
        data = response.json()
        assert "cannot review" in data.get("error", "").lower()

    # ------------------------------------------------------------------
    # SSE stream tests
    # ------------------------------------------------------------------

    def test_stream_analysis_not_found(self, client):
        """Test SSE endpoint for non-existent analysis returns 404."""
        response = client.get("/api/v1/properties/analyses/non-existent-id/stream")
        assert response.status_code == 404

    def test_stream_analysis_replays_existing_steps(self, client):
        """Test that SSE endpoint replays existing trace steps on connect."""
        _upsert_sync(
            "stream-replay-test",
            {
                "id": "stream-replay-test",
                "query": "test",
                "status": ANALYSIS_STATUS_PENDING_REVIEW,
                # terminal status — stream ends
                "result": None,
                "error": None,
                "trace_steps": [
                    {"step_number": 1, "action": "Step 1", "status": "success"},
                    {"step_number": 2, "action": "Step 2", "status": "success"},
                ],
                "created_at": "2026-01-01T00:00:00",
                "completed_at": "2026-01-01T00:01:00",
            },
        )

        response = client.get("/api/v1/properties/analyses/stream-replay-test/stream")
        assert response.status_code == 200
        content = response.text
        assert "Step 1" in content
        assert "Step 2" in content
        # Verify SSE format
        assert "event: trace_step" in content
        # Should also emit a terminal status event
        assert "pending_review" in content
