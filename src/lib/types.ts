/**
 * Kio TypeScript Types
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
  /** ISO date (YYYY-MM-DD). Required — drives the server-side age gate. */
  date_of_birth: string;
  accept_terms: boolean;
  accept_privacy: boolean;
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
  /** Email address confirmed via the verification link. Google sign-ups start verified. */
  is_verified: boolean;
  last_login: string | null;
  created_at: string;
  date_of_birth: string | null;
  /** null on accounts created before the age gate existed. */
  guardian_consent_status:
    | 'not_required'
    | 'pending'
    | 'granted'
    | 'denied'
    | null;
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
  /** Google verifies an email address, not an age — the gate applies here too. */
  date_of_birth: string;
  accept_terms: boolean;
  accept_privacy: boolean;
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

export interface WellnessBreakdown {
  trend: string;
  confidence: number | null;
  components: Record<string, { normalized: number; weight: number; contribution: number; detail: string }>;
  explanation: string | null;
  calculated_at: string | null;
}

export interface RiskTrendPoint {
  date: string;
  level: string;
  score: number | null;
}

export interface MoodTrendPoint {
  date: string;
  emotion: string;
}

export interface TodayInsightCard {
  type: 'positive' | 'caution' | 'info';
  title: string;
  body: string;
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
  wellness_breakdown: WellnessBreakdown | null;
  risk_trend: RiskTrendPoint[];
  mood_trend: MoodTrendPoint[];
  today_insights: TodayInsightCard[];
  improvements: string[];
  concerns: string[];
  weekly_progress: Record<string, number>;
  family_communication: string[];
  family_activities: string[];
  weekly_mood_summary: WeeklyMoodSummary | null;
  wellbeing_dimensions: WellbeingDimension[];
  protective_factors: string[];
  risk_factors: string[];
}

export interface WeeklyMoodSummary {
  headline: string;
  dominant_mood: string | null;
  low_days: number;
  trend: string;
  days_recorded: number;
}

export interface WellbeingDimension {
  dimension: string;
  value: number;
}

// ── Daily Check-in (official, once per calendar day) ─────────────────

export type DailyMood = 'amazing' | 'good' | 'okay' | 'low' | 'very_difficult';
export type CheckinReason =
  | 'academics' | 'family' | 'friends' | 'relationship' | 'health'
  | 'career' | 'sports' | 'financial' | 'social_media' | 'other';

export interface DailyCheckinRequest {
  mood: DailyMood;
  reason: CheckinReason;
  reflection?: string | null;
}

export interface DailyCheckinInfo {
  date: string;
  mood: DailyMood;
  reason: CheckinReason;
  reflection: string | null;
  created_at: string | null;
}

export interface DailyCheckinStatusResponse {
  /** True when a check-in exists in the current 12-hour window. */
  completed_today: boolean;
  checkin: DailyCheckinInfo | null;
  /** 2 = none yet, 1 = one update still allowed, 0 = window exhausted. */
  updates_remaining: number;
  window_ends_at: string | null;
}

export interface DailyCheckinResponse {
  checkin: DailyCheckinInfo;
  wellness: WellnessScoreResponse;
  updates_remaining: number;
}

// ── Mood Calendar ─────────────────────────────────────────────────────

export interface MoodCalendarDay {
  date: string;
  mood: DailyMood | null;
  mood_score: number | null;
  reason: CheckinReason | null;
  note: string | null;
}

export interface MoodCalendarResponse {
  month: string;
  days: MoodCalendarDay[];
}

// ── Personal Insights ─────────────────────────────────────────────────

export interface PersonalInsight {
  kind: string;
  title: string;
  body: string;
  evidence: string;
}

export interface PersonalInsightsResponse {
  insights: PersonalInsight[];
  sufficient_data: boolean;
  checkin_days: number;
}

// ── Activities ────────────────────────────────────────────────────────

export interface ActivityItem {
  activity_id: string;
  title: string;
  description: string;
  category: 'mindfulness' | 'physical' | 'social' | 'reflection' | 'rest' | 'creative';
  duration_minutes: number;
  reason: string;
  completed: boolean;
  is_daily: boolean;
}

export interface ActivitiesResponse {
  activities: ActivityItem[];
  personalized: boolean;
  generated_at: string;
}

// ── Counselor Students ────────────────────────────────────────────────

export interface CounselorStudentProfile {
  student_id: string;
  first_name: string;
  last_name: string;
  age: number | null;
  gender: string | null;
  risk_level: string;
  wellness_score: number | null;
  main_concerns: string[];
  emotional_trend: string;
  last_session: string | null;
  ai_summary: string | null;
}

export interface CounselorStudentListResponse {
  students: CounselorStudentProfile[];
  total: number;
}

// ── Full user profile (GET/PUT /users/me) ─────────────────────────────

