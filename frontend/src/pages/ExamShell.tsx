// frontend/src/pages/ExamShell.tsx
// AEGIS-38: Exam shell with GDPR consent gate.
// AEGIS-39: MCQ and short-answer question UI.
// AEGIS-40: Countdown timer + auto-submit.
// AEGIS-41: Submit confirmation modal + submitted confirmation page +
//           idempotent submit + clean telemetry/WS shutdown on submit.
// AEGIS-43–47: Signal producers wired after consent.
//
// Consent is always verified against the server on mount — navigating directly
// to this URL never bypasses the consent screen.
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import apiClient, { getAccessToken } from "../api/client";
import QuestionRenderer from "../components/exam/QuestionRenderer";
import ProgressSidebar from "../components/exam/ProgressSidebar";
import CountdownTimer from "../components/exam/CountdownTimer";
import ResourcePanel from "../components/exam/ResourcePanel";
import type { ExamResource } from "../components/exam/ResourcePanel";
import ThemeToggle from "../components/ThemeToggle";
import ExamErrorBoundary from "../components/exam/ExamErrorBoundary";
import SubmitConfirmModal from "../components/exam/SubmitConfirmModal";
import type { ExamQuestion } from "../components/exam/QuestionRenderer";
import { TelemetryClient } from "../telemetry/TelemetryClient";
import { attachTabBlur } from "../telemetry/signals/tabBlur";
import { isInternalPaste, makePasteEvent } from "../telemetry/signals/paste";
import { attachIKI } from "../telemetry/signals/iki";
import { attachFirstKeypress } from "../telemetry/signals/firstKeypress";
import { attachResize } from "../telemetry/signals/resize";
import {
  makeQuestionTimeEvent,
  accumulateDuration,
} from "../telemetry/signals/questionTime";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StudentSession {
  id: string;
  exam_id: string;
  student_id: string;
  consent_at: string | null;
  submitted_at: string | null;
  exam_state: string;
  // AEGIS-121: "closed_book" | "open_book" — drives the resource panel.
  mode?: string;
}

// AEGIS-40: shape returned by GET /exams/{exam_id} — used to derive the
// authoritative end time. We only need these three fields here; the full
// ExamRead schema on the backend has more (enrollment_count, quiz_title etc.)
// but we deliberately type only what this component consumes.
interface StudentSessionItem {
  exam_id: string;
  ends_at: string; // ISO 8601 — authoritative end time from server
}

type Answers = Record<string, string>;

type PageState =
  | { kind: "loading" }
  | { kind: "consent-required"; session: StudentSession }
  | { kind: "exam-active"; session: StudentSession }
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
              <strong className="font-semibold text-ink">Tab switching</strong>{" "}
              — when you leave and return to this browser tab
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-hairline mt-1.5" />
            <span>
              <strong className="font-semibold text-ink">Paste events</strong> —
              when text is pasted into an answer field (not what was pasted)
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-hairline mt-1.5" />
            <span>
              <strong className="font-semibold text-ink">Window resize</strong>{" "}
              — changes in the browser window size during the exam
            </span>
          </li>
        </ul>
      </div>
      <div className="mb-6 px-4 py-3 bg-accent-green-soft rounded-md border-l-2 border-accent-green text-sm text-ink">
        No webcam, microphone, screen recording, or clipboard contents are ever
        collected. Signals are combined into a confidence score for human review
        only — no automatic academic-misconduct verdicts are issued.
      </div>
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
// AEGIS-40: useServerEndTime hook
// ---------------------------------------------------------------------------
// Fetches GET /exams/{exam_id}, derives the authoritative end time as an
// ISO string, and re-fetches periodically so CountdownTimer can re-sync
// and correct for any local clock drift.

const END_TIME_RESYNC_MS = 30_000; // re-fetch from server every 30s

