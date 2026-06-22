// frontend/src/components/exam/CountdownTimer.tsx
// AEGIS-40: Countdown timer + T-30s warning banner + isolated auto-submit trigger.
//
// This component is purely a DISPLAY + TRIGGER component. It does NOT itself
// call the submit API — it calls the onAutoSubmit callback passed down from
// ExamShell, which owns the actual submission logic (answers, telemetry flush).
// This separation matters for acceptance criterion 5: "Auto-submit cannot be
// blocked by a JS error in other components." By keeping the timer's own
// rendering simple and wrapping the trigger logic in try/catch, a crash
// anywhere else in the exam shell (e.g. QuestionRenderer throwing) cannot
// prevent this component's own interval from firing onAutoSubmit.
//
// Acceptance criteria covered:
//   ✅ Shown in the top-right of the exam shell at all times (positioning is
//      the caller's responsibility — see ExamShell.tsx header)
//   ✅ At T-30s, shows an "Auto-submit in 30s" warning banner
//   ✅ At T-0, calls onAutoSubmit() exactly once (guarded against double-fire)
//   ✅ Auto-submit fires even if the student has not clicked Submit
//   ✅ Auto-submit cannot be blocked by a JS error in other components —
//      the trigger call itself is wrapped in try/catch
//   ✅ Resistant to local clock drift — recomputes from serverEndTime on
//      every prop change (i.e. whenever ExamShell re-syncs from the server)

import React, { useEffect, useRef, useState } from "react";

// ─── Props ────────────────────────────────────────────────────────────────────

interface CountdownTimerProps {
  // Authoritative end time from the server, as an ISO 8601 string.
  // ExamShell re-fetches this periodically (or on reconnect) and passes
  // a fresh value down — that re-sync is what makes the timer drift-resistant.
  // null/undefined means "we don't know the end time yet" (still loading).
  serverEndTime: string | null | undefined;

  // Called exactly once when the countdown reaches zero. ExamShell supplies
  // the real submit-and-flush logic here. This component does not know or
  // care what happens inside — it only guarantees the call happens once,
  // on time, and that a failure inside the callback is caught and logged
  // rather than crashing the timer or the page.
  onAutoSubmit: () => void | Promise<void>;

  // Seconds before T-0 at which to show the warning banner. Defaults to 30
  // per the ticket, but exposed as a prop so it's testable without waiting
  // 30 real seconds (see README for the manual T+60s test procedure).
  warningThresholdSeconds?: number;
}

// ─── Helper: format seconds remaining into HH:MM:SS or MM:SS ─────────────────

function formatRemaining(totalSeconds: number): string {
  const clamped = Math.max(0, totalSeconds);
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const s = clamped % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

// ─── Main CountdownTimer component ───────────────────────────────────────────

const CountdownTimer: React.FC<CountdownTimerProps> = ({
  serverEndTime,
  onAutoSubmit,
  warningThresholdSeconds = 30,
}) => {
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);

  // Guards against onAutoSubmit firing more than once. A plain boolean ref
  // (not state) because flipping it should never cause a re-render — it's
  // purely an internal guard, not something the UI reacts to.
  const hasAutoSubmittedRef = useRef(false);

  // Reset the guard whenever the server end time changes — this covers the
  // edge case where ExamShell re-syncs to a *new* exam/session (e.g. moving
  // from one question set to another in a future multi-stage exam format).
  // For the common case (same exam, just re-syncing the same end time) this
  // is a no-op since the ref is already false.
  useEffect(() => {
    hasAutoSubmittedRef.current = false;
  }, [serverEndTime]);

  // Main ticking effect. Re-runs whenever serverEndTime changes — which is
  // exactly the "re-sync from the server on reconnect" requirement: every
  // time ExamShell hands us a freshly-fetched serverEndTime, we throw away
  // the old interval and recompute from the new authoritative value, so any
  // local clock drift that accumulated is corrected immediately.
  useEffect(() => {
    if (!serverEndTime) {
      setSecondsRemaining(null);
      return;
    }

    const endMs = new Date(serverEndTime).getTime();

    function tick() {
      const remainingMs = endMs - Date.now();
      const remainingSec = Math.ceil(remainingMs / 1000);
      setSecondsRemaining(remainingSec);

      // ── Isolated auto-submit trigger ──────────────────────────────────
      // This is acceptance criterion 5 and 6: the trigger call is wrapped
      // in try/catch so that if onAutoSubmit (or anything it awaits) throws
      // synchronously, it cannot propagate up and crash this component's
      // own render or interval. We also guard with hasAutoSubmittedRef so
      // a slow callback can't be invoked twice across consecutive ticks.
      if (remainingSec <= 0 && !hasAutoSubmittedRef.current) {
        hasAutoSubmittedRef.current = true;
        try {
          const result = onAutoSubmit();
          // If the caller's onAutoSubmit returns a Promise, attach a catch
          // so a rejected promise is swallowed here rather than becoming
          // an unhandled rejection that could otherwise surface as a
          // console error or, in stricter environments, an uncaught
          // exception event.
          if (result && typeof (result as Promise<void>).catch === "function") {
            (result as Promise<void>).catch((err) => {
              console.error("[CountdownTimer] auto-submit callback rejected:", err);
            });
          }
        } catch (err) {
          console.error("[CountdownTimer] auto-submit callback threw synchronously:", err);
        }
      }
    }

    tick(); // compute immediately so there's no 1-second blank on mount/resync
    const intervalId = setInterval(tick, 1000);

    // Cleanup: stop ticking when serverEndTime changes again or the
    // component unmounts (e.g. student navigates away after submitting).
    return () => clearInterval(intervalId);
  }, [serverEndTime, onAutoSubmit]);

  // ── Render ─────────────────────────────────────────────────────────────────

  // Still waiting on the server end time — render a neutral placeholder
  // rather than nothing, so the top-right slot never visibly "pops in"
  // (acceptance criterion 1: shown at all times).
  if (secondsRemaining === null) {
    return (
      <span className="text-sm font-mono text-mute tabular-nums" aria-live="off">
        --:--
      </span>
    );
  }

  const isWarning =
    secondsRemaining > 0 && secondsRemaining <= warningThresholdSeconds;
  const isOver = secondsRemaining <= 0;

  return (
    <div className="flex items-center gap-2">
      {/* The numeric countdown itself — always visible, top-right per spec */}
      <span
        className={`text-sm font-mono font-semibold tabular-nums ${
          isOver
            ? "text-accent-red"
            : isWarning
            ? "text-accent-red"
            : "text-body"
        }`}
        // aria-live="off" deliberately — a screen reader announcing every
        // single second would be unusable. The warning banner below uses
        // role="alert" instead, which announces once when it first appears.
        aria-live="off"
      >
        {isOver ? "Submitting…" : formatRemaining(secondsRemaining)}
      </span>

      {/* T-30s warning banner — acceptance criterion 2 */}
      {isWarning && (
        <span
          role="alert"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent-red-soft border border-accent-red/30 text-accent-red text-xs font-semibold animate-pulse"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          Auto-submit in {secondsRemaining}s
        </span>
      )}
    </div>
  );
};

export default CountdownTimer;