export interface StudentProfileData {
  student_id: string;
  admission_number: string | null;
  age: number | null;
  gender: string | null;
  wellness_score: number | null;
  risk_level: string;
}

export interface UserProfileResponse {
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
  updated_at: string;
  student_profile: StudentProfileData | null;
}

// ── Counselor Sessions & Notes ────────────────────────────────────────

export type CounselorSessionStatus =
  | 'scheduled'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'no_show';

export interface CounselorSession {
  counselor_session_id: string;
  student_id: string;
  counselor_id: string;
  scheduled_at: string;
  status: CounselorSessionStatus;
  ai_summary: string | null;
  created_at: string;
  /** Joined from the student's user row; null only on legacy rows. */
  student_name: string | null;
}

export interface CounselorSessionListResponse {
  sessions: CounselorSession[];
  total: number;
}

export interface CounselorSessionNote {
  note_id: string;
  counselor_session_id: string;
  counselor_id: string;
  note_text: string;
  created_at: string;
}

export interface CounselorNoteListResponse {
  notes: CounselorSessionNote[];
}

// ── Weekly Report ─────────────────────────────────────────────────────

export interface WeeklyReportResponse {
  audience: 'student' | 'parent' | 'counselor';
  week_start: string;
  headline: string;
  summary: string;
  highlights: string[];
  focus_areas: string[];
  generated_by: string | null;
  created_at: string;
}

// ── Wellness Score & Emotions ─────────────────────────────────────────

export interface WellnessScoreResponse {
  has_data: boolean;
  overall: number | null;
  trend: string | null;
  confidence: number | null;
  components: Record<string, { normalized: number; weight: number; contribution: number; detail: string }> | null;
  explanation: string | null;
  streak_days: number;
  calculated_at: string | null;
}

export interface WellnessScorePoint {
  date: string;
  score: number;
  trend: string;
}

export interface WellnessScoreHistoryResponse {
  points: WellnessScorePoint[];
}

export type MoodCheckin = 'happy' | 'okay' | 'down';

export interface MoodCheckinRequest {
  mood: MoodCheckin;
}

export interface MoodCheckinResponse {
  record: WellnessRecordResponse;
  wellness: WellnessScoreResponse;
}

export interface WellnessRecordResponse {
  record_id: string;
  student_id: string;
  mood_score: number | null;
  stress_score: number | null;
  confidence_score: number | null;
  anxiety_score: number | null;
  energy_score: number | null;
  date_recorded: string;
  created_at: string;
}

export interface EmotionTimelinePoint {
  created_at: string;
  emotion: string;
  intensity: number | null;
}

export interface EmotionTrendPoint {
  period: string;
  emotion: string;
}

export interface EmotionSummaryResponse {
  has_data: boolean;
  current_emotion: string | null;
  dominant_emotion: string | null;
  stability: number | null;
  confidence: number | null;
  weekly_trend: EmotionTrendPoint[];
  monthly_trend: EmotionTrendPoint[];
  timeline: EmotionTimelinePoint[];
}

// ── Risk Queue (counselor review) ─────────────────────────────────────

export interface RiskQueueItem {
  risk_id: string;
  student_id: string;
  student_name: string;
  risk_level: string;
  risk_score: number | null;
  categories: Record<string, number> | null;
  confidence: number | null;
  inconclusive: boolean;
  summary: string | null;
  trigger_reason: string | null;
  generated_by: string | null;
  created_at: string;
}

export interface RiskQueueListResponse {
  items: RiskQueueItem[];
  total: number;
}

export type RiskOutcome =
  | 'no_action_needed'
  | 'monitoring'
  | 'counseling_scheduled'
  | 'parent_contacted'
  | 'escalated'
  | 'referred_external'
  | 'false_positive';

export interface RiskReviewUpdate {
  review_status: 'acknowledged' | 'resolved';
  verdict?: 'agree' | 'disagree' | null;
  counselor_risk_level?: 'green' | 'yellow' | 'red' | 'critical' | null;
  outcome?: RiskOutcome | null;
  note?: string | null;
}

// ── Counselors (platform-wide directory & booking) ────────────────────

export interface AvailabilitySlot {
  slot_id: string;
  start_at: string;
  end_at: string;
  is_booked: boolean;
}

export interface CounselorDirectoryItem {
  counselor_id: string;
  name: string;
  photo: string | null;
  bio: string | null;
  qualification: string | null;
  specializations: string[];
  languages: string[];
  experience_years: number | null;
  rating: number | null;
  next_slots: AvailabilitySlot[];
}

export interface CounselorDirectoryResponse {
  counselors: CounselorDirectoryItem[];
  total: number;
}

export interface SlotListResponse {
  counselor_id: string;
  slots: AvailabilitySlot[];
}

export interface BookResponse {
  counselor_session_id: string;
  counselor_id: string;
  counselor_name: string;
  scheduled_at: string;
  status: string;
  message: string;
}

