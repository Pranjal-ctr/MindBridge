/**
 * Platform Admin API layer — typed wrappers over the shared axios instance.
 * One function per backend endpoint; components never call api.* directly.
 */

import api from './api';
import type { AuditLogFilters, AuditLogListResponse } from './admin-types';

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
