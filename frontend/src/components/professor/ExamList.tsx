import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
  results_released: boolean;
  has_short_answers: boolean;
  // AEGIS-121: closed_book | open_book — drives the "Manage resources" action.
  mode: "closed_book" | "open_book";
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
  open: {
    label: "Open",
    classes:
      "bg-accent-green-soft text-accent-green border border-accent-green/20",
  },
  closed: {
    label: "Closed",
    classes: "bg-accent-red-soft text-accent-red border border-accent-red/20",
  },
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

// ---------------------------------------------------------------------------
// CSV bulk enroll section
// ---------------------------------------------------------------------------

interface ParsedRow {
  email: string;
  name: string;
}

function parseCSV(raw: string): { valid: ParsedRow[]; invalid: string[] } {
  const lines = raw
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  const valid: ParsedRow[] = [];
  const invalid: string[] = [];
  const seen = new Set<string>();
  for (const line of lines) {
    const cols = line.split(",").map((c) => c.trim());
    const email = cols[0] ?? "";
    const name = cols[1] ?? "";
    if (email.toLowerCase() === "email") continue;
    if (!email.includes("@")) {
      invalid.push(line);
      continue;
    }
    if (seen.has(email.toLowerCase())) continue;
    seen.add(email.toLowerCase());
    valid.push({ email, name });
  }
  return { valid, invalid };
}

