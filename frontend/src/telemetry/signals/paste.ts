import type { TelemetryEvent } from "../types";

/** Build a paste telemetry event for the given question. */
export function makePasteEvent(
  sessionId: string,
  questionId: string,
): TelemetryEvent {
  return {
    type: "paste",
    sessionId,
    clientTs: Date.now(),
    payload: { question_id: questionId },
  };
}
