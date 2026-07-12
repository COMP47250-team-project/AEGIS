// frontend/src/pages/StudentResults.tsx
// AEGIS-10: Student exam results — shows score and per-question breakdown
// after the exam is closed.
import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import apiClient from "../api/client";

// ---------------------------------------------------------------------------
// Types (mirror backend StudentExamResults schema)
// ---------------------------------------------------------------------------

interface StudentAnswerResult {
  question_id: string;
  position: number;
  question_type: "mcq" | "short";
  prompt: string;
  options: string[] | null;
  student_answer: string;
  correct_answer: string | null;
  is_correct: boolean | null;
  manual_score: number | null;
  max_score: number;
}

interface StudentExamResults {
  exam_id: string;
  exam_title: string;
  course_name: string;
  closed_at: string | null;
  mcq_correct: number;
  mcq_total: number;
  questions: StudentAnswerResult[];
  integrity_score: number | null;
  points_earned: number;
  points_possible: number;
  fully_graded: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const ScoreCard: React.FC<{ correct: number; total: number }> = ({
  correct,
  total,
}) => {
  const pct = total > 0 ? Math.round((correct / total) * 100) : null;
  const color =
    pct === null
      ? "text-mute"
      : pct >= 80
        ? "text-accent-green"
        : pct >= 50
          ? "text-primary-active"
          : "text-accent-red";

  return (
    <div className="bg-surface-card border border-hairline rounded-md p-6 flex flex-col items-center justify-center">
      <p className="text-xs text-mute uppercase tracking-widest mb-1">
        MCQ Score
      </p>
      {pct !== null ? (
        <>
          <p className={`text-4xl font-bold ${color}`}>{pct}%</p>
          <p className="text-sm text-mute mt-1">
            {correct} / {total} correct
          </p>
        </>
      ) : (
        <p className="text-sm text-mute">No MCQ questions</p>
      )}
    </div>
  );
};

// AEGIS-112: overall score across MCQ + manually graded short answers.
const TotalScoreCard: React.FC<{
  earned: number;
  possible: number;
  fullyGraded: boolean;
}> = ({ earned, possible, fullyGraded }) => {
  const pct = possible > 0 ? Math.round((earned / possible) * 100) : null;
  const color =
    pct === null
      ? "text-mute"
      : pct >= 80
        ? "text-accent-green"
        : pct >= 50
          ? "text-primary-active"
          : "text-accent-red";
  return (
    <div className="bg-surface-card border border-hairline rounded-md p-6 flex flex-col items-center justify-center">
      <p className="text-xs text-mute uppercase tracking-widest mb-1">
        Total Score
      </p>
      {pct !== null ? (
        <>
          <p className={`text-4xl font-bold ${color}`}>{pct}%</p>
          <p className="text-sm text-mute mt-1">
            {earned} / {possible} points
          </p>
        </>
      ) : (
        <p className="text-sm text-mute">—</p>
      )}
      {!fullyGraded && (
        <p className="text-xs text-accent-blue mt-2">
          Some answers are still being graded.
        </p>
      )}
    </div>
  );
};

const IntegrityScoreCard: React.FC<{ score: number | null }> = ({ score }) => {
  if (score === null) {
    return (
      <div className="bg-surface-card border border-hairline rounded-md p-6 flex flex-col items-center justify-center">
        <p className="text-xs text-mute uppercase tracking-widest mb-1">
          Integrity Score
        </p>
        <p className="text-sm text-mute">Pending</p>
      </div>
    );
  }
  const pct = Math.round(score * 100);
  const color =
    pct >= 70
      ? "text-accent-red"
      : pct >= 30
        ? "text-primary-active"
        : "text-accent-green";
  const label = pct >= 70 ? "High Risk" : pct >= 30 ? "Moderate" : "Low Risk";
  return (
    <div className="bg-surface-card border border-hairline rounded-md p-6 flex flex-col items-center justify-center">
      <p className="text-xs text-mute uppercase tracking-widest mb-1">
        Integrity Score
      </p>
      <p className={`text-4xl font-bold ${color}`}>{pct}%</p>
      <p className="text-sm text-mute mt-1">{label}</p>
    </div>
  );
};

interface QuestionResultCardProps {
  ans: StudentAnswerResult;
  index: number;
}

const QuestionResultCard: React.FC<QuestionResultCardProps> = ({
  ans,
  index,
}) => {
  const isShort = ans.question_type === "short";

  return (
    <div
      className={`bg-surface-card border rounded-md p-5 ${
        ans.is_correct === true
          ? "border-accent-green/40"
          : ans.is_correct === false
            ? "border-accent-red/40"
            : "border-hairline"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-full bg-surface-soft flex items-center justify-center text-xs font-bold text-mute flex-shrink-0">
            {index + 1}
          </span>
          <span className="text-xs text-mute uppercase tracking-wide">
            {isShort ? "Short answer" : "Multiple choice"}
          </span>
        </div>

        {/* Verdict badge */}
        {!isShort && (
          <span
            className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded ${
              ans.is_correct
                ? "bg-accent-green-soft text-accent-green"
                : "bg-accent-red-soft text-accent-red"
            }`}
          >
            {ans.is_correct ? (
              <>
                <svg
                  className="w-3 h-3"
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
              </>
            ) : (
              <>
                <svg
                  className="w-3 h-3"
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
              </>
            )}
          </span>
        )}

