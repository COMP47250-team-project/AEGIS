// frontend/src/pages/ExamShell.tsx
// AEGIS-38: Exam shell with GDPR consent gate.
//
// Consent is always verified against the server on mount — navigating directly
// to this URL never bypasses the consent screen.
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import apiClient from "../api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StudentSession {
  id: string;
  exam_id: string;
  student_id: string;
  consent_at: string | null;
}

type PageState =
  | { kind: "loading" }
  | { kind: "consent-required"; session: StudentSession }
  | { kind: "exam-active"; session: StudentSession }
  | { kind: "error"; message: string };

// ---------------------------------------------------------------------------
// Consent screen component
// ---------------------------------------------------------------------------

interface ConsentScreenProps {
  onConsent: () => void;
  onDecline: () => void;
  isSubmitting: boolean;
}

const ConsentScreen: React.FC<ConsentScreenProps> = ({
  onConsent,
  onDecline,
  isSubmitting,
}) => (
  <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
    <div className="max-w-lg w-full bg-white rounded-xl border border-slate-200 shadow-sm p-8">
      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center">
          <svg
            className="w-5 h-5 text-amber-600"
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
        </div>
        <div>
          <h1 className="text-lg font-semibold text-slate-900">
            Exam Integrity Monitoring
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Before you begin, please review what AEGIS collects during this
            exam.
          </p>
        </div>
      </div>

      {/* What is collected */}
      <div className="mb-6">
        <p className="text-sm font-medium text-slate-700 mb-3">
          AEGIS collects the following browser signals while the exam is open:
        </p>
        <ul className="space-y-2 text-sm text-slate-600">
          <li className="flex items-start gap-2">
            <span className="mt-0.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-slate-400 mt-1.5" />
            <span>
              <strong className="font-medium text-slate-800">
                Keystroke timing
              </strong>{" "}
              — intervals between keystrokes (not key content or clipboard text)
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-slate-400 mt-1.5" />
            <span>
              <strong className="font-medium text-slate-800">
                Tab switching
              </strong>{" "}
              — when you leave and return to this browser tab
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-slate-400 mt-1.5" />
            <span>
              <strong className="font-medium text-slate-800">
                Paste events
              </strong>{" "}
              — when text is pasted into an answer field (not what was pasted)
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-slate-400 mt-1.5" />
            <span>
              <strong className="font-medium text-slate-800">
                Window resize
              </strong>{" "}
              — changes in the browser window size during the exam
            </span>
          </li>
        </ul>
      </div>

      {/* Privacy note */}
      <div className="mb-6 px-4 py-3 bg-slate-50 rounded-lg border border-slate-200 text-sm text-slate-600">
        No webcam, microphone, screen recording, or clipboard contents are ever
        collected. Signals are combined into a confidence score for human
        review only — no automatic academic-misconduct verdicts are issued.
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-3">
        <button
          onClick={onConsent}
          disabled={isSubmitting}
          className="w-full py-3 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {isSubmitting ? "Starting exam…" : "I Consent — Begin Exam"}
        </button>
        <button
          onClick={onDecline}
          disabled={isSubmitting}
          className="w-full py-3 px-4 bg-white hover:bg-slate-50 disabled:text-slate-300 text-slate-700 text-sm font-medium rounded-lg border border-slate-300 transition-colors"
        >
          Decline (leave exam)
        </button>
      </div>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Exam shell (rendered after consent)
// ---------------------------------------------------------------------------

const ExamContent: React.FC = () => (
  <div className="min-h-screen bg-slate-100 flex items-center justify-center">
    <div className="text-center">
      <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-indigo-600 mb-4">
        <svg
          className="w-7 h-7 text-white"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
          />
        </svg>
      </div>
      <h1 className="text-2xl font-semibold text-slate-800 mb-2">Exam</h1>
      <p className="text-slate-400 text-xs">
        Exam shell — implemented by the frontend team.
      </p>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// ExamShell page
// ---------------------------------------------------------------------------

const ExamShell: React.FC = () => {
  const { id: examId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // On mount, always check consent via the API.
  // This prevents URL manipulation: navigating directly to /exam/:id still
  // triggers a server-side consent check, never showing the exam without it.
  useEffect(() => {
    if (!examId) {
      navigate("/student/dashboard", { replace: true });
      return;
    }

    let cancelled = false;

    apiClient
      .get<StudentSession>(`/exams/${examId}/session`)
      .then(({ data }) => {
        if (cancelled) return;
        if (data.consent_at) {
          setState({ kind: "exam-active", session: data });
        } else {
          setState({ kind: "consent-required", session: data });
        }
      })
      .catch(() => {
        if (!cancelled) {
          navigate("/student/dashboard", { replace: true });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [examId, navigate]);

  const handleConsent = useCallback(async () => {
    if (!examId) return;
    setIsSubmitting(true);
    try {
      const { data } = await apiClient.post<StudentSession>(
        `/exams/${examId}/consent`
      );
      setState({ kind: "exam-active", session: data });
    } catch {
      setState({ kind: "error", message: "Failed to record consent. Please try again." });
    } finally {
      setIsSubmitting(false);
    }
  }, [examId]);

  const handleDecline = useCallback(() => {
    navigate("/student/dashboard", { replace: true });
  }, [navigate]);

  if (state.kind === "loading") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-slate-600 mb-4">{state.message}</p>
          <button
            onClick={() => setState({ kind: "loading" })}
            className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  if (state.kind === "consent-required") {
    return (
      <ConsentScreen
        onConsent={handleConsent}
        onDecline={handleDecline}
        isSubmitting={isSubmitting}
      />
    );
  }

  // state.kind === "exam-active"
  return <ExamContent />;
};

export default ExamShell;
