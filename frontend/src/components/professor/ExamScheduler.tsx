import React, { useEffect, useState } from "react";
import apiClient from "../../api/client";
import { SCORING_PRESETS, type ScoringPreset } from "./scoringPresets";
import ResourceAllowlistEditor, {
  type DraftUrlResource,
} from "./ResourceAllowlistEditor";
import { postUrlResources } from "../../pages/examCreate.helpers";

interface Quiz {
  id: string;
  title: string;
  duration_minutes: number;
  is_published: boolean;
  questions: { id: string }[];
}

interface ExamSchedulerProps {
  preselectedQuizId?: string;
  onScheduled: () => void;
}

const ExamScheduler: React.FC<ExamSchedulerProps> = ({
  preselectedQuizId,
  onScheduled,
}) => {
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [quizId, setQuizId] = useState(preselectedQuizId ?? "");
  const [courseId, setCourseId] = useState("");
  const [scheduledStart, setScheduledStart] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [scoringPreset, setScoringPreset] = useState<ScoringPreset>("standard");
  const [isOpenBook, setIsOpenBook] = useState(false);
  const [urlResources, setUrlResources] = useState<DraftUrlResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    apiClient
      .get<Quiz[]>("/quizzes")
      .then((r) => {
        const published = r.data.filter((q) => q.is_published);
        setQuizzes(published);
        if (!preselectedQuizId && published.length > 0) {
          setQuizId(published[0].id);
          setDurationMinutes(published[0].duration_minutes);
        }
      })
      .catch(() => setError("Failed to load quizzes."))
      .finally(() => setLoading(false));
  }, [preselectedQuizId]);

  // When quiz selection changes, update default duration
  function handleQuizChange(id: string) {
    setQuizId(id);
    const quiz = quizzes.find((q) => q.id === id);
    if (quiz) setDurationMinutes(quiz.duration_minutes);
  }

  function validate(): string | null {
    if (!quizId) return "Select a quiz.";
    if (!courseId.trim()) return "Course ID is required.";
    if (!scheduledStart) return "Scheduled start time is required.";
    if (new Date(scheduledStart) <= new Date())
      return "Please select a future date and time for the exam start.";
    if (durationMinutes < 1) return "Duration must be at least 1 minute.";
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
    try {
      const exam = await apiClient.post("/exams", {
        quiz_id: quizId,
        course_id: courseId.trim(),
        scheduled_start: new Date(scheduledStart).toISOString(),
        duration_minutes: durationMinutes,
        scoring_preset: scoringPreset,
        mode: isOpenBook ? "open_book" : "closed_book",
      });
      // AEGIS-121: attach the open-book URL allowlist (needs the exam id).
      if (isOpenBook) {
        await postUrlResources(exam.data.id, urlResources);
      }
      setSuccess(true);
      onScheduled();
    } catch {
      setError("Failed to schedule exam. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-mute text-sm text-center py-10">Loading…</p>;
  }

  if (success) {
    return (
      <div className="text-center py-12">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-accent-green-soft mb-4">
          <svg
            className="w-6 h-6 text-accent-green"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <p className="text-ink font-semibold mb-1">Exam scheduled</p>
        <p className="text-mute text-sm">
          The exam is in draft state. Open it when you're ready to let students
          in.
        </p>
      </div>
    );
  }

  if (quizzes.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-mute text-sm">No published quizzes yet.</p>
        <p className="text-ash text-xs mt-1">
          Build and publish a quiz first, then schedule an exam.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4 max-w-lg">
      {/* Quiz selector */}
      <div>
        <label className="block text-xs text-mute mb-1" htmlFor="sched-quiz">
          Quiz <span className="text-accent-red">*</span>
        </label>
        <select
          id="sched-quiz"
          value={quizId}
          onChange={(e) => handleQuizChange(e.target.value)}
          className="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
          required
        >
          {quizzes.map((q) => (
            <option key={q.id} value={q.id}>
              {q.title} ({q.questions.length} question
              {q.questions.length !== 1 ? "s" : ""})
            </option>
          ))}
        </select>
      </div>

      {/* Course ID */}
      <div>
        <label className="block text-xs text-mute mb-1" htmlFor="sched-course">
          Course ID <span className="text-accent-red">*</span>
        </label>
        <input
          id="sched-course"
          type="text"
          value={courseId}
          onChange={(e) => setCourseId(e.target.value)}
          placeholder="e.g. CS201"
          className="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
          required
        />
      </div>

      {/* Scheduled start */}
      <div>
        <label className="block text-xs text-mute mb-1" htmlFor="sched-start">
          Scheduled start <span className="text-accent-red">*</span>
        </label>
        <input
          id="sched-start"
          type="datetime-local"
          value={scheduledStart}
          onChange={(e) => setScheduledStart(e.target.value)}
          className="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
          required
        />
      </div>

      {/* Duration */}
      <div>
        <label
          className="block text-xs text-mute mb-1"
          htmlFor="sched-duration"
        >
          Duration (minutes) <span className="text-accent-red">*</span>
        </label>
        <input
          id="sched-duration"
          type="number"
          min={1}
          value={durationMinutes}
          onChange={(e) => setDurationMinutes(Number(e.target.value))}
          className="w-32 border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
          required
        />
      </div>

      {/* Scoring sensitivity preset (AEGIS-84) */}
      <div>
        <label className="block text-xs text-mute mb-1" htmlFor="sched-preset">
          Scoring sensitivity
        </label>
        <select
          id="sched-preset"
          value={scoringPreset}
          onChange={(e) => setScoringPreset(e.target.value as ScoringPreset)}
          className="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
        >
          {SCORING_PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label} — {p.hint}
            </option>
          ))}
        </select>
        <p className="text-xs text-ash mt-1">
          {SCORING_PRESETS.find((p) => p.value === scoringPreset)?.hint}
        </p>
      </div>

      {/* AEGIS-121: open-book toggle + resource allowlist */}
      <ResourceAllowlistEditor
        isOpenBook={isOpenBook}
        onToggle={setIsOpenBook}
        resources={urlResources}
        onChange={setUrlResources}
        inputClass="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
      />

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
        {saving ? "Scheduling…" : "Schedule Exam"}
      </button>
    </form>
  );
};

export default ExamScheduler;
