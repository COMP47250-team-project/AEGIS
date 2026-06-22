// @vitest-environment jsdom
import { attachFirstKeypress } from "../firstKeypress";
import type { TelemetryEvent } from "../../types";

describe("attachFirstKeypress", () => {
  let events: TelemetryEvent[];
  let cleanup: () => void;
  let currentQuestionId: string;
  let questionStartTs: number;

  beforeEach(() => {
    events = [];
    currentQuestionId = "q1";
    questionStartTs = 1000;
    vi.spyOn(Date, "now").mockReturnValue(1500);

    cleanup = attachFirstKeypress(
      "session-1",
      () => currentQuestionId,
      () => questionStartTs,
      (e) => events.push(e),
    );
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("emits answer_start on first keypress", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe("answer_start");
  });

  it("emits only once per question", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "b" }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "c" }));
    expect(events).toHaveLength(1);
  });

  it("emits again for a new question", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    currentQuestionId = "q2";
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "b" }));
    expect(events).toHaveLength(2);
  });

  it("does not re-emit on revisit of same question", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    currentQuestionId = "q2";
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "b" }));
    currentQuestionId = "q1"; // revisit q1
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "c" }));
    expect(events).toHaveLength(2);
  });

  it("payload contains question_id and elapsed_ms", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    expect(events[0].payload).toHaveProperty("question_id", "q1");
    expect(events[0].payload).toHaveProperty("elapsed_ms", 500);
  });

  it("ignores Ctrl, Meta, Alt modifier combos", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "c", ctrlKey: true }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "v", metaKey: true }));
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "a", altKey: true }));
    expect(events).toHaveLength(0);
  });

  it("removes listener after cleanup", () => {
    cleanup();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "a" }));
    expect(events).toHaveLength(0);
  });
});