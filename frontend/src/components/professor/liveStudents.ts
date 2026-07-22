// AEGIS-59: shared types + pure helpers for the live student card grid.
// Kept framework-free so the sort/flag logic is unit-testable without a DOM.

export interface LiveStudent {
  student_id: string;
  name: string | null;
  email: string | null;
  risk_score: number | null;
  tab_blurs: number;
  pastes: number;
  last_event: string | null;
  active: boolean;
  // Legacy field from the original payload — used as a fallback.
  integrity_score?: number | null;
}

export type SortMode = "risk" | "name" | "flag";

// A student is "flagged" at/above this risk score (matches the UI's red cutoff).
export const FLAG_THRESHOLD = 0.4;

/** Risk score to display/sort by, falling back to the legacy field. */
export function studentRisk(s: LiveStudent): number {
  return s.risk_score ?? s.integrity_score ?? 0;
}

export function isFlagged(s: LiveStudent): boolean {
  return studentRisk(s) >= FLAG_THRESHOLD;
}

/** Sort a copy of the students by the chosen mode (does not mutate input). */
export function sortStudents(students: LiveStudent[], mode: SortMode): LiveStudent[] {
  const copy = [...students];
  switch (mode) {
    case "name":
      copy.sort((a, b) =>
        (a.name ?? a.student_id).localeCompare(b.name ?? b.student_id)
      );
      break;
    case "flag":
      // Flagged first, then by risk desc within each group.
      copy.sort(
        (a, b) =>
          Number(isFlagged(b)) - Number(isFlagged(a)) ||
          studentRisk(b) - studentRisk(a)
      );
      break;
    case "risk":
    default:
      copy.sort((a, b) => studentRisk(b) - studentRisk(a)); // desc (default)
  }
  return copy;
}
