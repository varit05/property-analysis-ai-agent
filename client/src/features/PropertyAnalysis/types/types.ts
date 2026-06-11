/* ── Analysis Types (mirrors server/api/properties/schemas.py) ── */

export type AnalysisStatus =
  | "running"
  | "pending_review"
  | "accepted"
  | "rejected"
  | "failed";

export interface TraceStep {
  step_number: number;
  action: string;
  skill_used: string;
  input: Record<string, unknown>;
  output_summary: string;
  status: string; // "success" | "failed"
  duration_seconds: number | null;
}

export interface ChartDataPoint {
  label: string;
  value: number;
  category: string | null;
  metadata: Record<string, unknown> | null;
}

export interface ChartSeries {
  name: string;
  data: ChartDataPoint[];
  chart_type: "line" | "bar" | "pie";
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface AgentOutput {
  research_note: string;
  charts: ChartSeries[];
  trace: TraceStep[];
  token_usage: TokenUsage | null;
}

export interface AnalysisResponse {
  id: string;
  query: string;
  additional_context: string | null;
  status: AnalysisStatus;
  result: AgentOutput | null;
  error: string | null;
  trace_steps: TraceStep[];
  created_at: string;
  completed_at: string | null;
  reviewed_at: string | null;
}

export interface ReviewResponse {
  message: string;
  analysis: AnalysisResponse;
}