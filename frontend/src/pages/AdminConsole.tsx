// frontend/src/pages/AdminConsole.tsx — super-admin console (AEGIS-107)
import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  fetchAdminUsers,
  fetchAdminExams,
  fetchAdminAudit,
  deactivateUser,
  type AdminUser,
  type AdminExam,
  type AdminAuditEntry,
} from "../api/admin";

type Tab = "users" | "exams" | "audit";

const TABS: { id: Tab; label: string }[] = [
  { id: "users", label: "Users" },
  { id: "exams", label: "Exams" },
  { id: "audit", label: "Audit Log" },
];

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

const ROLE_BADGE: Record<string, string> = {
  student: "bg-surface-soft text-body",
  professor: "bg-accent-blue/10 text-accent-blue",
  super_admin: "bg-primary/15 text-primary",
};

const EVENT_ICON: Record<string, string> = {
  user_registered: "👤",
  exam_created: "📝",
  exam_opened: "🟢",
  exam_closed: "🔴",
  student_flagged: "🚩",
};

const AdminConsole: React.FC = () => {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("users");

  return (
    <div className="min-h-screen bg-canvas">
      <header className="bg-surface-card border-b border-hairline px-4 sm:px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center justify-center w-7 h-7 rounded bg-surface-dark text-on-dark text-xs font-bold">
            A
          </span>
          <h1 className="text-base font-bold text-body">AEGIS Admin Console</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-mute hidden sm:inline">{user?.email}</span>
          <button
            onClick={() => logout()}
            className="text-sm font-semibold text-body hover:text-primary transition-colors"
          >
            Log out
          </button>
        </div>
      </header>

      {/* Tabs */}
      <nav className="bg-surface-card border-b border-hairline px-4 sm:px-6 flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-3 text-sm font-semibold border-b-2 -mb-px transition-colors ${
              activeTab === t.id
                ? "border-primary text-body"
                : "border-transparent text-mute hover:text-body"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {activeTab === "users" && <UsersTab />}
        {activeTab === "exams" && <ExamsTab />}
        {activeTab === "audit" && <AuditTab />}
      </main>
    </div>
  );
};

// ─── shared bits ──────────────────────────────────────────────────────────────

const Loading: React.FC = () => (
  <div className="flex justify-center py-12">
    <div className="w-6 h-6 border-2 border-hairline border-t-accent-blue rounded-full animate-spin" />
  </div>
);

const ErrorBox: React.FC<{ message: string }> = ({ message }) => (
  <div className="rounded-md border border-accent-red/30 bg-accent-red/5 text-accent-red px-4 py-3 text-sm">
    {message}
  </div>
);

// ─── Users tab ────────────────────────────────────────────────────────────────

