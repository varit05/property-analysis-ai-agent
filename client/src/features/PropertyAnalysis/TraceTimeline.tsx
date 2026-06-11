import type { TraceStep } from "./types/types";

interface TraceTimelineProps {
  steps: TraceStep[];
}

export function TraceTimeline({ steps }: Readonly<TraceTimelineProps>) {
  if (steps.length === 0) return null;

  return (
    <div>
      <h3 className="pa-section-title">Agent Trace Steps</h3>
      <p className="pa-section-subtitle">
        {steps.length} step{steps.length !== 1 ? "s" : ""} completed
      </p>
      <div className="pa-timeline" style={{ marginTop: "0.75rem" }}>
        {steps.map((step) => (
          <div
            key={step.step_number}
            className={`pa-timeline-step ${
              step.status === "success" ? "pa-step-success" : "pa-step-failed"
            }`}
          >
            <div className="pa-step-summary">
              Step {step.step_number}: {step.action}
            </div>
            <div className="pa-step-meta">
              Skill: <strong>{step.skill_used}</strong>
              {step.duration_seconds != null && (
                <span> &middot; {step.duration_seconds.toFixed(1)}s</span>
              )}
              <span> &middot; {step.status}</span>
            </div>
            {step.output_summary && (
              <div className="pa-step-detail">{step.output_summary}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
