import React, { useEffect, useState } from "react";
import apiClient from "../../api/client";

// ---------------------------------------------------------------------------
// Types (mirroring backend ExamGradeReport schema)
// ---------------------------------------------------------------------------

interface GradeAnswerItem {
  question_id: string;
  position: number;
  question_type: "mcq" | "short";
  prompt: string;
  student_answer: string;
  correct_answer: string | null;
  is_correct: boolean | null;
}

interface StudentGradeEntry {
  student_id: string;
  student_email: string | null;
  student_name: string | null;
  mcq_correct: number;
  mcq_total: number;
  answers: GradeAnswerItem[];
}

interface ExamGradeReport {
  exam_id: string;
  quiz_title: string;
  course_id: string;
  mcq_total: number;
  short_total: number;
  students: StudentGradeEntry[];
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const ScorePill: React.FC<{ correct: number; total: number }> = ({ correct, total }) => {
  if (total === 0) return <span className="text-xs text-mute">No MCQ</span>;
  const pct = Math.round((correct / total) * 100);
  const cls =
    pct >= 80
      ? "bg-accent-green-soft text-accent-green border-accent-green/20"
      : pct >= 50
      ? "bg-primary/10 text-primary-active border-primary/20"
      : "bg-accent-red-soft text-accent-red border-accent-red/20";
  return (
    <span className={`inline-block px-2 py-0.5 rounded border text-xs font-semibold ${cls}`}>
      {correct}/{total} MCQ ({pct}%)
    </span>
  );
};

interface StudentRowProps {
  entry: StudentGradeEntry;
  totalQuestions: number;
}

const StudentRow: React.FC<StudentRowProps> = ({ entry }) => {
  const [expanded, setExpanded] = useState(false);
  const displayName = entry.student_name ?? entry.student_email ?? entry.student_id;

  return (
    <div className="border border-hairline rounded-md overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-surface-card hover:bg-surface-soft transition-colors text-left"
      >
        <div>
          <p className="text-sm font-medium text-ink">{displayName}</p>
          {entry.student_email && entry.student_name && (
            <p className="text-xs text-mute">{entry.student_email}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          <ScorePill correct={entry.mcq_correct} total={entry.mcq_total} />
          <svg
            className={`w-4 h-4 text-mute transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
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
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                              </svg>
                              Correct
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs font-semibold text-accent-red">
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                              Incorrect
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-body">
                          Student: <span className="font-medium text-ink">{ans.student_answer || <em className="text-mute">no answer</em>}</span>
                        </p>
                        {!ans.is_correct && ans.correct_answer && (
                          <p className="text-xs text-accent-green">
                            Correct: <span className="font-medium">{ans.correct_answer}</span>
                          </p>
                        )}
                      </div>
                    ) : (
                      <div>
                        <span className="inline-block text-xs text-mute bg-surface-soft rounded px-1.5 py-0.5 mb-1">
                          Short answer — manual review
                        </span>
                        <p className="text-sm text-body whitespace-pre-wrap break-words bg-surface-card border border-hairline-soft rounded p-2 mt-1">
                          {ans.student_answer || <em className="text-mute">no answer</em>}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))
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

  useEffect(() => {
    apiClient
      .get<ExamGradeReport>(`/exams/${examId}/grade`)
      .then((r) => setReport(r.data))
      .catch(() => setError("Failed to load grade report."))
      .finally(() => setLoading(false));
  }, [examId]);

  if (loading) {
    return <p className="text-mute text-sm text-center py-10">Loading grades…</p>;
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
            100
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
          <p className="text-2xl font-bold text-ink">{report.students.length}</p>
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
          This exam has {report.short_total} short-answer question{report.short_total !== 1 ? "s" : ""} that require manual grading.
        </div>
      )}

      {/* Per-student rows */}
      {report.students.length === 0 ? (
        <p className="text-sm text-mute text-center py-8">No students submitted answers for this exam.</p>
      ) : (
        <div className="space-y-2">
          {report.students.map((student) => (
            <StudentRow
              key={student.student_id}
              entry={student}
              totalQuestions={report.mcq_total + report.short_total}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default ExamGradeView;