const UsersTab: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const page = await fetchAdminUsers(roleFilter, 200, 0);
      setUsers(page.items);
    } catch {
      setError("Failed to load users.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roleFilter]);

  async function handleDeactivate(id: string) {
    try {
      const updated = await deactivateUser(id);
      setUsers((prev) => prev.map((u) => (u.id === id ? updated : u)));
    } catch {
      setError("Failed to deactivate user.");
    }
  }

  const filtered = useMemo(
    () =>
      users.filter((u) =>
        u.email.toLowerCase().includes(search.toLowerCase())
      ),
    [users, search]
  );

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} />;

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search email…"
          className="flex-1 min-w-[200px] px-3 py-2 text-sm rounded-md border border-hairline bg-surface-card text-body placeholder:text-mute"
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          className="px-3 py-2 text-sm rounded-md border border-hairline bg-surface-card text-body"
        >
          <option value="">All roles</option>
          <option value="student">Students</option>
          <option value="professor">Professors</option>
          <option value="super_admin">Admins</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-md border border-hairline">
        <table className="w-full text-sm">
          <thead className="bg-surface-soft text-mute">
            <tr>
              <th className="text-left font-semibold px-4 py-2.5">Email</th>
              <th className="text-left font-semibold px-4 py-2.5">Role</th>
              <th className="text-left font-semibold px-4 py-2.5">Registered</th>
              <th className="text-left font-semibold px-4 py-2.5">Last login</th>
              <th className="text-left font-semibold px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((u) => (
              <tr key={u.id} className="border-t border-hairline-soft">
                <td className="px-4 py-2.5 text-body">{u.email}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
                      ROLE_BADGE[u.role] ?? "bg-surface-soft text-body"
                    }`}
                  >
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-mute">{formatDateTime(u.created_at)}</td>
                <td className="px-4 py-2.5 text-mute">{formatDateTime(u.last_login)}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`inline-flex items-center gap-1 text-xs font-semibold ${
                      u.is_active ? "text-accent-green" : "text-mute"
                    }`}
                  >
                    {u.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right">
                  {u.is_active && u.role !== "super_admin" && (
                    <button
                      onClick={() => handleDeactivate(u.id)}
                      className="text-xs font-semibold text-accent-red hover:underline"
                    >
                      Deactivate
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-mute">
                  No users found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ─── Exams tab ────────────────────────────────────────────────────────────────

const ExamsTab: React.FC = () => {
  const [exams, setExams] = useState<AdminExam[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const page = await fetchAdminExams(200, 0);
        setExams(page.items);
      } catch {
        setError("Failed to load exams.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} />;

  return (
    <div className="overflow-x-auto rounded-md border border-hairline">
      <table className="w-full text-sm">
        <thead className="bg-surface-soft text-mute">
          <tr>
            <th className="text-left font-semibold px-4 py-2.5">Title</th>
            <th className="text-left font-semibold px-4 py-2.5">Professor</th>
            <th className="text-left font-semibold px-4 py-2.5">State</th>
            <th className="text-left font-semibold px-4 py-2.5">Students</th>
            <th className="text-left font-semibold px-4 py-2.5">Created</th>
          </tr>
        </thead>
        <tbody>
          {exams.map((e) => (
            <tr key={e.exam_id} className="border-t border-hairline-soft">
              <td className="px-4 py-2.5 text-body font-medium">{e.title}</td>
              <td className="px-4 py-2.5 text-mute">{e.professor_email ?? "—"}</td>
              <td className="px-4 py-2.5">
                <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-surface-soft text-body">
                  {e.state}
                </span>
              </td>
              <td className="px-4 py-2.5 text-body">{e.student_count}</td>
              <td className="px-4 py-2.5 text-mute">{formatDateTime(e.created_at)}</td>
            </tr>
          ))}
          {exams.length === 0 && (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-mute">
                No exams found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

// ─── Audit tab ────────────────────────────────────────────────────────────────

const AuditTab: React.FC = () => {
  const [events, setEvents] = useState<AdminAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const page = await fetchAdminAudit(200, 0);
        setEvents(page.items);
      } catch {
        setError("Failed to load audit log.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  if (events.length === 0)
    return <p className="text-center text-mute py-8">No audit events yet.</p>;

  return (
    <ul className="space-y-2">
      {events.map((e, i) => (
        <li
          key={i}
          className="flex items-start gap-3 rounded-md border border-hairline bg-surface-card px-4 py-3"
        >
          <span className="text-lg leading-none mt-0.5">
            {EVENT_ICON[e.event_type] ?? "•"}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-sm font-semibold text-body">
                {e.event_type.replace(/_/g, " ")}
              </span>
              <span className="text-xs text-mute">
                {e.actor_email ?? "system"}
              </span>
            </div>
            {Object.keys(e.details).length > 0 && (
              <p className="text-xs text-mute truncate">
                {JSON.stringify(e.details)}
              </p>
            )}
          </div>
          <span className="text-xs text-mute whitespace-nowrap">
            {formatDateTime(e.timestamp)}
          </span>
        </li>
      ))}
    </ul>
  );
};

export default AdminConsole;
