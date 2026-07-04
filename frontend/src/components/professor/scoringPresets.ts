// Scoring sensitivity presets (AEGIS-84) — shared by the exam-create forms.
export type ScoringPreset = "strict" | "standard" | "lenient";

export const SCORING_PRESETS: { value: ScoringPreset; label: string; hint: string }[] = [
  { value: "strict", label: "Strict", hint: "Closed-book, no reference material" },
  { value: "standard", label: "Standard", hint: "Default — general exams" },
  { value: "lenient", label: "Lenient", hint: "Open-book, multi-tab research exams" },
];
