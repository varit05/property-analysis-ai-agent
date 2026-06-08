import { useCallback, useEffect, useRef } from "react";

type SSEEventHandler = (data: unknown) => void;

export interface UseSSEOptions {
  /** Called when a `trace_step` event arrives. */
  onTraceStep?: SSEEventHandler;
  /** Called when a `status_change` event arrives. */
  onStatusChange?: SSEEventHandler;
  /**
   * If provided, the SSE connection will be closed automatically when a
   * status_change event arrives with a status in this set.
   */
  terminalStatuses?: Set<string>;
  /** Called on any error (including connection errors). */
  onError?: (err: Error) => void;
}

/**
 * Opens an SSE connection to the given URL and dispatches events
 * to the provided callbacks.
 *
 * Returns a `close` function to explicitly terminate the connection.
 *
 * Automatically cleans up the EventSource on unmount.
 */
export function useSSE(url: string | null, options: UseSSEOptions) {
  const optionsRef = useRef<UseSSEOptions>(options);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Keep the ref in-sync inside the effect to avoid lint warnings
    // about ref mutation during render.
    if (!url) return;

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener("trace_step", (event) => {
      try {
        const data = JSON.parse(event.data);
        optionsRef.current.onTraceStep?.(data);
      } catch (e) {
        console.error("useSSE: failed to parse trace_step", e);
      }
    });

    es.addEventListener("status_change", (event) => {
      try {
        const data = JSON.parse(event.data) as { status: string };

        // If a terminal statuses set is configured and we've reached one,
        // close the EventSource so no further events can accumulate.
        const terminalStatuses = optionsRef.current.terminalStatuses;
        if (terminalStatuses?.has(data.status)) {
          es.close();
          esRef.current = null;
        }

        optionsRef.current.onStatusChange?.(data);
      } catch (e) {
        console.error("useSSE: failed to parse status_change", e);
      }
    });

    es.onerror = () => {
      // The browser fires onerror for transient connection issues and
      // will auto-reconnect, so we only report errors here — we do NOT
      // treat this as the stream ending. The consumer should detect
      // stream completion via terminal status_change events instead.
      optionsRef.current.onError?.(new Error("SSE connection error"));
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [url]); // NOTE: `options` intentionally excluded — we use optionsRef instead.
  // Including `options` (a new object on every render) would cause the
  // EventSource to be recreated on each render, leading to duplicate events.

  const close = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  return { close };
}
