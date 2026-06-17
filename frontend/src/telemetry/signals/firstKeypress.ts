import type { TelemetryEvent } from "../types";

/** Attach a first-keypress detector.
 *  Emits answer_start the first time the student types on each question,
 *  recording the elapsed ms since they navigated to that question.
 *  Returns a cleanup function. */
export function attachFirstKeypress(
  sessionId: string,
  getQuestionId: () => string,
  getQuestionStartTs: () => number,
  enqueue: (event: TelemetryEvent) => void,
): () => void {
  const seen = new Set<string>();

  function handler(e: KeyboardEvent) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    const qid = getQuestionId();
    if (seen.has(qid)) return;
    seen.add(qid);

    enqueue({
      type: "answer_start",
      sessionId,
      clientTs: Date.now(),
      payload: {
        question_id: qid,
        elapsed_ms: Date.now() - getQuestionStartTs(),
      },
    });
  }

  document.addEventListener("keydown", handler);
  return () => {
    document.removeEventListener("keydown", handler);
    seen.clear();
  };
}
