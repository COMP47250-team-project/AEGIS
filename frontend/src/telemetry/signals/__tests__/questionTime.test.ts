import { makeQuestionTimeEvent, accumulateDuration } from "../questionTime";

/**
 * AEGIS-47 — answer_time_distribution signal.
 *
 * Emits how long a student spent on each question (cumulative across re-visits),
 * with position and total_questions for server-side distribution scoring.
 */

describe("accumulateDuration", () => {
  it("sums time across re-visits for the same question (cumulative)", () => {
    const totals = new Map<string, number>();
    accumulateDuration(totals, "q1", 60_000); // 60s on first visit
    accumulateDuration(totals, "q1", 30_000); // 30s on a later re-visit
    expect(totals.get("q1")).toBe(90_000);
  });

  it("tracks questions independently", () => {
    const totals = new Map<string, number>();
    accumulateDuration(totals, "q1", 60_000);
    accumulateDuration(totals, "q2", 2_000);
    expect(totals.get("q1")).toBe(60_000);
    expect(totals.get("q2")).toBe(2_000);
  });

  it("starts a question from zero", () => {
    const totals = new Map<string, number>();
    accumulateDuration(totals, "q1", 0);
    expect(totals.get("q1")).toBe(0);
  });
});

describe("makeQuestionTimeEvent", () => {
  it("builds a question_time event with the full payload", () => {
    const event = makeQuestionTimeEvent("sess-1", "q1", 60_000, 0, 2);
    expect(event.type).toBe("question_time");
    expect(event.sessionId).toBe("sess-1");
    expect(event.payload).toEqual({
      question_id: "q1",
      duration_ms: 60_000,
      position: 0,
      total_questions: 2,
    });
    expect(typeof event.clientTs).toBe("number");
  });

  it("emits both Q1 (60s) and Q2 (2s) durations correctly (AC)", () => {
    const q1 = makeQuestionTimeEvent("s", "q1", 60_000, 0, 2);
    const q2 = makeQuestionTimeEvent("s", "q2", 2_000, 1, 2);
    expect(q1.payload.duration_ms).toBe(60_000);
    expect(q2.payload.duration_ms).toBe(2_000);
  });

  it("still emits an event for a 0ms / skipped question (AC)", () => {
    const event = makeQuestionTimeEvent("s", "q3", 0, 2, 3);
    expect(event.payload.duration_ms).toBe(0);
  });
});
