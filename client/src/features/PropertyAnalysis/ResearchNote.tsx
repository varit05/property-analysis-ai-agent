import type { AgentOutput } from "./types/types";
import { ChartView } from "./ChartView";

interface ResearchNoteProps {
  result: AgentOutput;
}

export function ResearchNote({ result }: ResearchNoteProps) {
  if (!result.research_note) return null;

  return (
    <div>
      <h3 className="pa-section-title">Research Note</h3>

      <div className="pa-research-note" style={{ marginTop: "0.5rem" }}>
        {result.research_note}
      </div>

      {result.charts.length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          <h4 className="pa-section-title" style={{ fontSize: "16px" }}>
            Charts
          </h4>
          <ChartView series={result.charts} />
        </div>
      )}

      {result.token_usage && (
        <div className="pa-token-usage" style={{ marginTop: "0.5rem" }}>
          Tokens: {result.token_usage.prompt_tokens} prompt &middot;{" "}
          {result.token_usage.completion_tokens} completion &middot;{" "}
          {result.token_usage.total_tokens} total
        </div>
      )}
    </div>
  );
}
