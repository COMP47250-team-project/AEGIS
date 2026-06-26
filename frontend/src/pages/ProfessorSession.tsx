// frontend/src/pages/ProfessorSession.tsx
// AEGIS-58: per-session live view.  AEGIS-59: live student card grid with
// risk scores, telemetry counts, sorting, flag acknowledgement, and a
// read-only per-student event timeline.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import apiClient, { getAccessToken } from "../api/client";
import {
  isFlagged,
  sortStudents,
  studentRisk,
  type LiveStudent,
  type SortMode,
} from "../components/professor/liveStudents";

interface ProfessorPayload {
  exam_id: string;
  students: LiveStudent[];
}

interface TimelineItem {
  event_type: string;
  payload: Record<string, unknown>;
  occurred_at: string;
}

type WsStatus = "idle" | "connecting" | "connected" | "error";

function riskColor(score: number): string {
  if (score >= 0.7) return "bg-accent-red";
  if (score >= 0.4) return "bg-primary";
  return "bg-accent-green";
}

function riskLabel(score: number): string {
  if (score >= 0.7) return "High risk";
  if (score >= 0.4) return "Moderate";
  return "Low risk";
}

function fmtTime(d: Date): string {
  return d.toLocaleTimeString(undefined, { hour12: false });
}

// ---------------------------------------------------------------------------
// Read-only event timeline (opens when a card is clicked)
// ---------------------------------------------------------------------------

