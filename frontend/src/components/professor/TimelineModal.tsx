// Reusable per-student event timeline modal with signal score breakdown.
// Used by ProfessorSession (live view) and ProfessorConsole (history tab).

import React, { useCallback, useEffect, useState } from "react";
import apiClient from "../../api/client";
import type { LiveStudent } from "./liveStudents";

interface TimelineItem {
  event_type: string;
  payload: Record<string, unknown>;
  occurred_at: string;
}

interface ScoreData {
  available: boolean;
  integrity_score?: number;
  components?: Record<string, number>;
}

const MAX_EVENTS = 1000;
const PAGE_SIZE = 200;

function fmtTime(d: Date): string {
  return d.toLocaleTimeString(undefined, { hour12: false });
}

function eventIcon(type: string): string {
  const map: Record<string, string> = {
    tab_hidden: "👁️",
    tab_shown: "👁️",
    focus_lost: "🔓",
    focus_gained: "🔒",
    paste: "📋",
    key_interval: "⌨️",
    first_keystroke: "⌨️",
    window_resized: "↔️",
    question_time: "⏱️",
  };
  return map[type] ?? "•";
}

function formatEventLabel(type: string, payload: Record<string, unknown>): string {
  switch (type) {
    case "tab_hidden":
      return "Student left this tab";
    case "tab_shown":
      return "Student returned to tab";
    case "focus_lost":
      return "Window lost focus";
    case "focus_gained":
      return "Window regained focus";
    case "paste": {
      const chars = payload["char_count"] ?? payload["length"] ?? payload["size"] ?? "?";
      return `Pasted ~${chars} characters`;
    }
    case "key_interval": {
      const ms = payload["interval_ms"] ?? payload["iki_ms"] ?? "?";
      return `Keystroke interval: ${ms}ms`;
    }
    case "first_keystroke": {
      const ms = payload["ms_since_start"] ?? payload["elapsed_ms"] ?? "?";
      return `First keystroke after ${ms}ms`;
    }
    case "window_resized": {
      const w = payload["width"] ?? "?";
      const h = payload["height"] ?? "?";
      return `Resized to ${w}×${h}px`;
    }
    case "question_time": {
      const q = payload["question_index"] ?? payload["question_id"] ?? "?";
      const ms = payload["duration_ms"] ?? payload["time_ms"] ?? "?";
      const secs = typeof ms === "number" ? `${Math.round(ms / 1000)}s` : "?";
      return `Question ${q} — spent ${secs}`;
    }
    default:
      return Object.entries(payload)
        .slice(0, 2)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
  }
}

