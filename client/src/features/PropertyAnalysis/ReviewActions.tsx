import { useState } from "react";

interface ReviewActionsProps {
  onAccept: (reason?: string) => void;
  onReject: (reason?: string) => void;
  disabled: boolean;
}

export function ReviewActions({ onAccept, onReject, disabled }: ReviewActionsProps) {
  const [reason, setReason] = useState("");

  return (
    <div>
      <h3 className="pa-section-title">Review Analysis</h3>
      <p className="pa-section-subtitle">
        Review the research note above. Accept if it meets your requirements, or reject with feedback.
      </p>

      <div className="pa-review">
        <button
          className="pa-btn pa-btn-accept"
          onClick={() => onAccept(reason || undefined)}
          disabled={disabled}
        >
          Accept
        </button>
        <button
          className="pa-btn pa-btn-reject"
          onClick={() => onReject(reason || undefined)}
          disabled={disabled}
        >
          Reject
        </button>
      </div>

      <div className="pa-form">
        <input
          type="text"
          placeholder="Optional reason for your decision (especially useful for rejection)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          disabled={disabled}
        />
      </div>
    </div>
  );
}