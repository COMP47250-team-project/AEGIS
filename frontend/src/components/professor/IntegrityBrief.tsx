// IntegrityBrief.tsx — 1A
// Renders the AI-generated integrity brief for one student.
// Used in ProfessorSession.tsx (live detail panel) and ExamGradeView.tsx (report).

import React, { useState } from "react";
import {
  type AIProvider,
  type IntegrityBriefResponse,
  getIntegrityBrief,
} from "../../api/ai";

interface Props {
  examId: string;
  studentId: string;
  studentName?: string | null;
}

const PROVIDER_BADGE: Record<AIProvider, string> = {
  azure: "Azure OpenAI",
  ollama: "Ollama (local)",
  stub: "Template (AI unavailable)",
  none: "Not available",
};

export default function IntegrityBrief({
  examId,
  studentId,
  studentName,
}: Props) {
  const [state, setState] = useState<"idle" | "loading" | "done" | "error">(
    "idle",
  );
  const [result, setResult] = useState<IntegrityBriefResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setState("loading");
    setError(null);
    try {
      const data = await getIntegrityBrief(examId, studentId);
      setResult(data);
      setState("done");
    } catch (e: unknown) {
      setError(
        e instanceof Error
          ? e.message
          : "Failed to generate brief. Please try again.",
      );
      setState("error");
    }
  }

  return (
    <div className="mt-4 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">
          AI Integrity Brief
          {studentName ? ` — ${studentName}` : ""}
        </h3>
        {state !== "loading" && (
          <button
            onClick={handleGenerate}
            className="rounded bg-primary px-3 py-1 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {state === "done" ? "Regenerate" : "Generate brief"}
          </button>
        )}
      </div>

      {state === "loading" && (
        <p className="mt-3 text-sm text-muted animate-pulse">
          Generating brief…
        </p>
      )}

      {state === "error" && (
        <p className="mt-3 text-sm text-red-600">{error}</p>
      )}

      {state === "done" && result && (
        <div className="mt-3 space-y-3">
          {/* Contributors */}
          {result.contributors.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {result.contributors.map((c) => (
                <span
                  key={c}
                  className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
                >
                  {c}
                </span>
              ))}
            </div>
          )}

          {/* Brief text */}
          <p className="text-sm leading-relaxed text-ink whitespace-pre-wrap">
            {result.brief}
          </p>

          {/* Provider + disclaimer */}
          <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <span className="font-semibold">⚠ AI-generated suggestion</span> —
            for human review only. Not a verdict and does not constitute
            evidence of academic misconduct.{" "}
            <span className="text-amber-600">
              Provider: {PROVIDER_BADGE[result.provider] ?? result.provider}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
