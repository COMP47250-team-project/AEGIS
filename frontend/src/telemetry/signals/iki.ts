import type { TelemetryEvent } from "../types";

/** Attach an inter-keystroke interval (IKI) listener to the document.
 *  Emits key_interval events with the ms gap between consecutive keystrokes.
 *  The caller provides a ref getter so the current question ID is always fresh.
 *  Returns a cleanup function. */
export function attachIKI(
  sessionId: string,
  getQuestionId: () => string,
  enqueue: (event: TelemetryEvent) => void,
): () => void {
  let lastTs: number | null = null;

  function handler(e: KeyboardEvent) {
    // Skip modifier-only combos (Ctrl+C, etc.)
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    const now = Date.now();
    if (lastTs !== null) {
      enqueue({
        type: "key_interval",
        sessionId,
        clientTs: now,
        payload: { interval_ms: now - lastTs, question_id: getQuestionId() },
      });
    }
    lastTs = now;
  }

  document.addEventListener("keydown", handler);
  return () => {
    document.removeEventListener("keydown", handler);
    lastTs = null;
  };
}
