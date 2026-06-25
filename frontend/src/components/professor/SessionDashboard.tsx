import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../../api/client";

interface SessionSummary {
  id: string;
  quiz_title: string | null;
  course_id: string;
  scheduled_start: string;
  state: string;
  student_count: number;
  flagged_count: number;
}

interface SessionListResponse {
  items: SessionSummary[];
  total: number;
  page: number;
  page_size: number;
}

const REFRESH_MS = 30_000; // AEGIS-58: auto-refresh every 30s

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

const SessionDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    apiClient
      .get<SessionListResponse>("/sessions?status=active")
      .then(({ data }) => {
        setSessions(data.items);
        setError(false);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="w-6 h-6 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <p className="text-accent-red text-sm text-center py-12">
        Could not load active sessions. Retrying…
      </p>
    );
  }

  // Empty state — shown, not hidden (AEGIS-58).
  if (sessions.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-mute text-sm">No active exams right now.</p>
        <p className="text-ash text-xs mt-1">
          Open an exam from “My Exams” to start a live session.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {sessions.map((s) => (
        <button
          key={s.id}
          onClick={() => navigate(`/professor/session/${s.id}`)}
          className="text-left bg-surface-card border border-hairline rounded-md p-4 hover:border-surface-dark transition-colors focus:outline-none focus:ring-2 focus:ring-accent-blue/30"
        >
          <div className="flex items-start justify-between gap-2 mb-1">
            <h3 className="text-sm font-semibold text-ink">
              {s.quiz_title ?? s.course_id}
            </h3>
            {s.flagged_count > 0 && (
              <span className="flex-shrink-0 text-xs font-semibold px-2 py-0.5 rounded bg-accent-red-soft text-accent-red border border-accent-red/20">
                {s.flagged_count} flagged
              </span>
            )}
          </div>
          <p className="text-xs text-mute mb-3">{s.course_id}</p>
          <div className="flex items-center justify-between text-xs text-body">
            <span className="text-mute">{formatWhen(s.scheduled_start)}</span>
            <span className="font-medium text-ink">
              {s.student_count} student{s.student_count === 1 ? "" : "s"}
            </span>
          </div>
        </button>
      ))}
    </div>
  );
};

export default SessionDashboard;
