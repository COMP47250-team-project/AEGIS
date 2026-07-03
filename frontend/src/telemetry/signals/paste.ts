import type { TelemetryEvent } from "../types";

/**
 * Number of characters in a paste, read from the event's clipboard data.
 * Observe-only: we read the length, never the content. Whitespace and empty
 * strings are counted as-is (no filtering), so an empty paste yields 0.
 */
export function pasteCharCount(
  clipboard: Pick<DataTransfer, "getData">,
): number {
  return clipboard.getData("text").length;
}

/**
 * Whether a paste originated from within the exam itself (text the student
 * previously copied on the page) and should therefore NOT be flagged.
 *
 * Only paste from outside the exam is a cheating signal. The comparison is done
 * entirely on the client — clipboard content is never transmitted (AEGIS-104,
 * data minimisation).
 */
export function isInternalPaste(
  pastedText: string,
  internalCopies: ReadonlySet<string>,
): boolean {
  const normalised = pastedText.trim();
  return normalised.length > 0 && internalCopies.has(normalised);
}

/** Build a paste telemetry event for the given question. */
export function makePasteEvent(
  sessionId: string,
  questionId: string,
  charCount: number,
): TelemetryEvent {
  return {
    type: "paste",
    sessionId,
    clientTs: Date.now(),
    payload: { question_id: questionId, char_count: charCount },
  };
}
