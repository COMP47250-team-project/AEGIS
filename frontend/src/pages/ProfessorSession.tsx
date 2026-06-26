// frontend/src/pages/ProfessorSession.tsx
// AEGIS-58: per-session live integrity view, opened from a dashboard card.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import apiClient, { getAccessToken } from "../api/client";

interface StudentRisk {
  student_id: string;
  name: string | null;
  email: string | null;
  integrity_score: number | null;
  tab_switch_score: number | null;
  paste_score: number | null;
  keystroke_score: number | null;
}

interface ProfessorPayload {
  exam_id: string;
  students: StudentRisk[];
}

type WsStatus = "idle" | "connecting" | "connected" | "error";

function riskColor(score: number | null): string {
  if (score === null) return "bg-surface-soft";
  if (score >= 0.7) return "bg-accent-red";
  if (score >= 0.4) return "bg-primary";
  return "bg-accent-green";
}

function riskLabel(score: number | null): string {
  if (score === null) return "No data yet";
  if (score >= 0.7) return "High risk";
  if (score >= 0.4) return "Moderate";
  return "Low risk";
}

function pct(score: number | null): string {
  return score === null ? "—" : `${Math.round(score * 100)}%`;
}

const ProfessorSession: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [students, setStudents] = useState<StudentRisk[]>([]);
  const [wsStatus, setWsStatus] = useState<WsStatus>("idle");
  const [ending, setEnding] = useState(false);
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
        {/* Status + end-exam */}
        <div className="flex items-center justify-between gap-3 mb-6">
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
              ? "Live — updating every 5s"
              : wsStatus === "connecting"
              ? "Connecting…"
              : wsStatus === "error"
              ? "Connection failed"
              : "Disconnected"}
          </span>

          <button
            onClick={handleEndExam}
            disabled={ending}
            className="px-3 py-1.5 bg-accent-red text-on-dark text-xs font-semibold rounded disabled:opacity-60 transition-colors"
          >
            {ending ? "Ending…" : "End exam"}
          </button>
        </div>

        {/* Student risk cards */}
        {students.length === 0 ? (
          <p className="text-mute text-sm text-center py-12">
            {wsStatus === "connected"
              ? "Waiting for student telemetry…"
              : "Connecting to the live session…"}
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {students.map((s) => (
              <div
                key={s.student_id}
                className="bg-surface-card border border-hairline rounded-md p-4"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-ink truncate">
                      {s.name ?? s.email ?? s.student_id.slice(0, 8)}
                    </p>
                    {s.name && <p className="text-xs text-mute truncate">{s.email}</p>}
                  </div>
                  <span
                    className={`flex-shrink-0 text-xs font-semibold px-2 py-0.5 rounded ${
                      s.integrity_score === null
                        ? "bg-surface-soft text-mute"
                        : s.integrity_score >= 0.7
                        ? "bg-accent-red-soft text-accent-red border border-accent-red/20"
                        : s.integrity_score >= 0.4
                        ? "bg-primary/10 text-primary-active border border-primary/30"
                        : "bg-accent-green-soft text-accent-green border border-accent-green/20"
                    }`}
                  >
                    {riskLabel(s.integrity_score)}
                  </span>
                </div>

                <div className="mb-3">
                  <div className="h-2 bg-surface-soft rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${riskColor(
                        s.integrity_score
                      )}`}
                      style={{ width: `${Math.round((s.integrity_score ?? 0) * 100)}%` }}
                    />
                  </div>
                  <p className="text-xs text-mute mt-1 text-right">
                    Risk: {pct(s.integrity_score)}
                  </p>
                </div>

                <div className="grid grid-cols-3 gap-x-2 gap-y-1 text-xs text-body">
                  <span className="text-mute">Tab switch</span>
                  <span className="text-mute">Paste</span>
                  <span className="text-mute">Keystroke</span>
                  <span className="font-semibold text-ink">{pct(s.tab_switch_score)}</span>
                  <span className="font-semibold text-ink">{pct(s.paste_score)}</span>
                  <span className="font-semibold text-ink">{pct(s.keystroke_score)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProfessorSession;
