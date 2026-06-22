// frontend/src/components/exam/ExamErrorBoundary.tsx
// AEGIS-40: Error boundary isolating the question/answer area from the
// CountdownTimer.
//
// React error boundaries only catch errors in the component tree BELOW
// them. By wrapping just the question-rendering area (QuestionRenderer +
// ProgressSidebar) in this boundary — and keeping CountdownTimer as a
// SIBLING outside the boundary, not a child — a thrown error in question
// rendering unmounts only the question area. The CountdownTimer keeps
// running in its own part of the tree, completely unaffected, and its
// setInterval continues ticking toward auto-submit.
//
// This directly satisfies acceptance criterion 5: "Auto-submit cannot be
// blocked by a JS error in other components."

import React, { ErrorInfo, ReactNode } from "react";

interface ExamErrorBoundaryProps {
  children: ReactNode;
}

interface ExamErrorBoundaryState {
  hasError: boolean;
}

class ExamErrorBoundary extends React.Component<
  ExamErrorBoundaryProps,
  ExamErrorBoundaryState
> {
  constructor(props: ExamErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  // React calls this when a descendant component throws during render.
  static getDerivedStateFromError(): ExamErrorBoundaryState {
    return { hasError: true };
  }

  // Log the error for debugging — does not affect the CountdownTimer,
  // which lives outside this boundary in ExamShell's render tree.
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ExamErrorBoundary] caught error in question area:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-accent-red-soft border border-accent-red/30 rounded-md p-6 text-center">
          <p className="text-sm font-semibold text-ink mb-1">
            Something went wrong displaying this question
          </p>
          <p className="text-sm text-body">
            Your timer is still running and your answers so far are safe.
            Try reloading the page — if the problem persists, contact your
            professor before time runs out.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ExamErrorBoundary;
