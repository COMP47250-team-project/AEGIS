// frontend/src/pages/ProfessorSession.tsx
// AEGIS-58: per-session live view.  AEGIS-59: live student card grid with
// risk scores, telemetry counts, sorting, flag acknowledgement, and a
// read-only per-student event timeline.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import apiClient, { getAccessToken } from "../api/client";
import {
  isFlagged,
  sortStudents,
  studentRisk,
  type LiveStudent,
  type SortMode,
} from "../components/professor/liveStudents";
import TimelineModal from "../components/professor/TimelineModal";

interface ProfessorPayload {
  exam_id: string;
  scoring_preset?: string;
  students: LiveStudent[];
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
// Page
// ---------------------------------------------------------------------------

const ProfessorSession: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [students, setStudents] = useState<LiveStudent[]>([]);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [scoringPreset, setScoringPreset] = useState<string | null>(null);
  // One-shot success toast passed from the create-exam redirect (AEGIS-62).
  const [toast, setToast] = useState<string | null>(
    (location.state as { toast?: string } | null)?.toast ?? null,
  );
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
    // encodeURIComponent: sessionId/token come from the route/session — never
    // interpolate user-controlled values into a request URL unencoded (SSRF).
    const ws = new WebSocket(
      `${wsBase}/ws/professor/${encodeURIComponent(sessionId)}?token=${encodeURIComponent(token)}`
    );
    wsRef.current = ws;

    ws.onopen = () => setWsStatus("connected");
    ws.onerror = () => setWsStatus("error");
    ws.onclose = () => setWsStatus("idle");
    ws.onmessage = (evt) => {
      try {
        const payload: ProfessorPayload = JSON.parse(evt.data as string);
        setStudents(payload.students ?? []);
        if (payload.scoring_preset) setScoringPreset(payload.scoring_preset);
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
      await apiClient.post(`/exams/${encodeURIComponent(sessionId)}/close`);
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
          {scoringPreset && (
            <span
              className="ml-1 text-xs font-medium px-2 py-0.5 rounded-full bg-surface-soft text-body border border-hairline capitalize"
              title="Scoring sensitivity preset for this exam"
            >
              {scoringPreset}
            </span>
          )}
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
        {toast && (
          <div
            role="status"
            className="mb-4 flex items-center justify-between gap-3 px-3 py-2 rounded bg-accent-green-soft text-accent-green text-sm"
          >
            <span>{toast}</span>
            <button
              onClick={() => setToast(null)}
              className="text-xs text-accent-green/70 hover:text-accent-green"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        )}

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
                    <div
                      className="h-2 bg-surface-soft rounded-full overflow-hidden"
                      role="progressbar"
                      aria-label="Risk score"
                      aria-valuenow={Math.round(risk * 100)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuetext={`Risk ${Math.round(risk * 100)} percent`}
                    >
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
