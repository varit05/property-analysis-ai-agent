"""MCP server for the Property Analysis FastAPI backend.

Exposes three tools that let the AI assistant trigger property analyses,
check analysis results, and review (accept/reject) pending analyses.

Communicates with the FastAPI server via HTTP using ``httpx``.
The FastAPI server URL is read from ``server.core.config.settings.FASTAPI_URL``,
which can be overridden via the ``FASTAPI_URL`` environment variable or ``.env``
file for production deployments.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from mcp.server.fastmcp import FastMCP

from server.core.config import settings

logger = logging.getLogger(__name__)

# ── MCP Server Instance ────────────────────────────────────────────────────

mcp = FastMCP(
    "property-analysis",
    instructions=(
        "Tools for analysing UK property data. "
        "Use `trigger_analysis` to start an AI analysis, "
        "`get_analysis` to retrieve results, "
        "and `review_analysis` to accept or reject a completed analysis."
    ),
)

# ── Shared HTTP Client ─────────────────────────────────────────────────────

# FastAPI base URL – resolved from settings for production compatibility.
BASE_URL = settings.FASTAPI_URL.rstrip("/")


@asynccontextmanager
async def get_client() -> AsyncIterator[httpx.AsyncClient]:
    """Yield a shared ``httpx.AsyncClient`` for the lifetime of a tool call."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        yield client


# ── Tool 1: trigger_analysis ───────────────────────────────────────────────


@mcp.tool()
async def trigger_analysis(
    query: str,
    additional_context: str | None = None,
) -> str:
    """Submit a natural-language property analysis request to the AI agent.

    The agent researches the property using available data sources (e.g.
    price-paid transactions, regional house-price indices, SPARQL queries)
    and returns a research note with optional chart data.

    Returns immediately with an ``analysis_id`` and status ``running``.
    Use ``get_analysis`` to poll for completion.

    Args:
        query: Free-form natural language description of what to analyse
               (e.g. "What's the average house price in GU1 over the last 5
               years?").
        additional_context: Optional extra context to guide the agent's
               analysis (e.g. "Focus on semi-detached properties only").
    """
    payload: dict[str, str | None] = {"query": query}
    if additional_context is not None:
        payload["additional_context"] = additional_context

    async with get_client() as client:
        resp = await client.post("/api/v1/properties/analyze", json=payload)

    if resp.is_error:
        _raise_http_error(resp)

    return _pretty_json(resp.json())


# ── Tool 2: get_analysis ───────────────────────────────────────────────────


@mcp.tool()
async def get_analysis(analysis_id: str) -> str:
    """Retrieve the result of a previously submitted property analysis.

    The response includes the current ``status`` (running, pending_review,
    accepted, rejected, or failed) and, once complete, the ``result``
    containing the research note and chart data.

    Args:
        analysis_id: The UUID returned by ``trigger_analysis``.
    """
    async with get_client() as client:
        resp = await client.get(f"/api/v1/properties/analyses/{analysis_id}")

    if resp.is_error:
        _raise_http_error(resp)

    return _pretty_json(resp.json())


# ── Tool 3: review_analysis ────────────────────────────────────────────────


@mcp.tool()
async def review_analysis(
    analysis_id: str,
    action: str,
    reason: str | None = None,
) -> str:
    """Accept or reject a completed analysis that is pending human review.

    Once accepted, the analysis is considered final. Rejected analyses
    are kept for audit purposes.

    Args:
        analysis_id: The UUID of the analysis to review.
        action: Must be ``"accept"`` or ``"reject"``.
        reason: Optional explanation, particularly useful when rejecting.
    """
    if action not in ("accept", "reject"):
        return json.dumps(
            {
                "error": f"Invalid action '{action}'. Must be 'accept' or 'reject'.",
            },
            indent=2,
        )

    payload: dict[str, str | None] = {"action": action}
    if reason is not None:
        payload["reason"] = reason

    async with get_client() as client:
        resp = await client.post(
            f"/api/v1/properties/analyses/{analysis_id}/review",
            json=payload,
        )

    if resp.is_error:
        _raise_http_error(resp)

    return _pretty_json(resp.json())


# ── Helpers ─────────────────────────────────────────────────────────────────


def _pretty_json(data: dict | list) -> str:
    """Return a human-readable JSON string."""
    return json.dumps(data, indent=2, default=str)


def _raise_http_error(resp: httpx.Response) -> None:
    """Raise a readable error from an unsuccessful HTTP response."""
    try:
        detail = resp.json()
    except Exception:
        detail = resp.text

    raise RuntimeError(
        f"FastAPI returned HTTP {resp.status_code}: {json.dumps(detail, indent=2)}"
    )


# ── Entry Point ────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio transport.

    This is the entry point called by the Cline MCP subprocess.
    """
    logger.info("Starting Property Analysis MCP server (stdio transport)")
    mcp.run()


if __name__ == "__main__":
    main()