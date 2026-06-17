import React from "react";
import type { ExamQuestion } from "./QuestionRenderer";

interface ProgressSidebarProps {
  questions: ExamQuestion[];
  answers: Record<string, string>;
  currentIndex: number;
  onSelect: (index: number) => void;
}

const ProgressSidebar: React.FC<ProgressSidebarProps> = ({
  questions,
  answers,
  currentIndex,
  onSelect,
}) => (
  <nav aria-label="Question progress" className="flex flex-col gap-1">
    <p className="text-xs font-semibold text-mute uppercase tracking-wide px-2 pb-2">
      Questions
    </p>
    {questions.map((q, idx) => {
      const answered = Boolean(answers[q.id]);
      const current = idx === currentIndex;
      return (
        <button
          key={q.id}
          onClick={() => onSelect(idx)}
          aria-current={current ? "step" : undefined}
          className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-left w-full transition-colors ${
            current
              ? "bg-surface-soft border border-hairline text-ink font-semibold"
              : "text-body hover:bg-surface-soft"
          }`}
        >
          <span
            className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
              answered ? "bg-accent-green text-white" : "bg-hairline text-mute"
            }`}
          >
            {answered ? "✓" : idx + 1}
          </span>
          <span className="truncate">Q{idx + 1}</span>
        </button>
      );
    })}
  </nav>
);

export default ProgressSidebar;
