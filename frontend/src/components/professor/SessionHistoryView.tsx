// AEGIS-60/AEGIS-61: Completed exam history with per-student score cards and CSV export.
// Styled with AEGIS design tokens (DESIGN.md / PostHog-derived system).
import React, { useCallback, useEffect, useState } from "react";
import apiClient from "../../api/client";

interface SessionSummary {
  id: string;
  quiz_title: string | null;
  course_id: string;
  scheduled_start: string;
  state: string;
  student_count: number;
  flagged_count: number;
}

interface StudentScore {
  student_id: string;
  student_name: string;
  integrity_score: number;
  tab_switch_score: number;
  paste_score: number;
  keystroke_score: number;
  focus_loss_score: number;
  answer_timing_score: number;
  copy_sequence_score: number;
  flagged: boolean;
  has_telemetry: boolean;
}

// Risk badge uses semantic AEGIS accent tokens:
//   high  → accent-red   (warning/caution)
//   mod   → primary      (brand amber — "pay attention")
//   low   → accent-green (positive/safe)
function riskBadge(score: number): { label: string; cls: string } {
  if (score >= 0.7)
    return {
      label: "High risk",
      cls: "bg-accent-red-soft text-accent-red border border-accent-red/20",
    };
  if (score >= 0.4)
    return {
      label: "Moderate",
      cls: "bg-primary/10 text-primary-active border border-primary/30",
    };
  return {
    label: "Low risk",
    cls: "bg-accent-green-soft text-accent-green border border-accent-green/20",
  };
}

