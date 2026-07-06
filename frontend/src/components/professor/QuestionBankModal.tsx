// AEGIS-90: Import questions from a professor's previous quizzes.
// Paginated, searchable bank; selected questions are handed back to the
// QuizBuilder as editable copies.
import React, { useCallback, useEffect, useState } from "react";
import apiClient from "../../api/client";

export interface BankItem {
  question_id: string;
  quiz_id: string;
  quiz_title: string;
  question_text: string;
  question_type: "mcq" | "short";
  options: string[] | null;
  correct_answer: string | null;
  created_at: string;
}

interface BankResponse {
  items: BankItem[];
  total: number;
  page: number;
  page_size: number;
}

interface Props {
  onClose: () => void;
  onImport: (items: BankItem[]) => void;
}

const PAGE_SIZE = 10;

function truncate(text: string, max = 60): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

const QuestionBankModal: React.FC<Props> = ({ onClose, onImport }) => {
  const [items, setItems] = useState<BankItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  // Keep the full items so selection survives pagination.
  const [selected, setSelected] = useState<Map<string, BankItem>>(new Map());

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const { data } = await apiClient.get<BankResponse>(
        "/quizzes/question-bank",
        { params: { page, page_size: PAGE_SIZE, search: search || undefined } }
      );
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  function toggle(item: BankItem) {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(item.question_id)) next.delete(item.question_id);
      else next.set(item.question_id, item);
      return next;
    });
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div
      className="fixed inset-0 z-50 bg-ink/40 flex items-center justify-center p-4"
      role="presentation"
    >
      <div
        className="bg-surface-card w-full max-w-2xl rounded-md border border-hairline max-h-[85vh] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-label="Import from question bank"
      >
        <header className="flex items-center justify-between px-4 py-3 border-b border-hairline">
          <h3 className="text-sm font-semibold text-ink">
            Import from question bank
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-mute hover:text-ink text-lg leading-none px-1"
          >
            ✕
          </button>
        </header>

        <div className="px-4 py-3 border-b border-hairline">
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setPage(1);
              setSearch(e.target.value);
            }}
            placeholder="Search question text…"
            aria-label="Search question text"
            className="w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark"
          />
        </div>

        <div className="overflow-y-auto p-4 flex-1">
          {error ? (
            <p className="text-accent-red text-sm">
              Could not load the question bank.
            </p>
          ) : loading ? (
            <p className="text-mute text-sm">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-mute text-sm">
              {search
                ? "No questions match your search."
                : "You have no previous quizzes to import from yet."}
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-mute text-left">
                  <th className="w-8" />
                  <th className="py-1 pr-2">Quiz</th>
                  <th className="py-1 pr-2">Question</th>
                  <th className="py-1 pr-2">Type</th>
                  <th className="py-1">Created</th>
                </tr>
              </thead>
              <tbody>
                {items.map((i) => (
                  <tr
                    key={i.question_id}
                    className="border-t border-hairline-soft"
                  >
                    <td className="py-1.5">
                      <input
                        type="checkbox"
                        checked={selected.has(i.question_id)}
                        onChange={() => toggle(i)}
                        aria-label={`Select question: ${i.question_text}`}
                      />
                    </td>
                    <td className="py-1.5 pr-2 text-mute truncate max-w-[8rem]">
                      {i.quiz_title}
                    </td>
                    <td className="py-1.5 pr-2 text-ink">
                      {truncate(i.question_text)}
                    </td>
                    <td className="py-1.5 pr-2 uppercase text-mute">
                      {i.question_type}
                    </td>
                    <td className="py-1.5 text-mute whitespace-nowrap">
                      {new Date(i.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <footer className="flex items-center justify-between px-4 py-3 border-t border-hairline">
          <div className="flex items-center gap-2 text-xs text-mute">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-2 py-1 border border-hairline rounded disabled:opacity-40"
            >
              Prev
            </button>
            <span>
              Page {page} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-2 py-1 border border-hairline rounded disabled:opacity-40"
            >
              Next
            </button>
          </div>
          <button
            type="button"
            onClick={() => onImport([...selected.values()])}
            disabled={selected.size === 0}
            className="px-4 py-2 bg-primary text-ink text-sm font-bold rounded-md disabled:opacity-50"
          >
            Add selected{selected.size > 0 ? ` (${selected.size})` : ""}
          </button>
        </footer>
      </div>
    </div>
  );
};

export default QuestionBankModal;
