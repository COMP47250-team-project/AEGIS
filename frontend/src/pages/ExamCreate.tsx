// frontend/src/pages/ExamCreate.tsx
// AEGIS-62: professor creates an exam (quiz + questions), schedules it, and
// enrols students — one form. Orchestrates the existing quiz/exam/enroll APIs.
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";
import { durationMinutes, parseStudentEmails } from "./examCreate.helpers";

type QType = "short" | "mcq";

interface DraftQuestion {
  type: QType;
  prompt: string;
  maxScore: number;
  options: string[];
  correctAnswer: string;
}

const newQuestion = (): DraftQuestion => ({
  type: "short",
  prompt: "",
  maxScore: 1,
  options: ["", ""],
  correctAnswer: "",
});

const inputClass =
  "w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark";

function errorDetail(err: unknown): string | undefined {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data
    ?.detail;
}

const ExamCreate: React.FC = () => {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [courseId, setCourseId] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [questions, setQuestions] = useState<DraftQuestion[]>([newQuestion()]);
  const [enrolText, setEnrolText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function patchQuestion(i: number, patch: Partial<DraftQuestion>) {
    setQuestions((qs) => qs.map((q, idx) => (idx === i ? { ...q, ...patch } : q)));
  }

  async function handleCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setEnrolText((prev) => (prev ? `${prev}\n${text}` : text));
    e.target.value = ""; // allow re-uploading the same file
  }

  function validate(): string | null {
    if (!title.trim()) return "Exam title is required.";
    if (!courseId.trim()) return "Course is required.";
    if (!start || !end) return "Start and end times are required.";
    if (durationMinutes(start, end) <= 0)
      return "End time must be later than the start time.";
    if (questions.length < 1) return "Add at least 1 question.";
    for (const [i, q] of questions.entries()) {
      if (!q.prompt.trim()) return `Question ${i + 1}: prompt is required.`;
      if (q.maxScore <= 0) return `Question ${i + 1}: max score must be above 0.`;
      if (q.type === "mcq") {
        const opts = q.options.map((o) => o.trim()).filter(Boolean);
        if (opts.length < 2)
          return `Question ${i + 1}: multiple choice needs at least 2 options.`;
        if (!q.correctAnswer || !opts.includes(q.correctAnswer))
          return `Question ${i + 1}: pick the correct option.`;
      }
    }
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setSaving(true);
    const duration = durationMinutes(start, end);
    try {
      const quiz = await apiClient.post("/quizzes", {
        title: title.trim(),
        duration_minutes: duration,
      });
      const quizId = quiz.data.id;

      for (const [i, q] of questions.entries()) {
        await apiClient.post(`/quizzes/${quizId}/questions`, {
          type: q.type,
          prompt: q.prompt.trim(),
          position: i,
          max_score: q.maxScore,
          ...(q.type === "mcq"
            ? {
                options: q.options.map((o) => o.trim()).filter(Boolean),
                correct_answer: q.correctAnswer,
              }
            : {}),
        });
      }

      await apiClient.post(`/quizzes/${quizId}/publish`);

      const exam = await apiClient.post("/exams", {
        quiz_id: quizId,
        course_id: courseId.trim(),
        scheduled_start: new Date(start).toISOString(),
        duration_minutes: duration,
      });
      const examId = exam.data.id;

      const emails = parseStudentEmails(enrolText);
      const results = await Promise.allSettled(
        emails.map((email) =>
          apiClient.post(`/exams/${examId}/enroll-by-email`, { email }),
        ),
      );
      const enrolled = results.filter((r) => r.status === "fulfilled").length;

      navigate(`/professor/session/${examId}`, {
        state: {
          toast: `Exam created — ${enrolled} student${
            enrolled === 1 ? "" : "s"
          } enrolled`,
        },
      });
    } catch (err: unknown) {
      setError(errorDetail(err) ?? "Failed to create exam. Please try again.");
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-canvas">
      <header className="bg-surface-card border-b border-hairline px-4 sm:px-6 py-3 flex items-center gap-2">
        <button
          onClick={() => navigate("/professor/dashboard")}
          className="text-xs text-mute hover:text-ink transition-colors"
        >
          ← Dashboard
        </button>
        <span className="text-hairline mx-1">|</span>
        <span className="text-sm font-semibold text-ink">New Exam</span>
      </header>

      <form
        onSubmit={handleSubmit}
        noValidate
        className="max-w-2xl mx-auto px-4 sm:px-6 py-6 space-y-5"
      >
        {/* Exam details */}
        <div>
          <label className="block text-xs text-mute mb-1" htmlFor="exam-title">
            Exam title <span className="text-accent-red">*</span>
          </label>
          <input
            id="exam-title"
            className={inputClass}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Midterm — Networks"
          />
        </div>

        <div>
          <label className="block text-xs text-mute mb-1" htmlFor="exam-course">
            Course <span className="text-accent-red">*</span>
          </label>
          <input
            id="exam-course"
            className={inputClass}
            value={courseId}
            onChange={(e) => setCourseId(e.target.value)}
            placeholder="e.g. CS201"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-mute mb-1" htmlFor="exam-start">
              Start <span className="text-accent-red">*</span>
            </label>
            <input
              id="exam-start"
              type="datetime-local"
              className={inputClass}
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs text-mute mb-1" htmlFor="exam-end">
              End <span className="text-accent-red">*</span>
            </label>
            <input
              id="exam-end"
              type="datetime-local"
              className={inputClass}
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </div>
        </div>

        {/* Questions */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">Questions</h2>
            <button
              type="button"
              onClick={() => setQuestions((qs) => [...qs, newQuestion()])}
              className="text-xs text-primary-active hover:underline"
            >
              + Add question
            </button>
          </div>

          {questions.map((q, i) => (
            <div
              key={i}
              className="border border-hairline rounded-md p-3 space-y-3 bg-surface-card"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-mute">Question {i + 1}</span>
                {questions.length > 1 && (
                  <button
                    type="button"
                    onClick={() =>
                      setQuestions((qs) => qs.filter((_, idx) => idx !== i))
                    }
                    className="text-xs text-accent-red hover:underline"
                  >
                    Remove
                  </button>
                )}
              </div>

              <div className="flex gap-3">
                <select
                  aria-label={`Question ${i + 1} type`}
                  className={`${inputClass} w-40`}
                  value={q.type}
                  onChange={(e) => patchQuestion(i, { type: e.target.value as QType })}
                >
                  <option value="short">Text</option>
                  <option value="mcq">Multiple choice</option>
                </select>
                <div className="w-32">
                  <input
                    type="number"
                    min={1}
                    aria-label={`Question ${i + 1} max score`}
                    className={inputClass}
                    value={q.maxScore}
                    onChange={(e) =>
                      patchQuestion(i, { maxScore: Number(e.target.value) })
                    }
                    placeholder="Max score"
                  />
                </div>
              </div>

              <textarea
                aria-label={`Question ${i + 1} prompt`}
                className={inputClass}
                rows={2}
                value={q.prompt}
                onChange={(e) => patchQuestion(i, { prompt: e.target.value })}
                placeholder="Prompt"
              />

              {q.type === "mcq" && (
                <div className="space-y-2">
                  {q.options.map((opt, oi) => (
                    <div key={oi} className="flex items-center gap-2">
                      <input
                        type="radio"
                        name={`correct-${i}`}
                        aria-label={`Question ${i + 1} option ${oi + 1} correct`}
                        checked={!!opt && q.correctAnswer === opt}
                        onChange={() => patchQuestion(i, { correctAnswer: opt })}
                      />
                      <input
                        className={inputClass}
                        value={opt}
                        onChange={(e) => {
                          const options = q.options.map((o, idx) =>
                            idx === oi ? e.target.value : o,
                          );
                          patchQuestion(i, {
                            options,
                            // if this option was the selected correct one, keep
                            // it synced as its text changes (guard against the
                            // empty-option case so typing doesn't auto-select)
                            correctAnswer:
                              opt !== "" && q.correctAnswer === opt
                                ? e.target.value
                                : q.correctAnswer,
                          });
                        }}
                        placeholder={`Option ${oi + 1}`}
                      />
                      {q.options.length > 2 && (
                        <button
                          type="button"
                          onClick={() =>
                            patchQuestion(i, {
                              options: q.options.filter((_, idx) => idx !== oi),
                            })
                          }
                          className="text-xs text-accent-red"
                          aria-label={`Remove option ${oi + 1}`}
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() =>
                      patchQuestion(i, { options: [...q.options, ""] })
                    }
                    className="text-xs text-primary-active hover:underline"
                  >
                    + Add option
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Enrolment */}
        <div>
          <label className="block text-xs text-mute mb-1" htmlFor="exam-enrol">
            Enrol students (emails)
          </label>
          <textarea
            id="exam-enrol"
            className={inputClass}
            rows={3}
            value={enrolText}
            onChange={(e) => setEnrolText(e.target.value)}
            placeholder="Type or paste emails, separated by commas or new lines"
          />
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={handleCsv}
            className="mt-2 text-xs text-mute"
            aria-label="Upload student emails CSV"
          />
        </div>

        {error && (
          <p className="text-sm text-accent-red" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full py-2.5 bg-primary text-ink font-semibold text-sm rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-pressed transition-colors"
        >
          {saving ? "Creating…" : "Create Exam"}
        </button>
      </form>
    </div>
  );
};

export default ExamCreate;
