import { makeResourceAccessEvent } from "../resourceAccess";

/**
 * AEGIS-121 — resource_access signal (open-book exams).
 *
 * Emits a lightweight event when a student opens/closes a resource, for the
 * professor's live timeline. Only the resource id, action, and duration are
 * captured — never page content.
 */

describe("makeResourceAccessEvent", () => {
  it("builds an open event without a duration", () => {
    const event = makeResourceAccessEvent("sess-1", "res-1", "open");
    expect(event.type).toBe("resource_access");
    expect(event.sessionId).toBe("sess-1");
    expect(event.payload).toEqual({ resource_id: "res-1", action: "open" });
    expect(typeof event.clientTs).toBe("number");
  });

  it("includes duration_ms on a close event", () => {
    const event = makeResourceAccessEvent("sess-1", "res-1", "close", 5000);
    expect(event.payload).toEqual({
      resource_id: "res-1",
      action: "close",
      duration_ms: 5000,
    });
  });

  it("omits duration_ms when not provided (never sends undefined)", () => {
    const event = makeResourceAccessEvent("s", "r", "open");
    expect("duration_ms" in event.payload).toBe(false);
  });

  it("captures no page content — only id, action, duration keys", () => {
    const event = makeResourceAccessEvent("s", "r", "close", 10);
    expect(Object.keys(event.payload).sort()).toEqual([
      "action",
      "duration_ms",
      "resource_id",
    ]);
  });
});
