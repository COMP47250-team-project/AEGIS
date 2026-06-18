import { makePasteEvent, pasteCharCount } from "../paste";

/**
 * AEGIS-44 — Capture paste events in short-answer fields.
 *
 * The browser delivers the same `paste` ClipboardEvent for both Ctrl+V and
 * right-click → Paste (AC1), so a single code path covers both gestures. These
 * tests exercise that path via `pasteCharCount` (which reads the length from
 * the event's clipboard data) and `makePasteEvent` (which builds the telemetry
 * event). MCQ fields are not monitored because `QuestionRenderer` only attaches
 * `onPaste` to the short-answer <textarea>.
 */

/** Minimal stand-in for the clipboard data carried by a paste ClipboardEvent. */
function clipboardWith(text: string): Pick<DataTransfer, "getData"> {
  return { getData: () => text };
}

describe("pasteCharCount", () => {
  it("counts 100 characters as 100 (AC3)", () => {
    expect(pasteCharCount(clipboardWith("a".repeat(100)))).toBe(100);
  });

  it("counts an empty paste as 0 and still resolves (AC2)", () => {
    expect(pasteCharCount(clipboardWith(""))).toBe(0);
  });

  it("counts whitespace-only pastes by their length (AC2)", () => {
    expect(pasteCharCount(clipboardWith("   "))).toBe(3);
  });
});

describe("makePasteEvent", () => {
  it("emits a paste event with char_count and question_id in the payload", () => {
    const event = makePasteEvent("sess-1", "q-1", 100);
    expect(event.type).toBe("paste");
    expect(event.sessionId).toBe("sess-1");
    expect(event.payload).toEqual({ question_id: "q-1", char_count: 100 });
    expect(typeof event.clientTs).toBe("number");
  });

  it("still logs an event when char_count is 0 (empty/whitespace paste) (AC2)", () => {
    const event = makePasteEvent("sess-1", "q-1", 0);
    expect(event.payload).toEqual({ question_id: "q-1", char_count: 0 });
  });
});