const CsvEnrollSection: React.FC<{ examId: string; onUpdated: () => void }> = ({
  examId,
  onUpdated,
}) => {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [parsed, setParsed] = React.useState<{
    valid: ParsedRow[];
    invalid: string[];
  } | null>(null);
  const [working, setWorking] = React.useState(false);
  // AEGIS-119: distinguish newly enrolled, already-enrolled (skipped), and
  // unknown-email students by name/email — not just a single count.
  const [result, setResult] = React.useState<{
    enrolled: number;
    skipped: string[];
    notFound: string[];
    failed: string[];
  } | null>(null);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      setParsed(parseCSV(ev.target?.result as string));
      setResult(null);
    };
    reader.readAsText(file);
  }

  async function handleEnroll() {
    if (!parsed || parsed.valid.length === 0) return;
    setWorking(true);
    let enrolled = 0;
    const skipped: string[] = [];
    const notFound: string[] = [];
    const failed: string[] = [];
    const label = (row: ParsedRow) =>
      row.name ? `${row.name} (${row.email})` : row.email;
    for (const row of parsed.valid) {
      try {
        await apiClient.post(`/exams/${examId}/enroll-by-email`, {
          email: row.email,
        });
        enrolled++;
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response
          ?.status;
        if (status === 409) {
          skipped.push(label(row)); // already enrolled
        } else if (status === 404) {
          notFound.push(label(row)); // no student with that email
        } else {
          failed.push(label(row));
        }
      }
    }
    setResult({ enrolled, skipped, notFound, failed });
    setWorking(false);
    onUpdated();
  }

  return (
    <div className="border-t border-hairline pt-3 space-y-2">
      <p className="text-xs font-medium text-mute">Bulk enroll via CSV</p>
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        onChange={handleFile}
        className="hidden"
      />
      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        className="px-3 py-1.5 bg-surface-soft text-ink text-xs font-semibold rounded border border-hairline"
      >
        Choose CSV file
      </button>
      <p className="text-xs text-ash">
        Format: <code>email,name</code> — one student per row
      </p>

      {parsed && (
        <div className="space-y-2">
          {parsed.valid.length > 0 && (
            <div>
              <p className="text-xs text-mute mb-1">
                {parsed.valid.length} student
                {parsed.valid.length !== 1 ? "s" : ""} parsed
                {parsed.valid.length > 5 ? " (showing first 5)" : ""}
              </p>
              <table className="w-full text-xs border border-hairline rounded overflow-hidden">
                <thead className="bg-surface-soft">
                  <tr>
                    <th className="text-left px-2 py-1 text-mute">Email</th>
                    <th className="text-left px-2 py-1 text-mute">Name</th>
                  </tr>
                </thead>
                <tbody>
                  {parsed.valid.slice(0, 5).map((row, i) => (
                    <tr key={i} className="border-t border-hairline">
                      <td className="px-2 py-1 text-ink">{row.email}</td>
                      <td className="px-2 py-1 text-body">{row.name || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button
                type="button"
                onClick={handleEnroll}
                disabled={working}
                className="mt-2 w-full py-1.5 bg-primary text-ink text-xs font-semibold rounded disabled:opacity-50"
              >
                {working
                  ? "Enrolling…"
                  : `Enroll ${parsed.valid.length} student${parsed.valid.length !== 1 ? "s" : ""}`}
              </button>
            </div>
          )}
          {parsed.invalid.length > 0 && (
            <div className="px-3 py-2 bg-accent-red-soft border-l-2 border-accent-red rounded">
              <p className="text-xs font-semibold text-ink mb-1">
                {parsed.invalid.length} invalid row
                {parsed.invalid.length !== 1 ? "s" : ""} skipped:
              </p>
              {parsed.invalid.slice(0, 3).map((l, i) => (
                <p key={i} className="text-xs font-mono text-body">
                  {l}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {result && (
        <div
          className={`px-3 py-2 rounded border-l-2 space-y-1 ${
            result.failed.length === 0 && result.notFound.length === 0
              ? "bg-accent-green-soft border-accent-green"
              : "bg-accent-red-soft border-accent-red"
          }`}
        >
          <p className="text-xs font-semibold text-ink">
            {result.enrolled} user{result.enrolled !== 1 ? "s" : ""} enrolled
            successfully.
          </p>
          {result.skipped.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-body">
                {result.skipped.length} user
                {result.skipped.length !== 1 ? "s" : ""} skipped (already
                enrolled):
              </p>
              {result.skipped.map((e, i) => (
                <p key={i} className="text-xs text-body pl-2">
                  • {e}
                </p>
              ))}
            </div>
          )}
          {result.notFound.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-body">
                {result.notFound.length} not found (no student with that email):
              </p>
              {result.notFound.map((e, i) => (
                <p key={i} className="text-xs text-body pl-2">
                  • {e}
                </p>
              ))}
            </div>
          )}
          {result.failed.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-body">
                {result.failed.length} failed:
              </p>
              {result.failed.map((e, i) => (
                <p key={i} className="text-xs text-body pl-2">
                  • {e}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Enroll panel — shown inline below a draft exam row
// ---------------------------------------------------------------------------

interface EnrollPanelProps {
  examId: string;
  onClose: () => void;
  onUpdated: () => void;
}

const EnrollPanel: React.FC<EnrollPanelProps> = ({
  examId,
  onClose,
  onUpdated,
}) => {
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
    reload().catch(() =>
      setMsg({ text: "Failed to load students.", ok: false }),
    );
  }, [reload]);

  const enrolledIds = new Set(enrollments.map((e) => e.student_id));
  const unenrolledStudents = allStudents.filter((s) => !enrolledIds.has(s.id));

  async function handleEnrollByEmail(e: React.FormEvent) {
    e.preventDefault();
    if (!emailInput.trim()) return;
    setWorking(true);
    setMsg(null);
    try {
      await apiClient.post(`/exams/${examId}/enroll-by-email`, {
        email: emailInput.trim(),
      });
      setEmailInput("");
      setMsg({ text: "Student enrolled.", ok: true });
      await reload();
      onUpdated();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setMsg({ text: detail ?? "Enrollment failed.", ok: false });
    } finally {
      setWorking(false);
    }
  }

  async function handleEnrollById(studentId: string) {
    setWorking(true);
    setMsg(null);
    try {
      await apiClient.post(`/exams/${examId}/enrollments`, {
        student_id: studentId,
      });
      setMsg({ text: "Student enrolled.", ok: true });
      await reload();
      onUpdated();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
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
        <button onClick={onClose} className="text-xs text-mute hover:text-ink">
          ✕ Close
        </button>
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
        <p
          className={`text-xs ${msg.ok ? "text-accent-green" : "text-accent-red"}`}
        >
          {msg.text}
        </p>
      )}

      {/* Bulk enroll via CSV */}
      <CsvEnrollSection
        examId={examId}
        onUpdated={() => {
          reload();
          onUpdated();
        }}
      />

      {/* Currently enrolled */}
      {enrollments.length > 0 && (
        <div>
          <p className="text-xs font-medium text-mute mb-2">
            Enrolled ({enrollments.length})
          </p>
          <ul className="space-y-1 max-h-40 overflow-y-auto">
            {enrollments.map((e) => {
              const student = allStudents.find((s) => s.id === e.student_id);
              return (
                <li
                  key={e.id}
                  className="flex items-center justify-between text-xs text-body py-1 border-b border-hairline-soft"
                >
                  <span>
                    {student
                      ? `${student.name ?? student.email} (${student.email})`
                      : e.student_id}
                  </span>
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
          <p className="text-xs font-medium text-mute mb-2">
            Available students
          </p>
          <ul className="space-y-1 max-h-40 overflow-y-auto">
            {unenrolledStudents.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between text-xs text-body py-1 border-b border-hairline-soft"
              >
                <span>
                  {s.name ?? s.email}{" "}
                  <span className="text-mute">({s.email})</span>
                </span>
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
        <p className="text-xs text-mute">
          No students are registered yet. Ask students to sign up first.
        </p>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Manage resources panel — open-book allowlist for a draft exam (AEGIS-121)
// ---------------------------------------------------------------------------

interface ResourceEntry {
  id: string;
  label: string;
  type: "url" | "file";
  url: string | null;
  embed: boolean;
}

const ManageResourcesPanel: React.FC<{
  examId: string;
  onClose: () => void;
}> = ({ examId, onClose }) => {
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [resources, setResources] = useState<ResourceEntry[]>([]);
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [embed, setEmbed] = useState(false);
  const [working, setWorking] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const reload = useCallback(async () => {
    const { data } = await apiClient.get<ResourceEntry[]>(
      `/exams/${examId}/resources`,
    );
    setResources(data);
  }, [examId]);

  useEffect(() => {
    reload().catch(() =>
      setMsg({ text: "Failed to load resources.", ok: false }),
    );
  }, [reload]);

  async function addUrl(e: React.FormEvent) {
    e.preventDefault();
    if (!label.trim() || !url.trim()) return;
    setWorking(true);
    setMsg(null);
    try {
      await apiClient.post(`/exams/${examId}/resources`, {
        label: label.trim(),
        url: url.trim(),
        embed,
      });
      setLabel("");
      setUrl("");
      setEmbed(false);
      await reload();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setMsg({ text: detail ?? "Failed to add link.", ok: false });
    } finally {
      setWorking(false);
    }
  }

  async function uploadFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setWorking(true);
    setMsg(null);
    const form = new FormData();
    form.append("file", file);
    form.append("label", file.name);
    try {
      await apiClient.post(`/exams/${examId}/resources/file`, form);
      await reload();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setMsg({ text: detail ?? "Failed to upload file.", ok: false });
    } finally {
      setWorking(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function remove(resourceId: string) {
    setWorking(true);
    try {
      await apiClient.delete(`/exams/${examId}/resources/${resourceId}`);
      await reload();
    } catch {
      setMsg({ text: "Could not remove resource.", ok: false });
    } finally {
      setWorking(false);
    }
  }

  const inputClass =
    "flex-1 border border-hairline rounded px-2 py-1.5 text-sm text-ink bg-surface-card focus:outline-none focus:ring-1 focus:ring-surface-dark";

  return (
    <div className="bg-surface-doc border border-hairline rounded-md p-4 mt-1 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">Manage Resources</h3>
        <button onClick={onClose} className="text-xs text-mute hover:text-ink">
          ✕ Close
        </button>
      </div>

      {/* Add a URL */}
      <form onSubmit={addUrl} className="space-y-2">
        <div className="flex gap-2">
          <input
            className={inputClass}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label"
            aria-label="Resource label"
          />
          <input
            className={inputClass}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
            aria-label="Resource URL"
          />
          <button
            type="submit"
            disabled={working || !label.trim() || !url.trim()}
            className="px-3 py-1.5 bg-primary text-ink text-xs font-semibold rounded disabled:opacity-50 shrink-0"
          >
            Add link
          </button>
        </div>
        <label className="flex items-center gap-2 text-xs text-mute">
          <input
            type="checkbox"
            checked={embed}
            onChange={(e) => setEmbed(e.target.checked)}
          />
          Show inside the exam (embeddable sites only)
        </label>
      </form>

      {/* Upload a PDF */}
      <div className="border-t border-hairline pt-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={uploadFile}
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={working}
          className="px-3 py-1.5 bg-surface-soft text-ink text-xs font-semibold rounded border border-hairline disabled:opacity-50"
        >
          Upload PDF
        </button>
        <span className="text-xs text-ash ml-2">PDF only, up to 20 MB</span>
      </div>

      {msg && (
        <p
          className={`text-xs ${msg.ok ? "text-accent-green" : "text-accent-red"}`}
        >
          {msg.text}
        </p>
      )}

      {/* Current resources */}
      {resources.length > 0 ? (
        <ul className="space-y-1">
          {resources.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between text-xs text-body py-1 border-b border-hairline-soft"
            >
              <span className="min-w-0 truncate">
                <span className="mr-1.5">
                  {r.type === "file" ? "📄" : "🔗"}
                </span>
                {r.label}
                {r.url && <span className="text-mute"> — {r.url}</span>}
              </span>
              <button
                onClick={() => remove(r.id)}
                disabled={working}
                className="text-accent-red hover:opacity-70 ml-2 disabled:opacity-40 shrink-0"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-mute">No resources added yet.</p>
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
  const [working, setWorking] = useState<string | null>(null);
  const [expandEnroll, setExpandEnroll] = useState<string | null>(null);
  // AEGIS-121: which draft open-book exam's resource manager is open.
  const [expandResources, setExpandResources] = useState<string | null>(null);
  // AEGIS-119: the open grade/evaluate view lives in the URL (?grade=…) so a
  // hard refresh reopens it instead of dropping back to the exam list.
  const [searchParams, setSearchParams] = useSearchParams();
  const gradeExamId = searchParams.get("grade");
  const setGradeExamId = useCallback(
    (id: string | null) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (id) next.set("grade", id);
          else next.delete("grade");
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

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
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
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
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      setActionMsg(detail ?? "Failed to close exam.");
    } finally {
      setWorking(null);
    }
  }

  if (loading) {
    return (
      <p className="text-mute text-sm text-center py-10">Loading exams…</p>
    );
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
        <p className="text-ash text-xs mt-1">
          Build a quiz and schedule an exam to get started.
        </p>
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
          const resourcesOpen = expandResources === exam.id;

          return (
            <div
              key={exam.id}
              className="bg-surface-card border border-hairline rounded-md overflow-hidden"
            >
              <div className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${badge.classes}`}
                      >
                        {badge.label}
                      </span>
                      <span className="text-xs text-mute">
                        {exam.enrollment_count} student
                        {exam.enrollment_count !== 1 ? "s" : ""}
                      </span>
                    </div>
                    <h3 className="text-sm font-semibold text-ink truncate">
                      {exam.quiz_title ?? "—"}{" "}
                      <span className="font-normal text-mute">
                        · {exam.course_id}
                      </span>
                    </h3>
                    <p className="text-xs text-mute mt-0.5">
                      {formatDate(exam.scheduled_start)} ·{" "}
                      {exam.duration_minutes} min
                    </p>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0 flex-wrap justify-end">
                    {exam.state === "draft" && (
                      <>
                        <button
                          onClick={() =>
                            setExpandEnroll(enrollOpen ? null : exam.id)
                          }
                          className={`px-2.5 py-1.5 text-xs font-semibold rounded border transition-colors ${
                            enrollOpen
                              ? "bg-surface-dark text-on-dark border-surface-dark"
                              : "bg-surface-soft text-body border-hairline hover:bg-surface-card"
                          }`}
                        >
                          Enroll Students
                        </button>
                        {exam.mode === "open_book" && (
                          <button
                            onClick={() =>
                              setExpandResources(resourcesOpen ? null : exam.id)
                            }
                            className={`px-2.5 py-1.5 text-xs font-semibold rounded border transition-colors ${
                              resourcesOpen
                                ? "bg-surface-dark text-on-dark border-surface-dark"
                                : "bg-surface-soft text-body border-hairline hover:bg-surface-card"
                            }`}
                          >
                            Manage Resources
                          </button>
                        )}
                        <button
                          onClick={() => handleOpen(exam.id)}
                          disabled={isWorking || exam.enrollment_count === 0}
                          title={
                            exam.enrollment_count === 0
                              ? "Enroll at least one student first"
                              : "Open this exam"
                          }
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
                        {/* AEGIS-112b: "Evaluate" until short answers are graded
                            and released; MCQ-only exams go straight to View Grades */}
                        {exam.has_short_answers && !exam.results_released
                          ? "Evaluate"
                          : "View Grades"}
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {enrollOpen && (
                <div className="border-t border-hairline px-4 pb-4 pt-0">
                  <EnrollPanel
                    examId={exam.id}
                    onClose={() => setExpandEnroll(null)}
                    onUpdated={loadExams}
                  />
                </div>
              )}

              {resourcesOpen && (
                <div className="border-t border-hairline px-4 pb-4 pt-0">
                  <ManageResourcesPanel
                    examId={exam.id}
                    onClose={() => setExpandResources(null)}
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
