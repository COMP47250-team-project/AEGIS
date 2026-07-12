// frontend/src/components/exam/SubmitConfirmModal.tsx
// AEGIS-41: Confirmation modal shown before a manual exam submission.
//
// Acceptance criteria covered:
//   ✅ Clicking Submit Exam shows a modal with the text:
//      "Are you sure? You cannot return."
//
// This component is purely presentational — it does not know about the
// submit API call, telemetry, or the WebSocket. It just asks "are you
// sure?" and reports the answer via onConfirm/onCancel. ExamShell owns
// what actually happens on confirm (see submitAndLeave).

import React from "react";

interface SubmitConfirmModalProps {
  isOpen: boolean;
  isSubmitting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const SubmitConfirmModal: React.FC<SubmitConfirmModalProps> = ({
  isOpen,
  isSubmitting,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="submit-confirm-title"
    >
      <div className="max-w-sm w-full bg-surface-card rounded-md border border-hairline p-6">
        <h2
          id="submit-confirm-title"
          className="text-base font-semibold text-ink mb-2"
        >
          Are you sure? You cannot return.
        </h2>
        <p className="text-sm text-body mb-6">
          Once you submit, your answers are final and you won't be able to come
          back into this exam.
        </p>
        <div className="flex flex-col gap-2">
          <button
            onClick={onConfirm}
            disabled={isSubmitting}
            data-testid="confirm-submit"
            className="w-full py-2.5 px-4 bg-primary disabled:bg-surface-soft disabled:text-ash text-ink text-sm font-bold rounded-md transition-colors"
          >
            {isSubmitting ? "Submitting…" : "Yes, submit my exam"}
          </button>
          <button
            onClick={onCancel}
            disabled={isSubmitting}
            className="w-full py-2.5 px-4 bg-surface-soft disabled:text-ash text-ink text-sm font-bold rounded-md transition-colors"
          >
            Cancel, go back
          </button>
        </div>
      </div>
    </div>
  );
};

export default SubmitConfirmModal;
