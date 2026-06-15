// frontend/src/pages/StudentDashboard.tsx
// AEGIS-37: Student dashboard — lists open, upcoming, and past exam sessions.
//
// Acceptance criteria covered:
//   ✅ Open exams show a live countdown timer (ticks every second)
//   ✅ Past exams show a Completed badge
//   ✅ Dashboard auto-refreshes exam list every 60 seconds
//   ✅ Exam card links directly to /exam/{session_id}
//
// Mock data strategy:
//   The function `fetchStudentSessions()` below currently returns hardcoded
//   mock data so the UI works end-to-end without a backend.
//   When the backend implements GET /student/sessions, replace the mock
//   with the real API call — see the TODO comment inside fetchStudentSessions.
//   Nothing else in this file needs to change.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import ExamCard from "../components/ExamCard";
// apiClient is imported but commented out — uncomment when swapping to real API
// import apiClient from "../api/client";

// ─── Types ────────────────────────────────────────────────────────────────────
// This type is exported so ExamCard.tsx can import it — both files share
// the same shape definition to keep things in sync.

export interface ExamSession {
  session_id: string;    // unique ID for this student's session — used in the URL /exam/{session_id}
  exam_title: string;    // display name shown on the card e.g. "Midterm Exam"
  course_name: string;   // course label shown above the title e.g. "CS101"
  status: "open" | "upcoming" | "completed";
  starts_at: string;     // ISO 8601 datetime string e.g. "2026-06-19T09:00:00Z"
  ends_at: string;       // ISO 8601 datetime string — countdown target for open exams
}

// ─── Mock API function ────────────────────────────────────────────────────────
// Returns a promise that resolves to an array of ExamSession objects.
// The slight artificial delay (300ms) simulates a real network call so the
// loading spinner is visible and the UI doesn't feel like it snaps instantly.
//
// HOW TO SWAP TO THE REAL API:
//   1. Delete the mock array and the setTimeout wrapper below
//   2. Uncomment the apiClient import at the top of this file
//   3. Replace the body of this function with:
//        const { data } = await apiClient.get<ExamSession[]>("/student/sessions");
//        return data;
//   4. That's it — nothing else changes.

async function fetchStudentSessions(): Promise<ExamSession[]> {
  // ── TODO: replace this entire block with: ──────────────────────────────
  // const { data } = await apiClient.get<ExamSession[]>("/student/sessions");
  // return data;
  // ───────────────────────────────────────────────────────────────────────

  // Compute realistic timestamps relative to "now" so the mock data
  // always makes sense regardless of when you run it:
  const now = new Date();

  // Open exam: started 30 minutes ago, ends 30 minutes from now
  const openStart = new Date(now.getTime() - 30 * 60 * 1000).toISOString();
  const openEnd   = new Date(now.getTime() + 30 * 60 * 1000).toISOString();

  // Upcoming exam: starts 2 hours from now, ends 3 hours from now
  const upcomingStart = new Date(now.getTime() + 2 * 60 * 60 * 1000).toISOString();
  const upcomingEnd   = new Date(now.getTime() + 3 * 60 * 60 * 1000).toISOString();

  // Another upcoming: starts tomorrow
  const tomorrowStart = new Date(now.getTime() + 22 * 60 * 60 * 1000).toISOString();
  const tomorrowEnd   = new Date(now.getTime() + 23 * 60 * 60 * 1000).toISOString();

  // Completed exam: ended yesterday
  const completedStart = new Date(now.getTime() - 25 * 60 * 60 * 1000).toISOString();
  const completedEnd   = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();

  // Completed exam: ended last week
  const oldStart = new Date(now.getTime() - 8 * 24 * 60 * 60 * 1000).toISOString();
  const oldEnd   = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();

  return new Promise((resolve) =>
    setTimeout(
      () =>
        resolve([
          {
            session_id: "sess-001",
            exam_title: "Midterm Exam",
            course_name: "COMP47250 — Team Software Project",
            status: "open",
            starts_at: openStart,
            ends_at: openEnd,
          },
          {
            session_id: "sess-002",
            exam_title: "Module Quiz — Week 6",
            course_name: "COMP47470 — Big Data Programming",
            status: "upcoming",
            starts_at: upcomingStart,
            ends_at: upcomingEnd,
          },
          {
            session_id: "sess-003",
            exam_title: "Final Assessment",
            course_name: "COMP47980 — Generative AI and Language Models",
            status: "upcoming",
            starts_at: tomorrowStart,
            ends_at: tomorrowEnd,
          },
          {
            session_id: "sess-004",
            exam_title: "Week 5 Quiz",
            course_name: "COMP47250 — Team Software Project",
            status: "completed",
            starts_at: completedStart,
            ends_at: completedEnd,
          },
          {
            session_id: "sess-005",
            exam_title: "Module Quiz — Week 2",
            course_name: "COMP47470 — Big Data Programming",
            status: "completed",
            starts_at: oldStart,
            ends_at: oldEnd,
          },
        ]),
      300 // simulated network delay in milliseconds
    )
  );
}

