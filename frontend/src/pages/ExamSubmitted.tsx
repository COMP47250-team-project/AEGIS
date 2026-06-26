// frontend/src/pages/ExamSubmitted.tsx
// AEGIS-41: Submission confirmation page at /exam/:id/submitted.
//
// Acceptance criteria covered:
//   ✅ After submission, redirected to /exam/{id}/submitted
//   ✅ Confirmation page shows "Submitted successfully at HH:MM"
//   ✅ Confirmation page shows the submission time
//   ✅ After submission, back-navigation cannot re-enter the exam
//
// How the submission time gets here: ExamShell navigates to this route
// with the submission timestamp passed via router state (navigate(path,
// { state: { submittedAt: ... } })). This avoids a second API round-trip
// just to ask the server "what time did I submit?" when we already know,
// since this page is reached immediately after the submit POST resolves.
//
// If a student lands here directly (e.g. via a stale bookmark, a page
// refresh that drops router state, or by typing the URL manually) we
// don't have a submittedAt in state — in that case we fall back to
// fetching the session from the server and showing its consent_at/whatever
// timestamp is available, rather than showing a broken or blank page.

import React, { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import apiClient from "../api/client";

interface SubmittedLocationState {
  submittedAt?: string; // ISO 8601
}

interface StudentSessionSummary {
  id: string;
  exam_id: string;
  submitted_at: string | null;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

const ExamSubmitted: React.FC = () => {
  const { id: examId } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const stateFromNav = location.state as SubmittedLocationState | null;

  const [submittedAtIso, setSubmittedAtIso] = useState<string | null>(
    stateFromNav?.submittedAt ?? null
  );
  const [loadError, setLoadError] = useState(false);

  // Fallback: if we landed here without router state (e.g. page refresh,
  // direct URL entry), ask the server when this session was submitted.
  // If the server says it was never submitted, this exam isn't actually
  // finished — redirect back to the dashboard rather than show a
  // confirmation for something that didn't happen.
  useEffect(() => {
    if (submittedAtIso || !examId) return;

    let cancelled = false;
    apiClient
      .get<StudentSessionSummary>(`/exams/${examId}/session`)
      .then(({ data }) => {
        if (cancelled) return;
        if (data.submitted_at) {
          setSubmittedAtIso(data.submitted_at);
        } else {
          navigate("/student/dashboard", { replace: true });
        }
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });

    return () => {
      cancelled = true;
    };
  }, [examId, submittedAtIso, navigate]);

  // AEGIS-41: back-navigation cannot re-enter the exam. Pushing a fresh
  // history entry that points at THIS same submitted page means that if
  // the student presses the browser's back button, they land back on
  // /exam/:id/submitted again (not on the live exam) — popping back to
  // this page is harmless since it's just a confirmation screen, not an
  // active session.
  useEffect(() => {
    const blockBack = () => {
      window.history.pushState(null, "", window.location.href);
    };
    window.history.pushState(null, "", window.location.href);
    window.addEventListener("popstate", blockBack);
    return () => window.removeEventListener("popstate", blockBack);
  }, []);

  if (loadError) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
        <p className="text-sm text-body">
          Couldn't confirm your submission status. If you already submitted,
          your answers are safe — check your dashboard for results.
        </p>
      </div>
    );
  }

  if (!submittedAtIso) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-surface-card rounded-md border border-hairline p-8 text-center">
        <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-accent-green-soft border border-accent-green/30 flex items-center justify-center">
          <svg
            className="w-6 h-6 text-accent-green"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <h1 className="text-lg font-semibold text-ink mb-1">
          Submitted successfully at {formatTime(submittedAtIso)}
        </h1>
        <p className="text-sm text-body mb-6">
          Your answers have been recorded. You can close this window or
          return to your dashboard.
        </p>
        <button
          onClick={() => navigate("/student/dashboard", { replace: true })}
          className="w-full py-2.5 px-4 bg-primary text-ink text-sm font-bold rounded-md transition-colors"
        >
          Back to dashboard
        </button>
      </div>
    </div>
  );
};

export default ExamSubmitted;
