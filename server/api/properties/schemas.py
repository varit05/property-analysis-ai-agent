from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, description="Free-form natural language analysis request"
    )
    additional_context: str | None = Field(
        None, description="Optional additional context to guide the agent's analysis"
    )


class TokenUsage(BaseModel):
    """Aggregated token consumption across all LLM calls made by the agent."""

    prompt_tokens: int = Field(0, description="Total input / prompt tokens sent")
    completion_tokens: int = Field(
        0, description="Total output / completion tokens received"
    )
    total_tokens: int = Field(0, description="Sum of prompt + completion tokens")


class AgentOutput(BaseModel):
    """The structured result produced by the agent."""

    research_note: str = Field(
        ..., description="The written analysis in natural language"
    )
    charts: list[ChartSeries] = Field(
        default_factory=list, description="Chart-ready data series"
    )
    trace: list[TraceStep] = Field(
        default_factory=list, description="Step-by-step log of what the agent did"
    )
    token_usage: TokenUsage | None = Field(
        None, description="Aggregated token usage across all LLM calls"
    )


class SSEEvent(BaseModel):
    """Payload envelope for SSE events."""

    event: str = Field(
        ..., description="Event type: trace_step, status_change, or error"
    )
    data: dict = Field(..., description="Event-specific payload")


class TraceStep(BaseModel):
    """A single step the agent took, explained for a non-technical reader."""

    step_number: int = Field(..., description="Step order in the execution sequence")
    action: str = Field(
        ...,
        description=(
            "What the agent did, in plain English"
            " (e.g. 'Searched for recent property sales in GU1')"
        ),
    )
    skill_used: str = Field(..., description="The skill or tool that was called")
    input: dict = Field(
        default_factory=dict, description="The parameters passed to the skill"
    )
    output_summary: str = Field(
        ..., description="A plain-English summary of what the skill returned"
    )
    status: str = Field(..., description="Whether the step succeeded or failed")
    duration_seconds: float | None = Field(
        None, description="How long the step took to execute"
    )


class ChartDataPoint(BaseModel):
    """A single data point for chart rendering."""

    label: str = Field(..., description="X-axis label or category name")
    value: float = Field(..., description="The numeric value")
    category: str | None = Field(
        None, description="Grouping category for multi-series charts"
    )
    metadata: dict | None = Field(
        None, description="Extra info for tooltips or hover states"
    )


class ChartSeries(BaseModel):
    """A series of data points that form one line/bar/slice on a chart."""

    name: str = Field(..., description="Series name shown in the chart legend")
    data: list[ChartDataPoint] = Field(
        ..., description="The data points in this series"
    )
    chart_type: str = Field(..., description="Type of chart: 'line', 'bar', or 'pie'")


# Analysis statuses
ANALYSIS_STATUS_RUNNING = "running"
ANALYSIS_STATUS_PENDING_REVIEW = "pending_review"
ANALYSIS_STATUS_ACCEPTED = "accepted"
ANALYSIS_STATUS_REJECTED = "rejected"
ANALYSIS_STATUS_FAILED = "failed"

VALID_ANALYSIS_STATUSES = {
    ANALYSIS_STATUS_RUNNING,
    ANALYSIS_STATUS_PENDING_REVIEW,
    ANALYSIS_STATUS_ACCEPTED,
    ANALYSIS_STATUS_REJECTED,
    ANALYSIS_STATUS_FAILED,
}


class AnalysisResponse(BaseModel):
    id: str = Field(..., description="Unique analysis result ID")
    query: str = Field(..., description="The original query submitted by the user")
    additional_context: str | None = Field(
        None, description="Additional context provided with the query"
    )
    status: str = Field(
        ...,
        description=f"Analysis status: {', '.join(sorted(VALID_ANALYSIS_STATUSES))}",
    )
    result: AgentOutput | None = Field(
        None, description="Structured analysis result from the agent"
    )
    error: str | None = Field(None, description="Error message if analysis failed")
    trace_steps: list[TraceStep] = Field(
        default_factory=list,
        description="Append-only log of trace steps for SSE replay",
    )
    created_at: datetime = Field(..., description="When the analysis was triggered")
    completed_at: datetime | None = Field(
        None, description="When the analysis completed"
    )
    reviewed_at: datetime | None = Field(
        None, description="When the analysis was reviewed by a human"
    )

    model_config = ConfigDict(from_attributes=True)


class ReviewRequest(BaseModel):
    """Request body for reviewing a pending analysis."""

    action: Literal["accept", "reject"] = Field(
        ..., description="Whether to accept or reject the analysis suggestion"
    )
    reason: str | None = Field(None, description="Optional reason for rejection")


class ReviewResponse(BaseModel):
    """Response after reviewing an analysis."""

    message: str = Field(..., description="Human-readable result of the review action")
    analysis: AnalysisResponse = Field(..., description="The updated analysis record")
