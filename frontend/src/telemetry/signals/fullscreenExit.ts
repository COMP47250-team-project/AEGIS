import type { TelemetryEvent } from "../types";

/**
 * Attach a `fullscreenchange` listener that emits a `fullscreen_exit`
 * telemetry event whenever the student leaves fullscreen during an active
 * exam (Esc, Alt+Tab, tab switch, or the OS app-switcher — all of which the
 * standard Fullscreen API cannot block; see MDN Fullscreen API).
 *
 * fullscreen_exit is EVIDENCE-ONLY: it is emitted for the professor's event
 * timeline and must never be added to the signal scorer's weighted
 * components (backend/app/services/scorer.py only processes explicitly
 * named event types, so simply not adding a component for this type keeps
 * it excluded automatically).
 *
 * Only emits on the fullscreen→not-fullscreen edge (not on entry, and not
 * repeatedly while already out of fullscreen), matching the edge-triggered
 * pattern used by attachTabBlur. Returns a cleanup function.
 */
export function attachFullscreenExit(
  sessionId: string,
  enqueue: (event: TelemetryEvent) => void,
): () => void {
  let wasFullscreen = document.fullscreenElement !== null;

  const onFullscreenChange = () => {
    const isFullscreen = document.fullscreenElement !== null;
    if (wasFullscreen && !isFullscreen) {
      enqueue({
        type: "fullscreen_exit",
        sessionId,
        clientTs: Date.now(),
        payload: {},
      });
    }
    wasFullscreen = isFullscreen;
  };

  document.addEventListener("fullscreenchange", onFullscreenChange);

  return () => {
    document.removeEventListener("fullscreenchange", onFullscreenChange);
  };
}
