import type { TelemetryEvent } from "../types";

/**
 * Reason a student became "away" from the exam:
 * - "tab_hidden": the page itself was hidden (tab switch, minimise, occluded).
 * - "window_blur": the window lost focus while still visible (Alt+Tab to
 *   another app/browser/window, virtual-desktop switch, address bar, etc.).
 */
export type AwayReason = "tab_hidden" | "window_blur";

/** Running min/max of away durations, exposed for monitoring. */
export interface TabAwayStats {
  count: number;
  minAwayMs: number | null;
  maxAwayMs: number | null;
}

interface TrackerOptions {
  sessionId: string;
  enqueue: (event: TelemetryEvent) => void;
  /** High-resolution clock for durations; injectable for tests. */
  now?: () => number;
}

/**
 * State machine that tracks whether the student is present (page visible AND
 * window focused) or away (either condition false). It emits exactly one
 * `tab_blur` on the present→away edge and one `tab_return` on away→present,
 * so overlapping visibility/focus signals for a single switch are not
 * double-counted. Durations use `performance.now()` for sub-millisecond
 * accuracy; emission is synchronous (no timers) so an Alt+Tab is captured
 * immediately.
 */
export function createTabVisibilityTracker({
  sessionId,
  enqueue,
  now = () => performance.now(),
}: TrackerOptions) {
  let isVisible = true;
  let hasFocus = true;
  let blurAt = 0;
  let blurReason: AwayReason = "tab_hidden";

  let count = 0;
  let minAwayMs: number | null = null;
  let maxAwayMs: number | null = null;

  const isAway = () => !isVisible || !hasFocus;

  function emit(
    type: "tab_blur" | "tab_return",
    payload: Record<string, unknown>,
  ) {
    enqueue({ type, sessionId, clientTs: Date.now(), payload });
  }

  // Recompute presence after a state change and emit only on a real edge.
  function reconcile(wasAway: boolean) {
    const nowAway = isAway();
    if (nowAway === wasAway) return;

    if (nowAway) {
      blurAt = now();
      blurReason = !isVisible ? "tab_hidden" : "window_blur";
      emit("tab_blur", { duration_visible_ms: null, reason: blurReason });
    } else {
      const durationAwayMs = now() - blurAt;
      count += 1;
      minAwayMs =
        minAwayMs === null
          ? durationAwayMs
          : Math.min(minAwayMs, durationAwayMs);
      maxAwayMs =
        maxAwayMs === null
          ? durationAwayMs
          : Math.max(maxAwayMs, durationAwayMs);
      emit("tab_return", {
        duration_away_ms: durationAwayMs,
        reason: blurReason,
      });
    }
  }

  return {
    setVisible(visible: boolean) {
      if (visible === isVisible) return;
      const wasAway = isAway();
      isVisible = visible;
      reconcile(wasAway);
    },
    setFocus(focused: boolean) {
      if (focused === hasFocus) return;
      const wasAway = isAway();
      hasFocus = focused;
      reconcile(wasAway);
    },
    getStats(): TabAwayStats {
      return { count, minAwayMs, maxAwayMs };
    },
  };
}

/**
 * Attach visibility + window focus/blur listeners that emit tab_blur /
 * tab_return events. Returns a cleanup function.
 *
 * `shouldIgnoreBlur` (AEGIS-121): an optional predicate consulted on window
 * blur. When it returns true, the blur is treated as a non-event — the tracker
 * is not moved to the "away" state, so no `tab_blur` is emitted and the
 * present/away edge bookkeeping stays consistent. Used by open-book exams to
 * ignore focus moving into an in-page resource iframe (legitimate viewing),
 * which is detectable because the tab as a whole still has focus
 * (`document.hasFocus()` stays true when focus is inside an iframe, and only
 * goes false on a real tab/window switch).
 */
export function attachTabBlur(
  sessionId: string,
  enqueue: (event: TelemetryEvent) => void,
  shouldIgnoreBlur?: () => boolean,
): () => void {
  const tracker = createTabVisibilityTracker({ sessionId, enqueue });

  const onVisibility = () => tracker.setVisible(!document.hidden);
  const onBlur = () => {
    if (shouldIgnoreBlur?.()) return;
    tracker.setFocus(false);
  };
  const onFocus = () => tracker.setFocus(true);

  document.addEventListener("visibilitychange", onVisibility);
  window.addEventListener("blur", onBlur);
  window.addEventListener("focus", onFocus);

  return () => {
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("blur", onBlur);
    window.removeEventListener("focus", onFocus);
  };
}
