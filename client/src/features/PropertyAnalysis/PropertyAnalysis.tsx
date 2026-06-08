import { useAnalysis } from "../../hooks/useAnalysis";
import { AnalysisForm } from "./AnalysisForm";
import { AnalysisProgress } from "./AnalysisProgress";
import { TraceTimeline } from "./TraceTimeline";
import { ResearchNote } from "./ResearchNote";
import { ReviewActions } from "./ReviewActions";
import "./PropertyAnalysis.css";

/** Main orchestrator for the Property Analysis feature.
 *
 *  Manages the full lifecycle:
 *    submit query → SSE stream (trace steps) → review (accept/reject)
 */
export function PropertyAnalysis() {
  const {
    phase,
    analysis,
    traceSteps,
    error,
    submit,
    accept,
    reject,
    reset,
  } = useAnalysis();

  const isBusy = phase === "submitting" || phase === "running";
  const showResult =
    analysis?.result &&
    (phase === "pending_review" ||
      phase === "accepted" ||
      phase === "rejected");

  return (
    <section className="pa-container">
      <h2 className="pa-section-title">Property Analysis</h2>
      <p className="pa-section-subtitle">
        Ask a natural-language question about UK property data. The AI agent
        will research the answer and show you each step it takes.
      </p>

      {/* ── Form ──────────────────────────────────────────────────── */}
      {(phase === "idle" || phase === "submitting") && (
        <AnalysisForm onSubmit={submit} disabled={isBusy} />
      )}

      {/* ── Active analysis status ────────────────────────────────── */}
      {phase !== "idle" && <AnalysisProgress phase={phase} />}

      {/* ── Error banner ──────────────────────────────────────────── */}
      {error && <div className="pa-error">{error}</div>}

      {/* ── Trace steps (live from SSE) ───────────────────────────── */}
      {(phase === "running" || phase === "pending_review" || showResult) && (
        <TraceTimeline steps={traceSteps} />
      )}

      {/* ── Research note + charts ────────────────────────────────── */}
      {showResult && analysis?.result && (
        <ResearchNote result={analysis.result} />
      )}

      {/* ── Review buttons ────────────────────────────────────────── */}
      {phase === "pending_review" && (
        <ReviewActions
          onAccept={accept}
          onReject={reject}
          disabled={phase !== "pending_review"}
        />
      )}

      {/* ── Final state messages ──────────────────────────────────── */}
      {phase === "accepted" && (
        <div
          className="pa-status pa-status-accepted"
          style={{ alignSelf: "flex-start" }}
        >
          Analysis accepted
        </div>
      )}
      {phase === "rejected" && (
        <div
          className="pa-status pa-status-rejected"
          style={{ alignSelf: "flex-start" }}
        >
          Analysis rejected
        </div>
      )}
      {phase === "failed" && (
        <div
          className="pa-status pa-status-failed"
          style={{ alignSelf: "flex-start" }}
        >
          Analysis failed
        </div>
      )}

      {/* ── Reset / Start Over ────────────────────────────────────── */}
      {phase !== "idle" && phase !== "submitting" && phase !== "running" && (
        <div>
          <button className="pa-btn pa-btn-reset" onClick={reset}>
            Start Over
          </button>
        </div>
      )}
    </section>
  );
}