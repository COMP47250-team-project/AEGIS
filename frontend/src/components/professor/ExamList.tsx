import React, { useCallback, useEffect, useState } from "react";
import apiClient from "../../api/client";
import ExamGradeView from "./ExamGradeView";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExamRow {
  id: string;
  quiz_id: string;
  quiz_title: string | null;
  course_id: string;
  scheduled_start: string;
  duration_minutes: number;
  state: "draft" | "open" | "closed";
  enrollment_count: number;
}

interface StudentOption {
  id: string;
  email: string;
  name: string | null;
}

interface EnrollmentEntry {
  id: string;
  student_id: string;
  enrolled_at: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATE_BADGE: Record<string, { label: string; classes: string }> = {
  draft: { label: "Draft", classes: "bg-surface-soft text-mute" },
  open: { label: "Open", classes: "bg-accent-green-soft text-accent-green border border-accent-green/20" },
  closed: { label: "Closed", classes: "bg-accent-red-soft text-accent-red border border-accent-red/20" },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

// ---------------------------------------------------------------------------
// Enroll panel — shown inline below a draft exam row
// ---------------------------------------------------------------------------

interface EnrollPanelProps {
  examId: string;
  onClose: () => void;
  onUpdated: () => void;
}

const EnrollPanel: React.FC<EnrollPanelProps> = ({ examId, onClose, onUpdated }) => {
  const [allStudents, setAllStudents] = useState<StudentOption[]>([]);
  const [enrollments, setEnrollments] = useState<EnrollmentEntry[]>([]);
  const [emailInput, setEmailInput] = useState("");
  const [working, setWorking] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const reload = useCallback(async () => {
    const [students, enrolled] = await Promise.all([
      apiClient.get<StudentOption[]>("/users/students"),
      apiClient.get<EnrollmentEntry[]>(`/exams/${examId}/enrollments`),
    ]);
    setAllStudents(students.data);
    setEnrollments(enrolled.data);
  }, [examId]);

  useEffect(() => {
    reload().catch(() => setMsg({ text: "Failed to load students.", ok: false }));
  }, [reload]);

  const enrolledIds = new Set(enrollments.map((e) => e.student_id));
  const unenrolledStudents = allStudents.filter((s) => !enrolledIds.has(s.id));

  async function handleEnrollByEmail(e: React.FormEvent) {
    e.preventDefault();
    if (!emailInput.trim()) return;
    setWorking(true);
    setMsg(null);
    try {
      await apiClient.post(`/exams/${examId}/enroll-by-email`, { email: emailInput.trim() });
      setEmailInput("");
      setMsg({ text: "Student enrolled.", ok: true });
      await reload();
      onUpdated();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMsg({ text: detail ?? "Enrollment failed.", ok: false });
    } finally {
      setWorking(false);
    }
  }

  async function handleEnrollById(studentId: string) {
    setWorking(true);
    setMsg(null);
    try {
      await apiClient.post(`/exams/${examId}/enrollments`, { student_id: studentId });
      setMsg({ text: "Student enrolled.", ok: true });
      await reload();
      onUpdated();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMsg({ text: detail ?? "Enrollment failed.", ok: false });
    } finally {
      setWorking(false);
    }
  }

  async function handleUnenroll(studentId: string) {
    setWorking(true);
    setMsg(null);
    try {
      await apiClient.delete(`/exams/${examId}/enrollments/${studentId}`);
      await reload();
      onUpdated();
    } catch {
      setMsg({ text: "Could not remove student.", ok: false });
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="bg-surface-doc border border-hairline rounded-md p-4 mt-1 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">Manage Enrollment</h3>
        <button onClick={onClose} className="text-xs text-mute hover:text-ink">✕ Close</button>
      </div>

      {/* Enroll by email */}
      <form onSubmit={handleEnrollByEmail} className="flex gap-2">
        <input
          type="email"
          placeholder="student@example.com"
          value={emailInput}
          onChange={(e) => setEmailInput(e.target.value)}
          className="flex-1 border border-hairline rounded px-2 py-1.5 text-sm text-ink bg-surface-card focus:outline-none focus:ring-1 focus:ring-surface-dark"
        />
        <button
          type="submit"
          disabled={working || !emailInput.trim()}
          className="px-3 py-1.5 bg-primary text-ink text-xs font-semibold rounded disabled:opacity-50"
        >
          Enroll by email
        </button>
      </form>

      {msg && (
        <p className={`text-xs ${msg.ok ? "text-accent-green" : "text-accent-red"}`}>
          {msg.text}
        </p>
      )}

      {/* Currently enrolled */}
      {enrollments.length > 0 && (
        <div>
          <p className="text-xs font-medium text-mute mb-2">Enrolled ({enrollments.length})</p>
          <ul className="space-y-1 max-h-40 overflow-y-auto">
            {enrollments.map((e) => {
              const student = allStudents.find((s) => s.id === e.student_id);
              return (
                <li key={e.id} className="flex items-center justify-between text-xs text-body py-1 border-b border-hairline-soft">
                  <span>{student ? `${student.name ?? student.email} (${student.email})` : e.student_id}</span>
                  <button
                    onClick={() => handleUnenroll(e.student_id)}
                    disabled={working}
                    className="text-accent-red hover:opacity-70 text-xs ml-2 disabled:opacity-40"
                  >
                    Remove
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Quick-add from list */}
      {unenrolledStudents.length > 0 && (
        <div>
          <p className="text-xs font-medium text-mute mb-2">Available students</p>
          <ul className="space-y-1 max-h-40 overflow-y-auto">
            {unenrolledStudents.map((s) => (
              <li key={s.id} className="flex items-center justify-between text-xs text-body py-1 border-b border-hairline-soft">
                <span>{s.name ?? s.email} <span className="text-mute">({s.email})</span></span>
                <button
                  onClick={() => handleEnrollById(s.id)}
                  disabled={working}
                  className="text-accent-blue hover:opacity-70 text-xs ml-2 disabled:opacity-40"
                >
                  + Enroll
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {allStudents.length === 0 && enrollments.length === 0 && (
        <p className="text-xs text-mute">No students are registered yet. Ask students to sign up first.</p>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main ExamList
// ---------------------------------------------------------------------------

const ExamList: React.FC = () => {
  const [exams, setExams] = useState<ExamRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [working, setWorking] = useState<string | null>(null); // exam id being actioned
  const [expandEnroll, setExpandEnroll] = useState<string | null>(null); // exam id with enroll panel open
  const [gradeExamId, setGradeExamId] = useState<string | null>(null);

  const loadExams = useCallback(async () => {
    try {
      const r = await apiClient.get<ExamRow[]>("/exams");
      setExams(r.data);
    } catch {
      setError("Failed to load exams.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExams();
  }, [loadExams]);

  async function handleOpen(examId: string) {
    setWorking(examId);
    setActionMsg(null);
    try {
      await apiClient.post(`/exams/${examId}/open`);
      await loadExams();
      setActionMsg("Exam opened — students can now join.");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setActionMsg(detail ?? "Failed to open exam.");
    } finally {
      setWorking(null);
    }
  }

  async function handleClose(examId: string) {
    setWorking(examId);
    setActionMsg(null);
    try {
      await apiClient.post(`/exams/${examId}/close`);
      await loadExams();
      setActionMsg("Exam closed. Results are now available to students.");
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setActionMsg(detail ?? "Failed to close exam.");
    } finally {
      setWorking(null);
    }
  }

  if (loading) {
    return <p className="text-mute text-sm text-center py-10">Loading exams…</p>;
  }

  if (error) {
    return <p className="text-accent-red text-sm text-center py-10">{error}</p>;
  }

  if (gradeExamId) {
    const exam = exams.find((e) => e.id === gradeExamId);
    return (
      <div>
        <button
          onClick={() => setGradeExamId(null)}
          className="flex items-center gap-1 text-sm text-mute hover:text-ink mb-4"
        >
          ← Back to exam list
        </button>
        <ExamGradeView
          examId={gradeExamId}
          examTitle={exam?.quiz_title ?? exam?.course_id ?? "Exam"}
        />
      </div>
    );
  }

  if (exams.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-mute text-sm">No exams yet.</p>
        <p className="text-ash text-xs mt-1">Build a quiz and schedule an exam to get started.</p>
      </div>
    );
  }

  return (
    <div>
      {actionMsg && (
        <div className="mb-4 px-3 py-2 rounded bg-accent-blue-soft text-accent-blue text-sm border border-accent-blue/20">
          {actionMsg}
        </div>
      )}

      <div className="space-y-3">
        {exams.map((exam) => {
          const badge = STATE_BADGE[exam.state] ?? STATE_BADGE.closed;
          const isWorking = working === exam.id;
          const enrollOpen = expandEnroll === exam.id;

          return (
            <div key={exam.id} className="bg-surface-card border border-hairline rounded-md overflow-hidden">
              {/* Exam row */}
              <div className="p-4">
                <div className="flex items-start justify-between gap-4">
                  {/* Left: title + meta */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${badge.classes}`}>
                        {badge.label}
                      </span>
                      <span className="text-xs text-mute">{exam.enrollment_count} student{exam.enrollment_count !== 1 ? "s" : ""}</span>
                    </div>
                    <h3 className="text-sm font-semibold text-ink truncate">
                      {exam.quiz_title ?? "—"}{" "}
                      <span className="font-normal text-mute">· {exam.course_id}</span>
                    </h3>
                    <p className="text-xs text-mute mt-0.5">
                      {formatDate(exam.scheduled_start)} · {exam.duration_minutes} min
                    </p>
                  </div>

                  {/* Right: actions */}
                  <div className="flex items-center gap-2 flex-shrink-0 flex-wrap justify-end">
                    {exam.state === "draft" && (
                      <>
                        <button
                          onClick={() => setExpandEnroll(enrollOpen ? null : exam.id)}
                          className={`px-2.5 py-1.5 text-xs font-semibold rounded border transition-colors ${
                            enrollOpen
                              ? "bg-surface-dark text-on-dark border-surface-dark"
                              : "bg-surface-soft text-body border-hairline hover:bg-surface-card"
                          }`}
                        >
                          Enroll Students
                        </button>
                        <button
                          onClick={() => handleOpen(exam.id)}
                          disabled={isWorking || exam.enrollment_count === 0}
                          title={exam.enrollment_count === 0 ? "Enroll at least one student first" : "Open this exam"}
                          className="px-2.5 py-1.5 text-xs font-semibold rounded bg-accent-green text-white hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
                        >
                          {isWorking ? "Opening…" : "Open Exam"}
                        </button>
                      </>
                    )}

                    {exam.state === "open" && (
                      <button
                        onClick={() => handleClose(exam.id)}
                        disabled={isWorking}
                        className="px-2.5 py-1.5 text-xs font-semibold rounded bg-accent-red text-white hover:opacity-90 disabled:opacity-40 transition-opacity"
                      >
                        {isWorking ? "Closing…" : "Close Exam"}
                      </button>
                    )}

                    {exam.state === "closed" && (
                      <button
                        onClick={() => setGradeExamId(exam.id)}
                        className="px-2.5 py-1.5 text-xs font-semibold rounded bg-primary text-ink hover:bg-primary-pressed transition-colors"
                      >
                        View Grades
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Inline enroll panel */}
              {enrollOpen && (
                <div className="border-t border-hairline px-4 pb-4 pt-0">
                  <EnrollPanel
                    examId={exam.id}
                    onClose={() => setExpandEnroll(null)}
                    onUpdated={loadExams}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ExamList;
