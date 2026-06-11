import { useState, useCallback, useRef } from "react";
import type {
  AnalysisResponse,
  TraceStep,
  AnalysisStatus,
} from "../features/PropertyAnalysis/types/types";
import {
  triggerAnalysis as apiTrigger,
  getAnalysis as apiGet,
  reviewAnalysis as apiReview,
} from "../features/PropertyAnalysis/apis/api";
import { useSSE } from "./useSSE";

export type AnalysisPhase =
  | "idle" // no analysis running
  | "submitting" // calling POST /analyze
  | "running" // SSE stream is live, trace steps arriving
  | "pending_review"
  | "accepted"
  | "rejected"
  | "failed";

export interface UseAnalysisReturn {
  phase: AnalysisPhase;
  analysisId: string | null;
  analysis: AnalysisResponse | null;
  traceSteps: TraceStep[];
  error: string | null;

  /** Submit a new analysis query. */
  submit: (query: string, additionalContext?: string) => Promise<void>;
  /** Accept a pending analysis. */
  accept: (reason?: string) => Promise<void>;
  /** Reject a pending analysis. */
  reject: (reason?: string) => Promise<void>;
  /** Reset back to idle. */
  reset: () => void;
}

const TERMINAL_STATUSES = new Set<AnalysisStatus>([
  "pending_review",
  "accepted",
  "rejected",
  "failed",
]);

/**
 * Orchestrates the full lifecycle of a property analysis:
 * submit → SSE stream → review → final.
 */
export function useAnalysis(): UseAnalysisReturn {
  const [phase, setPhase] = useState<AnalysisPhase>("idle");
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [traceSteps, setTraceSteps] = useState<TraceStep[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Ref to avoid stale closure in SSE callbacks
  const analysisIdRef = useRef<string | null>(null);

  // ── SSE URL ──────────────────────────────────────────────────────
  const sseUrl = analysisId
    ? `/api/v1/properties/analyses/${analysisId}/stream`
    : null;

  // ── Handle incoming trace steps ──────────────────────────────────
  const handleTraceStep = useCallback((data: unknown) => {
    const step = data as TraceStep;
    setTraceSteps((prev) => [...prev, step]);
  }, []);

  // ── Handle status changes ────────────────────────────────────────
  const handleStatusChange = useCallback((data: unknown) => {
    const { status } = data as { status: AnalysisStatus };
    setPhase(status as AnalysisPhase);

    // Re-fetch the full analysis record to get the latest result
    const id = analysisIdRef.current;
    if (id) {
      apiGet(id).then(setAnalysis).catch(console.error);
    }
  }, []);

  // ── SSE connection ───────────────────────────────────────────────
  // Terminal statuses are passed to useSSE so it auto-closes the
  // EventSource when a terminal status_change is received. This
  // prevents further events (including replayed steps from browser
  // auto-reconnects) from accumulating.
  useSSE(sseUrl, {
    onTraceStep: handleTraceStep,
    onStatusChange: handleStatusChange,
    terminalStatuses: TERMINAL_STATUSES,
    onError: (err) => setError(err.message),
  });

  // ── Submit ───────────────────────────────────────────────────────
  const submit = useCallback(
    async (query: string, additionalContext?: string) => {
      setPhase("submitting");
      setError(null);
      setTraceSteps([]);
      setAnalysis(null);

      try {
        const resp = await apiTrigger(query, additionalContext);
        setAnalysisId(resp.id);
        analysisIdRef.current = resp.id;
        setAnalysis(resp);
        setPhase("running");
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setPhase("idle");
      }
    },
    [],
  );

  // ── Review ───────────────────────────────────────────────────────
  const accept = useCallback(
    async (reason?: string) => {
      if (!analysisId) return;
      try {
        const resp = await apiReview(analysisId, "accept", reason);
        setAnalysis(resp.analysis);
        setPhase("accepted");
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [analysisId],
  );

  const reject = useCallback(
    async (reason?: string) => {
      if (!analysisId) return;
      try {
        const resp = await apiReview(analysisId, "reject", reason);
        setAnalysis(resp.analysis);
        setPhase("rejected");
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [analysisId],
  );

  // ── Reset ────────────────────────────────────────────────────────
  const reset = useCallback(() => {
    setPhase("idle");
    setAnalysisId(null);
    setAnalysis(null);
    setTraceSteps([]);
    setError(null);
    analysisIdRef.current = null;
  }, []);

  return {
    phase,
    analysisId,
    analysis,
    traceSteps,
    error,
    submit,
    accept,
    reject,
    reset,
  };
}