// ---------------------------------------------------------------------------
// ScoreBreakdown — bar chart of 6 signal components
// ---------------------------------------------------------------------------
const ScoreBreakdown: React.FC<{ sessionId: string; studentId: string }> = ({
  sessionId,
  studentId,
}) => {
  const [score, setScore] = useState<ScoreData | null>(null);

  useEffect(() => {
    apiClient
      .get<ScoreData>(
        `/sessions/${encodeURIComponent(sessionId)}/students/${encodeURIComponent(
          studentId
        )}/score`
      )
      .then(({ data }) => setScore(data))
      .catch(() => setScore({ available: false }));
  }, [sessionId, studentId]);

  if (!score)
    return <p className="text-xs text-mute px-4 py-2">Loading score…</p>;
  if (!score.available)
    return (
      <p className="text-xs text-mute px-4 py-2">
        Score not yet available (computed after exam closes)
      </p>
    );

  const overall = Math.round((score.integrity_score ?? 0) * 100);
  const overallColor =
    overall >= 70
      ? "text-accent-red"
      : overall >= 40
      ? "text-primary"
      : "text-accent-green";

  return (
    <div className="px-4 py-3 border-b border-hairline bg-surface-soft">
      <p className="text-xs font-semibold text-ink mb-2">
        Integrity Score:{" "}
        <span className={`text-sm font-bold ${overallColor}`}>{overall}%</span>
      </p>
      <div className="space-y-1.5">
        {Object.entries(score.components ?? {}).map(([label, value]) => {
          const pct = Math.round(value * 100);
          const barColor =
            pct >= 70
              ? "bg-accent-red"
              : pct >= 40
              ? "bg-primary"
              : "bg-accent-green";
          return (
            <div key={label} className="flex items-center gap-2">
              <span className="text-xs text-mute w-24 shrink-0">{label}</span>
              <div className="flex-1 h-2 bg-surface-card rounded-full overflow-hidden border border-hairline">
                <div
                  className={`h-full rounded-full ${barColor} transition-all duration-500`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="text-xs font-semibold text-ink w-8 text-right">
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// TimelineModal
// ---------------------------------------------------------------------------
const TimelineModal: React.FC<{
  sessionId: string;
  student: LiveStudent;
  onClose: () => void;
}> = ({ sessionId, student, onClose }) => {
  const [events, setEvents] = useState<TimelineItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState(false);

  // Fetch a single page and append to existing events.
  const fetchPage = useCallback(
    async (pageNum: number) => {
      const { data } = await apiClient.get<{
        items: TimelineItem[];
        total: number;
        page: number;
        page_size: number;
      }>(
        `/sessions/${encodeURIComponent(sessionId)}/students/${encodeURIComponent(
          student.student_id
        )}/events?page=${pageNum}&page_size=${PAGE_SIZE}`
      );
      return data;
    },
    [sessionId, student.student_id]
  );

  // Initial load — page 1
  useEffect(() => {
    setIsLoading(true);
    setEvents([]);
    setPage(1);
    setTotal(0);
    setError(false);

    fetchPage(1)
      .then((data) => {
        setEvents(data.items);
        setTotal(data.total);
      })
      .catch(() => setError(true))
      .finally(() => setIsLoading(false));
  }, [fetchPage]);

  // Load more — appends next page, respects MAX_EVENTS cap
  const handleLoadMore = useCallback(async () => {
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const data = await fetchPage(nextPage);
      setEvents((prev) => {
        const combined = [...prev, ...data.items];
        return combined.slice(0, MAX_EVENTS);
      });
      setPage(nextPage);
      setTotal(data.total);
    } catch {
      // Silent failure — existing events still visible
    } finally {
      setIsLoadingMore(false);
    }
  }, [fetchPage, page]);

  // Escape key closes modal
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Whether there are more events to load (and we haven't hit the cap yet)
  const canLoadMore =
    !isLoading &&
    !isLoadingMore &&
    events.length < total &&
    events.length < MAX_EVENTS;

  return (
    <div
      className="fixed inset-0 z-50 bg-ink/40 flex items-end sm:items-center justify-center p-0 sm:p-4"
      role="presentation"
    >
      <div
        className="bg-surface-card w-full sm:max-w-lg sm:rounded-md border border-hairline max-h-[85vh] flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        <header className="flex items-center justify-between px-4 py-3 border-b border-hairline">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink truncate">
              {student.name ?? student.student_id}
            </p>
            <p className="text-xs text-mute">
              Event timeline (read-only)
              {total > 0 && (
                <span className="ml-1">
                  — showing {events.length} of {total}
                  {total > MAX_EVENTS && ` (max ${MAX_EVENTS})`}
                </span>
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-mute hover:text-ink text-lg leading-none px-1"
            aria-label="Close"
          >
            ✕
          </button>
        </header>

        <ScoreBreakdown sessionId={sessionId} studentId={student.student_id} />

        <div className="overflow-y-auto p-4 flex-1">
          {error ? (
            <p className="text-accent-red text-sm">Could not load events.</p>
          ) : isLoading ? (
            <p className="text-mute text-sm">Loading…</p>
          ) : events.length === 0 ? (
            <p className="text-mute text-sm">No telemetry events yet.</p>
          ) : (
            <>
              <ul className="space-y-2">
                {events.map((e, i) => {
                  const label = formatEventLabel(e.event_type, e.payload);
                  const icon = eventIcon(e.event_type);
                  return (
                    <li
                      key={i}
                      className="flex items-start gap-3 text-xs border-l-2 border-hairline pl-3 py-1"
                    >
                      <span className="text-mute whitespace-nowrap w-14 shrink-0">
                        {fmtTime(new Date(e.occurred_at))}
                      </span>
                      <span className="text-base shrink-0 w-5">{icon}</span>
                      <div className="min-w-0">
                        <span className="font-semibold text-ink block">
                          {e.event_type}
                        </span>
                        <span className="text-mute">{label}</span>
                      </div>
                    </li>
                  );
                })}
              </ul>

              {canLoadMore && (
                <div className="mt-4 text-center">
                  <button
                    onClick={handleLoadMore}
                    className="px-4 py-2 bg-surface-soft text-ink text-xs font-bold rounded-md border border-hairline transition-colors"
                  >
                    Load more events
                  </button>
                </div>
              )}

              {isLoadingMore && (
                <p className="text-center text-xs text-mute mt-4">
                  Loading more…
                </p>
              )}

              {events.length >= MAX_EVENTS && (
                <p className="text-center text-xs text-mute mt-4">
                  Showing maximum {MAX_EVENTS} events.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default TimelineModal;
