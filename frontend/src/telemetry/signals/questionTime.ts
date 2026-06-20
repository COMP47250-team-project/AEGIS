import type { TelemetryEvent } from "../types";

/**
 * Add the time just spent in a question to its running total, so time is
 * cumulative across re-visits (e.g. 60s on Q1, leave, return for 30s → 90s).
 * Pure helper (mutates and returns the map) so the accumulation is unit-testable.
 */
export function accumulateDuration(
  totals: Map<string, number>,
  questionId: string,
  elapsedMs: number,
): Map<string, number> {
  totals.set(questionId, (totals.get(questionId) ?? 0) + elapsedMs);
  return totals;
}

/**
 * Build a question_time event recording the cumulative time a student has
 * spent on a question, plus its position and the total question count (so the
 * server can score the time distribution relative to position/complexity).
 */
export function makeQuestionTimeEvent(
  sessionId: string,
  questionId: string,
  durationMs: number,
  position: number,
  totalQuestions: number,
): TelemetryEvent {
  return {
    type: "question_time",
    sessionId,
    clientTs: Date.now(),
    payload: {
      question_id: questionId,
      duration_ms: durationMs,
      position,
      total_questions: totalQuestions,
    },
  };
}
