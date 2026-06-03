import asyncio
import json
import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse, StreamingResponse

from server.api.properties.events import get_event_manager
from server.api.properties.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ReviewRequest,
    ReviewResponse,
)
from server.api.properties.service import PropertiesService
from server.api.properties.store import get_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED
)
async def trigger_analysis(request: AnalysisRequest):
    """Trigger AI analysis for a property via DeepAgent.

    Returns immediately with status "running". The agent executes in the
    background. Progress can be monitored via the SSE endpoint or by
    polling GET /analyses/{id}.
    """
    return await PropertiesService.trigger_analysis(request)


@router.get("/analyses/{analysis_id}/stream")
async def stream_analysis(analysis_id: str):
    """SSE endpoint that streams trace step progress for an analysis.

    On connect, replays any existing trace steps. Then streams new
    steps as they are produced by the background agent task.

    Event types:
      - trace_step: a new trace step was completed
      - status_change: the analysis status changed (e.g. pending_review, failed)

    The stream ends when the analysis reaches a terminal status
    (pending_review, accepted, rejected, or failed).
    """
    events = get_event_manager()
    store = await get_store()

    # Check the analysis exists
    record = await store.get(analysis_id)
    if not record:
        return JSONResponse(
            status_code=404,
            content={"error": f"Analysis {analysis_id} not found"},
        )

    async def event_generator():

        queue = events.subscribe(analysis_id)
        try:
            # Replay existing trace steps
            existing_steps = record.get("trace_steps", [])
            for step in existing_steps:
                yield f"event: trace_step\ndata: {json.dumps(step)}\n\n"

            terminal_statuses = {"pending_review", "accepted", "rejected", "failed"}
            # If already terminal, send status and stop
            current_status = record.get("status")
            if current_status in terminal_statuses:
                status_data = json.dumps({"status": current_status})
                yield f"event: status_change\ndata: {status_data}\n\n"
                return

            # Stream live events from the queue
            while True:
                try:
                    raw = await asyncio.wait_for(queue.get(), timeout=30.0)
                    parsed = json.loads(raw)
                    event_type = parsed.get("event", "message")
                    data = parsed.get("data", {})
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

                    # Check if terminal — re-read from store to get latest status
                    current = await store.get(analysis_id)
                    if current and current.get("status") in terminal_statuses:
                        break
                except TimeoutError:
                    # Send keep-alive comment to prevent connection timeout
                    yield ": keepalive\n\n"

        except asyncio.CancelledError:
            logger.debug("SSE connection cancelled for %s", analysis_id)
        except Exception:
            logger.exception("SSE generator error for %s", analysis_id)
        finally:
            events.unsubscribe(analysis_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(analysis_id: str):
    """Get analysis result by ID."""
    return await PropertiesService.get_analysis(analysis_id)


@router.post("/analyses/{analysis_id}/review", response_model=ReviewResponse)
async def review_analysis(analysis_id: str, review: ReviewRequest):
    """Accept or reject a pending analysis suggestion.

    Once accepted, the analysis is considered final. Rejected analyses
    are kept with status 'rejected' for audit purposes.
    """
    return await PropertiesService.review_analysis(analysis_id, review)
