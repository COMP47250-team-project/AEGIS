import React, { useCallback, useEffect, useState } from "react";
import apiClient from "../../api/client";

interface GroupSummary {
  id: string;
  name: string;
  member_count: number;
}
interface Member {
  student_id: string;
  email: string;
  name: string | null;
}
interface Skip {
  email: string;
  reason: string;
}
interface GroupDetail {
  id: string;
  name: string;
  members: Member[];
  skipped?: Skip[];
}
interface ValidationResult {
  matched: Member[];
  skipped: Skip[];
}
interface ExamRow {
  id: string;
  quiz_title: string | null;
  course_id: string;
  state: string;
}

const inputClass =
  "w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark";
const primaryBtn =
  "px-3 py-1.5 bg-primary text-ink text-xs font-semibold rounded disabled:opacity-50 hover:bg-primary-pressed transition-colors";
const secondaryBtn =
  "px-3 py-1.5 border border-hairline text-ink text-xs font-semibold rounded hover:bg-surface-soft disabled:opacity-50 transition-colors";

// Always return a string. FastAPI 422s return `detail` as a list of objects,
// which must never reach JSX (React can't render an object -> blank screen).
function errorDetail(err: unknown): string | undefined {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
      .filter(Boolean);
    return msgs.length ? msgs.join(", ") : undefined;
  }
  return undefined;
}

// Free-text emails: split on commas/semicolons/newlines. Duplicates are kept so
// the backend can report them (it dedupes and flags repeats).
function splitEmails(text: string): string[] {
  return text.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean);
}

// CSV: one student per row, email in the first column (email[,name]). Header
// row "email" is skipped; duplicates are kept for reporting.
function parseCsvEmails(text: string): string[] {
  const out: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    const first = (line.split(",")[0] ?? "").trim();
    if (!first || first.toLowerCase() === "email") continue;
    out.push(first);
  }
  return out;
}