const TimelineModal: React.FC<{
  sessionId: string;
  student: LiveStudent;
  onClose: () => void;
}> = ({ sessionId, student, onClose }) => {
  const [events, setEvents] = useState<TimelineItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    apiClient
      .get<{ items: TimelineItem[] }>(
        `/sessions/${sessionId}/students/${student.student_id}/events`
      )
      .then(({ data }) => setEvents(data.items))
      .catch(() => setError(true));
  }, [sessionId, student.student_id]);

  // Close on Escape (keyboard-accessible — no click-outside handler needed).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

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
            <p className="text-xs text-mute">Event timeline (read-only)</p>
          </div>
          <button
            onClick={onClose}
            className="text-mute hover:text-ink text-lg leading-none px-1"
            aria-label="Close"
          >
            ✕
          </button>
        </header>

        <div className="overflow-y-auto p-4">
          {error ? (
            <p className="text-accent-red text-sm">Could not load events.</p>
          ) : events === null ? (
            <p className="text-mute text-sm">Loading…</p>
          ) : events.length === 0 ? (
            <p className="text-mute text-sm">No telemetry events yet.</p>
          ) : (
            <ul className="space-y-2">
              {events.map((e, i) => (
                <li
                  key={i}
                  className="flex items-start gap-3 text-xs border-l-2 border-hairline pl-3"
                >
                  <span className="text-mute whitespace-nowrap">
                    {fmtTime(new Date(e.occurred_at))}
                  </span>
                  <span className="font-semibold text-ink">{e.event_type}</span>
                  <span className="text-mute truncate">
                    {JSON.stringify(e.payload)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const ProfessorSession: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [students, setStudents] = useState<LiveStudent[]>([]);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>("idle");
  const [ending, setEnding] = useState(false);
  const [sortMode, setSortMode] = useState<SortMode>("risk");
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<LiveStudent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    const token = getAccessToken();
    if (!token) return;

    setWsStatus("connecting");
    const wsBase = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(
      /^http/,
      "ws"
    );
    const ws = new WebSocket(`${wsBase}/ws/professor/${sessionId}?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus("connected");
    ws.onerror = () => setWsStatus("error");
    ws.onclose = () => setWsStatus("idle");
    ws.onmessage = (evt) => {
      try {
        const payload: ProfessorPayload = JSON.parse(evt.data as string);
        setStudents(payload.students ?? []);
        setUpdatedAt(new Date());
      } catch {
        /* ignore malformed frames */
      }
    };

    return () => ws.close();
  }, [sessionId]);

  const handleEndExam = useCallback(async () => {
    if (!sessionId) return;
    setEnding(true);
    try {
      await apiClient.post(`/exams/${sessionId}/close`);
      navigate("/professor/dashboard");
    } catch {
      setEnding(false);
    }
  }, [sessionId, navigate]);

  const acknowledge = useCallback((studentId: string) => {
    setAcknowledged((prev) => new Set(prev).add(studentId));
  }, []);

  const sorted = sortStudents(students, sortMode);

  return (
    <div className="min-h-screen bg-canvas">
      {/* Top bar */}
      <header className="bg-surface-card border-b border-hairline px-4 sm:px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <button
            onClick={() => navigate("/professor/dashboard")}
            className="text-xs text-mute hover:text-ink transition-colors"
          >
            ← Dashboard
          </button>
          <span className="text-hairline mx-1">|</span>
          <span className="text-sm font-semibold text-ink truncate">Live Session</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline text-sm text-body">{user?.name}</span>
          <button
            onClick={logout}
            className="text-xs text-mute hover:text-ink transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6">
        {/* Status + controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <span
            className={`flex items-center gap-1.5 text-xs font-medium ${
              wsStatus === "connected"
                ? "text-accent-green"
                : wsStatus === "error"
                ? "text-accent-red"
                : "text-mute"
            }`}
          >
            <span
              className={`inline-block w-2 h-2 rounded-full ${
                wsStatus === "connected"
                  ? "bg-accent-green animate-pulse"
                  : wsStatus === "error"
                  ? "bg-accent-red"
                  : "bg-hairline"
              }`}
            />
            {wsStatus === "connected"
              ? `Live${updatedAt ? ` — updated ${fmtTime(updatedAt)}` : ""}`
              : wsStatus === "connecting"
              ? "Connecting…"
              : wsStatus === "error"
              ? "Connection failed"
              : "Disconnected"}
          </span>

          <div className="flex items-center gap-2">
            <label htmlFor="sort" className="text-xs text-mute">
              Sort
            </label>
            <select
              id="sort"
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value as SortMode)}
              className="border border-hairline rounded px-2 py-1 text-xs text-ink bg-surface-card focus:outline-none focus:ring-1 focus:ring-surface-dark"
            >
              <option value="risk">Risk (high → low)</option>
              <option value="name">Name (A → Z)</option>
              <option value="flag">Flagged first</option>
            </select>
            <button
              onClick={handleEndExam}
              disabled={ending}
              className="px-3 py-1.5 bg-accent-red text-on-dark text-xs font-semibold rounded disabled:opacity-60 transition-colors"
            >
              {ending ? "Ending…" : "End exam"}
            </button>
          </div>
        </div>

        {/* Student cards */}
        {sorted.length === 0 ? (
          <p className="text-mute text-sm text-center py-12">
            {wsStatus === "connected"
              ? "Waiting for student telemetry…"
              : "Connecting to the live session…"}
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {sorted.map((s) => {
              const risk = studentRisk(s);
              const flagged = isFlagged(s);
              const showBorder = flagged && !acknowledged.has(s.student_id);
              return (
                <div
                  key={s.student_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelected(s)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected(s);
                    }
                  }}
                  className={`bg-surface-card rounded-md p-4 cursor-pointer transition-colors hover:border-surface-dark focus:outline-none focus:ring-2 focus:ring-accent-blue/30 ${
                    showBorder
                      ? "border-2 border-accent-red"
                      : "border border-hairline"
                  }`}
                >
                  <div className="flex items-start justify-between mb-3 gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-ink truncate flex items-center gap-1">
                        {flagged && <span title="Flagged">⚠️</span>}
                        {s.name ?? s.student_id}
                      </p>
                      <p className="text-xs text-mute truncate">{s.student_id}</p>
                    </div>
                    <span
                      className={`flex-shrink-0 text-xs font-semibold px-2 py-0.5 rounded ${
                        risk >= 0.7
                          ? "bg-accent-red-soft text-accent-red border border-accent-red/20"
                          : risk >= 0.4
                          ? "bg-primary/10 text-primary-active border border-primary/30"
                          : "bg-accent-green-soft text-accent-green border border-accent-green/20"
                      }`}
                    >
                      {riskLabel(risk)}
                    </span>
                  </div>

                  {/* Risk bar */}
                  <div className="mb-3">
                    <div className="h-2 bg-surface-soft rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${riskColor(
                          risk
                        )}`}
                        style={{ width: `${Math.round(risk * 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-mute mt-1 text-right">
                      Risk: {Math.round(risk * 100)}%
                    </p>
                  </div>

                  {/* Telemetry counts + last event */}
                  <div className="flex items-center justify-between text-xs text-body">
                    <span>
                      <span className="text-mute">Tab blurs</span>{" "}
                      <span className="font-semibold text-ink">{s.tab_blurs}</span>
                    </span>
                    <span>
                      <span className="text-mute">Pastes</span>{" "}
                      <span className="font-semibold text-ink">{s.pastes}</span>
                    </span>
                  </div>
                  <p className="text-xs text-mute mt-2 truncate">
                    Last: {s.last_event ?? "—"}
                    {updatedAt ? ` · ${fmtTime(updatedAt)}` : ""}
                  </p>

                  {showBorder && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        acknowledge(s.student_id);
                      }}
                      className="mt-3 w-full py-1.5 bg-accent-red-soft text-accent-red text-xs font-semibold rounded border border-accent-red/20"
                    >
                      Acknowledge flag
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selected && sessionId && (
        <TimelineModal
          sessionId={sessionId}
          student={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
};

export default ProfessorSession;
