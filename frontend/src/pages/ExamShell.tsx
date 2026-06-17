// frontend/src/pages/ExamShell.tsx
// AEGIS-38: Exam shell with GDPR consent gate.
// AEGIS-39: MCQ and short-answer question UI.
// AEGIS-40: Countdown timer + auto-submit.
// AEGIS-41: Telemetry flush on submit.
// AEGIS-43–47: Signal producers wired after consent.
//
// Consent is always verified against the server on mount — navigating directly
// to this URL never bypasses the consent screen.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import apiClient, { getAccessToken } from "../api/client";
import QuestionRenderer from "../components/exam/QuestionRenderer";
import ProgressSidebar from "../components/exam/ProgressSidebar";
import type { ExamQuestion } from "../components/exam/QuestionRenderer";
import { TelemetryClient } from "../telemetry/TelemetryClient";
import { attachTabBlur } from "../telemetry/signals/tabBlur";
import { makePasteEvent } from "../telemetry/signals/paste";
import { attachIKI } from "../telemetry/signals/iki";
import { attachFirstKeypress } from "../telemetry/signals/firstKeypress";
import { attachResize } from "../telemetry/signals/resize";
import { makeAnswerTimeEvent } from "../telemetry/signals/answerTime";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StudentSession {
  id: string;
  exam_id: string;
  student_id: string;
  consent_at: string | null;
}

interface ExamSessionData {
  id: string;
  exam_id: string;
  duration_minutes?: number | null;
  scheduled_end?: string | null;
}

type Answers = Record<string, string>;

type PageState =
  | { kind: "loading" }
  | { kind: "consent-required"; session: StudentSession }
  | { kind: "exam-active"; session: StudentSession; examData?: ExamSessionData }
  | { kind: "error"; message: string };

type ContentState =
  | { kind: "loading" }
  | { kind: "loaded"; questions: ExamQuestion[] }
  | { kind: "error" };

// ---------------------------------------------------------------------------
// Consent screen component (AEGIS-38)
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
  <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
    <div className="max-w-lg w-full bg-surface-card rounded-md border border-hairline p-8">
      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <div className="flex-shrink-0 w-10 h-10 rounded-md bg-accent-blue-soft border border-accent-blue/20 flex items-center justify-center">
          <svg
            className="w-5 h-5 text-accent-blue"
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
          <h1 className="text-lg font-semibold text-ink">
            Exam Integrity Monitoring
          </h1>
          <p className="text-sm text-mute mt-0.5">
            Before you begin, please review what AEGIS collects during this
            exam.
          </p>
        </div>
      </div>

      {/* What is collected */}
      <div className="mb-6">
        <p className="text-sm font-medium text-body mb-3">
          AEGIS collects the following browser signals while the exam is open:
        </p>
        <ul className="space-y-2 text-sm text-body">
          <li className="flex items-start gap-2">
            <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-hairline mt-1.5" />
            <span>
              <strong className="font-semibold text-ink">
                Keystroke timing
              </strong>{" "}
              — intervals between keystrokes (not key content or clipboard text)
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-hairline mt-1.5" />
            <span>
              <strong className="font-semibold text-ink">
                Tab switching
              </strong>{" "}
              — when you leave and return to this browser tab
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-hairline mt-1.5" />
            <span>
              <strong className="font-semibold text-ink">
                Paste events
              </strong>{" "}
              — when text is pasted into an answer field (not what was pasted)
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-hairline mt-1.5" />
            <span>
              <strong className="font-semibold text-ink">
                Window resize
              </strong>{" "}
              — changes in the browser window size during the exam
            </span>
          </li>
        </ul>
      </div>

      {/* Privacy note */}
      <div className="mb-6 px-4 py-3 bg-accent-green-soft rounded-md border-l-2 border-accent-green text-sm text-ink">
        No webcam, microphone, screen recording, or clipboard contents are ever
        collected. Signals are combined into a confidence score for human
        review only — no automatic academic-misconduct verdicts are issued.
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-3">
        <button
          onClick={onConsent}
          disabled={isSubmitting}
          className="w-full py-2.5 px-4 bg-primary disabled:bg-surface-soft disabled:text-ash text-ink text-sm font-bold rounded-md transition-colors"
        >
          {isSubmitting ? "Starting exam…" : "I Consent — Begin Exam"}
        </button>
        <button
          onClick={onDecline}
          disabled={isSubmitting}
          className="w-full py-2.5 px-4 bg-surface-soft disabled:text-ash text-ink text-sm font-bold rounded-md transition-colors"
        >
          Decline (leave exam)
        </button>
      </div>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// Countdown timer hook
