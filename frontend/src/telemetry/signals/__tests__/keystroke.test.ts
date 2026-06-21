// @vitest-environment jsdom
import { KeystrokeSignal } from "../keystroke";

import type { TelemetryEvent } from "../../types";

function makeTarget(): HTMLElement {
  return document.createElement("textarea");
}

function fireKey(target: HTMLElement, key: string, time: number): void {
  vi.setSystemTime(time);
  Object.defineProperty(performance, "now", { value: () => time, writable: true, configurable: true });
  target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
}

describe("KeystrokeSignal", () => {
  let events: TelemetryEvent[];
  let target: HTMLElement;
  let signal: KeystrokeSignal;

  beforeEach(() => {
    events = [];
    target = makeTarget();
    signal = new KeystrokeSignal(target, {
      questionId: "q1",
      onEvent: (e) => events.push(e),
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    signal.destroy();
    vi.useRealTimers();
  });

  it("does not emit before 5 keystrokes", () => {
    for (let i = 0; i < 4; i++) {
      fireKey(target, "a", (i + 1) * 300);
    }
    expect(events).toHaveLength(0);
  });

  it("emits after 5 keystrokes", () => {
    fireKey(target, "a", 100);
    fireKey(target, "a", 400);
    fireKey(target, "a", 700);
    fireKey(target, "a", 1000);
    fireKey(target, "a", 1300);
    fireKey(target, "a", 3400);
    expect(events.length).toBeGreaterThanOrEqual(1);
    expect(events[0].type).toBe("key_interval");
  });

  it("ignores arrow keys", () => {
    for (let i = 0; i < 10; i++) {
      fireKey(target, "ArrowLeft", (i + 1) * 300);
    }
    expect(events).toHaveLength(0);
  });

  it("ignores Ctrl, Shift, Tab", () => {
    const ignored = ["Control", "Shift", "Tab"];
    for (const key of ignored) {
      for (let i = 0; i < 10; i++) {
        fireKey(target, key, (i + 1) * 300);
      }
    }
    expect(events).toHaveLength(0);
  });

  it("payload contains iki_ms and question_id", () => {
    fireKey(target, "a", 100);
    fireKey(target, "a", 400);
    fireKey(target, "a", 700);
    fireKey(target, "a", 1000);
    fireKey(target, "a", 1300);
    fireKey(target, "a", 3400);
    expect(events[0].payload).toHaveProperty("iki_ms");
    expect(events[0].payload).toHaveProperty("question_id", "q1");
  });

  it("caps IKI at 5000ms for long pauses", () => {
    fireKey(target, "a", 1000);
    fireKey(target, "a", 10000);
    fireKey(target, "a", 10300);
    fireKey(target, "a", 10600);
    fireKey(target, "a", 10900);
    fireKey(target, "a", 13000);
    const ikiValues = events.map((e) => e.payload["iki_ms"] as number);
    expect(Math.max(...ikiValues)).toBeLessThanOrEqual(5000);
  });

  it("throttles to max 1 event per 2 seconds", () => {
    for (let i = 0; i < 20; i++) {
      fireKey(target, "a", i * 100);
    }
    expect(events.length).toBeLessThanOrEqual(1);
  });

  it("removes event listener on destroy", () => {
    signal.destroy();
    for (let i = 0; i < 10; i++) {
      fireKey(target, "a", (i + 1) * 300);
    }
    expect(events).toHaveLength(0);
  });
});