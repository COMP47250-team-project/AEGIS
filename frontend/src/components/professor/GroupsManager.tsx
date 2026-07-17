import React, { useCallback, useEffect, useState } from "react";
import apiClient from "../../api/client";
import { parseStudentEmails } from "../../pages/examCreate.helpers";

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

// Skip reason for a valid email with no matching student account. Those can be
// turned into invited accounts.
const UNREGISTERED = "no registered student with this email";

function errorDetail(err: unknown): string | undefined {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
}

const GroupsManager: React.FC = () => {
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [name, setName] = useState("");
  const [emailRows, setEmailRows] = useState<string[]>([""]);
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

  function setRow(i: number, value: string) {
    setEmailRows((rows) => rows.map((r, idx) => (idx === i ? value : r)));
  }
  function addRow() {
    setEmailRows((rows) => [...rows, ""]);
  }
  function removeRow(i: number) {
    setEmailRows((rows) => (rows.length === 1 ? [""] : rows.filter((_, idx) => idx !== i)));
  }

  // Create student accounts for these emails; returns the emails that now exist.
  async function inviteEmails(emails: string[]): Promise<string[]> {
    const { data } = await apiClient.post<{ created: Member[]; skipped: Skip[] }>(
      "/groups/invite-students",
      { emails }
    );
    return data.created.map((m) => m.email);
  }

  async function doCreate(emails: string[]) {
    setBusy(true);
    setMsg(null);
    try {
      const { data } = await apiClient.post<GroupDetail>("/groups", {
        name: name.trim(),
        student_emails: emails,
      });
      setPending(null);
      setName("");
      setEmailRows([""]);
      const n = data.members.length;
      setMsg({ text: `Group "${data.name}" created with ${n} student${n === 1 ? "" : "s"}.`, ok: true });
      loadGroups();
    } catch {
      setMsg({ text: "Failed to create group", ok: false });
    } finally {
      setBusy(false);
    }
  }

  async function createGroup(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    // Join rows so pasting several emails into one box still splits and dedupes.
    const parsed = parseStudentEmails(emailRows.join("\n"));
    if (emailRows.some((r) => r.trim()) && parsed.length === 0) {
      setPending(null);
      setMsg({ text: "No valid emails found. Type one student per box (e.g. alice@ucd.ie).", ok: false });
      return;
    }
    setBusy(true);
    setMsg(null);
    setPending(null);
    try {
      // Dry run first so we never create a group when some emails fail.
      const { data } = await apiClient.post<ValidationResult>("/groups/validate", {
        student_emails: parsed,
      });
      if (data.skipped.length > 0) {
        setPending(data); // ask the professor to fix or proceed
        return;
      }
      await doCreate(parsed);
    } catch {
      setMsg({ text: "Failed to check emails", ok: false });
    } finally {
      setBusy(false);
    }
  }

  // From the create confirm panel: create accounts for the unregistered emails,
  // then create the group with the valid + newly-created students.
  async function createWithInvited() {
    if (!pending) return;
    const toInvite = pending.skipped.filter((s) => s.reason === UNREGISTERED).map((s) => s.email);
    setBusy(true);
    setMsg(null);
    try {
      const created = await inviteEmails(toInvite);
      await doCreate([...pending.matched.map((m) => m.email), ...created]);
    } catch {
      setMsg({ text: "Failed to create accounts", ok: false });
      setBusy(false);
    }
  }

  // From the edit panel: create accounts for these emails, then add them.
  async function addInvited(emails: string[]) {
    if (!detail) return;
    setBusy(true);
    setMsg(null);
    try {
      const created = await inviteEmails(emails);
      const { data } = await apiClient.put<GroupDetail>(`/groups/${detail.id}/members`, {
        add: created,
      });
      setDetail(data);
      setEditSkipped(data.skipped ?? []);
      setMsg({
        text: `Created ${created.length} account${created.length === 1 ? "" : "s"} and added them.`,
        ok: true,
      });
      loadGroups();
    } catch {
      setMsg({ text: "Failed to create accounts", ok: false });
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
    const parsed = parseStudentEmails(editEmails);
    if (parsed.length === 0) {
      setEditSkipped([]);
      setMsg({ text: "Enter at least one email to add.", ok: false });
      return;
    }
    setBusy(true);
    setMsg(null);
    setEditSkipped([]);
    try {
      const { data } = await apiClient.put<GroupDetail>(`/groups/${detail.id}/members`, {
        add: parsed,
      });
      setDetail(data);
      setEditEmails("");
      const dropped = data.skipped ?? [];
      setEditSkipped(dropped);
      setMsg({
        text: dropped.length
          ? `Added the valid emails. ${dropped.length} could not be added.`
          : "Members added.",
        ok: dropped.length === 0,
      });
      loadGroups();
    } catch {
      setMsg({ text: "Failed to add members", ok: false });
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

  const invitable = pending
    ? pending.skipped.filter((s) => s.reason === UNREGISTERED).map((s) => s.email)
    : [];
  const editInvitable = editSkipped
    .filter((s) => s.reason === UNREGISTERED)
    .map((s) => s.email);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Create group */}
      <form onSubmit={createGroup} className="space-y-3">
        <h3 className="text-sm font-semibold text-ink">New group</h3>
        <input
          className={inputClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Group name (e.g. CS Students 2026)"
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
        <button
          type="button"
          onClick={addRow}
          className="text-xs font-semibold text-accent-green hover:underline"
        >
          + Add student
        </button>
        <p className="text-xs text-mute">
          One student per box. Only registered students can be added; anything
          else is reported before the group is created.
        </p>
        <button type="submit" disabled={busy || !name.trim()} className={primaryBtn}>
          Create group
        </button>

        {pending && (
          <div className="border border-accent-red/40 rounded p-3 space-y-2">
            <p className="text-xs font-semibold text-ink">
              {pending.skipped.length} email{pending.skipped.length === 1 ? "" : "s"} could not
              be added:
            </p>
            <ul className="text-xs text-accent-red space-y-0.5">
              {pending.skipped.map((s) => (
                <li key={s.email}>
                  {s.email}: {s.reason}
                </li>
              ))}
            </ul>
            <p className="text-xs text-mute">
              Fix the emails above (they may be typos), create the group with the{" "}
              {pending.matched.length} valid one{pending.matched.length === 1 ? "" : "s"}, or
              create accounts for the ones that aren&apos;t registered yet.
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setPending(null)} className={secondaryBtn}>
                Go back and fix
              </button>
              {pending.matched.length > 0 && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => doCreate(pending.matched.map((m) => m.email))}
                  className={secondaryBtn}
                >
                  Create with {pending.matched.length} valid
                </button>
              )}
              {invitable.length > 0 && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={createWithInvited}
                  className={primaryBtn}
                >
                  Create {invitable.length} account{invitable.length === 1 ? "" : "s"} &amp; add
                </button>
              )}
            </div>
          </div>
        )}

        {msg && (
          <p
            className={`text-xs ${msg.ok ? "text-accent-green" : "text-accent-red"}`}
            role="status"
          >
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
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="text-mute hover:text-ink"
                  >
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
            <div className="flex items-center gap-2">
              <input
                className={`${inputClass} flex-1`}
                value={editEmails}
                onChange={(e) => setEditEmails(e.target.value)}
                placeholder="Add students by email (comma or paste)"
                aria-label="Add students by email"
              />
              <button
                onClick={addMembers}
                disabled={busy || !editEmails.trim()}
                className={primaryBtn}
              >
                Add
              </button>
            </div>
            {editSkipped.length > 0 && (
              <div className="space-y-2">
                <ul className="text-xs text-accent-red space-y-0.5">
                  {editSkipped.map((s) => (
                    <li key={s.email}>
                      {s.email}: {s.reason}
                    </li>
                  ))}
                </ul>
                {editInvitable.length > 0 && (
                  <button
                    onClick={() => addInvited(editInvitable)}
                    disabled={busy}
                    className={secondaryBtn}
                  >
                    Create {editInvitable.length} account{editInvitable.length === 1 ? "" : "s"} &amp; add
                  </button>
                )}
              </div>
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