function useServerEndTime(examId: string): {
  endTimeIso: string | null;
} {
  const [endTimeIso, setEndTimeIso] = useState<string | null>(null);

  const fetchEndTime = useCallback(async () => {
    try {
      const { data } =
        await apiClient.get<StudentSessionItem[]>("/student/sessions");
      const session = data.find((s) => s.exam_id === examId);
      if (!session) return;
      const endMs = new Date(session.ends_at).getTime();
      setEndTimeIso(new Date(endMs).toISOString());
    } catch {
      // If this particular re-sync fails (e.g. brief network blip), keep
      // the previous endTimeIso rather than clearing it — CountdownTimer
      // will keep counting down from the last known-good value rather than
      // freezing or resetting. The next scheduled re-sync will try again.
    }
  }, [examId]);

  useEffect(() => {
    fetchEndTime(); // initial fetch
    const id = setInterval(fetchEndTime, END_TIME_RESYNC_MS);
    return () => clearInterval(id);
  }, [fetchEndTime]);

  return { endTimeIso };
}

// ---------------------------------------------------------------------------
// Exam content component (AEGIS-39, 40, 41, 43–47)
// ---------------------------------------------------------------------------

interface ExamContentProps {
  examId: string;
  sessionId: string;
  mode: string;
}

const ExamContent: React.FC<ExamContentProps> = ({
  examId,
  sessionId,
  mode,
}) => {
  const navigate = useNavigate();
  const [contentState, setContentState] = useState<ContentState>({
    kind: "loading",
  });
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Answers>({});
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [isAutoSubmitting, setIsAutoSubmitting] = useState(false);
  // Set when the professor closes the exam (pushed over the telemetry socket).
  const [closedByProfessor, setClosedByProfessor] = useState(false);

  // AEGIS-121: open-book resource panel state. Only populated for open_book exams.
  const isOpenBook = mode === "open_book";
  const [resources, setResources] = useState<ExamResource[]>([]);
  const [showResources, setShowResources] = useState(true);

  // Warning banner (AEGIS-85): shown briefly after monitored events fire.
  const [warningMsg, setWarningMsg] = useState<string | null>(null);
  const warningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showWarning = useCallback((msg: string) => {
    setWarningMsg(msg);
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    warningTimerRef.current = setTimeout(() => setWarningMsg(null), 4000);
  }, []);

  // Text the student copied from within the exam. A paste of the same text is
  // internal and allowed (not flagged). Stored and compared on the client only
  // — clipboard content is never transmitted (AEGIS-104, data minimisation).
  const internalCopiesRef = useRef<Set<string>>(new Set());
  const rememberInternalCopy = useCallback((text: string) => {
    const normalised = text.trim();
    if (!normalised) return;
    const set = internalCopiesRef.current;
    set.add(normalised);
    // Bound memory — keep only the most recent copies (Set preserves order).
    if (set.size > 50) {
      const oldest = set.values().next().value;
      if (oldest !== undefined) set.delete(oldest);
    }
  }, []);
  // AEGIS-41: controls visibility of the "Are you sure?" modal triggered
  // by the manual Finish Exam button. Auto-submit (from CountdownTimer)
  // never opens this — the clock already decided, no confirmation needed.
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  const answersRef = useRef<Answers>({});
  // Telemetry client — created once after consent
  const telemetryRef = useRef<TelemetryClient | null>(null);
  const currentQuestionIdRef = useRef<string>("");
  const questionStartTsRef = useRef<number>(Date.now());
  const contentStateRef = useRef<ContentState>(contentState);
  const currentIndexRef = useRef(currentIndex);
  // Cumulative time spent per question id (adds up across re-visits)
  const questionDurationsRef = useRef<Map<string, number>>(new Map());
  // AEGIS-41: idempotency guard. submitAndLeave can be triggered from three
  // places — the manual confirm button, a double-click on that same button
  // before the first click finishes, and CountdownTimer's auto-submit. A
  // ref (not state) is used so the check-and-set happens synchronously,
  // with no risk of two near-simultaneous calls both reading "not yet
  // submitted" before either has set the flag.
  const hasSubmittedRef = useRef(false);

  // AEGIS-40: authoritative end time, re-synced from the server every 30s
  const { endTimeIso } = useServerEndTime(examId);

  useEffect(() => {
    answersRef.current = answers;
  }, [answers]);

  useEffect(() => {
    contentStateRef.current = contentState;
  }, [contentState]);

  useEffect(() => {
    currentIndexRef.current = currentIndex;
  }, [currentIndex]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;

    const wsBase = (
      import.meta.env.VITE_API_URL ?? "http://localhost:8000"
    ).replace(/^http/, "ws");
    const wsUrl = `${wsBase}/ws/exam/${examId}`;

    const client = new TelemetryClient({
      wsUrl,
      sessionToken: token,
      sessionId,
      onExamClosed: () => setClosedByProfessor(true),
    });
    telemetryRef.current = client;

    const enqueue = client.enqueue.bind(client);

    // AEGIS-121: in an open-book exam, focus moving into the in-panel resource
    // iframe is legitimate — not a tab/window switch. The tab as a whole still
    // has focus in that case (document.hasFocus() stays true when focus is
    // inside an iframe, and only goes false on a real Alt+Tab / tab switch), so
    // we ignore that blur rather than emitting a tab_blur. Closed-book is
    // unaffected (predicate always false → identical behaviour).
    const ignoreResourceBlur = () => isOpenBook && document.hasFocus();

    const cleanupTabBlur = attachTabBlur(
      sessionId,
      enqueue,
      ignoreResourceBlur,
    );
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
  }, [examId, sessionId, isOpenBook]);

  // Warning banner cleanup on unmount.
  useEffect(() => {
    return () => {
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    };
  }, []);

  // DOM listeners that drive the warning banner — ExamContent only mounts
  // after consent, so no consentGiven guard needed.
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.hidden) {
        showWarning(
          "⚠️ Leaving this tab has been recorded for integrity review.",
        );
      }
    };
    const onCopyOrCut = () => {
      // Remember text copied on the page so a later paste of it counts as
      // internal (allowed). Paste warnings/flags are raised in handlePaste,
      // only for text that did NOT originate within the exam.
      rememberInternalCopy(document.getSelection()?.toString() ?? "");
    };
    const onBlur = () => {
      // AEGIS-121: in an open-book exam, focus moving into the in-panel resource
      // iframe fires window "blur" but the tab still has focus — that's
      // legitimate viewing, not a window switch, so don't warn. A real Alt+Tab
      // drops document.hasFocus() to false and still warns. Closed-book is
      // unaffected (isOpenBook false → always warns as before).
      if (isOpenBook && document.hasFocus()) return;
      showWarning("⚠️ Window focus lost — this has been recorded.");
    };

    document.addEventListener("visibilitychange", onVisibilityChange);
    document.addEventListener("copy", onCopyOrCut);
    document.addEventListener("cut", onCopyOrCut);
    window.addEventListener("blur", onBlur);

    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      document.removeEventListener("copy", onCopyOrCut);
      document.removeEventListener("cut", onCopyOrCut);
      window.removeEventListener("blur", onBlur);
    };
  }, [showWarning, rememberInternalCopy, isOpenBook]);

  // Warn before a browser refresh / tab close so the student doesn't
  // accidentally interrupt the exam (AEGIS-104). The browser shows its native
  // "Leave site?" dialog. In-app submit navigates via the router and does not
  // trigger this; once submitted, the guard is disabled.
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasSubmittedRef.current) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data: questions } = await apiClient.get<ExamQuestion[]>(
          `/exams/${examId}/questions`,
        );
        if (cancelled) return;

        // Rehydrate previously saved answers so a refresh / re-login resumes
        // the exam instead of restarting it (AEGIS-104).
        let saved: Answers = {};
        try {
          const { data: savedAnswers } = await apiClient.get<
            { question_id: string; answer: string }[]
          >(`/exams/${examId}/answers`);
          if (cancelled) return;
          saved = Object.fromEntries(
            savedAnswers.map((a) => [a.question_id, a.answer]),
          );
        } catch {
          // No saved answers yet (or fetch failed) — start fresh.
        }
        if (Object.keys(saved).length > 0) setAnswers(saved);

        setContentState({ kind: "loaded", questions });
        if (questions.length > 0) {
          // Resume at the first unanswered question; if all are answered,
          // land on the last one rather than restarting at the top.
          const firstUnanswered = questions.findIndex(
            (q) => saved[q.id] === undefined || saved[q.id] === "",
          );
          const idx =
            firstUnanswered === -1 ? questions.length - 1 : firstUnanswered;
          setCurrentIndex(idx);
          currentQuestionIdRef.current = questions[idx].id;
          questionStartTsRef.current = Date.now();
        }
      } catch {
        if (!cancelled) setContentState({ kind: "error" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [examId]);

  useEffect(() => {
    if (contentState.kind !== "loaded") return;
    const shortQuestions = contentState.questions.filter(
      (q) => q.type === "short",
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

  // AEGIS-121: fetch the open-book resource allowlist once (open_book only).
  useEffect(() => {
    if (!isOpenBook) return;
    let cancelled = false;
    apiClient
      .get<ExamResource[]>(`/exams/${examId}/resources`)
      .then(({ data }) => {
        if (!cancelled) setResources(data);
      })
      .catch(() => {
        /* no resources / fetch failed — panel simply shows an empty state */
      });
    return () => {
      cancelled = true;
    };
  }, [examId, isOpenBook]);

  const handleAnswerChange = useCallback(
    (questionId: string, value: string) => {
      setAnswers((prev) => ({ ...prev, [questionId]: value }));
    },
    [],
  );

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
    [examId],
  );

  const handlePaste = useCallback(
    (questionId: string, charCount: number, pastedText: string) => {
      // Copy/paste within the exam is allowed — only flag paste from outside.
      if (isInternalPaste(pastedText, internalCopiesRef.current)) {
        return;
      }
      showWarning(
        "⚠️ A paste from outside the exam has been recorded for integrity review.",
      );
      telemetryRef.current?.enqueue(
        makePasteEvent(sessionId, questionId, charCount),
      );
    },
    [sessionId, showWarning],
  );

  const goTo = useCallback(
    (index: number) => {
      if (contentState.kind !== "loaded") return;
      const nextIndex = Math.max(
        0,
        Math.min(index, contentState.questions.length - 1),
      );
      if (nextIndex === currentIndex) return;

      // Accumulate time on the question we're leaving (cumulative across
      // re-visits) and emit its running total.
      const leavingQuestion = contentState.questions[currentIndex];
      if (leavingQuestion) {
        const elapsed = Date.now() - questionStartTsRef.current;
        accumulateDuration(
          questionDurationsRef.current,
          leavingQuestion.id,
          elapsed,
        );
        telemetryRef.current?.enqueue(
          makeQuestionTimeEvent(
            sessionId,
            leavingQuestion.id,
            questionDurationsRef.current.get(leavingQuestion.id) ?? 0,
            leavingQuestion.position,
            contentState.questions.length,
          ),
        );
      }

      const nextQuestion = contentState.questions[nextIndex];
      if (nextQuestion) {
        currentQuestionIdRef.current = nextQuestion.id;
        questionStartTsRef.current = Date.now();
      }

      setCurrentIndex(nextIndex);
    },
    [contentState, currentIndex, sessionId],
  );

  // ── Shared submit-and-leave logic ─────────────────────────────────────────
  // Used by the manual "confirm submit" path (after the AEGIS-41 modal),
  // AND the automatic T-0 trigger from CountdownTimer.
  //
  // AEGIS-41 additions on top of the AEGIS-40 version of this function:
  //   - Idempotent: a second call (double-click, or auto-submit racing a
  //     manual submit that's already in flight) is a no-op.
  //   - Cleanly closes the WebSocket via telemetryRef.current?.close()
  //     after flushing, rather than leaving it for unmount to handle.
  //   - Captures the submission timestamp and passes it to the new
  //     /exam/:id/submitted confirmation page via router state, instead
  //     of navigating straight back to the dashboard.
  const submitAndLeave = useCallback(async () => {
    // AEGIS-41 acceptance criterion: "double-click or double-submit is
    // idempotent." This check-and-set happens synchronously on a ref, so
    // there's no window where two near-simultaneous calls both see "not
    // yet submitted" and both proceed.
    if (hasSubmittedRef.current) return;
    hasSubmittedRef.current = true;

    const state = contentStateRef.current;
    if (state.kind !== "loaded") return;

    // Accumulate time on the question currently open before submitting.
    const idx = currentIndexRef.current;
    const currentQuestion = state.questions[idx];
    if (currentQuestion) {
      const elapsed = Date.now() - questionStartTsRef.current;
      accumulateDuration(
        questionDurationsRef.current,
        currentQuestion.id,
        elapsed,
      );
    }

    // Emit a question_time event for EVERY question, including ones never
    // visited (duration 0) — so the scorer can flag 0ms / skipped questions.
    const totalQuestions = state.questions.length;
    for (const q of state.questions) {
      telemetryRef.current?.enqueue(
        makeQuestionTimeEvent(
          sessionId,
          q.id,
          questionDurationsRef.current.get(q.id) ?? 0,
          q.position,
          totalQuestions,
        ),
      );
    }

    // AEGIS-40/41: flush buffered telemetry events before leaving.
    telemetryRef.current?.flush();

    const current = answersRef.current;
    const allAnswers = state.questions.map((q) => ({
      question_id: q.id,
      answer: current[q.id] ?? "",
    }));

    let submittedAtIso = new Date().toISOString();
    try {
      const { data } = await apiClient.post<{ submitted_at?: string }>(
        `/exams/${examId}/answers`,
        { answers: allAnswers, final: true },
      );
      // Prefer the server's own submitted_at if it returns one — it's the
      // authoritative timestamp the professor's grade report will use.
      // Falling back to the client-side timestamp above means the
      // confirmation page still shows *something* reasonable even if the
      // backend response shape changes or the field is omitted.
      if (data?.submitted_at) {
        submittedAtIso = data.submitted_at;
      }
    } catch {
      /* best-effort final save — we still navigate away below regardless,
         since the exam window has closed either way and staying on this
         page serves no purpose for the student */
    }

    // AEGIS-41: close the WebSocket cleanly now that we're done with it,
    // rather than waiting for the component to unmount. close() cancels
    // any pending reconnect attempt and closes the socket immediately.
    telemetryRef.current?.close();

    navigate(`/exam/${examId}/submitted`, {
      replace: true,
      state: { submittedAt: submittedAtIso },
    });
  }, [examId, sessionId, navigate]);

  // Manual submit: open the confirmation modal rather than submitting
  // immediately (AEGIS-41 acceptance criterion 1).
  const handleFinishClick = useCallback(() => {
    setShowConfirmModal(true);
  }, []);

  const handleConfirmSubmit = useCallback(async () => {
    await submitAndLeave();
    // No need to setShowConfirmModal(false) on success — submitAndLeave
    // navigates away, unmounting this component. If it fails partway and
    // we're still here, hasSubmittedRef guards against a retry storm, but
    // we still want the modal to close so the student isn't stuck looking
    // at a frozen "Submitting…" button forever.
    setShowConfirmModal(false);
  }, [submitAndLeave]);

  const handleCancelSubmit = useCallback(() => {
    setShowConfirmModal(false);
  }, []);

  // ── AEGIS-40: isolated auto-submit handler ────────────────────────────────
  // Passed to CountdownTimer's onAutoSubmit prop. CountdownTimer already
  // wraps the call to this function in try/catch, so a synchronous throw
  // here cannot escape and stop the timer's own interval. We also wrap the
  // body here so this function fails safely even if called directly.
  const handleAutoSubmit = useCallback(async () => {
    setIsAutoSubmitting(true);
    try {
      await submitAndLeave();
    } catch (err) {
      // does not re-throw, per acceptance criterion 5/6
      console.error("[ExamShell] auto-submit failed:", err);
      navigate("/student/dashboard", { replace: true });
    }
  }, [submitAndLeave, navigate]);

  // The professor closed the exam — end the session with a clear notice.
  if (closedByProfessor) {
    return (
      <div className="min-h-screen bg-canvas flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-surface-card rounded-md border border-hairline p-8 text-center">
          <h1 className="text-lg font-semibold text-ink mb-2">Exam closed</h1>
          <p className="text-sm text-body mb-6">
            The professor has closed this exam. Your session has ended and any
            saved answers have been submitted.
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
  }

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
    (q) => answers[q.id] !== undefined && answers[q.id] !== "",
  ).length;

  return (
    <div className="min-h-screen bg-canvas flex flex-col">
      <header className="flex items-center justify-between gap-2 px-3 sm:px-6 py-3 border-b border-hairline bg-surface-card">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">AEGIS Exam</p>
          <p className="text-xs text-mute">
            Question {currentIndex + 1} of {questions.length}
          </p>
        </div>

        {/* AEGIS-40: CountdownTimer — top-right, always visible.
            Positioned as a sibling of the question content, OUTSIDE the
            ExamErrorBoundary below — a crash in question rendering cannot
            reach this and stop the timer or auto-submit. */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <ThemeToggle />
          <CountdownTimer
            serverEndTime={endTimeIso}
            onAutoSubmit={handleAutoSubmit}
          />
          {isSaving && (
            <span className="hidden sm:inline text-xs text-mute">Saving…</span>
          )}
          {saveError && (
            <span className="hidden sm:inline text-xs text-accent-red">
              Auto-save failed — answers are safe locally
            </span>
          )}
          <button
            onClick={handleFinishClick}
            disabled={isAutoSubmitting}
            className="px-3 sm:px-4 py-2 bg-primary disabled:bg-surface-soft disabled:text-ash text-ink text-sm font-bold rounded-md transition-colors whitespace-nowrap"
          >
            {isAutoSubmitting ? (
              "Submitting…"
            ) : (
              <>
                <span className="sm:hidden">Finish</span>
                <span className="hidden sm:inline">Finish Exam</span>
              </>
            )}
          </button>
        </div>
      </header>

      {/* AEGIS-85: warning banner — brand amber, auto-dismisses after 4 seconds */}
      {warningMsg && (
        <div
          className="mx-4 mt-2 mb-0 px-4 py-2 bg-primary/10 border border-primary/30 text-charcoal text-sm rounded-md flex items-center gap-2 animate-fade-in"
          role="alert"
          aria-live="assertive"
        >
          <span className="shrink-0 text-base">⚠️</span>
          <span>{warningMsg}</span>
        </div>
      )}

      {/* AEGIS-41: confirmation modal — only shown for manual submission */}
      <SubmitConfirmModal
        isOpen={showConfirmModal}
        isSubmitting={isAutoSubmitting}
        onConfirm={handleConfirmSubmit}
        onCancel={handleCancelSubmit}
      />

      <ExamErrorBoundary>
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar hidden on mobile (AEGIS-74c) — the main area's
              Previous/Next controls provide navigation on small screens. */}
          <aside className="hidden md:block w-56 flex-shrink-0 border-r border-hairline bg-surface-card overflow-y-auto px-3 py-4">
            <ProgressSidebar
              questions={questions}
              answers={answers}
              currentIndex={currentIndex}
              onSelect={goTo}
            />
          </aside>

          <main className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 sm:py-8">
            <div className="max-w-2xl mx-auto">
              <div className="bg-surface-card border border-hairline rounded-md p-6">
                <QuestionRenderer
                  question={current}
                  answer={answers[current.id] ?? ""}
                  onAnswerChange={
                    current.type === "mcq"
                      ? handleMcqChange
                      : handleAnswerChange
                  }
                  onPaste={handlePaste}
                />
              </div>

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

          {/* AEGIS-121: open-book resource panel — a collapsible right pane,
              rendered only for open-book exams. When collapsed it leaves a
              slim "Resources" tab so the student can reopen it. */}
          {isOpenBook &&
            (showResources ? (
              <aside className="w-full max-w-md flex-shrink-0 border-l border-hairline bg-surface-card overflow-hidden flex flex-col">
                <ResourcePanel
                  examId={examId}
                  sessionId={sessionId}
                  resources={resources}
                  enqueue={(event) => telemetryRef.current?.enqueue(event)}
                  onCollapse={() => setShowResources(false)}
                />
              </aside>
            ) : (
              <button
                onClick={() => setShowResources(true)}
                className="flex-shrink-0 border-l border-hairline bg-surface-card px-2 py-4 text-xs font-semibold text-primary-active hover:bg-surface-soft transition-colors [writing-mode:vertical-rl]"
                aria-label="Show resources panel"
              >
                📚 Resources
              </button>
            ))}
        </div>
      </ExamErrorBoundary>
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
        // AEGIS-111: a finished exam can't be re-entered — send the student to
        // the completion page instead of reopening the exam.
        if (data.submitted_at) {
          navigate(`/exam/${examId}/submitted`, {
            replace: true,
            state: { submittedAt: data.submitted_at },
          });
          return;
        }
        if (data.exam_state === "closed") {
          navigate(`/student/exams/${examId}/results`, { replace: true });
          return;
        }
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
        `/exams/${examId}/consent`,
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
      mode={state.session.mode ?? "closed_book"}
    />
  );
};

export default ExamShell;
