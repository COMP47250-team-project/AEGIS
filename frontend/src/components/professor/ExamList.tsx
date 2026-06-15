import React, { useEffect, useState } from "react";
import apiClient from "../../api/client";

interface ExamRow {
  id: string;
  quiz_id: string;
  course_id: string;
  scheduled_start: string;
  duration_minutes: number;
  state: "draft" | "open" | "closed";
  enrollment_count: number;
}

const STATE_BADGE: Record<string, { label: string; classes: string }> = {
  draft: { label: "Draft", classes: "bg-surface-soft text-mute" },
  open: { label: "Open", classes: "bg-accent-green-soft text-accent-green" },
  closed: { label: "Closed", classes: "bg-accent-red-soft text-accent-red" },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

const ExamList: React.FC = () => {
  const [exams, setExams] = useState<ExamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get<ExamRow[]>("/exams")
      .then((r) => setExams(r.data))
      .catch(() => setError("Failed to load exams."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <p className="text-mute text-sm text-center py-10">Loading exams…</p>
    );
  }

  if (error) {
    return <p className="text-accent-red text-sm text-center py-10">{error}</p>;
  }

  if (exams.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-mute text-sm">No exams yet.</p>
        <p className="text-ash text-xs mt-1">
          Build a quiz and schedule an exam to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left border-b border-hairline">
            <th className="pb-2 pr-4 text-mute font-medium">Course</th>
            <th className="pb-2 pr-4 text-mute font-medium">Scheduled</th>
            <th className="pb-2 pr-4 text-mute font-medium">Duration</th>
            <th className="pb-2 pr-4 text-mute font-medium">Students</th>
            <th className="pb-2 text-mute font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {exams.map((exam) => {
            const badge = STATE_BADGE[exam.state] ?? STATE_BADGE.closed;
            return (
              <tr key={exam.id} className="border-b border-hairline-soft">
                <td className="py-3 pr-4 text-ink font-medium">
                  {exam.course_id}
                </td>
                <td className="py-3 pr-4 text-body">
                  {formatDate(exam.scheduled_start)}
                </td>
                <td className="py-3 pr-4 text-body">
                  {exam.duration_minutes} min
                </td>
                <td className="py-3 pr-4 text-body">{exam.enrollment_count}</td>
                <td className="py-3">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${badge.classes}`}
                  >
                    {badge.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default ExamList;
