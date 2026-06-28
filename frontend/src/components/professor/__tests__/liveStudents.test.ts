import {
  isFlagged,
  sortStudents,
  studentRisk,
  type LiveStudent,
} from "../liveStudents";

function makeStudent(i: number, risk: number): LiveStudent {
  return {
    student_id: `s${String(i).padStart(2, "0")}`,
    name: `Student ${String(i).padStart(2, "0")}`,
    email: `s${i}@demo.ac.uk`,
    risk_score: risk,
    tab_blurs: i % 3,
    pastes: i % 2,
    last_event: "paste",
    active: true,
  };
}

// 20 students with deterministic, non-monotonic risk scores (AEGIS-59 AC).
const TWENTY: LiveStudent[] = Array.from({ length: 20 }, (_, i) =>
  makeStudent(i, ((i * 7) % 20) / 20) // 0.00..0.95, shuffled
);

describe("studentRisk / isFlagged", () => {
  it("flags students at or above 0.7", () => {
    expect(isFlagged(makeStudent(1, 0.7))).toBe(true);
    expect(isFlagged(makeStudent(2, 0.95))).toBe(true);
    expect(isFlagged(makeStudent(3, 0.69))).toBe(false);
  });

  it("falls back to integrity_score when risk_score is null", () => {
    const s: LiveStudent = { ...makeStudent(1, 0), risk_score: null, integrity_score: 0.8 };
    expect(studentRisk(s)).toBe(0.8);
    expect(isFlagged(s)).toBe(true);
  });
});

describe("sortStudents (20 students)", () => {
  it("default risk sort is descending and keeps all 20", () => {
    const sorted = sortStudents(TWENTY, "risk");
    expect(sorted).toHaveLength(20);
    for (let i = 1; i < sorted.length; i++) {
      expect(studentRisk(sorted[i - 1])).toBeGreaterThanOrEqual(studentRisk(sorted[i]));
    }
  });

  it("alphabetical sort orders by name", () => {
    const names = sortStudents(TWENTY, "name").map((s) => s.name);
    expect(names).toEqual([...names].sort());
  });

  it("flag sort puts all flagged students first", () => {
    const sorted = sortStudents(TWENTY, "flag");
    const firstUnflagged = sorted.findIndex((s) => !isFlagged(s));
    const lastFlagged = sorted.map(isFlagged).lastIndexOf(true);
    // every flagged student appears before every unflagged one
    if (firstUnflagged !== -1) expect(lastFlagged).toBeLessThan(firstUnflagged);
    expect(sorted).toHaveLength(20);
  });

  it("does not mutate the input array", () => {
    const before = TWENTY.map((s) => s.student_id);
    sortStudents(TWENTY, "risk");
    expect(TWENTY.map((s) => s.student_id)).toEqual(before);
  });
});
