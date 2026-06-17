import type { TelemetryEvent } from "../types";

/** Attach a visibilitychange listener that emits tab_blur / tab_focus events.
 *  Returns a cleanup function. */
export function attachTabBlur(
  sessionId: string,
  enqueue: (event: TelemetryEvent) => void,
): () => void {
  function handler() {
    enqueue({
      type: document.hidden ? "tab_blur" : "tab_focus",
      sessionId,
      clientTs: Date.now(),
      payload: { hidden: document.hidden },
    });
  }
  document.addEventListener("visibilitychange", handler);
  return () => document.removeEventListener("visibilitychange", handler);
}