// ─── Helper: compute countdown string from an ISO end-time ───────────────────
// Returns "HH:MM:SS" while time remains, or "Closing soon" in the last minute,
// or null if the exam has already ended (caller should re-fetch to update status).

function computeCountdown(endsAt: string): string | null {
  const totalSeconds = Math.floor(
    (new Date(endsAt).getTime() - Date.now()) / 1000
  );

  if (totalSeconds <= 0) return null;                 // exam over — trigger re-fetch
  if (totalSeconds < 60) return "Closing soon";       // last-minute message

  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;

  // Always two digits: 01:05:09
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

// ─── Sub-component: section header ───────────────────────────────────────────
// Renders the "OPEN NOW (1)" / "UPCOMING (2)" / "PAST EXAMS (2)" labels.
// Follows DESIGN.md typography.utility-xs: 12px / 700 / uppercase.

interface SectionHeaderProps {
  label: string;
  count: number;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({ label, count }) => (
  <div className="flex items-center gap-3 mb-4">
    <h2 className="text-xs font-bold text-mute uppercase tracking-widest">
      {label}
    </h2>
    {/* Count pill — shows number of exams in this section */}
    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-surface-soft text-mute text-xs font-bold">
      {count}
    </span>
    {/* Full-width hairline rule to the right of the label */}
    <div className="flex-1 h-px bg-hairline-soft" />
  </div>
);

// ─── Sub-component: empty state ───────────────────────────────────────────────
// Shown when there are no exams at all — e.g. a new student not yet enrolled.

const EmptyState: React.FC = () => (
  <div className="flex flex-col items-center justify-center py-20 text-center">
    <div className="inline-flex items-center justify-center w-14 h-14 rounded-lg bg-surface-soft border border-hairline mb-5">
      <svg className="w-7 h-7 text-ash" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
    </div>
    <p className="text-sm font-semibold text-ink mb-1">No exams yet</p>
    <p className="text-sm text-mute max-w-xs">
      You have no scheduled or past exams. Check back when your professor opens a session.
    </p>
  </div>
);

// ─── Sub-component: loading skeleton ─────────────────────────────────────────
// Three placeholder cards that pulse while the API call is in flight.
// This prevents a jarring flash of empty content on first load.

const LoadingSkeleton: React.FC = () => (
  <div className="space-y-4">
    {[1, 2, 3].map((i) => (
      <div key={i} className="bg-surface-card border border-hairline rounded-md p-6 animate-pulse">
        <div className="flex justify-between mb-4">
          <div className="space-y-2 flex-1">
            <div className="h-3 w-24 bg-surface-soft rounded" />
            <div className="h-4 w-48 bg-surface-soft rounded" />
          </div>
          <div className="h-5 w-20 bg-surface-soft rounded-full" />
        </div>
        <div className="h-3 w-36 bg-surface-soft rounded mb-4" />
        <div className="border-t border-hairline-soft pt-4">
          <div className="h-8 w-28 bg-surface-soft rounded-md" />
        </div>
      </div>
    ))}
  </div>
);

// ─── Main StudentDashboard component ─────────────────────────────────────────

const StudentDashboard: React.FC = () => {
  const { user, logout } = useAuth();

  // ── State ──────────────────────────────────────────────────────────────────
  // sessions: the list fetched from the API (or mock)
  // isLoading: true during the initial fetch only (not during background refresh)
  // error: non-null if the fetch failed — shows a retry UI
  // timers: object mapping session_id → countdown string for open exams
  //         computed client-side every second via a setInterval

  const [sessions, setSessions]   = useState<ExamSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [timers, setTimers]       = useState<Record<string, string>>({});

  // useRef stores the polling interval ID so we can clear it on unmount.
  // Using a ref (not state) because changing it should not trigger a re-render.
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Fetch sessions ─────────────────────────────────────────────────────────
  // useCallback memoises the function so it can safely be listed as a
  // dependency of useEffect without causing an infinite loop.

  const loadSessions = useCallback(async (showSpinner = false) => {
    if (showSpinner) setIsLoading(true);
    setError(null);
    try {
      const data = await fetchStudentSessions();
      setSessions(data);
    } catch {
      setError("Could not load your exams. Check your connection and try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ── Effect 1: initial load + 60-second polling ────────────────────────────
  // Runs once on mount. Sets up a 60-second interval that silently re-fetches
  // (no spinner) so newly opened exams appear automatically.
  // The cleanup function runs when the component unmounts (e.g. the student
  // navigates away) and cancels the interval to prevent memory leaks.

  useEffect(() => {
    loadSessions(true); // first load shows the skeleton spinner

    pollIntervalRef.current = setInterval(() => {
      loadSessions(false); // background refreshes are silent (no spinner)
    }, 60_000); // 60 000 ms = 60 seconds

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [loadSessions]);

  // ── Effect 2: countdown timer for open exams ──────────────────────────────
  // Runs whenever `sessions` changes. For every session with status "open",
  // it computes the time remaining and stores it in the `timers` state.
  // A setInterval ticks every second to keep the display live.
  //
  // If an open exam's countdown reaches zero (computeCountdown returns null),
  // it means the exam window has closed — we trigger a silent re-fetch so
  // the status updates to "completed" automatically.

  useEffect(() => {
    const openSessions = sessions.filter((s) => s.status === "open");

    if (openSessions.length === 0) return; // nothing to tick

    // Compute timers immediately so there's no 1-second blank on render
    const computeAll = () => {
      const next: Record<string, string> = {};
      let needsRefetch = false;

      openSessions.forEach((s) => {
        const t = computeCountdown(s.ends_at);
        if (t === null) {
          needsRefetch = true; // exam just closed — need fresh data
        } else {
          next[s.session_id] = t;
        }
      });

      setTimers(next);
      if (needsRefetch) loadSessions(false);
    };

    computeAll(); // immediate first tick

    const id = setInterval(computeAll, 1_000); // tick every 1 second
    return () => clearInterval(id);             // cleanup on unmount or re-run
  }, [sessions, loadSessions]);

  // ── Derived data: split sessions into three sections ──────────────────────
  // We derive these from state rather than storing them separately — they
  // always stay in sync with `sessions` automatically.

  const openSessions      = sessions.filter((s) => s.status === "open");
  const upcomingSessions  = sessions.filter((s) => s.status === "upcoming");
  const completedSessions = sessions.filter((s) => s.status === "completed");
  const hasAnySessions    = sessions.length > 0;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    // Full-height canvas background — cream #eeefe9 set globally in index.css
    <div className="min-h-screen bg-canvas">

      {/* ── Top navigation bar ────────────────────────────────────────────── */}
      {/* primary-nav: canvas background, 56px height, no border-radius
          per DESIGN.md: "background {colors.canvas} (cream — same as page)" */}
      <header className="bg-canvas border-b border-hairline">
        <div className="max-w-4xl mx-auto px-6 h-14 flex items-center justify-between">

          {/* Brand: shield icon + AEGIS wordmark */}
          <div className="flex items-center gap-2.5">
            <div className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-surface-dark">
              <svg className="w-4 h-4 text-on-dark" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <span className="text-sm font-bold text-ink tracking-tight">AEGIS</span>
          </div>

          {/* Right side: user name + sign out */}
          <div className="flex items-center gap-4">
            <span className="text-sm text-mute hidden sm:block">
              {user?.name}
            </span>
            {/* button-secondary: bg-surface-soft, text-ink, rounded-md */}
            <button
              onClick={logout}
              className="px-3 py-1.5 bg-surface-soft text-ink text-sm font-bold rounded-md transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* ── Page content ──────────────────────────────────────────────────── */}
      <main className="max-w-4xl mx-auto px-6 py-10">

        {/* Page heading */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-ink mb-1">My Exams</h1>
          <p className="text-sm text-mute">
            Your enrolled exam sessions — refreshes automatically every 60 seconds.
          </p>
        </div>

        {/* ── Loading state ─────────────────────────────────────────────── */}
        {isLoading && <LoadingSkeleton />}

        {/* ── Error state ───────────────────────────────────────────────── */}
        {!isLoading && error && (
          // accent-red-soft banner — "Warning / Caution" callout per DESIGN.md
          <div className="px-4 py-4 bg-accent-red-soft border-l-2 border-accent-red rounded-md flex items-start gap-3">
            <svg className="w-5 h-5 text-accent-red flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-semibold text-ink mb-1">Failed to load exams</p>
              <p className="text-sm text-body">{error}</p>
            </div>
            <button
              onClick={() => loadSessions(true)}
              className="flex-shrink-0 px-3 py-1.5 bg-surface-card border border-hairline text-ink text-sm font-bold rounded-md"
            >
              Retry
            </button>
          </div>
        )}

        {/* ── Empty state ───────────────────────────────────────────────── */}
        {!isLoading && !error && !hasAnySessions && <EmptyState />}

        {/* ── Exam sections ─────────────────────────────────────────────── */}
        {!isLoading && !error && hasAnySessions && (
          <div className="space-y-10">

            {/* SECTION 1: Open Now — only shown when there are open exams */}
            {openSessions.length > 0 && (
              <section>
                <SectionHeader label="Open Now" count={openSessions.length} />
                <div className="grid gap-4 sm:grid-cols-2">
                  {openSessions.map((session) => (
                    <ExamCard
                      key={session.session_id}
                      session={session}
                      timeLeft={timers[session.session_id]}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* SECTION 2: Upcoming — only shown when there are upcoming exams */}
            {upcomingSessions.length > 0 && (
              <section>
                <SectionHeader label="Upcoming" count={upcomingSessions.length} />
                <div className="grid gap-4 sm:grid-cols-2">
                  {upcomingSessions.map((session) => (
                    <ExamCard
                      key={session.session_id}
                      session={session}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* SECTION 3: Past Exams — only shown when there are completed exams */}
            {completedSessions.length > 0 && (
              <section>
                <SectionHeader label="Past Exams" count={completedSessions.length} />
                <div className="grid gap-4 sm:grid-cols-2">
                  {completedSessions.map((session) => (
                    <ExamCard
                      key={session.session_id}
                      session={session}
                    />
                  ))}
                </div>
              </section>
            )}

          </div>
        )}
      </main>
    </div>
  );
};

export default StudentDashboard;
