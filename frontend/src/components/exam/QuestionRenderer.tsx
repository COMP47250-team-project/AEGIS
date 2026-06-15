import React from "react";

export interface ExamQuestion {
  id: string;
  type: "mcq" | "short";
  prompt: string;
  options: string[] | null;
  position: number;
}

interface QuestionRendererProps {
  question: ExamQuestion;
  answer: string;
  onAnswerChange: (questionId: string, value: string) => void;
  onPaste: (questionId: string) => void;
}

const QuestionRenderer: React.FC<QuestionRendererProps> = ({
  question,
  answer,
  onAnswerChange,
  onPaste,
}) => {
  if (question.type === "mcq" && question.options) {
    return (
      <div className="space-y-4">
        <p className="text-base text-ink leading-relaxed">{question.prompt}</p>
        <div className="space-y-2">
          {question.options.map((option, idx) => {
            const optId = `${question.id}-opt-${idx}`;
            const checked = answer === option;
            return (
              <label
                key={idx}
                htmlFor={optId}
                className={`flex items-center gap-3 px-4 py-3 rounded-md border cursor-pointer transition-colors ${
                  checked
                    ? "bg-accent-blue-soft border-accent-blue"
                    : "bg-surface-card border-hairline hover:bg-surface-soft"
                }`}
              >
                <input
                  id={optId}
                  type="radio"
                  name={`q-${question.id}`}
                  value={option}
                  checked={checked}
                  onChange={() => onAnswerChange(question.id, option)}
                  className="w-4 h-4 accent-primary"
                />
                <span className="text-sm text-ink">{option}</span>
              </label>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-base text-ink leading-relaxed">{question.prompt}</p>
      <textarea
        value={answer}
        onChange={(e) => onAnswerChange(question.id, e.target.value)}
        onPaste={() => onPaste(question.id)}
        placeholder="Type your answer here…"
        rows={6}
        className="w-full px-4 py-3 bg-surface-card border border-hairline rounded-md text-sm text-ink placeholder-ash resize-y focus:outline-none focus:border-accent-blue focus:ring-2 focus:ring-accent-blue/20 leading-relaxed"
      />
    </div>
  );
};

export default QuestionRenderer;
