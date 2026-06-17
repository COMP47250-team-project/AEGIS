import type { TelemetryEvent } from "../types";

/** Attach a debounced resize listener.
 *  Emits resize events 500ms after the window stops resizing.
 *  Returns a cleanup function. */
export function attachResize(
  sessionId: string,
  enqueue: (event: TelemetryEvent) => void,
): () => void {
  let timeout: ReturnType<typeof setTimeout> | null = null;

  function handler() {
    if (timeout !== null) clearTimeout(timeout);
    timeout = setTimeout(() => {
      enqueue({
        type: "resize",
        sessionId,
        clientTs: Date.now(),
        payload: { width: window.innerWidth, height: window.innerHeight },
      });
    }, 500);
  }

  window.addEventListener("resize", handler);
  return () => {
    window.removeEventListener("resize", handler);
    if (timeout !== null) clearTimeout(timeout);
  };
}
