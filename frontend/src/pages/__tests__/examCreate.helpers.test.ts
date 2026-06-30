import { describe, expect, it } from "vitest";

import { durationMinutes, parseStudentEmails } from "../examCreate.helpers";

describe("parseStudentEmails", () => {
  it("lowercases, dedupes silently, and ignores non-email tokens", () => {
    const raw = "A@x.com, a@x.com\nb@x.com; email\nC@X.com";
    expect(parseStudentEmails(raw)).toEqual(["a@x.com", "b@x.com", "c@x.com"]);
  });

  it("returns empty when there are no emails", () => {
    expect(parseStudentEmails("name,header\n\n")).toEqual([]);
  });
});

describe("durationMinutes", () => {
  it("computes whole minutes from start to end", () => {
    expect(durationMinutes("2026-09-01T09:00", "2026-09-01T10:30")).toBe(90);
  });

  it("is non-positive when end is not after start", () => {
    expect(durationMinutes("2026-09-01T10:00", "2026-09-01T10:00")).toBe(0);
  });
});
