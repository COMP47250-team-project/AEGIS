// @vitest-environment jsdom
import { attachResize } from "../resize";
import type { TelemetryEvent } from "../../types";

describe("attachResize", () => {
  let events: TelemetryEvent[];
  let cleanup: () => void;

  beforeEach(() => {
    events = [];
    vi.useFakeTimers();
    cleanup = attachResize("session-1", (e) => events.push(e));
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("does not emit before debounce delay", () => {
    window.dispatchEvent(new Event("resize"));
    expect(events).toHaveLength(0);
  });

  it("emits after 500ms debounce", () => {
    window.dispatchEvent(new Event("resize"));
    vi.advanceTimersByTime(500);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("resize");
  });

  it("payload contains width and height", () => {
    window.dispatchEvent(new Event("resize"));
    vi.advanceTimersByTime(500);
    expect(events[0].payload).toHaveProperty("width");
    expect(events[0].payload).toHaveProperty("height");
  });

  it("debounces rapid resize events into a single emit", () => {
    for (let i = 0; i < 10; i++) {
      window.dispatchEvent(new Event("resize"));
      vi.advanceTimersByTime(100);
    }
    vi.advanceTimersByTime(500);
    expect(events).toHaveLength(1);
  });

  it("emits a new event after a fresh resize following debounce", () => {
    window.dispatchEvent(new Event("resize"));
    vi.advanceTimersByTime(500);
    window.dispatchEvent(new Event("resize"));
    vi.advanceTimersByTime(500);
    expect(events).toHaveLength(2);
  });

  it("removes listener and cancels pending timer after cleanup", () => {
    window.dispatchEvent(new Event("resize"));
    cleanup();
    vi.advanceTimersByTime(500);
    expect(events).toHaveLength(0);
  });
});