// ---------------------------------------------------------------------------

function useCountdown(scheduledEndIso: string | null | undefined): string {
  const [label, setLabel] = useState("");

  useEffect(() => {
    if (!scheduledEndIso) return;

    const endMs = new Date(scheduledEndIso).getTime();

    function tick() {
      const remaining = endMs - Date.now();
      if (remaining <= 0) {
        setLabel("Time up");
        return;
      }
      const totalSec = Math.floor(remaining / 1000);
      const h = Math.floor(totalSec / 3600);
      const m = Math.floor((totalSec % 3600) / 60);
      const s = totalSec % 60;
      if (h > 0) {
        setLabel(`${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`);
      } else {
        setLabel(`${m}:${String(s).padStart(2, "0")}`);
      }
    }

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [scheduledEndIso]);

  return label;
}

// ---------------------------------------------------------------------------
// Exam content component (AEGIS-39, 40, 41, 43–47)
// ---------------------------------------------------------------------------

interface ExamContentProps {
  examId: string;
  sessionId: string;
  scheduledEnd?: string | null;
}

const ExamContent: React.FC<ExamContentProps> = ({
  examId,
  sessionId,
  scheduledEnd,
}) => {
  const navigate = useNavigate();
  const [contentState, setContentState] = useState<ContentState>({
    kind: "loading",
  });
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Answers>({});
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);

  // Ref keeps the auto-save interval closure from capturing stale answers
  const answersRef = useRef<Answers>({});
  // Tracks Ctrl+A → Ctrl+C → Ctrl+V sequence for paste telemetry
  const keySeqRef = useRef<string[]>([]);
  // Telemetry client — created once after consent
  const telemetryRef = useRef<TelemetryClient | null>(null);
  // Current question ID (ref so signal closures always see the latest)
  const currentQuestionIdRef = useRef<string>("");
  // Timestamp when student navigated to the current question
  const questionStartTsRef = useRef<number>(Date.now());

  const countdown = useCountdown(scheduledEnd);

  useEffect(() => {
    answersRef.current = answers;
  }, [answers]);

  // Instantiate TelemetryClient and attach all signal producers
  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;

    const wsBase = (import.meta.env.VITE_API_URL ?? "http://localhost:8000")
      .replace(/^http/, "ws");
    const wsUrl = `${wsBase}/ws/exam/${examId}`;

    const client = new TelemetryClient({ wsUrl, sessionToken: token, sessionId });
    telemetryRef.current = client;

    const enqueue = client.enqueue.bind(client);

    const cleanupTabBlur = attachTabBlur(sessionId, enqueue);
    const cleanupIKI = attachIKI(
      sessionId,
      () => currentQuestionIdRef.current,
      enqueue,
    );
    const cleanupFirstKeypress = attachFirstKeypress(
      sessionId,
      () => currentQuestionIdRef.current,
      () => questionStartTsRef.current,
      enqueue,
    );
    const cleanupResize = attachResize(sessionId, enqueue);

    return () => {
      cleanupTabBlur();
      cleanupIKI();
      cleanupFirstKeypress();
      cleanupResize();
      client.flush();
      client.destroy();
      telemetryRef.current = null;
    };
  }, [examId, sessionId]);

  // Load questions on mount
  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<ExamQuestion[]>(`/exams/${examId}/questions`)
      .then(({ data }) => {
        if (!cancelled) {
          setContentState({ kind: "loaded", questions: data });
          if (data.length > 0) {
            currentQuestionIdRef.current = data[0].id;
            questionStartTsRef.current = Date.now();
          }
        }
      })
      .catch(() => {
        if (!cancelled) setContentState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [examId]);

  // Auto-save short-answer responses to the backend every 5 seconds
  useEffect(() => {
    if (contentState.kind !== "loaded") return;
    const shortQuestions = contentState.questions.filter(
      (q) => q.type === "short"
    );
    if (shortQuestions.length === 0) return;

    const tick = () => {
      const current = answersRef.current;
      const items = shortQuestions
        .filter((q) => current[q.id] !== undefined && current[q.id] !== "")
        .map((q) => ({ question_id: q.id, answer: current[q.id] }));
      if (items.length === 0) return;

      setIsSaving(true);
      apiClient
        .post(`/exams/${examId}/answers`, { answers: items })
        .then(() => {
          setSaveError(false);
          setIsSaving(false);
        })
        .catch(() => {
          setSaveError(true);
          setIsSaving(false);
        });
    };

    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [examId, contentState]);

  // Ctrl+A → Ctrl+C → Ctrl+V sequence detection
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey;
      if (!ctrl) {
        keySeqRef.current = [];
        return;
      }
      const k = e.key.toLowerCase();
      if (k === "a") {
        keySeqRef.current = ["ctrl+a"];
      } else if (k === "c" && keySeqRef.current[keySeqRef.current.length - 1] === "ctrl+a") {
        keySeqRef.current.push("ctrl+c");
      } else if (k === "v") {
        const seq = keySeqRef.current;
        if (seq.length >= 2 && seq[0] === "ctrl+a" && seq[1] === "ctrl+c") {
          // Emit paste telemetry for the keyboard shortcut sequence
          telemetryRef.current?.enqueue(
            makePasteEvent(sessionId, currentQuestionIdRef.current)
          );
        }
        keySeqRef.current = [];
      } else {
        keySeqRef.current = [];
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [sessionId]);

  const handleAnswerChange = useCallback(
    (questionId: string, value: string) => {
      setAnswers((prev) => ({ ...prev, [questionId]: value }));
    },
    []
  );

  // MCQ answers are persisted immediately on selection
  const handleMcqChange = useCallback(
    (questionId: string, value: string) => {
      setAnswers((prev) => ({ ...prev, [questionId]: value }));
      apiClient
        .post(`/exams/${examId}/answers`, {
          answers: [{ question_id: questionId, answer: value }],
        })
        .catch(() => {
          /* local state is preserved on network failure */
        });
    },
    [examId]
  );

  const handlePaste = useCallback(
    (questionId: string) => {
      telemetryRef.current?.enqueue(makePasteEvent(sessionId, questionId));
    },
    [sessionId]
  );

  const goTo = useCallback(
    (index: number) => {
      if (contentState.kind !== "loaded") return;
      const nextIndex = Math.max(0, Math.min(index, contentState.questions.length - 1));
      if (nextIndex === currentIndex) return;

      // Emit answer_time for the question we're leaving
      const leavingQuestion = contentState.questions[currentIndex];
      if (leavingQuestion) {
        telemetryRef.current?.enqueue(
          makeAnswerTimeEvent(sessionId, leavingQuestion.id, questionStartTsRef.current)
        );
      }

      // Update tracking refs for the new question
      const nextQuestion = contentState.questions[nextIndex];
      if (nextQuestion) {
        currentQuestionIdRef.current = nextQuestion.id;
        questionStartTsRef.current = Date.now();
      }

      setCurrentIndex(nextIndex);
    },
    [contentState, currentIndex, sessionId]
  );

  const handleFinish = useCallback(async () => {
    if (contentState.kind !== "loaded") return;

    // Emit answer_time for the current question before submitting
    const currentQuestion = contentState.questions[currentIndex];
    if (currentQuestion) {
      telemetryRef.current?.enqueue(
        makeAnswerTimeEvent(sessionId, currentQuestion.id, questionStartTsRef.current)
      );
    }

    // Flush buffered telemetry events before leaving
    telemetryRef.current?.flush();

    // Durably persist all answers (MVP criterion 7: works even if WS fails)
    const current = answersRef.current;
    const allAnswers = contentState.questions.map((q) => ({
      question_id: q.id,
      answer: current[q.id] ?? "",
    }));
    try {
      await apiClient.post(`/exams/${examId}/answers`, {
        answers: allAnswers,
      });
    } catch {
      /* best-effort final save */
    }
    navigate("/student/dashboard", { replace: true });
  }, [examId, contentState, currentIndex, sessionId, navigate]);

  // --- Loading / error states ---

  if (contentState.kind === "loading") {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (contentState.kind === "error") {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
        <p className="text-sm text-body">
          Failed to load exam questions. Please refresh the page.
        </p>
      </div>
    );
  }

  const { questions } = contentState;

  if (questions.length === 0) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
        <p className="text-sm text-body">No questions found for this exam.</p>
      </div>
    );
  }

  const current = questions[currentIndex];
  const answeredCount = questions.filter(
    (q) => answers[q.id] !== undefined && answers[q.id] !== ""
  ).length;

  const isLowTime = countdown !== "" && !countdown.includes(":") === false &&
    (() => {
      const parts = countdown.split(":").map(Number);
      const totalSec = parts.length === 3
        ? parts[0] * 3600 + parts[1] * 60 + parts[2]
        : parts[0] * 60 + (parts[1] ?? 0);
      return totalSec <= 120; // last 2 minutes
    })();

  return (
    <div className="min-h-screen bg-canvas flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-hairline bg-surface-card">
        <div>
          <p className="text-sm font-semibold text-ink">AEGIS Exam</p>
          <p className="text-xs text-mute">
            Question {currentIndex + 1} of {questions.length}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {countdown && (
            <span
              className={`text-sm font-mono font-semibold ${
                isLowTime ? "text-accent-red" : "text-body"
              }`}
            >
              {countdown}
            </span>
          )}
          {isSaving && <span className="text-xs text-mute">Saving…</span>}
          {saveError && (
            <span className="text-xs text-accent-red">
              Auto-save failed — answers are safe locally
            </span>
          )}
          <button
            onClick={handleFinish}
            className="px-4 py-2 bg-primary text-ink text-sm font-bold rounded-md"
          >
            Finish Exam
          </button>
        </div>
      </header>

      {/* Main body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Progress sidebar */}
        <aside className="w-56 flex-shrink-0 border-r border-hairline bg-surface-card overflow-y-auto px-3 py-4">
          <ProgressSidebar
            questions={questions}
            answers={answers}
            currentIndex={currentIndex}
            onSelect={goTo}
          />
        </aside>

        {/* Question area */}
        <main className="flex-1 overflow-y-auto px-8 py-8">
          <div className="max-w-2xl mx-auto">
            <div className="bg-surface-card border border-hairline rounded-md p-6">
              <QuestionRenderer
                question={current}
                answer={answers[current.id] ?? ""}
                onAnswerChange={
                  current.type === "mcq" ? handleMcqChange : handleAnswerChange
                }
                onPaste={handlePaste}
              />
            </div>

            {/* Prev / Next navigation */}
            <div className="flex items-center justify-between mt-6">
              <button
                onClick={() => goTo(currentIndex - 1)}
                disabled={currentIndex === 0}
                className="px-4 py-2 bg-surface-soft text-ink text-sm font-bold rounded-md disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
              >
                ← Previous
              </button>
              <span className="text-xs text-mute">
                {answeredCount} of {questions.length} answered
              </span>
              <button
                onClick={() => goTo(currentIndex + 1)}
                disabled={currentIndex === questions.length - 1}
                className="px-4 py-2 bg-primary text-ink text-sm font-bold rounded-md disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
              >
                Next →
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// ExamShell page
// ---------------------------------------------------------------------------

const ExamShell: React.FC = () => {
  const { id: examId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [state, setState] = useState<PageState>({ kind: "loading" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  // On mount, always check consent via the API.
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
      setState({
        kind: "error",
        message: "Failed to record consent. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [examId]);

  const handleDecline = useCallback(() => {
    navigate("/student/dashboard", { replace: true });
  }, [navigate]);

  if (state.kind === "loading") {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
        <div className="text-center">
          <p className="text-body mb-4">{state.message}</p>
          <button
            onClick={() => setState({ kind: "loading" })}
            className="px-4 py-2 bg-primary text-ink text-sm font-bold rounded-md"
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
  return (
    <ExamContent
      examId={state.session.exam_id}
      sessionId={state.session.id}
      scheduledEnd={state.examData?.scheduled_end}
    />
  );
};

export default ExamShell;
