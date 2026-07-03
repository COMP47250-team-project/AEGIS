// Pure helpers for the create-exam form (AEGIS-62), split out so they're unit-testable.

/**
 * Parse student emails typed or pasted/CSV-uploaded. Splits on whitespace,
 * commas and semicolons, keeps only email-like tokens (so CSV headers/extra
 * columns are dropped), lowercases, and de-duplicates silently (order kept).
 */
export function parseStudentEmails(raw: string): string[] {
  // Set preserves insertion order, so this dedupes silently while keeping order.
  return [
    ...new Set(
      raw
        .split(/[\s,;]+/)
        .map((t) => t.trim().toLowerCase())
        .filter((t) => t.includes("@")),
    ),
  ];
}

/** Whole minutes between two datetime-local strings (end - start). */
export function durationMinutes(startLocal: string, endLocal: string): number {
  return Math.round(
    (new Date(endLocal).getTime() - new Date(startLocal).getTime()) / 60000,
  );
}
