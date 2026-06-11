import { useState, type SubmitEventHandler } from "react";

interface AnalysisFormProps {
  onSubmit: (query: string, additionalContext?: string) => void;
  disabled: boolean;
}

export function AnalysisForm({
  onSubmit,
  disabled,
}: Readonly<AnalysisFormProps>) {
  const [query, setQuery] = useState("");
  const [context, setContext] = useState("");

  const handleSubmit = (e: SubmitEventHandler<HTMLFormElement>) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSubmit(query.trim(), context.trim() || undefined);
  };

  return (
    <form className="pa-form" onSubmit={handleSubmit}>
      <label htmlFor="pa-query" className="pa-section-subtitle">
        What would you like to analyse?
      </label>
      <textarea
        id="pa-query"
        placeholder='e.g. "What is the average house price in GU1 over the last 5 years?"'
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={disabled}
      />
      <div className="pa-row">
        <input
          type="text"
          placeholder="Optional: additional context (e.g. focus on semi-detached)"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={disabled}
        />
        <button
          type="submit"
          className="pa-btn pa-btn-primary"
          disabled={disabled || !query.trim()}
        >
          {disabled ? (
            <>
              <span className="pa-spinner" /> Submitting…
            </>
          ) : (
            "Analyse"
          )}
        </button>
      </div>
    </form>
  );
}
