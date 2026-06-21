import { createTabVisibilityTracker } from "../tabBlur";
import type { TelemetryEvent } from "../../types";

/**
 * Tab-change detection: the tracker watches page visibility and window focus
 * and emits a tab_blur on present→away and a tab_return on away→present.
 * Overlapping signals for a single switch must not double-count.
 */

/** Build a tracker whose clock returns the supplied values in order. */
function setup(nowValues: number[]) {
  const events: TelemetryEvent[] = [];
  let i = 0;
  const now = () => nowValues[Math.min(i++, nowValues.length - 1)];
  const tracker = createTabVisibilityTracker({
    sessionId: "sess-1",
    enqueue: (e) => events.push(e),
    now,
  });
  return { tracker, events };
}

describe("createTabVisibilityTracker — tab switch (visibility)", () => {
  it("emits tab_blur then tab_return for a hide/show cycle", () => {
    const { tracker, events } = setup([100, 350]);
    tracker.setVisible(false); // tab hidden
    tracker.setVisible(true); // tab shown again

    expect(events).toHaveLength(2);
    expect(events[0].type).toBe("tab_blur");
    expect(events[0].payload).toEqual({
      duration_visible_ms: null,
      reason: "tab_hidden",
    });
    expect(events[1].type).toBe("tab_return");
    expect(events[1].payload).toEqual({
      duration_away_ms: 250,
      reason: "tab_hidden",
    });
  });

  it("stamps a wall-clock clientTs on each event", () => {
    const { tracker, events } = setup([0, 10]);
    tracker.setVisible(false);
    tracker.setVisible(true);
    expect(typeof events[0].clientTs).toBe("number");
    expect(typeof events[1].clientTs).toBe("number");
  });
});

describe("createTabVisibilityTracker — window focus (other app/window)", () => {
  it("emits a window_blur pair when focus is lost while still visible", () => {
    const { tracker, events } = setup([1000, 1600]);
    tracker.setFocus(false); // Alt+Tab to another app
    tracker.setFocus(true); // back to the exam window

    expect(events).toHaveLength(2);
    expect(events[0].payload).toMatchObject({ reason: "window_blur" });
    expect(events[1].payload).toEqual({
      duration_away_ms: 600,
      reason: "window_blur",
    });
  });
});

describe("createTabVisibilityTracker — dedup of overlapping signals", () => {
  it("emits a single blur/return pair when both visibility and focus toggle", () => {
    const { tracker, events } = setup([0, 500]);
    // A tab switch typically fires visibility AND focus changes.
    tracker.setVisible(false); // away -> tab_blur (reason tab_hidden)
    tracker.setFocus(false); // still away -> no event
    tracker.setFocus(true); // still hidden -> still away -> no event
    tracker.setVisible(true); // present -> tab_return

    expect(events.map((e) => e.type)).toEqual(["tab_blur", "tab_return"]);
    expect(events[0].payload).toMatchObject({ reason: "tab_hidden" });
  });

  it("ignores no-op state sets", () => {
    const { tracker, events } = setup([0, 1]);
    tracker.setVisible(true); // already visible
    tracker.setFocus(true); // already focused
    expect(events).toHaveLength(0);
  });
});

describe("createTabVisibilityTracker — min/max stats", () => {
  it("tracks count, min and max away durations across cycles", () => {
    // away durations: 250, 1000, 500
    const { tracker } = setup([100, 350, 1000, 2000, 3000, 3500]);
    tracker.setVisible(false);
    tracker.setVisible(true); // 350 - 100 = 250
    tracker.setVisible(false);
    tracker.setVisible(true); // 2000 - 1000 = 1000
    tracker.setVisible(false);
    tracker.setVisible(true); // 3500 - 3000 = 500

    expect(tracker.getStats()).toEqual({
      count: 3,
      minAwayMs: 250,
      maxAwayMs: 1000,
    });
  });

  it("reports null min/max before any away cycle", () => {
    const { tracker } = setup([0]);
    expect(tracker.getStats()).toEqual({
      count: 0,
      minAwayMs: null,
      maxAwayMs: null,
    });
  });
});

describe("createTabVisibilityTracker — timing", () => {
  it("emits synchronously (no timers) so Alt+Tab is captured immediately", () => {
    const { tracker, events } = setup([0, 5]);
    tracker.setVisible(false);
    expect(events).toHaveLength(1); // already present, no waiting
  });
});
