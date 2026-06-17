import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import ExamList, { type ExamRow } from "../components/professor/ExamList";
import QuizBuilder from "../components/professor/QuizBuilder";
import ExamScheduler from "../components/professor/ExamScheduler";
import apiClient, { getAccessToken } from "../api/client";

type Tab = "exams" | "build" | "schedule" | "integrity";

const TABS: { id: Tab; label: string }[] = [
  { id: "exams", label: "My Exams" },
  { id: "build", label: "Build Quiz" },
  { id: "schedule", label: "Schedule Exam" },
  { id: "integrity", label: "Live Integrity" },
];

// ---------------------------------------------------------------------------
// Types for the professor WebSocket payload
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// IntegrityView component
// ---------------------------------------------------------------------------

const IntegrityView: React.FC = () => {
  const [exams, setExams] = useState<ExamRow[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<string>("");
  const [students, setStudents] = useState<StudentRisk[]>([]);
  const [wsStatus, setWsStatus] = useState<"idle" | "connecting" | "connected" | "error">("idle");
  const wsRef = useRef<WebSocket | null>(null);

  // Load open exams on mount
  useEffect(() => {
    apiClient
      .get<ExamRow[]>("/exams")
      .then(({ data }) => {
        const open = data.filter((e) => e.state === "open");
        setExams(open);
        if (open.length > 0) setSelectedExamId(open[0].id);
      })
      .catch(() => {/* ignore */});
  }, []);

  // Connect/disconnect WebSocket when selected exam changes
  useEffect(() => {
    if (!selectedExamId) return;

    const token = getAccessToken();
    if (!token) return;

    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setWsStatus("connecting");
    setStudents([]);

    const wsBase = (import.meta.env.VITE_API_URL ?? "http://localhost:8000")
      .replace(/^http/, "ws");
    const url = `${wsBase}/ws/professor/${selectedExamId}?token=${token}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus("connected");
    ws.onerror = () => setWsStatus("error");
    ws.onclose = () => {
      setWsStatus("idle");
      wsRef.current = null;
    };

    ws.onmessage = (evt) => {
      try {
        const payload: ProfessorPayload = JSON.parse(evt.data as string);
        setStudents(payload.students ?? []);
      } catch {
        /* ignore malformed frames */
      }
    };

    return () => {
      ws.close();
    };
  }, [selectedExamId]);

  if (exams.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-mute text-sm">No open exams right now.</p>
        <p className="text-ash text-xs mt-1">
          Open an exam from the "My Exams" tab to monitor live integrity scores.
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Exam selector + status */}
      <div className="flex items-center gap-3 mb-6">
        <label className="text-sm font-medium text-body" htmlFor="exam-select">
          Monitoring:
        </label>
        <select
          id="exam-select"
          value={selectedExamId}
          onChange={(e) => setSelectedExamId(e.target.value)}
          className="border border-hairline rounded px-2 py-1.5 text-sm text-ink bg-surface-card focus:outline-none focus:ring-1 focus:ring-surface-dark"
        >
          {exams.map((e) => (
            <option key={e.id} value={e.id}>
              {e.quiz_title ?? e.course_id} — {e.course_id}
            </option>
          ))}
        </select>

        <span
          className={`ml-auto flex items-center gap-1.5 text-xs font-medium ${
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
      </div>

      {/* Student cards */}
      {students.length === 0 ? (
        <p className="text-mute text-sm text-center py-8">
          {wsStatus === "connected"
            ? "Waiting for student telemetry…"
            : "Connect to an open exam to see live scores."}
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {students.map((s) => (
            <div
              key={s.student_id}
              className="bg-surface-card border border-hairline rounded-md p-4"
            >
              {/* Name + risk label */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-sm font-semibold text-ink">
                    {s.name ?? s.email ?? s.student_id.slice(0, 8)}
                  </p>
                  {s.name && (
                    <p className="text-xs text-mute">{s.email}</p>
                  )}
                </div>
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded ${
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

              {/* Risk bar */}
              <div className="mb-3">
                <div className="h-2 bg-surface-soft rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${riskColor(s.integrity_score)}`}
                    style={{ width: `${Math.round((s.integrity_score ?? 0) * 100)}%` }}
                  />
                </div>
                <p className="text-xs text-mute mt-1 text-right">
                  Risk: {pct(s.integrity_score)}
                </p>
              </div>

              {/* Signal breakdown */}
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
  );
};

// ---------------------------------------------------------------------------
// ProfessorConsole page
// ---------------------------------------------------------------------------

const ProfessorConsole: React.FC = () => {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("exams");
  const [pendingQuizId, setPendingQuizId] = useState<string | undefined>();
  const [examListKey, setExamListKey] = useState(0);

  function handleQuizCreated(quizId: string) {
    setPendingQuizId(quizId);
    setActiveTab("schedule");
  }

  function handleExamScheduled() {
    setExamListKey((k) => k + 1);
    setActiveTab("exams");
  }

  return (
    <div className="min-h-screen bg-canvas">
      {/* Top bar */}
      <header className="bg-surface-card border-b border-hairline px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded bg-surface-dark">
            <svg
              className="w-4 h-4 text-on-dark"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
          </span>
          <span className="text-sm font-semibold text-ink">AEGIS</span>
          <span className="text-hairline mx-1">|</span>
          <span className="text-sm text-mute">Professor Console</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-body">{user?.name}</span>
          <button
            onClick={logout}
            className="text-xs text-mute hover:text-ink transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Tab nav */}
        <nav className="flex border-b border-hairline mb-6" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                activeTab === tab.id
                  ? "border-ink text-ink"
                  : "border-transparent text-mute hover:text-body"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab panels */}
        {activeTab === "exams" && (
          <section aria-label="My Exams">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-ink">Exams</h2>
              <button
                onClick={() => setActiveTab("build")}
                className="px-3 py-1.5 bg-primary text-ink text-xs font-semibold rounded hover:bg-primary-pressed transition-colors"
              >
                + New quiz
              </button>
            </div>
            <ExamList key={examListKey} />
          </section>
        )}

        {activeTab === "build" && (
          <section aria-label="Build Quiz">
            <h2 className="text-base font-semibold text-ink mb-4">
              Build a Quiz
            </h2>
            <QuizBuilder onCreated={handleQuizCreated} />
          </section>
        )}

        {activeTab === "schedule" && (
          <section aria-label="Schedule Exam">
            <h2 className="text-base font-semibold text-ink mb-4">
              Schedule an Exam
            </h2>
            <ExamScheduler
              preselectedQuizId={pendingQuizId}
              onScheduled={handleExamScheduled}
            />
          </section>
        )}

        {activeTab === "integrity" && (
          <section aria-label="Live Integrity Monitor">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-ink">
                Live Integrity Monitor
              </h2>
              <p className="text-xs text-mute">
                Scores update every 5 seconds from live telemetry.
              </p>
            </div>
            <IntegrityView />
          </section>
        )}
      </div>
    </div>
  );
};

export default ProfessorConsole;
