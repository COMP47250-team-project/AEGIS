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
interface GroupDetail {
  id: string;
  name: string;
  members: Member[];
}
interface ExamRow {
  id: string;
  quiz_title: string | null;
  course_id: string;
  state: string;
}

const inputClass =
  "w-full border border-hairline rounded px-3 py-2 text-sm text-ink bg-surface-doc focus:outline-none focus:ring-1 focus:ring-surface-dark";

function errorDetail(err: unknown): string | undefined {
  return (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
}

const GroupsManager: React.FC = () => {
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [name, setName] = useState("");
  const [emails, setEmails] = useState("");
  const [detail, setDetail] = useState<GroupDetail | null>(null);
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

  async function createGroup(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      await apiClient.post("/groups", {
        name: name.trim(),
        student_emails: parseStudentEmails(emails),
      });
      setName("");
      setEmails("");
      setMsg({ text: "Group created", ok: true });
      loadGroups();
    } catch {
      setMsg({ text: "Failed to create group", ok: false });
    } finally {
      setBusy(false);
    }
  }

  function openGroup(id: string) {
    apiClient
      .get<GroupDetail>(`/groups/${id}`)
      .then(({ data }) => setDetail(data))
      .catch(() => setMsg({ text: "Failed to load group", ok: false }));
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
      setMsg({
        text: `Enrolled ${data.enrolled} of ${data.group_size} in exam`,
        ok: true,
      });
    } catch (err) {
      setMsg({
        text: errorDetail(err) ?? "Enroll failed — exam must be in draft state",
        ok: false,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Create group */}
      <form onSubmit={createGroup} className="space-y-3">
        <h3 className="text-sm font-semibold text-ink">New group</h3>
        <input
          className={inputClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Group name — e.g. CS Students 2026"
        />
        <textarea
          className={inputClass}
          rows={4}
          value={emails}
          onChange={(e) => setEmails(e.target.value)}
          placeholder="Student emails — one per line, or comma/CSV paste"
        />
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="px-3 py-1.5 bg-primary text-ink text-xs font-semibold rounded disabled:opacity-50 hover:bg-primary-pressed transition-colors"
        >
          Create group
        </button>
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
          <div className="border border-hairline rounded p-3 space-y-2">
            <p className="text-sm font-semibold text-ink">{detail.name}</p>
            {detail.members.length === 0 ? (
              <p className="text-xs text-mute">No members in this group.</p>
            ) : (
              <ul className="text-xs text-body space-y-0.5">
                {detail.members.map((m) => (
                  <li key={m.student_id}>{m.name ? `${m.name} · ` : ""}{m.email}</li>
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
                      {ex.quiz_title ?? "Exam"} · {ex.course_id}
                    </option>
                  ))}
                </select>
                <button
                  onClick={enrollInExam}
                  disabled={busy || detail.members.length === 0}
                  className="px-3 py-1.5 bg-primary text-ink text-xs font-semibold rounded disabled:opacity-50 hover:bg-primary-pressed transition-colors whitespace-nowrap"
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
