import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import ExamList from "../components/professor/ExamList";
import QuizBuilder from "../components/professor/QuizBuilder";
import ExamScheduler from "../components/professor/ExamScheduler";
import SessionDashboard from "../components/professor/SessionDashboard";
import SessionHistoryView from "../components/professor/SessionHistoryView";
import TimelineModal from "../components/professor/TimelineModal";
import type { LiveStudent } from "../components/professor/liveStudents";

type Tab = "dashboard" | "exams" | "build" | "schedule" | "history";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "exams", label: "My Exams" },
  { id: "build", label: "Build Quiz" },
  { id: "schedule", label: "Schedule Exam" },
  { id: "history", label: "History" },
];

const ProfessorConsole: React.FC = () => {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [pendingQuizId, setPendingQuizId] = useState<string | undefined>();
  const [examListKey, setExamListKey] = useState(0);
  const [historyTimeline, setHistoryTimeline] = useState<{
    sessionId: string;
    studentId: string;
    studentName: string;
  } | null>(null);

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
      <header className="bg-surface-card border-b border-hairline px-4 sm:px-6 py-3 flex items-center justify-between">
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
          <span className="hidden sm:inline text-sm text-mute">Professor Console</span>
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

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        {/* Tab nav */}
        <nav className="flex border-b border-hairline mb-6 overflow-x-auto" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px whitespace-nowrap transition-colors ${
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
        {activeTab === "dashboard" && (
          <section aria-label="Active Sessions">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-ink">Active Sessions</h2>
              <p className="hidden sm:block text-xs text-mute">
                Auto-refreshes every 30s · click a card to monitor live
              </p>
            </div>
            <SessionDashboard />
          </section>
        )}

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
            <h2 className="text-base font-semibold text-ink mb-4">Build a Quiz</h2>
            <QuizBuilder onCreated={handleQuizCreated} />
          </section>
        )}

        {activeTab === "schedule" && (
          <section aria-label="Schedule Exam">
            <h2 className="text-base font-semibold text-ink mb-4">Schedule an Exam</h2>
            <ExamScheduler
              preselectedQuizId={pendingQuizId}
              onScheduled={handleExamScheduled}
            />
          </section>
        )}

        {activeTab === "history" && (
          <section aria-label="Completed Exams">
            <h2 className="text-base font-semibold text-ink mb-4">Completed Exams</h2>
            <SessionHistoryView
              onViewTimeline={(sessionId, studentId, studentName) =>
                setHistoryTimeline({ sessionId, studentId, studentName })
              }
            />
            {historyTimeline && (
              <TimelineModal
                sessionId={historyTimeline.sessionId}
                student={
                  {
                    student_id: historyTimeline.studentId,
                    name: historyTimeline.studentName,
                    email: null,
                    risk_score: null,
                    tab_blurs: 0,
                    pastes: 0,
                    last_event: null,
                    active: false,
                  } satisfies LiveStudent
                }
                onClose={() => setHistoryTimeline(null)}
              />
            )}
          </section>
        )}
      </div>
    </div>
  );
};

export default ProfessorConsole;
