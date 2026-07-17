/**
 * Platform Admin DTOs — mirrors backend/app/admin/schemas.py.
 * Kept separate from types.ts so the admin bundle stays self-contained.
 */

// ── Shared ────────────────────────────────────────────────────────────

export interface Paginated<T> {
  items: T[];
  total: number;
}

// ── Audit Logs ────────────────────────────────────────────────────────

export interface AuditLogEntry {
  audit_id: string;
  user_id: string | null;
  user_name: string | null;
  user_role: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  logs: AuditLogEntry[];
  total: number;
}

export interface AuditLogFilters {
  user_id?: string;
  action?: string;
  date_from?: string;
  date_to?: string;
}
