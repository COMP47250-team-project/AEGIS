import { describe, expect, it } from "vitest";

import {
  durationMinutes,
  parseStudentEmails,
  validUrlResources,
} from "../examCreate.helpers";

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

describe("validUrlResources", () => {
  it("keeps rows with a label and an http(s) URL, trimming whitespace", () => {
    const result = validUrlResources([
      {
        label: "  MDN  ",
        url: "  https://developer.mozilla.org  ",
        embed: true,
      },
    ]);
    expect(result).toEqual([
      { label: "MDN", url: "https://developer.mozilla.org", embed: true },
    ]);
  });

  it("drops rows missing a label or a URL", () => {
    const result = validUrlResources([
      { label: "", url: "https://example.com", embed: false },
      { label: "No URL", url: "", embed: false },
    ]);
    expect(result).toEqual([]);
  });

  it("drops non-http(s) URLs (e.g. javascript: / data:)", () => {
    const result = validUrlResources([
      { label: "evil", url: "javascript:alert(1)", embed: false },
      { label: "data", url: "data:text/html,<script>", embed: false },
      { label: "ok", url: "http://ok.example", embed: false },
    ]);
    expect(result.map((r) => r.label)).toEqual(["ok"]);
  });
});
