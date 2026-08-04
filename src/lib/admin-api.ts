/**
 * Platform Admin API layer — typed wrappers over the shared axios instance.
 * One function per backend endpoint; components never call api.* directly.
 */

import api from './api';
import type {
  AdminUserFilters,
  AdminUserListResponse,
  AuditLogFilters,
  AuditLogListResponse,
  StaffUserCreatePayload,
  SubscriptionPayload,
  TenantCreatePayload,
  TenantDetail,
  TenantListResponse,
  TenantRow,
  TenantUpdatePayload,
  TenantUserListResponse,
  UserAdminUpdatePayload,
} from './admin-types';

// ── Schools ───────────────────────────────────────────────────────────

export async function listSchools(
  page: number,
  pageSize: number,
  opts: { search?: string; status?: string; include_archived?: boolean } = {},
): Promise<TenantListResponse> {
  const { data } = await api.get<TenantListResponse>('/admin/tenants', {
    params: { page, page_size: pageSize, ...opts },
  });
  return data;
}

export async function getSchoolDetail(tenantId: string): Promise<TenantDetail> {
  const { data } = await api.get<TenantDetail>(`/admin/tenants/${tenantId}`);
  return data;
}

export async function createSchool(payload: TenantCreatePayload): Promise<TenantRow> {
  const { data } = await api.post<TenantRow>('/admin/tenants', payload);
  return data;
}

export async function updateSchool(
  tenantId: string,
  payload: TenantUpdatePayload,
): Promise<TenantRow> {
  const { data } = await api.put<TenantRow>(`/admin/tenants/${tenantId}`, payload);
  return data;
}

export async function archiveSchool(tenantId: string): Promise<void> {
  await api.delete(`/admin/tenants/${tenantId}`);
}

export async function listSchoolUsers(
  tenantId: string,
  page: number,
  pageSize: number,
  role?: string,
): Promise<TenantUserListResponse> {
  const { data } = await api.get<TenantUserListResponse>(
    `/admin/tenants/${tenantId}/users`,
    { params: { page, page_size: pageSize, role } },
  );
  return data;
}

export async function setSchoolSubscription(
  tenantId: string,
  payload: SubscriptionPayload,
): Promise<void> {
  await api.post(`/admin/tenants/${tenantId}/subscription`, payload);
}

// ── Users ─────────────────────────────────────────────────────────────

export async function listUsers(
  page: number,
  pageSize: number,
  filters: AdminUserFilters = {},
): Promise<AdminUserListResponse> {
  const { data } = await api.get<AdminUserListResponse>('/admin/users', {
    params: { page, page_size: pageSize, ...filters },
  });
  return data;
}

export async function updateUserAdmin(
  userId: string,
  payload: UserAdminUpdatePayload,
): Promise<void> {
  await api.patch(`/admin/users/${userId}`, payload);
}

export async function deleteUserAdmin(userId: string): Promise<void> {
  await api.delete(`/admin/users/${userId}`);
}

export async function createStaffUser(payload: StaffUserCreatePayload): Promise<void> {
  await api.post('/admin/users', payload);
}

// ── Audit Logs ────────────────────────────────────────────────────────

export async function listAuditLogs(
  page: number,
  pageSize: number,
  filters: AuditLogFilters = {},
): Promise<AuditLogListResponse> {
  const { data } = await api.get<AuditLogListResponse>('/admin/audit-logs', {
    params: { page, page_size: pageSize, ...filters },
  });
  return data;
}

export async function exportAuditLogsCsv(filters: AuditLogFilters = {}): Promise<Blob> {
  const { data } = await api.get('/admin/audit-logs/export', {
    params: filters,
    responseType: 'blob',
  });
  return data;
}

/** Extract the FastAPI error detail from an axios error for toast messages. */
export function apiErrorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

/** Trigger a browser download of a blob (used by CSV export buttons). */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