// ── Availability engine (migration 016) ───────────────────────────────

/** 0 = Monday .. 6 = Sunday, matching the backend and Python's weekday(). */
export type DayOfWeek = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export interface CounselorSchedule {
  schedule_id: string;
  counselor_id: string;
  day_of_week: DayOfWeek;
  /** Local to the counselor's timezone, "HH:MM:SS". */
  start_time: string;
  end_time: string;
  is_active: boolean;
  effective_from: string | null;
  effective_until: string | null;
  /** True when end_time <= start_time, i.e. the interval runs past midnight. */
  crosses_midnight: boolean;
}

export interface ScheduleListResponse {
  schedules: CounselorSchedule[];
  timezone: string;
}

export interface CounselorScheduleException {
  exception_id: string;
  counselor_id: string;
  exception_date: string;
  /** Null start and end mean the whole day. */
  start_time: string | null;
  end_time: string | null;
  /** False = time off, true = extra availability outside the usual pattern. */
  is_available: boolean;
  reason: string | null;
}

export interface ExceptionListResponse {
  exceptions: CounselorScheduleException[];
  timezone: string;
}

export interface SessionSettings {
  session_duration_minutes: number;
  buffer_minutes: number;
  timezone: string;
}

/** One concrete bookable slot. `start`/`end` are UTC; display_* are formatted. */
export interface AvailableSlot {
  counselor_id: string;
  counselor_name: string;
  start: string;
  end: string;
  duration_minutes: number;
  display_start: string;
  display_end: string;
  display_date: string;
}

export interface AvailabilitySearchResponse {
  timezone: string;
  window_start: string;
  window_end: string;
  slots: AvailableSlot[];
  counselors_considered: number;
}

// ── Consent & age gate ────────────────────────────────────────────────

export interface PolicyVersions {
  terms_version: string;
  privacy_version: string;
}

export interface ConsentRecord {
  consent_id: string;
  consent_type: 'terms' | 'privacy' | 'guardian';
  policy_version: string;
  granted_at: string;
  granted_by_email: string | null;
  verification_method: string | null;
  revoked_at: string | null;
}

export interface ConsentStatus {
  date_of_birth: string | null;
  age: number | null;
  is_minor: boolean;
  terms_version: string;
  privacy_version: string;
  has_accepted_terms: boolean;
  has_accepted_privacy: boolean;
  /** Consented to an older version — prompt to re-accept, not to first-accept. */
  needs_reconsent: boolean;
  guardian_consent_status: 'not_required' | 'pending' | 'granted' | 'denied' | 'unknown';
  guardian_email: string | null;
  records: ConsentRecord[];
}

export interface GuardianConsentContext {
  student_first_name: string;
  student_last_name: string;
  school_name: string | null;
  terms_version: string;
  privacy_version: string;
  already_decided: boolean;
}

// ── Notifications ─────────────────────────────────────────────────────

export interface NotificationItem {
  notification_id: string;
  user_id: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: NotificationItem[];
  total: number;
  unread_count: number;
}

// ── School Analytics ──────────────────────────────────────────────────

export interface RiskBucket {
  /** Stable key — use this, not `name`, for colour/order logic. */
  level: 'green' | 'yellow' | 'red' | 'critical';
  name: string;
  value: number;
  color: string;
}

/**
 * Named distinctly from the parent-dashboard `WellnessTrendPoint` above, which
 * is a per-child daily series. Same concept, different grain and shape —
 * sharing the name silently merged the two declarations.
 */
export interface SchoolWellnessTrendPoint {
  month: string;
  /** "Mar" repeats across years; this disambiguates. */
  month_start: string;
  /** null = no scores recorded that month. Render as a gap, never as 0. */
  score: number | null;
  students: number;
}

export interface StressCategory {
  category: string;
  students: number;
}

export interface CounselorActivity {
  active_counselors: number;
  sessions_last_30d: number;
  students_seen_last_30d: number;
  upcoming_sessions: number;
}

export interface AnalyticsOverview {
  school_name: string;
  total_students: number;
  students_with_wellness_data: number;
  /** null = nothing recorded yet. Distinct from a genuine score of 0. */
  avg_wellness_score: number | null;
  checked_in_last_7d: number;
  checkin_participation: number;
  counselors: CounselorActivity;
  risk_distribution: RiskBucket[];
  wellness_trend: SchoolWellnessTrendPoint[];
  stress_by_category: StressCategory[];
  /**
   * True when the school is too small to break down without identifying
   * individuals. All distributions come back empty — say so explicitly
   * rather than rendering empty charts.
   */
  cohort_suppressed: boolean;
  min_cohort_size: number;
  generated_at: string;
}

// ── API Error ─────────────────────────────────────────────────────────

export interface ApiError {
  detail: string | Array<{ loc: string[]; msg: string; type: string }>;
}
