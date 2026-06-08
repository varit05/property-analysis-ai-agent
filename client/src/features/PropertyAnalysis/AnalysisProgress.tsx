import type { AnalysisPhase } from "../../hooks/useAnalysis";

interface AnalysisProgressProps {
  phase: AnalysisPhase;
}

const PHASE_LABELS: Record<AnalysisPhase, string> = {
  idle: "Idle",
  submitting: "Submitting",
  running: "Running",
  pending_review: "Pending Review",
  accepted: "Accepted",
  rejected: "Rejected",
  failed: "Failed",
};

export function AnalysisProgress({ phase }: AnalysisProgressProps) {
  const isActive = phase === "submitting" || phase === "running";

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <span className={`pa-status pa-status-${phase}`}>
          {isActive && <span className="pa-spinner" />}
          {PHASE_LABELS[phase]}
        </span>
      </div>
      {phase === "running" && (
        <p className="pa-section-subtitle" style={{ marginTop: "0.5rem" }}>
          The AI agent is analysing the property data. Trace steps will appear below as they complete.
        </p>
      )}
      {phase === "pending_review" && (
        <p className="pa-section-subtitle" style={{ marginTop: "0.5rem" }}>
          The analysis is complete. Review the research note below, then accept or reject it.
        </p>
      )}
    </div>
  );
}