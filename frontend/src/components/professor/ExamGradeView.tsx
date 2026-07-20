import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import apiClient from "../../api/client";

// ---------------------------------------------------------------------------
// Types (mirroring backend ExamGradeReport schema)
// ---------------------------------------------------------------------------

interface GradeAnswerItem {
  question_id: string;
  answer_id: string | null;
  position: number;
  question_type: "mcq" | "short";
  prompt: string;
  student_answer: string;
  correct_answer: string | null;
  is_correct: boolean | null;
  manual_score: number | null;
  max_score: number;
}

interface StudentGradeEntry {
  student_id: string;
  student_email: string | null;
  student_name: string | null;
  mcq_correct: number;
  mcq_total: number;
  answers: GradeAnswerItem[];
  attended: boolean;
}

interface ExamGradeReport {
  exam_id: string;
  quiz_title: string;
  course_id: string;
  mcq_total: number;
  short_total: number;
  students: StudentGradeEntry[];
  results_released: boolean;
  ungraded_short: number;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const ScorePill: React.FC<{ correct: number; total: number }> = ({
  correct,
  total,
}) => {
  if (total === 0) return <span className="text-xs text-mute">No MCQ</span>;
  const pct = Math.round((correct / total) * 100);
  const cls =
    pct >= 80
      ? "bg-accent-green-soft text-accent-green border-accent-green/20"
      : pct >= 50
        ? "bg-primary/10 text-primary-active border-primary/20"
        : "bg-accent-red-soft text-accent-red border-accent-red/20";
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded border text-xs font-semibold ${cls}`}
    >
      {correct}/{total} MCQ ({pct}%)
    </span>
  );
};

interface StudentRowProps {
  entry: StudentGradeEntry;
  totalQuestions: number;
  examId: string;
  // Called after a successful batch save so the parent can refetch the grade
  // report — this is what makes "Submit Grades" re-enable without a refresh.
  onSaved: () => Promise<unknown>;
}

const StudentRow: React.FC<StudentRowProps> = ({ entry, examId, onSaved }) => {
  const [expanded, setExpanded] = useState(false);
  const [scores, setScores] = useState<Record<string, string>>({});
  const [savingAll, setSavingAll] = useState(false);
  const [savedAll, setSavedAll] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  // The score currently persisted in the DB, so a save is visibly reflected.
  const [savedScores, setSavedScores] = useState<Record<string, number | null>>(
    {}
  );
  const displayName =
    entry.student_name ?? entry.student_email ?? entry.student_id;

  // Initialise local score inputs from existing manual_score values
  const initialised = useRef(false);
  useEffect(() => {
    if (initialised.current) return;
    initialised.current = true;
    const init: Record<string, string> = {};
    const initSaved: Record<string, number | null> = {};
    for (const ans of entry.answers) {
      if (ans.question_type === "short" && ans.answer_id) {
        init[ans.answer_id] =
          ans.manual_score !== null ? String(ans.manual_score) : "";
        initSaved[ans.answer_id] = ans.manual_score;
      }
    }
    setScores(init);
    setSavedScores(initSaved);
  }, [entry.answers]);

  const shortAnswers = entry.answers.filter(
    (a) => a.question_type === "short" && a.answer_id
  );

  // AEGIS-119: one "Save all" commits every entered short-answer score in a
  // single action, replacing the per-answer Save buttons. Validates each input,
  // saves them together, then triggers a report refetch so the "Submit Grades"
  // gate re-evaluates immediately (no page refresh).
  const handleSaveAll = async () => {
    const newErrors: Record<string, string> = {};
    const toSave: { answerId: string; score: number }[] = [];
    for (const ans of shortAnswers) {
      const raw = scores[ans.answer_id!] ?? "";
      if (raw.trim() === "") continue; // leave blank answers ungraded
      const val = parseFloat(raw);
      if (isNaN(val)) {
        newErrors[ans.answer_id!] = "Enter a valid number.";
      } else if (val < 0 || val > ans.max_score) {
        newErrors[ans.answer_id!] = `Score must be 0–${ans.max_score}.`;
      } else {
        toSave.push({ answerId: ans.answer_id!, score: val });
      }
    }
    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0 || toSave.length === 0) return;

    setSavingAll(true);
    try {
      await Promise.all(
        toSave.map((s) =>
          apiClient.patch(`/exams/${examId}/answers/grade`, {
            answer_id: s.answerId,
            score: s.score,
          })
        )
      );
      setSavedScores((prev) => {
        const next = { ...prev };
        for (const s of toSave) next[s.answerId] = s.score;
        return next;
      });
      setSavedAll(true);
      setTimeout(() => setSavedAll(false), 2000);
      await onSaved(); // refetch report → ungraded_short updates → Submit Grades enables
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setErrors({
        _all: typeof detail === "string" ? detail : "Failed to save scores.",
      });
    } finally {
      setSavingAll(false);
    }
  };

  // AEGIS-118: "Absent" (never joined — no StudentSession) is visually
  // distinct from "No Answer" (joined, but left every question blank).
  const noAnswer =
    entry.attended && entry.answers.every((a) => !a.student_answer);

  // AEGIS-112: overall points (MCQ + manual short answers), reflecting the
  // live-saved scores so the total updates the moment a grade is saved.
  const totalPossible = entry.answers.reduce((sum, a) => sum + a.max_score, 0);
  const totalEarned = entry.answers.reduce((sum, a) => {
    if (a.question_type === "mcq") return sum + (a.is_correct ? a.max_score : 0);
    const live = a.answer_id ? savedScores[a.answer_id] : undefined;
    const score = live !== undefined && live !== null ? live : a.manual_score;
    return sum + (score ?? 0);
  }, 0);

  return (
    <div className="border border-hairline rounded-md overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-surface-card hover:bg-surface-soft transition-colors text-left"
      >
        <div>
          <p className="text-sm font-medium text-ink flex items-center gap-2">
            {displayName}
            {!entry.attended && (
              <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-surface-soft text-mute border border-hairline">
                Absent
              </span>
            )}
            {noAnswer && (
              <span className="inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary-active border border-primary/20">
                No Answer
              </span>
            )}
          </p>
          {entry.student_email && entry.student_name && (
            <p className="text-xs text-mute">{entry.student_email}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {totalPossible > 0 && (
            <span className="inline-block px-2 py-0.5 rounded border border-hairline bg-surface-soft text-xs font-semibold text-ink">
              {totalEarned}/{totalPossible} pts
            </span>
          )}
          <ScorePill correct={entry.mcq_correct} total={entry.mcq_total} />
          <svg
            className={`w-4 h-4 text-mute transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="bg-surface-doc border-t border-hairline divide-y divide-hairline-soft">
          {entry.answers.length === 0 ? (
            <p className="px-4 py-3 text-sm text-mute">No answers submitted.</p>
          ) : (
            entry.answers.map((ans) => (
              <div key={ans.question_id} className="px-4 py-3">
                <div className="flex items-start gap-3">
                  {/* Q number + type */}
                  <span className="flex-shrink-0 w-7 h-7 rounded-full bg-surface-soft flex items-center justify-center text-xs font-bold text-mute">
                    {ans.position + 1}
                  </span>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-ink mb-1">{ans.prompt}</p>

                    {ans.question_type === "mcq" ? (
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          {ans.is_correct ? (
                            <span className="inline-flex items-center gap-1 text-xs font-semibold text-accent-green">
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2.5}
                                  d="M5 13l4 4L19 7"
                                />
                              </svg>
                              Correct
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs font-semibold text-accent-red">
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2.5}
                                  d="M6 18L18 6M6 6l12 12"
                                />
                              </svg>
                              Incorrect
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-body">
                          Student:{" "}
                          <span className="font-medium text-ink">
                            {ans.student_answer || (
                              <em className="text-mute">no answer</em>
                            )}
                          </span>
                        </p>
                        {!ans.is_correct && ans.correct_answer && (
                          <p className="text-xs text-accent-green">
                            Correct:{" "}
                            <span className="font-medium">
                              {ans.correct_answer}
                            </span>
                          </p>
                        )}
                      </div>
                    ) : (
                      <div>
                        <span className="inline-block text-xs text-mute bg-surface-soft rounded px-1.5 py-0.5 mb-1">
                          Short answer — manual review
                        </span>
                        <p className="text-sm text-body whitespace-pre-wrap break-words bg-surface-card border border-hairline-soft rounded p-2 mt-1">
                          {ans.student_answer || (
                            <em className="text-mute">no answer</em>
                          )}
                        </p>
                        {ans.answer_id && (
                          <div className="flex items-center gap-2 mt-2">
                            <label className="text-xs text-mute">
                              Score (0–{ans.max_score}):
                            </label>
                            <input
                              type="number"
                              min={0}
                              max={ans.max_score}
                              step={0.5}
                              value={scores[ans.answer_id] ?? ""}
                              onChange={(e) =>
                                setScores((s) => ({
                                  ...s,
                                  [ans.answer_id!]: e.target.value,
                                }))
                              }
                              className="w-16 px-2 py-1 text-xs border border-hairline rounded-md bg-surface-card text-ink focus:outline-none focus:border-accent-blue"
                            />
                            {/* Reflect the persisted score so a save is visible */}
                            {savedScores[ans.answer_id] != null && (
                              <span className="text-xs text-accent-green font-semibold">
                                {savedScores[ans.answer_id]}/{ans.max_score} saved
                              </span>
                            )}
                          </div>
                        )}
                        {ans.answer_id && errors[ans.answer_id] && (
                          <p className="text-xs text-accent-red mt-1">
                            {errors[ans.answer_id]}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}

          {/* AEGIS-119: one Save action for all this student's short answers. */}
          {shortAnswers.length > 0 && (
            <div className="px-4 py-3 flex items-center justify-end gap-3">
              {errors._all && (
                <span className="text-xs text-accent-red">{errors._all}</span>
              )}
              {savedAll && (
                <span className="text-xs text-accent-green font-semibold">
                  All scores saved ✓
                </span>
              )}
              <button
                onClick={handleSaveAll}
                disabled={savingAll}
                className="px-4 py-1.5 text-xs bg-primary disabled:bg-surface-soft disabled:text-ash text-ink font-bold rounded-md transition-colors"
              >
                {savingAll ? "Saving…" : "Save all scores"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ExamGradeViewProps {
  examId: string;
  examTitle: string;
}

const ExamGradeView: React.FC<ExamGradeViewProps> = ({ examId, examTitle }) => {
  const [report, setReport] = useState<ExamGradeReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [releasing, setReleasing] = useState(false);
  const [releaseError, setReleaseError] = useState<string | null>(null);

  // AEGIS-112b: release results to students ("Submit Grades").
  const handleRelease = async () => {
    setReleasing(true);
    setReleaseError(null);
    try {
      const { data } = await apiClient.post<ExamGradeReport>(
        `/exams/${examId}/release-results`
      );
      setReport(data);
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : null;
      setReleaseError(
        typeof detail === "string" ? detail : "Failed to release results."
      );
    } finally {
      setReleasing(false);
    }
  };

  // AEGIS-119: reusable so a save can refetch and re-evaluate the Submit-Grades
  // gate (ungraded_short) without a page refresh.
  const loadReport = useCallback(
    () =>
      apiClient
        .get<ExamGradeReport>(`/exams/${examId}/grade`)
        .then((r) => setReport(r.data))
        .catch(() => setError("Failed to load grade report.")),
    [examId]
  );

  useEffect(() => {
    loadReport().finally(() => setLoading(false));
  }, [loadReport]);

  if (loading) {
    return (
      <p className="text-mute text-sm text-center py-10">Loading grades…</p>
    );
  }

  if (error) {
    return <p className="text-accent-red text-sm py-4">{error}</p>;
  }

  if (!report) return null;

  const totalMcq = report.mcq_total;
  const classAvg =
    report.students.length > 0 && totalMcq > 0
      ? Math.round(
          (report.students.reduce((s, st) => s + st.mcq_correct, 0) /
            (report.students.length * totalMcq)) *
            100,
        )
      : null;

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-base font-semibold text-ink">{examTitle}</h2>
        <p className="text-sm text-mute">{report.course_id}</p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="bg-surface-card border border-hairline rounded-md px-4 py-3">
          <p className="text-xs text-mute mb-1">Students</p>
          <p className="text-2xl font-bold text-ink">
            {report.students.length}
          </p>
        </div>
        <div className="bg-surface-card border border-hairline rounded-md px-4 py-3">
          <p className="text-xs text-mute mb-1">MCQ questions</p>
          <p className="text-2xl font-bold text-ink">{report.mcq_total}</p>
        </div>
        <div className="bg-surface-card border border-hairline rounded-md px-4 py-3">
          <p className="text-xs text-mute mb-1">Class avg (MCQ)</p>
          <p className="text-2xl font-bold text-ink">
            {classAvg !== null ? `${classAvg}%` : "—"}
          </p>
        </div>
      </div>

      {report.short_total > 0 && (
        <div className="mb-4 px-3 py-2 bg-accent-blue-soft border border-accent-blue/20 rounded-md text-sm text-accent-blue">
          This exam has {report.short_total} short-answer question
          {report.short_total !== 1 ? "s" : ""} that require manual grading.
        </div>
      )}

      {/* AEGIS-112b: Submit Grades — releases results to students. Only shown
          for exams with short answers (MCQ-only results are instant). */}
      {report.short_total > 0 && (
        <div className="mb-6 flex items-center justify-between gap-3 px-4 py-3 bg-surface-card border border-hairline rounded-md">
          {report.results_released ? (
            <p className="text-sm text-accent-green font-semibold">
              ✓ Results released to students.
            </p>
          ) : (
            <p className="text-sm text-body">
              Results are hidden from students until you submit grades.
              {report.ungraded_short > 0 && (
                <span className="text-mute">
                  {" "}
                  {report.ungraded_short} answer
                  {report.ungraded_short !== 1 ? "s" : ""} still ungraded.
                </span>
              )}
            </p>
          )}
          {!report.results_released && (
            <button
              onClick={handleRelease}
              disabled={releasing || report.ungraded_short > 0}
              title={
                report.ungraded_short > 0
                  ? "Grade every short answer before releasing results."
                  : undefined
              }
              className="flex-shrink-0 px-4 py-2 bg-primary disabled:bg-surface-soft disabled:text-ash text-ink text-sm font-bold rounded-md transition-colors"
            >
              {releasing ? "Releasing…" : "Submit Grades"}
            </button>
          )}
        </div>
      )}
      {releaseError && (
        <p className="text-sm text-accent-red mb-4">{releaseError}</p>
      )}

      {/* Per-student rows */}
      {report.students.length === 0 ? (
        <p className="text-sm text-mute text-center py-8">
          No students submitted answers for this exam.
        </p>
      ) : (
        <div className="space-y-2">
          {report.students.map((student) => (
            <StudentRow
              key={student.student_id}
              entry={student}
              examId={examId}
              totalQuestions={report.mcq_total + report.short_total}
              onSaved={loadReport}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default ExamGradeView;
