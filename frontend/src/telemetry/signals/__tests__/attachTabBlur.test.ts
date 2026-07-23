// @vitest-environment jsdom
import { attachTabBlur } from "../tabBlur";
import type { TelemetryEvent } from "../../types";

/**
 * AEGIS-121 — attachTabBlur's shouldIgnoreBlur hook.
 *
 * Open-book exams ignore a window "blur" caused by focus moving into the
 * in-panel resource iframe (the tab still has focus in that case). The hook is
 * consulted on blur; when it returns true the tracker is not moved to "away",
 * so no tab_blur is emitted. Closed-book (no predicate) is unchanged.
 */

describe("attachTabBlur — shouldIgnoreBlur", () => {
  it("suppresses tab_blur when the predicate returns true (iframe focus)", () => {
    const events: TelemetryEvent[] = [];
    const cleanup = attachTabBlur(
      "sess-1",
      (e) => events.push(e),
      () => true,
    );

    window.dispatchEvent(new Event("blur"));

    expect(events).toHaveLength(0);
    cleanup();
  });

  it("still emits tab_blur when the predicate returns false (real Alt+Tab)", () => {
    const events: TelemetryEvent[] = [];
    const cleanup = attachTabBlur(
      "sess-1",
      (e) => events.push(e),
      () => false,
    );

    window.dispatchEvent(new Event("blur"));

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("tab_blur");
    expect(events[0].payload).toMatchObject({ reason: "window_blur" });
    cleanup();
  });

  it("emits tab_blur with no predicate (closed-book unchanged)", () => {
    const events: TelemetryEvent[] = [];
    const cleanup = attachTabBlur("sess-1", (e) => events.push(e));

    window.dispatchEvent(new Event("blur"));

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("tab_blur");
    cleanup();
  });

  it("a suppressed blur does not desync later real away detection", () => {
    // Ignore the first blur (iframe focus), then a genuine blur must still fire.
    let ignore = true;
    const events: TelemetryEvent[] = [];
    const cleanup = attachTabBlur(
      "sess-1",
      (e) => events.push(e),
      () => ignore,
    );

    window.dispatchEvent(new Event("blur")); // iframe focus — suppressed
    expect(events).toHaveLength(0);

    ignore = false;
    window.dispatchEvent(new Event("blur")); // real Alt+Tab — emits
    expect(events.map((e) => e.type)).toEqual(["tab_blur"]);

    cleanup();
  });
});
