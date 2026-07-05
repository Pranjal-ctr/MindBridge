/**
 * MindBridge TypeScript Types
 * Mirrors backend Pydantic schemas for type-safe API communication.
 */

// ── Auth ──────────────────────────────────────────────────────────────

export interface SignupRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: 'student' | 'parent' | 'counselor' | 'school_admin';
  phone: string;
  school_code?: string | null;
  invite_code?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  user_id: string;
  tenant_id: string;
  email: string;
  role: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  profile_image: string | null;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

export interface AuthResponse {
  tokens: TokenResponse;
  user: UserResponse;
}

// ── Google Sign-In ────────────────────────────────────────────────────

export interface GoogleAuthResponse {
  status: 'authenticated' | 'registration_required';
  tokens: TokenResponse | null;
  user: UserResponse | null;
  registration_token: string | null;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  profile_image: string | null;
}

export interface GoogleCompleteRequest {
  registration_token: string;
  role: 'student' | 'parent';
  phone: string;
  school_code?: string | null;
  invite_code?: string | null;
}

// ── Onboarding ────────────────────────────────────────────────────────

export interface OnboardingSubmit {
  class_level: string;
  help_goals: string[];
  hobbies: string[];
  strengths: string[];
  interaction_style: string;
}

export interface OnboardingResponse {
  class_level: string | null;
  help_goals: string[];
  hobbies: string[];
  strengths: string[];
  interaction_style: string | null;
  completed_at: string;
}

// ── Guardians ─────────────────────────────────────────────────────────

export type GuardianRelationship =
  | 'mother' | 'father' | 'guardian' | 'grandparent' | 'sibling' | 'other';

export interface GuardianCreate {
  name: string;
  email?: string | null;
  phone?: string | null;
  relationship: GuardianRelationship;
  is_primary?: boolean;
}

export interface GuardianResponse {
  guardian_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  relationship: string;
  is_primary: boolean;
  status: string;
  invite_code: string | null;
  created_at: string;
}

// ── Conversations ─────────────────────────────────────────────────────

export interface ConversationCreate {
  title?: string | null;
}

export interface ConversationUpdate {
  title?: string | null;
  is_archived?: boolean | null;
}

export interface ConversationResponse {
  conversation_id: string;
  student_id: string;
  title: string | null;
  ai_generated_title: boolean;
  is_archived: boolean;
  total_messages: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: ConversationResponse[];
  total: number;
  page: number;
  page_size: number;
}

// ── Messages ──────────────────────────────────────────────────────────

export interface MessageCreate {
  message_text: string;
  sender_type?: 'user' | 'ai' | 'system';
  metadata?: Record<string, unknown> | null;
}

export interface MessageResponse {
  message_id: string;
  conversation_id: string;
  sender_type: string;
  sender_id: string | null;
  message_text: string;
  metadata: Record<string, unknown> | null;
  token_count: number | null;
  sentiment: string | null;
  created_at: string;
}

export interface MessageListResponse {
  messages: MessageResponse[];
  has_more: boolean;
  next_cursor: string | null;
}

export interface SendMessageResponse {
  user_message: MessageResponse;
  ai_message: MessageResponse;
}

// ── Memory ────────────────────────────────────────────────────────────

export type MemoryType = 'goal' | 'academic' | 'preference' | 'fact' | 'emotion' | 'relationship';

export interface MemoryItem {
  memory_id: string;
  student_id: string;
  memory_type: MemoryType;
  content: string;
  importance_score: number | null;
  confidence_score: number | null;
  is_pinned: boolean;
  source_conversation_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryListResponse {
  items: MemoryItem[];
  total: number;
}

// ── Linking (Invite Codes) ────────────────────────────────────────────

export interface InviteCodeResponse {
  code_id: string;
  code: string;
  expires_at: string;
  is_used: boolean;
  created_at: string;
}

export interface InviteCodeCreateResponse {
  code: string;
  expires_at: string;
  message: string;
}

export interface RedeemInviteRequest {
  invite_code: string;
  relationship: string;
}

export interface RedeemInviteResponse {
  link_id: string;
  student_name: string;
  relationship: string;
  message: string;
}

export interface LinkedParentResponse {
  link_id: string;
  parent_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  relationship: string | null;
  linked_at: string;
}

export interface LinkedChildResponse {
  link_id: string;
  student_id: string;
  first_name: string;
  last_name: string;
  age: number | null;
  wellness_score: number | null;
  risk_level: string;
  relationship: string | null;
  linked_at: string;
}

// ── Parent Insights ──────────────────────────────────────────────────

export interface WellnessTrendPoint {
  date: string;
  score: number;
}

export interface StressFactor {
  name: string;
  value: number;
}

export interface ChildInsightResponse {
  student_id: string;
  student_name: string;
  wellness_score: number | null;
  risk_level: string;
  emotional_state: string;
  summary: string | null;
  wellness_trend: WellnessTrendPoint[];
  stress_factors: StressFactor[];
  recommendations: string[];
  last_updated: string | null;
}

// ── API Error ─────────────────────────────────────────────────────────

export interface ApiError {
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
}
