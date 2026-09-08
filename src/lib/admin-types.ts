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

// ── Platform Analytics ────────────────────────────────────────────────

export interface PlatformAnalytics {
  total_schools: number;
  total_students: number;
  total_parents: number;
  total_counselors: number;
  /** Signed in within the last 30 days. */
  active_users: number;
  ai_requests: number;
  ai_cost_usd: number;
  conversation_count: number;
  revenue_usd: number;
}

// ── Counselors ────────────────────────────────────────────────────────

export interface CounselorAdmin {
  counselor_id: string;
  user_id: string;
  name: string;
  email: string;
  phone: string | null;
  bio: string | null;
  qualification: string | null;
  specializations: string[];
  languages: string[];
  experience_years: number | null;
  rating: number | null;
  /** Credentials checked by a platform admin. Gates the public directory. */
  is_verified: boolean;
  is_available: boolean;
  is_active: boolean;
}

export interface CounselorListResponse {
  counselors: CounselorAdmin[];
  total: number;
}

export interface CounselorCreatePayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  qualification?: string;
  bio?: string;
  specializations?: string[];
  languages?: string[];
  experience_years?: number;
}

export interface CounselorAdminUpdatePayload {
  qualification?: string;
  bio?: string;
  specializations?: string[];
  languages?: string[];
  experience_years?: number;
  is_verified?: boolean;
  is_available?: boolean;
  is_active?: boolean;
}

// ── Risk oversight (cross-tenant) ─────────────────────────────────────

export interface AdminRiskRow {
  risk_id: string;
  student_id: string;
  student_name: string;
  tenant_id: string;
  school_name: string;
  risk_level: 'green' | 'yellow' | 'red' | 'critical';
  risk_score: number | null;
  confidence: number | null;
  review_status: string | null;
  assigned_counselor_id: string | null;
  assigned_counselor_name: string | null;
  reviewed_by_name: string | null;
  reviewed_at: string | null;
  generated_by: string | null;
  created_at: string;
  /** Server-computed so SLA flags don't depend on the browser's clock. */
  age_hours: number;
}

export interface AdminRiskListResponse {
  items: AdminRiskRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminRiskDetail extends AdminRiskRow {
  categories: Record<string, number> | null;
  summary: string | null;
  trigger_reason: string | null;
  resolution_note: string | null;
  counselor_risk_level: string | null;
  verdict: string | null;
  outcome: string | null;
}

export interface AdminRiskFilters {
  review_status?: string;
  risk_level?: string;
  tenant_id?: string;
}

// ── AI control ────────────────────────────────────────────────────────

export interface AIRoute {
  feature_name: string;
  primary_provider: string;
  primary_model: string;
  fallback_provider: string | null;
  fallback_model: string | null;
  max_retries: number;
  is_active: boolean;
}

export interface AIRouteListResponse {
  routes: AIRoute[];
}

export interface AIRouteUpdatePayload {
  primary_provider?: string;
  primary_model?: string;
  fallback_provider?: string | null;
  fallback_model?: string | null;
  max_retries?: number;
  is_active?: boolean;
}

export interface AIProviderConfig {
  provider_name: string;
  display_name: string;
  is_enabled: boolean;
  default_model: string;
}

export interface AIProviderListResponse {
  providers: AIProviderConfig[];
}

export interface PromptVersion {
  prompt_id: string;
  prompt_name: string;
  prompt_version: string;
  prompt_content: string;
  is_active: boolean;
  created_at: string;
}

export interface PromptListResponse {
  prompts: PromptVersion[];
}

// ── Platform config (Settings) ────────────────────────────────────────

export interface PlatformConfigEntry {
  config_key: string;
  config_value: Record<string, unknown>;
  description: string | null;
  /** "database" = overridden here; "default" = still the code fallback. */
  source: 'database' | 'default';
}

export interface PlatformConfigListResponse {
  configs: PlatformConfigEntry[];
}