const GroupsManager: React.FC = () => {
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [name, setName] = useState("");
  const [emailRows, setEmailRows] = useState<string[]>([""]);
  const [csvEmails, setCsvEmails] = useState<string[]>([]);
  const [csvFileCount, setCsvFileCount] = useState(0);
  const [pending, setPending] = useState<ValidationResult | null>(null);
  const [detail, setDetail] = useState<GroupDetail | null>(null);
  const [editEmails, setEditEmails] = useState("");
  const [editSkipped, setEditSkipped] = useState<Skip[]>([]);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [exams, setExams] = useState<ExamRow[]>([]);
  const [examId, setExamId] = useState("");
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  const loadGroups = useCallback(() => {
    apiClient
      .get<GroupSummary[]>("/groups")
      .then(({ data }) => setGroups(data))
      .catch(() => setMsg({ text: "Failed to load groups", ok: false }));
  }, []);

  useEffect(() => {
    loadGroups();
    apiClient
      .get<ExamRow[]>("/exams")
      .then(({ data }) => {
        const draft = data.filter((e) => e.state === "draft");
        setExams(draft);
        if (draft[0]) setExamId(draft[0].id);
      })
      .catch(() => {});
  }, [loadGroups]);

  function collectEmails(): string[] {
    return [...emailRows.map((r) => r.trim()).filter(Boolean), ...csvEmails];
  }

  function resetCreateForm() {
    setName("");
    setEmailRows([""]);
    setCsvEmails([]);
    setCsvFileCount(0);
    setPending(null);
  }

  function setRow(i: number, value: string) {
    setEmailRows((rows) => rows.map((r, idx) => (idx === i ? value : r)));
  }
  function addRow() {
    setEmailRows((rows) => [...rows, ""]);
  }
  function removeRow(i: number) {
    setEmailRows((rows) => (rows.length === 1 ? [""] : rows.filter((_, idx) => idx !== i)));
  }

  // Upload one or more CSV files; accumulate their emails and re-run validation.
  async function handleCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = ""; // allow re-uploading the same file
    if (files.length === 0) return;
    const parsed = (await Promise.all(files.map((f) => f.text()))).flatMap(parseCsvEmails);
    const nextCsv = [...csvEmails, ...parsed];
    setCsvEmails(nextCsv);
    setCsvFileCount((n) => n + files.length);
    await review([...emailRows.map((r) => r.trim()).filter(Boolean), ...nextCsv]);
  }

  // Dry-run validation; show a preview of who will be added and who is skipped.
  async function review(emails: string[]) {
    setBusy(true);
    setMsg(null);
    try {
      const { data } = await apiClient.post<ValidationResult>("/groups/validate", {
        student_emails: emails,
      });
      setPending(data);
    } catch {
      setMsg({ text: "Failed to check emails", ok: false });
    } finally {
      setBusy(false);
    }
  }

  async function reviewAndCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    const emails = collectEmails();
    if (emails.length === 0) {
      await doCreate([]); // deliberately empty group
      return;
    }
    await review(emails);
  }

  async function doCreate(emails: string[]) {
    setBusy(true);
    setMsg(null);
    try {
      const { data } = await apiClient.post<GroupDetail>("/groups", {
        name: name.trim(),
        student_emails: emails,
      });
      const n = data.members.length;
      resetCreateForm();
      setMsg({ text: `Group "${data.name}" created with ${n} student${n === 1 ? "" : "s"}.`, ok: true });
      loadGroups();
    } catch (err) {
      setMsg({ text: errorDetail(err) ?? "Failed to create group", ok: false });
    } finally {
      setBusy(false);
    }
  }

  function openGroup(id: string) {
    setEditEmails("");
    setEditSkipped([]);
    setConfirmDelete(false);
    apiClient
      .get<GroupDetail>(`/groups/${id}`)
      .then(({ data }) => setDetail(data))
      .catch(() => setMsg({ text: "Failed to load group", ok: false }));
  }

  async function removeMember(email: string) {
    if (!detail) return;
    setBusy(true);
    setMsg(null);
    try {
      const { data } = await apiClient.put<GroupDetail>(`/groups/${detail.id}/members`, {
        remove: [email],
      });
      setDetail(data);
      loadGroups();
    } catch {
      setMsg({ text: "Failed to remove member", ok: false });
    } finally {
      setBusy(false);
    }
  }

  async function addMembers() {
    if (!detail) return;
    const emails = splitEmails(editEmails);
    if (emails.length === 0) {
      setEditSkipped([]);
      setMsg({ text: "Enter at least one email to add.", ok: false });
      return;
    }
    setBusy(true);
    setMsg(null);
    setEditSkipped([]);
    try {
      const { data } = await apiClient.put<GroupDetail>(`/groups/${detail.id}/members`, {
        add: emails,
      });
      setDetail(data);
      setEditEmails("");
      const dropped = data.skipped ?? [];
      setEditSkipped(dropped);
      setMsg({
        text: dropped.length ? `Added the valid emails. ${dropped.length} skipped.` : "Members added.",
        ok: dropped.length === 0,
      });
      loadGroups();
    } catch {
      setMsg({ text: "Failed to add members", ok: false });
    } finally {
      setBusy(false);
    }
  }

  async function handleEditCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;
    const parsed = (await Promise.all(files.map((f) => f.text()))).flatMap(parseCsvEmails);
    setEditEmails((prev) => [prev, ...parsed].filter(Boolean).join("\n"));
  }

  async function deleteGroup() {
    if (!detail) return;
    setBusy(true);
    setMsg(null);
    try {
      await apiClient.delete(`/groups/${detail.id}`);
      setMsg({ text: `Deleted "${detail.name}".`, ok: true });
      setDetail(null);
      setConfirmDelete(false);
      loadGroups();
    } catch {
      setMsg({ text: "Failed to delete group", ok: false });
    } finally {
      setBusy(false);
    }
  }

  async function enrollInExam() {
    if (!detail || !examId) return;
    setBusy(true);
    setMsg(null);
    try {
      const { data } = await apiClient.post<{ enrolled: number; group_size: number }>(
        `/exams/${examId}/enroll-group`,
        { group_id: detail.id }
      );
      setMsg({ text: `Enrolled ${data.enrolled} of ${data.group_size} in the exam.`, ok: true });
    } catch (err) {
      setMsg({ text: errorDetail(err) ?? "Enrol failed. The exam must be in draft state.", ok: false });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Create group */}
      <form onSubmit={reviewAndCreate} className="space-y-3">
        <h3 className="text-sm font-semibold text-ink">New group</h3>
        <input
          className={inputClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Group name (e.g. Computer Science 123)"
        />
        <div className="space-y-2">
          {emailRows.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="email"
                className={`${inputClass} flex-1`}
                value={row}
                onChange={(e) => setRow(i, e.target.value)}
                placeholder={`Student ${i + 1} (e.g. alice@ucd.ie)`}
                aria-label={`Student email ${i + 1}`}
              />
              <button
                type="button"
                onClick={() => removeRow(i)}
                disabled={emailRows.length === 1 && !row}
                aria-label={`Remove student ${i + 1}`}
                className="w-8 h-8 flex items-center justify-center rounded border border-hairline text-mute hover:text-ink disabled:opacity-40 transition-colors"
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={addRow}
            className="text-xs font-semibold text-accent-green hover:underline"
          >
            + Add student
          </button>
          <label className="text-xs font-semibold text-accent-green hover:underline cursor-pointer">
            Upload CSV
            <input
              type="file"
              accept=".csv,text/csv"
              multiple
              onChange={handleCsv}
              className="hidden"
              aria-label="Upload student emails CSV"
            />
          </label>
        </div>
        <p className="text-xs text-mute">
          Type one student per box, or upload CSV files (one email per row,
          format <code>email</code> or <code>email,name</code>). Only registered
          students are added; you can review everything before it is created.
        </p>
        {csvFileCount > 0 && (
          <p className="text-xs text-mute">
            Loaded {csvEmails.length} row{csvEmails.length === 1 ? "" : "s"} from {csvFileCount} file
            {csvFileCount === 1 ? "" : "s"}.{" "}
            <button
              type="button"
              onClick={() => {
                setCsvEmails([]);
                setCsvFileCount(0);
                setPending(null);
              }}
              className="text-accent-red hover:underline"
            >
              Clear CSV
            </button>
          </p>
        )}
        <button type="submit" disabled={busy || !name.trim()} className={primaryBtn}>
          Review &amp; create
        </button>

        {pending && (
          <div className="border border-hairline rounded p-3 space-y-2">
            {pending.matched.length > 0 ? (
              <>
                <p className="text-xs font-semibold text-ink">
                  {pending.matched.length} student{pending.matched.length === 1 ? "" : "s"} will be
                  added:
                </p>
                <ul className="text-xs text-body space-y-0.5 max-h-32 overflow-y-auto">
                  {pending.matched.map((m) => (
                    <li key={m.student_id}>{m.name ? `${m.name} (${m.email})` : m.email}</li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="text-xs font-semibold text-ink">No students can be added yet.</p>
            )}

            {pending.skipped.length > 0 && (
              <>
                <p className="text-xs font-semibold text-accent-red">
                  {pending.skipped.length} skipped:
                </p>
                <ul className="text-xs text-accent-red space-y-0.5 max-h-32 overflow-y-auto">
                  {pending.skipped.map((s, i) => (
                    <li key={`${s.email}-${i}`}>
                      {s.email}: {s.reason}
                    </li>
                  ))}
                </ul>
              </>
            )}

            <div className="flex flex-wrap gap-2 pt-1">
              <button type="button" onClick={() => setPending(null)} className={secondaryBtn}>
                Go back and fix
              </button>
              <button
                type="button"
                disabled={busy || pending.matched.length === 0}
                onClick={() => doCreate(pending.matched.map((m) => m.email))}
                className={primaryBtn}
              >
                Create group with {pending.matched.length}
              </button>
            </div>
          </div>
        )}

        {msg && (
          <p className={`text-xs ${msg.ok ? "text-accent-green" : "text-accent-red"}`} role="status">
            {msg.text}
          </p>
        )}
      </form>

      {/* Group list + detail */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-ink">Your groups</h3>
        {groups.length === 0 ? (
          <p className="text-xs text-mute">No groups yet.</p>
        ) : (
          <ul className="space-y-1">
            {groups.map((g) => (
              <li key={g.id}>
                <button
                  onClick={() => openGroup(g.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded border text-left text-sm transition-colors ${
                    detail?.id === g.id
                      ? "border-primary bg-primary/5"
                      : "border-hairline hover:bg-surface-soft"
                  }`}
                >
                  <span className="text-ink">{g.name}</span>
                  <span className="text-xs text-mute">
                    {g.member_count} member{g.member_count === 1 ? "" : "s"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {detail && (
          <div className="border border-hairline rounded p-3 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-ink">{detail.name}</p>
              {confirmDelete ? (
                <span className="flex items-center gap-2 text-xs">
                  <span className="text-mute">Delete group?</span>
                  <button
                    onClick={deleteGroup}
                    disabled={busy}
                    className="font-semibold text-accent-red hover:underline disabled:opacity-50"
                  >
                    Yes, delete
                  </button>
                  <button onClick={() => setConfirmDelete(false)} className="text-mute hover:text-ink">
                    Cancel
                  </button>
                </span>
              ) : (
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="text-xs text-mute hover:text-accent-red transition-colors"
                >
                  Delete
                </button>
              )}
            </div>

            {detail.members.length === 0 ? (
              <p className="text-xs text-mute">No members yet.</p>
            ) : (
              <ul className="text-xs text-body space-y-1">
                {detail.members.map((m) => (
                  <li key={m.student_id} className="flex items-center justify-between gap-2">
                    <span>{m.name ? `${m.name} (${m.email})` : m.email}</span>
                    <button
                      onClick={() => removeMember(m.email)}
                      disabled={busy}
                      aria-label={`Remove ${m.email}`}
                      className="text-mute hover:text-accent-red disabled:opacity-40 transition-colors"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {/* Add members to this group */}
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <input
                  className={`${inputClass} flex-1`}
                  value={editEmails}
                  onChange={(e) => setEditEmails(e.target.value)}
                  placeholder="Add students by email (comma or paste)"
                  aria-label="Add students by email"
                />
                <button onClick={addMembers} disabled={busy || !editEmails.trim()} className={primaryBtn}>
                  Add
                </button>
              </div>
              <label className="text-xs font-semibold text-accent-green hover:underline cursor-pointer">
                Upload CSV
                <input
                  type="file"
                  accept=".csv,text/csv"
                  multiple
                  onChange={handleEditCsv}
                  className="hidden"
                  aria-label="Upload student emails CSV to add"
                />
              </label>
            </div>
            {editSkipped.length > 0 && (
              <ul className="text-xs text-accent-red space-y-0.5">
                {editSkipped.map((s, i) => (
                  <li key={`${s.email}-${i}`}>
                    {s.email}: {s.reason}
                  </li>
                ))}
              </ul>
            )}

            {exams.length === 0 ? (
              <p className="text-xs text-mute">No draft exams to enrol into.</p>
            ) : (
              <div className="flex items-center gap-2 pt-1">
                <select
                  className={`${inputClass} flex-1`}
                  value={examId}
                  onChange={(e) => setExamId(e.target.value)}
                >
                  {exams.map((ex) => (
                    <option key={ex.id} value={ex.id}>
                      {ex.quiz_title ?? "Exam"} ({ex.course_id})
                    </option>
                  ))}
                </select>
                <button
                  onClick={enrollInExam}
                  disabled={busy || detail.members.length === 0}
                  className={`${primaryBtn} whitespace-nowrap`}
                >
                  Enrol in exam
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default GroupsManager;
