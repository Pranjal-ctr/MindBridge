/**
 * Platform Admin DTOs — mirrors backend/app/admin/schemas.py.
 * Kept separate from types.ts so the admin bundle stays self-contained.
 */

// ── Shared ────────────────────────────────────────────────────────────

export interface Paginated<T> {
  items: T[];
  total: number;
}

// ── Schools (tenants) ─────────────────────────────────────────────────

export interface TenantRow {
  tenant_id: string;
  tenant_name: string;
  tenant_type: string;
  school_code: string | null;
  subscription_plan: string;
  student_limit: number;
  active_students: number;
  status: string;
  city: string | null;
  address: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  principal_name: string | null;
  logo_url: string | null;
  deleted_at: string | null;
  created_at: string;
}

export interface TenantListResponse {
  tenants: TenantRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface TenantStats {
  students: number;
  parents: number;
  counselors: number;
  school_admins: number;
  seats_used: number;
  seat_limit: number;
}

export interface TenantSubscription {
  subscription_id: string;
  plan_name: string;
  student_limit: number;
  billing_cycle: string;
  amount: number;
  start_date: string;
  renewal_date: string | null;
  status: string;
}

export interface TenantDetail extends TenantRow {
  stats: TenantStats;
  subscription: TenantSubscription | null;
}

export interface TenantProfilePayload {
  city?: string | null;
  address?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  principal_name?: string | null;
  logo_url?: string | null;
}

export interface TenantCreatePayload extends TenantProfilePayload {
  tenant_name: string;
  tenant_type?: string;
  school_code?: string | null;
  subscription_plan?: string;
  student_limit?: number;
}

export interface TenantUpdatePayload extends TenantProfilePayload {
  tenant_name?: string;
  status?: 'active' | 'inactive' | 'suspended' | 'trial';
  subscription_plan?: string;
  student_limit?: number;
}

export interface SubscriptionPayload {
  plan_name: string;
  student_limit: number;
  billing_cycle: string;
  amount: number;
  start_date: string;
  renewal_date: string | null;
}

/** Row from GET /admin/tenants/{id}/users (users module response shape). */
export interface TenantUserRow {
  user_id: string;
  email: string;
  role: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  is_active: boolean;
  last_login: string | null;
}

export interface TenantUserListResponse {
  users: TenantUserRow[];
  total: number;
  page: number;
  page_size: number;
}

// ── Users ─────────────────────────────────────────────────────────────

export interface AdminUserRow {
  user_id: string;
  tenant_id: string;
  tenant_name: string | null;
  email: string;
  role: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  profile_image: string | null;
  is_active: boolean;
  deleted_at: string | null;
  last_login: string | null;
  created_at: string;
}

export interface AdminUserListResponse {
  users: AdminUserRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminUserFilters {
  role?: string;
  search?: string;
  tenant_id?: string;
  status?: 'active' | 'inactive' | 'deleted';
}

export interface UserAdminUpdatePayload {
  is_active?: boolean;
  new_password?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
}

export interface StaffUserCreatePayload {
  tenant_id: string;
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: 'counselor' | 'school_admin';
  phone?: string;
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
