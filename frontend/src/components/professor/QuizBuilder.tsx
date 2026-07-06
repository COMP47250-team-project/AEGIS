import React, { useRef, useState } from "react";
import apiClient from "../../api/client";
import QuestionBankModal, { BankItem } from "./QuestionBankModal";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type QuestionType = "mcq" | "short";

interface DraftQuestion {
  localId: number;
  type: QuestionType;
  prompt: string;
  options: string[];
  correct_answer: string;
}

interface QuizBuilderProps {
  onCreated: (quizId: string, quizTitle: string) => void;
}

// ---------------------------------------------------------------------------
// Helper — single question card
// ---------------------------------------------------------------------------

interface QuestionCardProps {
  q: DraftQuestion;
  index: number;
  total: number;
  onChange: (updated: DraftQuestion) => void;
  onRemove: () => void;
}

const QuestionCard: React.FC<QuestionCardProps> = ({
  q,
  index,
  total,
  onChange,
  onRemove,
}) => {
  function setType(type: QuestionType) {
    onChange({
      ...q,
      type,
      options: type === "mcq" && q.options.length < 2 ? ["", ""] : q.options,
      correct_answer: "",
    });
  }

  function setOption(i: number, val: string) {
    const opts = [...q.options];
    opts[i] = val;
    onChange({ ...q, options: opts });
  }

  function addOption() {
    onChange({ ...q, options: [...q.options, ""] });
  }

  function removeOption(i: number) {
    const opts = q.options.filter((_, idx) => idx !== i);
    const correct = q.correct_answer === q.options[i] ? "" : q.correct_answer;
    onChange({ ...q, options: opts, correct_answer: correct });
  }

  return (
    <div className="bg-surface-card border border-hairline rounded-lg p-4">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-mute uppercase tracking-wide">
          Q{index + 1} / {total}
        </span>
        <div className="flex items-center gap-2">
          {/* Type toggle */}
          <button
            type="button"
            onClick={() => setType("mcq")}
            className={`px-2 py-0.5 rounded text-xs font-semibold transition-colors ${
              q.type === "mcq"
                ? "bg-surface-dark text-on-dark"
                : "bg-surface-soft text-mute"
            }`}
          >
            MCQ
          </button>
          <button
            type="button"
            onClick={() => setType("short")}
            className={`px-2 py-0.5 rounded text-xs font-semibold transition-colors ${
              q.type === "short"
                ? "bg-surface-dark text-on-dark"
                : "bg-surface-soft text-mute"
            }`}
          >
            Short
          </button>
          {/* Remove */}
          <button
            type="button"
            onClick={onRemove}
            className="text-accent-red hover:text-accent-red text-xs px-1"
            aria-label="Remove question"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Prompt */}
      <textarea
        rows={2}
        placeholder="Question prompt…"
        value={q.prompt}
        onChange={(e) => onChange({ ...q, prompt: e.target.value })}
        className="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc resize-none focus:outline-none focus:ring-1 focus:ring-surface-dark"
        required
      />

      {/* MCQ options */}
      {q.type === "mcq" && (
        <div className="mt-3 space-y-2">
          {q.options.map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="radio"
                name={`correct-${q.localId}`}
                checked={q.correct_answer === opt && opt !== ""}
                onChange={() => onChange({ ...q, correct_answer: opt })}
                className="accent-accent-green"
                title="Mark as correct answer"
              />
              <input
                type="text"
                placeholder={`Option ${i + 1}`}
                value={opt}
                onChange={(e) => setOption(i, e.target.value)}
                className="flex-1 border border-hairline rounded px-3 py-1.5 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
              />
              {q.options.length > 2 && (
                <button
                  type="button"
                  onClick={() => removeOption(i)}
                  className="text-mute hover:text-accent-red text-xs"
                  aria-label="Remove option"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={addOption}
            className="text-xs text-mute hover:text-ink mt-1"
          >
            + Add option
          </button>
          {q.correct_answer === "" && (
            <p className="text-xs text-accent-red mt-1">
              Select the correct answer (radio button).
            </p>
          )}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

let _localIdCounter = 0;
function nextLocalId() {
  return ++_localIdCounter;
}

const QuizBuilder: React.FC<QuizBuilderProps> = ({ onCreated }) => {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [questions, setQuestions] = useState<DraftQuestion[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showBank, setShowBank] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // AEGIS-90: append imported bank questions as editable copies (fresh localId,
  // so editing them never touches the original quiz).
  function importFromBank(bankItems: BankItem[]) {
    setQuestions((prev) => [
      ...prev,
      ...bankItems.map((b) => ({
        localId: nextLocalId(),
        type: b.question_type,
        prompt: b.question_text,
        options: b.question_type === "mcq" ? b.options ?? ["", ""] : [],
        correct_answer: b.correct_answer ?? "",
      })),
    ]);
    setShowBank(false);
  }

  function addQuestion(type: QuestionType) {
    setQuestions((prev) => [
      ...prev,
      {
        localId: nextLocalId(),
        type,
        prompt: "",
        options: type === "mcq" ? ["", ""] : [],
        correct_answer: "",
      },
    ]);
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  function updateQuestion(localId: number, updated: DraftQuestion) {
    setQuestions((prev) => prev.map((q) => (q.localId === localId ? updated : q)));
  }

  function removeQuestion(localId: number) {
    setQuestions((prev) => prev.filter((q) => q.localId !== localId));
  }

  function validate(): string | null {
    if (!title.trim()) return "Quiz title is required.";
    if (durationMinutes < 1) return "Duration must be at least 1 minute.";
    if (questions.length === 0) return "Add at least one question before publishing.";
    for (let i = 0; i < questions.length; i++) {
      const q = questions[i];
      if (!q.prompt.trim()) return `Question ${i + 1}: prompt is required.`;
      if (q.type === "mcq") {
        if (q.options.some((o) => !o.trim()))
          return `Question ${i + 1}: all options must be filled.`;
        if (!q.correct_answer)
          return `Question ${i + 1}: select the correct answer.`;
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
    try {
      // 1. Create quiz
      const quizRes = await apiClient.post<{ id: string }>("/quizzes", {
        title: title.trim(),
        description: description.trim() || undefined,
        duration_minutes: durationMinutes,
      });
      const quizId = quizRes.data.id;

      // 2. Add questions sequentially (position = array index)
      for (let i = 0; i < questions.length; i++) {
        const q = questions[i];
        const body: Record<string, unknown> = {
          type: q.type,
          prompt: q.prompt.trim(),
          position: i,
        };
        if (q.type === "mcq") {
          body.options = q.options;
          body.correct_answer = q.correct_answer;
        }
        await apiClient.post(`/quizzes/${quizId}/questions`, body);
      }

      // 3. Publish
      await apiClient.post(`/quizzes/${quizId}/publish`);

      onCreated(quizId, title.trim());
    } catch {
      setError("Failed to create quiz. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const canSubmit = !saving && title.trim().length > 0 && questions.length > 0;

  return (
    <form onSubmit={handleSubmit} noValidate>
      {/* Quiz metadata */}
      <div className="bg-surface-card border border-hairline rounded-lg p-4 mb-4 space-y-3">
        <h3 className="text-sm font-semibold text-ink">Quiz details</h3>
        <div>
          <label className="block text-xs text-mute mb-1" htmlFor="quiz-title">
            Title <span className="text-accent-red">*</span>
          </label>
          <input
            id="quiz-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Networking Fundamentals"
            className="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
            required
            autoFocus
          />
        </div>
        <div>
          <label
            className="block text-xs text-mute mb-1"
            htmlFor="quiz-description"
          >
            Description (optional)
          </label>
          <input
            id="quiz-description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Brief description for students"
            className="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
          />
        </div>
        <div>
          <label
            className="block text-xs text-mute mb-1"
            htmlFor="quiz-duration"
          >
            Duration (minutes) <span className="text-accent-red">*</span>
          </label>
          <input
            id="quiz-duration"
            type="number"
            min={1}
            value={durationMinutes}
            onChange={(e) => setDurationMinutes(Number(e.target.value))}
            className="w-32 border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
            required
          />
        </div>
      </div>

      {/* Question list */}
      <div className="space-y-3 mb-4">
        {questions.map((q, idx) => (
          <QuestionCard
            key={q.localId}
            q={q}
            index={idx}
            total={questions.length}
            onChange={(updated) => updateQuestion(q.localId, updated)}
            onRemove={() => removeQuestion(q.localId)}
          />
        ))}
      </div>

      {/* Add question buttons */}
      <div className="flex gap-2 mb-6">
        <button
          type="button"
          onClick={() => addQuestion("mcq")}
          className="px-3 py-1.5 border border-hairline rounded text-sm text-body hover:bg-surface-soft transition-colors"
        >
          + Multiple choice
        </button>
        <button
          type="button"
          onClick={() => addQuestion("short")}
          className="px-3 py-1.5 border border-hairline rounded text-sm text-body hover:bg-surface-soft transition-colors"
        >
          + Short answer
        </button>
        <button
          type="button"
          onClick={() => setShowBank(true)}
          className="px-3 py-1.5 border border-hairline rounded text-sm text-body hover:bg-surface-soft transition-colors"
        >
          Import from question bank
        </button>
      </div>

      <div ref={bottomRef} />

      {error && (
        <p className="text-sm text-accent-red mb-3" role="alert">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full py-2.5 bg-primary text-ink font-semibold text-sm rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-pressed transition-colors"
      >
        {saving ? "Creating…" : "Create & Publish Quiz"}
      </button>
      {questions.length === 0 && (
        <p className="text-xs text-mute text-center mt-2">
          Add at least one question to publish.
        </p>
      )}

      {showBank && (
        <QuestionBankModal
          onClose={() => setShowBank(false)}
          onImport={importFromBank}
        />
      )}
    </form>
  );
};

export default QuizBuilder;
