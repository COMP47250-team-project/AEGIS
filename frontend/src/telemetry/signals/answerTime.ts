import type { TelemetryEvent } from "../types";

/** Build an answer_submit event recording how long the student spent on a question. */
export function makeAnswerTimeEvent(
  sessionId: string,
  questionId: string,
  startTs: number,
): TelemetryEvent {
  return {
    type: "answer_submit",
    sessionId,
    clientTs: Date.now(),
    payload: {
      question_id: questionId,
      time_spent_ms: Date.now() - startTs,
    },
  };
}
