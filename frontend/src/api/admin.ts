// frontend/src/api/admin.ts — super-admin console API (AEGIS-107)
import apiClient from "./client";

export interface AdminUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface AdminExam {
  exam_id: string;
  title: string;
  professor_email: string | null;
  state: string;
  student_count: number;
  created_at: string;
}

export interface AdminAuditEntry {
  event_type: string;
  actor_email: string | null;
  target_id: string | null;
  timestamp: string;
  details: Record<string, unknown>;
}

interface Page<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

export async function fetchAdminUsers(
  role?: string,
  limit = 50,
  offset = 0
): Promise<Page<AdminUser>> {
  const { data } = await apiClient.get<Page<AdminUser>>("/admin/users", {
    params: { role: role || undefined, limit, offset },
  });
  return data;
}

export async function fetchAdminExams(
  limit = 50,
  offset = 0
): Promise<Page<AdminExam>> {
  const { data } = await apiClient.get<Page<AdminExam>>("/admin/exams", {
    params: { limit, offset },
  });
  return data;
}

export async function fetchAdminAudit(
  limit = 50,
  offset = 0
): Promise<Page<AdminAuditEntry>> {
  const { data } = await apiClient.get<Page<AdminAuditEntry>>("/admin/audit", {
    params: { limit, offset },
  });
  return data;
}

export async function deactivateUser(userId: string): Promise<AdminUser> {
  const { data } = await apiClient.post<AdminUser>(
    `/admin/users/${userId}/deactivate`
  );
  return data;
}

export async function activateUser(userId: string): Promise<AdminUser> {
  const { data } = await apiClient.post<AdminUser>(
    `/admin/users/${userId}/activate`
  );
  return data;
}
