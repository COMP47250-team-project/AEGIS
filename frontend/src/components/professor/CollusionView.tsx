// CollusionView.tsx — 1C
// Displays pairwise answer-similarity results for a closed exam.
// Shows a ranked flagged-pairs list and a per-question similarity matrix.

import React, { useState } from "react";
import {
  type CollusionResponse,
  type SimilarPairItem,
  getCollusionReport,
} from "../../api/ai";

interface Props {
  examId: string;
  // Map of student_id -> display name (from the grade report)
  studentNames: Record<string, string>;
  // Map of question_id -> question prompt (for display)
  questionPrompts: Record<string, string>;
}

function similarityColor(sim: number): string {
  if (sim >= 0.97) return "bg-red-100 text-red-800";
  if (sim >= 0.94) return "bg-orange-100 text-orange-800";
  return "bg-yellow-100 text-yellow-800";
}

function PairRow({
  pair,
  studentNames,
  questionPrompts,
}: {
  pair: SimilarPairItem;
  studentNames: Record<string, string>;
  questionPrompts: Record<string, string>;
}) {
  const nameA = studentNames[pair.student_a] ?? pair.student_a.slice(0, 8);
  const nameB = studentNames[pair.student_b] ?? pair.student_b.slice(0, 8);
  const qPrompt = questionPrompts[pair.question_id];
  const pct = Math.round(pair.similarity * 100);

  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 pr-4 text-sm text-ink font-medium">{nameA}</td>
      <td className="py-2 pr-4 text-sm text-ink font-medium">{nameB}</td>
      <td
        className="py-2 pr-4 text-xs text-muted max-w-xs truncate"
        title={qPrompt}
      >
        {qPrompt ?? pair.question_id.slice(0, 8)}
      </td>
      <td className="py-2">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${similarityColor(pair.similarity)}`}
        >
          {pct}%
        </span>
      </td>
    </tr>
  );
}

export default function CollusionView({
  examId,
  studentNames,
  questionPrompts,
}: Props) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">(
    "idle",
  );
  const [result, setResult] = useState<CollusionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threshold, setThreshold] = useState(0.92);

  async function handleRun() {
    setState("loading");
    setError(null);
    try {
      const data = await getCollusionReport(examId, threshold);
      setResult(data);
      setState("done");
    } catch (e: unknown) {
      setError(
        e instanceof Error ? e.message : "Failed to run collusion detection.",
      );
      setState("error");
    }
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">
            Similarity threshold
          </label>
          <input
            type="number"
            min={0.5}
            max={1.0}
            step={0.01}
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="w-24 rounded border border-border px-2 py-1 text-sm"
          />
        </div>
        <button
          onClick={handleRun}
          disabled={state === "loading"}
          className="rounded bg-primary px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
        >
          {state === "loading" ? "Analysing…" : "Run collusion detection"}
        </button>
      </div>

      {state === "error" && <p className="text-sm text-red-600">{error}</p>}

      {state === "done" && result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted">
              Provider:{" "}
              <span className="font-medium text-ink capitalize">
                {result.provider}
              </span>
            </span>
            <span className="text-sm text-muted">
              Threshold: {Math.round(result.threshold_used * 100)}%
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                result.pair_count > 0
                  ? "bg-red-100 text-red-800"
                  : "bg-green-100 text-green-800"
              }`}
            >
              {result.pair_count} flagged pair
              {result.pair_count !== 1 ? "s" : ""}
            </span>
          </div>

          {/* Disclaimer */}
          <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <span className="font-semibold">⚠ AI-generated analysis</span> —
            high similarity may reflect common knowledge or shared resources.
            This is evidence for human review, not proof of misconduct.
          </div>

          {/* Flagged pairs table */}
          {result.pair_count > 0 ? (
            <div className="overflow-x-auto rounded border border-border">
              <table className="w-full text-left">
                <thead className="bg-surface-alt text-xs font-semibold text-muted uppercase">
                  <tr>
                    <th className="py-2 pr-4 pl-3">Student A</th>
                    <th className="py-2 pr-4">Student B</th>
                    <th className="py-2 pr-4">Question</th>
                    <th className="py-2 pr-3">Similarity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {result.flagged_pairs.map((pair, i) => (
                    <PairRow
                      key={i}
                      pair={pair}
                      studentNames={studentNames}
                      questionPrompts={questionPrompts}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-muted">
              No suspiciously similar answer pairs found above the{" "}
              {Math.round(result.threshold_used * 100)}% threshold.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
