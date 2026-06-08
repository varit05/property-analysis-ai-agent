/* ── API wrappers for the Property Analysis backend ──────────────── */

import type { AnalysisResponse, ReviewResponse } from "../types/types";

const BASE = "/api/v1/properties";

/** Submit a natural-language property analysis request.
 *  Returns immediately with analysis_id and status "running". */
export async function triggerAnalysis(
  query: string,
  additionalContext?: string,
): Promise<AnalysisResponse> {
  const res = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      additional_context: additionalContext ?? null,
    }),
  });
  if (!res.ok) throw await apiError(res);
  return res.json();
}

/** Poll for the current state of an analysis. */
export async function getAnalysis(id: string): Promise<AnalysisResponse> {
  const res = await fetch(`${BASE}/analyses/${id}`);
  if (!res.ok) throw await apiError(res);
  return res.json();
}

/** Open an SSE stream for live trace steps & status changes. */
export function streamAnalysis(id: string): EventSource {
  return new EventSource(`${BASE}/analyses/${id}/stream`);
}

/** Accept or reject a pending analysis. */
export async function reviewAnalysis(
  id: string,
  action: "accept" | "reject",
  reason?: string,
): Promise<ReviewResponse> {
  const res = await fetch(`${BASE}/analyses/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, reason: reason ?? null }),
  });
  if (!res.ok) throw await apiError(res);
  return res.json();
}

/* ── Helpers ──────────────────────────────────────────────────────── */

async function apiError(res: Response): Promise<Error> {
  let body: string;
  try {
    body = JSON.stringify(await res.json(), null, 2);
  } catch {
    body = await res.text();
  }
  return new Error(`API ${res.status} (${res.url}): ${body}`);
}
