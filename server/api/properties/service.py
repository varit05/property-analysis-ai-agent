"""
Service layer for DeepAgent AI analysis interactions.

Supports:
- Triggering analysis as a background task (returns immediately)
- Streaming trace step progress via SSE
- Human review (accept/reject) of completed analyses
- JSON file-backed persistence
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from server.api.properties.events import get_event_manager
from server.api.properties.schemas import (
    ANALYSIS_STATUS_ACCEPTED,
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_PENDING_REVIEW,
    ANALYSIS_STATUS_REJECTED,
    ANALYSIS_STATUS_RUNNING,
    AgentOutput,
    AnalysisRequest,
    AnalysisResponse,
    ChartDataPoint,
    ChartSeries,
    ReviewRequest,
    ReviewResponse,
    TraceStep,
)
from server.api.properties.skills_loader import load_skills
from server.api.properties.store import get_store
from server.core.config import settings
from server.core.deep_agent import DeepAgent
from server.core.exceptions import (
    ConflictException,
    NotFoundException,
)
from server.core.llm_factory import get_llm

logger = logging.getLogger(__name__)


class PropertiesService:
    """Service layer for DeepAgent AI analysis interactions."""

    _background_tasks: set[asyncio.Task] = set()

    @classmethod
    async def trigger_analysis(cls, request: AnalysisRequest) -> AnalysisResponse:
        """Trigger analysis via DeepAgent for a given query.

        Creates a pending record in the JSON file and launches the agent
        as a background task. Returns immediately with status "running".
        """

        analysis_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Create initial record
        record = {
            "id": analysis_id,
            "query": request.query,
            "additional_context": request.additional_context,
            "status": ANALYSIS_STATUS_RUNNING,
            "result": None,
            "error": None,
            "trace_steps": [],
            "created_at": now.isoformat(),
            "completed_at": None,
            "reviewed_at": None,
        }

        store = await get_store()
        await store.upsert(analysis_id, record)

        logger.info(
            "Analysis triggered (background)",
            extra={
                "analysis_id": analysis_id,
                "query_preview": request.query[:100],
            },
        )

        # Launch background task
        task = asyncio.create_task(cls._run_analysis_background(analysis_id, request))
        cls._background_tasks.add(task)
        task.add_done_callback(cls._background_tasks.discard)

        return AnalysisResponse(**record)

    @classmethod
    async def _run_analysis_background(
        cls, analysis_id: str, request: AnalysisRequest
    ) -> None:
        """Run the agent in the background, updating the record as it goes."""
        store = await get_store()
        events = get_event_manager()

        async def _on_trace_step(step: dict) -> None:
            """Callback invoked by DeepAgent after each trace step.

            Persists the step to the JSON file and publishes an SSE event.
            """
            # Get the current record, append step, save
            record = await store.get(analysis_id)
            if record:
                trace_steps = record.get("trace_steps", [])
                trace_steps.append(step)
                await store.upsert(analysis_id, {"trace_steps": trace_steps})

            # Publish SSE event
            events.publish(analysis_id, "trace_step", step)

        try:
            # Create a fresh DeepAgent per background task so concurrent
            # requests each get their own independent LLM instance and
            # can execute fully in parallel without blocking on a shared
            # singleton.
            logger.info(
                "Creating DeepAgent for background analysis"
                " (env=%s, max_iterations=%d)",
                settings.ENVIRONMENT,
                settings.MAX_AGENT_ITERATIONS,
            )
            skills = load_skills()
            llm = get_llm()
            agent = DeepAgent(skills=skills, llm=llm)
            agent_result = await agent.run(
                query=request.query,
                additional_context=request.additional_context,
                on_trace_step=_on_trace_step,
            )

            # Build structured output
            agent_output = AgentOutput(
                research_note=agent_result.get("research_note", ""),
                charts=[
                    ChartSeries(
                        name=chart.get("name", ""),
                        chart_type=chart.get("chart_type", "bar"),
                        data=[
                            ChartDataPoint(
                                label=dp.get("label", ""),
                                value=dp.get("value", 0),
                                category=dp.get("category"),
                                metadata=dp.get("metadata"),
                            )
                            for dp in chart.get("data", [])
                        ],
                    )
                    for chart in agent_result.get("charts", [])
                ],
                trace=[
                    TraceStep(
                        step_number=t.get("step_number", 0),
                        action=t.get("action", ""),
                        skill_used=t.get("skill_used", ""),
                        input=t.get("input", {}),
                        output_summary=t.get("output_summary", ""),
                        status=t.get("status", "success"),
                        duration_seconds=t.get("duration_seconds"),
                    )
                    for t in agent_result.get("trace", [])
                ],
            )

            # Update record to pending_review
            await store.upsert(
                analysis_id,
                {
                    "status": ANALYSIS_STATUS_PENDING_REVIEW,
                    "result": agent_output.model_dump(),
                    "completed_at": datetime.now(UTC).isoformat(),
                },
            )

            events.publish(
                analysis_id,
                "status_change",
                {
                    "status": ANALYSIS_STATUS_PENDING_REVIEW,
                },
            )

            logger.info(
                "Analysis completed (pending review)",
                extra={
                    "analysis_id": analysis_id,
                    "iterations": agent_result.get("iterations", 0),
                    "trace_steps": len(agent_result.get("trace", [])),
                },
            )

        except Exception as e:
            logger.exception("Analysis failed: %s", str(e), exc_info=True)
            await store.upsert(
                analysis_id,
                {
                    "status": ANALYSIS_STATUS_FAILED,
                    "error": str(e),
                    "completed_at": datetime.now(UTC).isoformat(),
                },
            )
            events.publish(
                analysis_id,
                "status_change",
                {
                    "status": ANALYSIS_STATUS_FAILED,
                    "error": str(e),
                },
            )

    @classmethod
    async def get_analysis(cls, analysis_id: str) -> AnalysisResponse:
        """Get analysis result by ID."""
        store = await get_store()
        record = await store.get(analysis_id)
        if not record:
            raise NotFoundException("Analysis", analysis_id)
        return AnalysisResponse(**record)

    @classmethod
    async def review_analysis(
        cls, analysis_id: str, review: ReviewRequest
    ) -> ReviewResponse:
        """Accept or reject a pending analysis.

        Raises ConflictException if the analysis has already been reviewed.
        """
        store = await get_store()
        record = await store.get(analysis_id)
        if not record:
            raise NotFoundException("Analysis", analysis_id)

        if record["status"] in (ANALYSIS_STATUS_ACCEPTED, ANALYSIS_STATUS_REJECTED):
            raise ConflictException(
                f"Analysis {analysis_id} has already been {record['status']}"
            )

        if record["status"] != ANALYSIS_STATUS_PENDING_REVIEW:
            raise ConflictException(
                f"Analysis {analysis_id} is in status '{record['status']}', "
                f"cannot review. Must be '{ANALYSIS_STATUS_PENDING_REVIEW}'."
            )

        new_status = (
            ANALYSIS_STATUS_ACCEPTED
            if review.action == "accept"
            else ANALYSIS_STATUS_REJECTED
        )

        await store.upsert(
            analysis_id,
            {
                "status": new_status,
                "reviewed_at": datetime.now(UTC).isoformat(),
            },
        )

        # Update local record for response
        record["status"] = new_status
        record["reviewed_at"] = datetime.now(UTC)

        message = (
            f"Analysis {analysis_id} has been accepted."
            if review.action == "accept"
            else f"Analysis {analysis_id} has been rejected."
        )

        logger.info("Analysis reviewed: %s → %s", analysis_id, new_status)

        return ReviewResponse(
            message=message,
            analysis=AnalysisResponse(**record),
        )
