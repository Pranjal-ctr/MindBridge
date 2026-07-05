-- ===================================================================
-- MindBridge PostgreSQL Schema
-- Generated from DBML with production-ready constraints & indexes
-- ===================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===================================================================
-- TENANTS & SCHOOL SETTINGS
-- ===================================================================

CREATE TABLE tenants (
    tenant_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_name     VARCHAR(255) NOT NULL,
    tenant_type     VARCHAR(50) NOT NULL DEFAULT 'school'
                    CHECK (tenant_type IN ('school', 'district', 'organization')),
    school_code     VARCHAR(50) UNIQUE,
    subscription_plan VARCHAR(50) DEFAULT 'free'
                    CHECK (subscription_plan IN ('free', 'starter', 'professional', 'enterprise')),
    student_limit   INTEGER DEFAULT 100,
    active_students INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive', 'suspended', 'trial')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE school_settings (
    setting_id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id                   UUID NOT NULL UNIQUE REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    school_logo                 TEXT,
    primary_color               VARCHAR(20),
    wellness_threshold          NUMERIC(5,2),
    allow_parent_notifications  BOOLEAN DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- USERS & PROFILES
-- ===================================================================

CREATE TABLE users (
    user_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            VARCHAR(20) NOT NULL
                    CHECK (role IN ('student', 'parent', 'counselor', 'school_admin', 'admin')),
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    phone           VARCHAR(20),
    profile_image   TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_users_tenant_role ON users(tenant_id, role);
CREATE INDEX ix_users_email ON users(email);

CREATE TABLE classes (
    class_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    class_name      VARCHAR(100) NOT NULL,
    section         VARCHAR(20),
    academic_year   VARCHAR(20),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE student_profiles (
    student_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    class_id        UUID REFERENCES classes(class_id) ON DELETE SET NULL,
    admission_number VARCHAR(50),
    age             INTEGER,
    gender          VARCHAR(30),
    wellness_score  NUMERIC(5,2),
    risk_level      VARCHAR(20) DEFAULT 'green'
                    CHECK (risk_level IN ('green', 'yellow', 'red', 'critical')),
    joined_date     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_student_profiles_risk ON student_profiles(risk_level);

CREATE TABLE parent_profiles (
    parent_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    occupation      VARCHAR(100),
    relationship_type VARCHAR(30),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE counselor_profiles (
    counselor_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    specialization  VARCHAR(100),
    experience_years INTEGER,
    license_number  VARCHAR(100),
    rating          NUMERIC(3,2),
    bio             TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE school_admin_profiles (
    admin_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    designation     VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- FAMILY RELATIONSHIPS
-- ===================================================================

CREATE TABLE student_parent_links (
    link_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    parent_id       UUID NOT NULL REFERENCES parent_profiles(parent_id) ON DELETE CASCADE,
    relationship    VARCHAR(30),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_student_parent UNIQUE (student_id, parent_id)
);

-- ===================================================================
-- CONVERSATIONS & MESSAGES
-- ===================================================================

CREATE TABLE conversations (
    conversation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    title           VARCHAR(255),
    ai_generated_title BOOLEAN DEFAULT FALSE,
    is_archived     BOOLEAN DEFAULT FALSE,
    total_messages  INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_conversations_student ON conversations(student_id, created_at DESC);

CREATE TABLE messages (
    message_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    sender_type     VARCHAR(10) NOT NULL
                    CHECK (sender_type IN ('user', 'ai', 'system')),
    sender_id       UUID,  -- user_id if human, NULL if AI
    message_text    TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}'::jsonb,
    token_count     INTEGER,
    sentiment       VARCHAR(20)
                    CHECK (sentiment IS NULL OR sentiment IN ('positive', 'neutral', 'negative', 'mixed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_messages_conversation ON messages(conversation_id, created_at);

CREATE TABLE conversation_tags (
    tag_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    tag_name        VARCHAR(100) NOT NULL,
    confidence_score NUMERIC(3,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE conversation_summaries (
    summary_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    summary         TEXT NOT NULL,
    key_topics      TEXT,
    sentiment       VARCHAR(20),
    last_message_id UUID REFERENCES messages(message_id) ON DELETE SET NULL,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- RISK DETECTION
-- ===================================================================

CREATE TABLE risk_assessments (
    risk_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(conversation_id) ON DELETE SET NULL,
    risk_score      NUMERIC(5,2),
    risk_level      VARCHAR(20) NOT NULL
                    CHECK (risk_level IN ('green', 'yellow', 'red', 'critical')),
    trigger_reason  TEXT,
    generated_by    VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_risk_student_level ON risk_assessments(student_id, risk_level);

-- ===================================================================
-- MEMORY SYSTEM
-- ===================================================================

CREATE TABLE memory_items (
    memory_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    memory_type     VARCHAR(30) NOT NULL
                    CHECK (memory_type IN ('preference', 'fact', 'emotion', 'relationship', 'academic', 'goal')),
    content         TEXT NOT NULL,
    importance_score NUMERIC(3,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- WELLNESS TRACKING
-- ===================================================================

CREATE TABLE wellness_records (
    record_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    mood_score      INTEGER CHECK (mood_score BETWEEN 1 AND 10),
    stress_score    INTEGER CHECK (stress_score BETWEEN 1 AND 10),
    confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),
    anxiety_score   INTEGER CHECK (anxiety_score BETWEEN 1 AND 10),
    energy_score    INTEGER CHECK (energy_score BETWEEN 1 AND 10),
    date_recorded   DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_wellness_student_date ON wellness_records(student_id, date_recorded);

CREATE TABLE goals (
    goal_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    goal_title      VARCHAR(255) NOT NULL,
    goal_description TEXT,
    status          VARCHAR(20) DEFAULT 'active'
                    CHECK (status IN ('active', 'completed', 'paused', 'abandoned')),
    target_date     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE journal_entries (
    journal_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    title           VARCHAR(255),
    content         TEXT NOT NULL,
    mood_score      INTEGER CHECK (mood_score BETWEEN 1 AND 10),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- PARENT INSIGHTS
-- ===================================================================

CREATE TABLE parent_insight_history (
    insight_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    wellness_score  NUMERIC(5,2),
    risk_level      VARCHAR(20),
    summary         TEXT,
    recommendations TEXT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- COUNSELOR SESSIONS
-- ===================================================================

CREATE TABLE counselor_sessions (
    counselor_session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    counselor_id    UUID NOT NULL REFERENCES counselor_profiles(counselor_id) ON DELETE CASCADE,
    scheduled_at    TIMESTAMPTZ NOT NULL,
    status          VARCHAR(20) DEFAULT 'scheduled'
                    CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled', 'no_show')),
    ai_summary      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_sessions_counselor ON counselor_sessions(counselor_id, scheduled_at);

CREATE TABLE counselor_notes (
    note_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    counselor_session_id UUID NOT NULL REFERENCES counselor_sessions(counselor_session_id) ON DELETE CASCADE,
    counselor_id    UUID NOT NULL REFERENCES counselor_profiles(counselor_id) ON DELETE CASCADE,
    note_text       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- STUDENT TIMELINE
-- ===================================================================

CREATE TABLE student_timeline (
    event_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES student_profiles(student_id) ON DELETE CASCADE,
    event_type      VARCHAR(30) NOT NULL
                    CHECK (event_type IN ('conversation', 'wellness_check', 'goal_created',
                           'goal_completed', 'journal_entry', 'counselor_session',
                           'risk_alert', 'mood_log')),
    reference_id    UUID,
    event_description TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_timeline_student ON student_timeline(student_id, created_at DESC);

-- ===================================================================
-- ANALYTICS
-- ===================================================================

CREATE TABLE analytics_snapshots (
    snapshot_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    snapshot_month  DATE NOT NULL,
    total_students  INTEGER DEFAULT 0,
    avg_wellness    NUMERIC(5,2),
    avg_risk        NUMERIC(5,2),
    engagement_rate NUMERIC(5,2),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_snapshot_month UNIQUE (tenant_id, snapshot_month)
);

-- ===================================================================
-- NOTIFICATIONS
-- ===================================================================

CREATE TABLE notifications (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    message         TEXT NOT NULL,
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_notifications_user_read ON notifications(user_id, is_read);

-- ===================================================================
-- SUBSCRIPTIONS & PAYMENTS
-- ===================================================================

CREATE TABLE subscriptions (
    subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    plan_name       VARCHAR(50) NOT NULL,
    student_limit   INTEGER DEFAULT 100,
    active_students INTEGER DEFAULT 0,
    billing_cycle   VARCHAR(20) DEFAULT 'monthly'
                    CHECK (billing_cycle IN ('monthly', 'quarterly', 'annual')),
    amount          NUMERIC(10,2) NOT NULL,
    start_date      DATE NOT NULL,
    renewal_date    DATE,
    status          VARCHAR(20) DEFAULT 'active'
                    CHECK (status IN ('active', 'past_due', 'cancelled', 'expired', 'trial')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE payment_transactions (
    transaction_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscription_id UUID NOT NULL REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
    payment_provider VARCHAR(50),
    amount          NUMERIC(10,2) NOT NULL,
    currency        VARCHAR(10) DEFAULT 'USD',
    payment_status  VARCHAR(20) DEFAULT 'pending'
                    CHECK (payment_status IN ('pending', 'completed', 'failed', 'refunded')),
    transaction_reference VARCHAR(255),
    paid_at         TIMESTAMPTZ
);

-- ===================================================================
-- AUDIT LOGS
-- ===================================================================

CREATE TABLE audit_logs (
    audit_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(user_id) ON DELETE SET NULL,
    action          VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(50),
    entity_id       UUID,
    ip_address      VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_audit_user_action ON audit_logs(user_id, action);

-- ===================================================================
-- FILES
-- ===================================================================

CREATE TABLE files (
    file_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID REFERENCES student_profiles(student_id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversations(conversation_id) ON DELETE SET NULL,
    file_name       VARCHAR(255) NOT NULL,
    file_type       VARCHAR(50),
    file_url        TEXT NOT NULL,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ===================================================================
-- AI PROMPT VERSIONS
-- ===================================================================

CREATE TABLE ai_prompt_versions (
    prompt_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prompt_name     VARCHAR(100) NOT NULL,
    prompt_version  VARCHAR(20) NOT NULL,
    prompt_content  TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_prompt_name_version UNIQUE (prompt_name, prompt_version)
);

-- ===================================================================
-- Updated_at trigger function
-- ===================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memory_items_updated_at
    BEFORE UPDATE ON memory_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