        {isShort && (
          <span className="text-xs text-mute bg-surface-soft rounded px-2 py-0.5">
            Manual review
          </span>
        )}
      </div>

      {/* Prompt */}
      <p className="text-sm text-ink mb-3 leading-relaxed">{ans.prompt}</p>

      {/* MCQ options (show correct/wrong highlighting) */}
      {!isShort && ans.options && (
        <div className="space-y-1.5 mb-3">
          {ans.options.map((opt, i) => {
            const isStudentChoice = opt === ans.student_answer;
            const isCorrectChoice = opt === ans.correct_answer;
            const base =
              "flex items-center gap-2.5 px-3 py-2 rounded-md border text-sm";
            let cls = `${base} border-hairline text-body`;
            if (isCorrectChoice)
              cls = `${base} bg-accent-green-soft border-accent-green/40 text-accent-green font-medium`;
            else if (isStudentChoice && !isCorrectChoice)
              cls = `${base} bg-accent-red-soft border-accent-red/30 text-accent-red`;

            return (
              <div key={i} className={cls}>
                <span className="w-4 h-4 rounded-full border border-current flex items-center justify-center flex-shrink-0">
                  {isStudentChoice && (
                    <span className="w-2 h-2 rounded-full bg-current" />
                  )}
                </span>
                <span>{opt}</span>
                {isCorrectChoice && !isStudentChoice && (
                  <span className="ml-auto text-xs text-accent-green font-normal">
                    correct answer
                  </span>
                )}
                {isStudentChoice && (
                  <span className="ml-auto text-xs text-current font-normal">
                    your answer
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* MCQ no-options fallback */}
      {!isShort && !ans.options && (
        <div className="text-sm text-body mb-3">
          <span className="text-mute">Your answer: </span>
          <span
            className={
              ans.is_correct
                ? "text-accent-green font-medium"
                : "text-accent-red font-medium"
            }
          >
            {ans.student_answer || "—"}
          </span>
          {!ans.is_correct && ans.correct_answer && (
            <>
              <span className="text-mute mx-2">·</span>
              <span className="text-mute">Correct: </span>
              <span className="text-accent-green font-medium">
                {ans.correct_answer}
              </span>
            </>
          )}
        </div>
      )}

      {/* Short answer */}
      {isShort && (
        <div className="bg-surface-doc border border-hairline-soft rounded p-3">
          <p className="text-sm text-body whitespace-pre-wrap break-words">
            {ans.student_answer || (
              <em className="text-mute">No answer submitted</em>
            )}
          </p>
          {/* AEGIS-112: the professor's manual grade, once given */}
          <div className="mt-2 pt-2 border-t border-hairline-soft">
            {ans.manual_score !== null ? (
              <span className="text-xs font-semibold text-accent-green">
                Score: {ans.manual_score} / {ans.max_score}
              </span>
            ) : (
              <span className="text-xs text-accent-blue">
                Awaiting grading
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const StudentResults: React.FC = () => {
  const { id: examId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [results, setResults] = useState<StudentExamResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!examId) {
      navigate("/student/dashboard", { replace: true });
      return;
    }
    apiClient
      .get<StudentExamResults>(`/student/exams/${examId}/results`)
      .then((r) => setResults(r.data))
      .catch((err) => {
        const detail = (err as { response?: { data?: { detail?: string } } })
          ?.response?.data?.detail;
        setError(detail ?? "Failed to load results.");
      })
      .finally(() => setLoading(false));
  }, [examId, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
        <div className="text-center max-w-sm">
          <p className="text-sm text-body mb-4">{error}</p>
          <Link
            to="/student/dashboard"
            className="px-4 py-2 bg-primary text-ink text-sm font-bold rounded-md"
          >
            Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (!results) return null;

  return (
    <div className="min-h-screen bg-canvas">
      {/* Header */}
      <header className="bg-canvas border-b border-hairline">
        <div className="max-w-3xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-surface-dark">
              <svg
                className="w-4 h-4 text-on-dark"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
            </div>
            <span className="text-sm font-bold text-ink tracking-tight">
              AEGIS
            </span>
          </div>
          <Link
            to="/student/dashboard"
            className="text-sm text-mute hover:text-ink transition-colors"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        {/* Exam meta */}
        <div className="mb-6">
          <p className="text-xs text-mute uppercase tracking-widest mb-1">
            {results.course_name}
          </p>
          <h1 className="text-2xl font-bold text-ink mb-1">
            {results.exam_title}
          </h1>
          <p className="text-sm text-mute">
            Closed {formatDate(results.closed_at)}
          </p>
        </div>

        {/* Score cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <TotalScoreCard
            earned={results.points_earned}
            possible={results.points_possible}
            fullyGraded={results.fully_graded}
          />
          <ScoreCard correct={results.mcq_correct} total={results.mcq_total} />
          <IntegrityScoreCard score={results.integrity_score} />
          <div className="sm:col-span-2 bg-surface-card border border-hairline rounded-md p-5 flex flex-col justify-center">
            <p className="text-xs text-mute uppercase tracking-widest mb-3">
              Question breakdown
            </p>
            <div className="flex gap-6">
              <div>
                <p className="text-2xl font-bold text-ink">
                  {results.questions.length}
                </p>
                <p className="text-xs text-mute">Total questions</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-accent-green">
                  {results.mcq_correct}
                </p>
                <p className="text-xs text-mute">MCQ correct</p>
              </div>
              {results.mcq_total > results.mcq_correct && (
                <div>
                  <p className="text-2xl font-bold text-accent-red">
                    {results.mcq_total - results.mcq_correct}
                  </p>
                  <p className="text-xs text-mute">MCQ incorrect</p>
                </div>
              )}
              {results.questions.some((q) => q.question_type === "short") && (
                <div>
                  <p className="text-2xl font-bold text-mute">
                    {
                      results.questions.filter(
                        (q) => q.question_type === "short",
                      ).length
                    }
                  </p>
                  <p className="text-xs text-mute">Short answer (manual)</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Per-question results */}
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-ink uppercase tracking-wide">
            Question Review
          </h2>
          {results.questions.map((ans, i) => (
            <QuestionResultCard key={ans.question_id} ans={ans} index={i} />
          ))}
        </div>
      </main>
    </div>
  );
};

export default StudentResults;