const ScoreBar: React.FC<{ value: number; label: string }> = ({ value, label }) => {
  const pct = Math.round(value * 100);
  const barColor =
    pct >= 70 ? "bg-accent-red" : pct >= 40 ? "bg-primary" : "bg-accent-green";
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-mute w-28 shrink-0">{label}</span>
      <div
        className="flex-1 h-1.5 bg-surface-soft rounded-full overflow-hidden"
        role="progressbar"
        aria-label={`${label} score`}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={`${pct} percent`}
      >
        <div className={`h-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-body w-8 text-right">{pct}%</span>
    </div>
  );
};

const StudentScoreCard: React.FC<{
  score: StudentScore;
  onViewTimeline: (studentId: string, name: string) => void;
}> = ({ score, onViewTimeline }) => {
  const { label, cls } = riskBadge(score.integrity_score);
  const overallPct = Math.round(score.integrity_score * 100);

  if (!score.has_telemetry) {
    return (
      <div className="rounded-md border border-hairline bg-surface-card p-4">
        <div className="flex items-start justify-between mb-1">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink truncate">
              {score.student_name}
            </p>
            <p className="text-xs text-ash mt-0.5 truncate">{score.student_id}</p>
          </div>
          <div className="flex items-center gap-2 ml-2 shrink-0">
            <span className="text-lg font-bold text-ink">0%</span>
            <span className="text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap bg-surface-soft text-mute border border-hairline">
              Absent
            </span>
          </div>
        </div>
        <p className="text-xs text-mute mt-2">No telemetry captured — student never joined the exam.</p>
      </div>
    );
  }

  return (
    <div
      className={`rounded-md border p-4 ${
        score.flagged
          ? "border-accent-red/40 bg-accent-red-soft/30"
          : "border-hairline bg-surface-card"
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink flex items-center gap-1 truncate">
            {score.flagged && <span title="Flagged student">⚠️</span>}
            {score.student_name}
          </p>
          <p className="text-xs text-ash mt-0.5 truncate">{score.student_id}</p>
        </div>
        <div className="flex items-center gap-2 ml-2 shrink-0">
          <span className="text-lg font-bold text-ink">{overallPct}%</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${cls}`}>
            {label}
          </span>
        </div>
      </div>

      <div className="space-y-1 mb-3">
        <ScoreBar value={score.tab_switch_score} label="Tab Switch" />
        <ScoreBar value={score.paste_score} label="Paste" />
        <ScoreBar value={score.keystroke_score} label="Keystroke" />
        <ScoreBar value={score.focus_loss_score} label="Focus Loss" />
        <ScoreBar value={score.answer_timing_score} label="Answer Timing" />
        <ScoreBar value={score.copy_sequence_score} label="Copy Sequence" />
      </div>

      <button
        onClick={() => onViewTimeline(score.student_id, score.student_name)}
        className="w-full py-1.5 text-xs font-semibold text-accent-blue border border-accent-blue/20 rounded-md hover:bg-accent-blue-soft transition-colors"
      >
        View event timeline →
      </button>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const SessionHistoryView: React.FC<{
  onViewTimeline: (sessionId: string, studentId: string, studentName: string) => void;
}> = ({ onViewTimeline }) => {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [scores, setScores] = useState<Record<string, StudentScore[]>>({});
  const [loadingScores, setLoadingScores] = useState<Record<string, boolean>>({});

  useEffect(() => {
    apiClient
      .get<{ items: SessionSummary[] }>("/sessions?status=completed&page_size=20")
      .then(({ data }) => {
        setSessions(data.items);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });
  }, []);

  const toggleSession = useCallback(
    (id: string) => {
      if (expanded === id) {
        setExpanded(null);
        return;
      }
      setExpanded(id);
      if (!scores[id]) {
        setLoadingScores((prev) => ({ ...prev, [id]: true }));
        apiClient
          .get<StudentScore[]>(`/sessions/${encodeURIComponent(id)}/scores`)
          .then(({ data }) => {
            setScores((prev) => ({ ...prev, [id]: data }));
          })
          .catch(() => {
            setScores((prev) => ({ ...prev, [id]: [] }));
          })
          .finally(() => {
            setLoadingScores((prev) => ({ ...prev, [id]: false }));
          });
      }
    },
    [expanded, scores]
  );

  const handleDownloadCSV = useCallback(
    async (e: React.MouseEvent, sessionId: string, quizTitle: string | null) => {
      e.stopPropagation();
      try {
        const response = await apiClient.get(
          `/exams/${encodeURIComponent(sessionId)}/export`,
          { responseType: "blob" }
        );
        const url = URL.createObjectURL(response.data as Blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `aegis_${quizTitle ?? "export"}_scores.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch {
        alert("Export failed. Make sure the exam is closed.");
      }
    },
    []
  );

  if (loading)
    return (
      <div className="flex justify-center py-12">
        <div className="w-6 h-6 border-2 border-hairline border-t-accent-blue rounded-full animate-spin" />
      </div>
    );

  if (error)
    return (
      <p className="text-center text-accent-red py-12 text-sm">
        Could not load completed sessions.
      </p>
    );

  if (sessions.length === 0)
    return (
      <div className="text-center py-16">
        <div className="text-4xl mb-3">📋</div>
        <p className="text-mute text-sm">No completed exams yet.</p>
        <p className="text-ash text-xs mt-1">Scores appear here after you close an exam.</p>
      </div>
    );

  return (
    <div className="space-y-3">
      {sessions.map((s) => {
        const isOpen = expanded === s.id;
        const sessionScores = scores[s.id] ?? [];
        const isLoadingScores = loadingScores[s.id] ?? false;
        const start = new Date(s.scheduled_start).toLocaleString(undefined, {
          dateStyle: "medium",
          timeStyle: "short",
        });

        return (
          <div
            key={s.id}
            className="border border-hairline rounded-md overflow-hidden"
          >
            {/* Session header — clickable accordion trigger */}
            <button
              onClick={() => toggleSession(s.id)}
              className="w-full flex items-center justify-between px-4 py-3 bg-surface-card hover:bg-surface-soft transition-colors text-left"
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink truncate">
                  {s.quiz_title ?? "Untitled Exam"}{" "}
                  <span className="font-normal text-ash">· {s.course_id}</span>
                </p>
                <p className="text-xs text-mute mt-0.5">
                  {start} · {s.student_count} students
                  {s.flagged_count > 0 && (
                    <span className="ml-2 text-accent-red font-medium">
                      ⚠️ {s.flagged_count} flagged
                    </span>
                  )}
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0 ml-4">
                {/* CSV download — stopPropagation so it doesn't toggle the accordion */}
                <button
                  onClick={(e) => handleDownloadCSV(e, s.id, s.quiz_title)}
                  className="text-xs px-2 py-0.5 rounded-md border border-accent-blue/20 text-accent-blue hover:bg-accent-blue-soft transition-colors"
                  title="Download CSV report"
                >
                  ⬇ CSV
                </button>
                <span className="text-xs px-2 py-0.5 rounded-full bg-surface-soft text-mute">
                  Closed
                </span>
                <span
                  className={`text-mute transition-transform ${isOpen ? "rotate-180" : ""}`}
                >
                  ▾
                </span>
              </div>
            </button>

            {/* Expanded student score grid */}
            {isOpen && (
              <div className="border-t border-hairline bg-surface-soft px-4 py-4">
                {isLoadingScores ? (
                  <div className="flex justify-center py-4">
                    <div className="w-5 h-5 border-2 border-hairline border-t-accent-blue rounded-full animate-spin" />
                  </div>
                ) : sessionScores.length === 0 ? (
                  <p className="text-xs text-mute text-center py-4">
                    No integrity scores computed yet for this session.
                  </p>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {sessionScores.map((sc) => (
                      <StudentScoreCard
                        key={sc.student_id}
                        score={sc}
                        onViewTimeline={(studentId, name) =>
                          onViewTimeline(s.id, studentId, name)
                        }
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default SessionHistoryView;
