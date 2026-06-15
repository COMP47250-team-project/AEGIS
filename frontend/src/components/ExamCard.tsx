// frontend/src/components/ExamCard.tsx
// AEGIS-37: Exam card component used inside StudentDashboard.
//
// Renders one exam session as a card. Appearance varies by status:
//   "open"      — amber Enter Exam button + live countdown timer
//   "upcoming"  — greyed-out, shows scheduled start time, no action
//   "completed" — green Completed badge, no action
//
// Props:
//   session — a single ExamSession object (defined in StudentDashboard.tsx)
//   timeLeft — for "open" sessions only, the pre-computed countdown string
//              ("01:23:45") passed down from StudentDashboard which owns the
//              interval. Passing it as a prop keeps the timer logic in one
//              place and avoids multiple competing intervals.

import React from "react";
import { Link } from "react-router-dom";
import { ExamSession } from "../pages/StudentDashboard";

// ─── Props ────────────────────────────────────────────────────────────────────

interface ExamCardProps {
  session: ExamSession;
  // Only provided when session.status === "open".
  // Format: "HH:MM:SS" or "Closing soon" when under 60 seconds.
  timeLeft?: string;
}

// ─── Helper: format a date string into a human-readable local time ────────────
// e.g. "2026-06-19T14:00:00Z"  →  "Thu 19 Jun · 2:00 PM"

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IE", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

// ─── Sub-component: Status badge shown in the top-right of every card ─────────

interface BadgeProps {
  status: ExamSession["status"];
}

const StatusBadge: React.FC<BadgeProps> = ({ status }) => {
  // "open" — pulsing amber dot + "Open Now" label
  if (status === "open") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-primary/15 text-primary-active text-xs font-semibold">
        {/* Pulsing dot — draws the eye to active exams */}
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
        </span>
        Open Now
      </span>
    );
  }

  // "upcoming" — neutral muted badge
  if (status === "upcoming") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-surface-soft border border-hairline text-mute text-xs font-semibold">
        Upcoming
      </span>
    );
  }

  // "completed" — green success badge (accent-green-soft + accent-green border)
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-green-soft border border-accent-green/30 text-accent-green text-xs font-semibold">
      {/* Checkmark icon */}
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
      </svg>
      Completed
    </span>
  );
};

// ─── Main ExamCard component ──────────────────────────────────────────────────

const ExamCard: React.FC<ExamCardProps> = ({ session, timeLeft }) => {
  const isOpen = session.status === "open";
  const isCompleted = session.status === "completed";
  const isUpcoming = session.status === "upcoming";

  return (
    // Card container — white card on canvas, 1px hairline border, no shadow
    // (per DESIGN.md: "Cards sit flat on cream with thin olive borders only")
    <div className="bg-surface-card border border-hairline rounded-md p-6 flex flex-col gap-4">

      {/* ── Row 1: exam title + status badge ─────────────────────────────── */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Course name — small muted eyebrow above the exam title */}
          <p className="text-xs text-mute font-medium uppercase tracking-wide mb-1">
            {session.course_name}
          </p>
          {/* Exam title — heading-sm-mixed: 18px / 600 per DESIGN.md */}
          <h3 className="text-base font-semibold text-ink leading-snug">
            {session.exam_title}
          </h3>
        </div>
        {/* Status badge top-right */}
        <div className="flex-shrink-0 pt-0.5">
          <StatusBadge status={session.status} />
        </div>
      </div>

      {/* ── Row 2: time information ───────────────────────────────────────── */}
      <div className="flex items-center gap-2 text-sm">

        {/* Clock icon */}
        <svg className="w-4 h-4 text-ash flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M12 8v4l2.5 2.5M12 3a9 9 0 100 18A9 9 0 0012 3z" />
        </svg>

        {/* OPEN: show live countdown "Time remaining: 01:23:45" */}
        {isOpen && timeLeft && (
          <span className="text-body">
            Time remaining:{" "}
            <span className="font-mono font-semibold text-ink tabular-nums">
              {timeLeft}
            </span>
          </span>
        )}

        {/* UPCOMING: show scheduled start time */}
        {isUpcoming && (
          <span className="text-mute">
            Starts {formatDateTime(session.starts_at)}
          </span>
        )}

        {/* COMPLETED: show when it ended */}
        {isCompleted && (
          <span className="text-mute">
            Ended {formatDateTime(session.ends_at)}
          </span>
        )}
      </div>

      {/* ── Row 3: divider + action ───────────────────────────────────────── */}
      {/* Hairline soft divider between info and action — in-card row divider
          per DESIGN.md elevation level 2 */}
      <div className="border-t border-hairline-soft pt-4">

        {/* OPEN: primary amber CTA — "the brand's only loud chromatic moment"
            (DESIGN.md). Only one yellow button per fold. */}
        {isOpen && (
          <Link
            to={`/exam/${session.session_id}`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-ink text-sm font-bold rounded-md transition-colors"
          >
            Enter Exam
            {/* Arrow icon */}
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </Link>
        )}

        {/* UPCOMING: soft disabled-style pill — no link, exam not open yet */}
        {isUpcoming && (
          <span className="inline-flex items-center px-4 py-2 bg-surface-soft text-ash text-sm font-bold rounded-md cursor-not-allowed">
            Not open yet
          </span>
        )}

        {/* COMPLETED: subtle view-results link (tertiary button style) */}
        {isCompleted && (
          <span className="inline-flex items-center text-sm text-mute font-medium">
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Submission recorded
          </span>
        )}
      </div>
    </div>
  );
};

export default ExamCard;
