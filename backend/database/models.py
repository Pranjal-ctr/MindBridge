"""
MindBridge SQLAlchemy 2.0 Models
All 27 tables with typed relationships and multi-tenancy support.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


# ===================================================================
# Base & Mixins
# ===================================================================

class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


class TimestampMixin:
    """Adds created_at to any model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class FullTimestampMixin(TimestampMixin):
    """Adds created_at and updated_at."""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ===================================================================
# Multi-Tenancy
# ===================================================================

class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_type: Mapped[str] = mapped_column(String(50), nullable=False, default="school")
    school_code: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    subscription_plan: Mapped[str] = mapped_column(String(50), default="free")
    student_limit: Mapped[int] = mapped_column(Integer, default=100)
    active_students: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Relationships
    users: Mapped[list[User]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    classes: Mapped[list[Class]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    analytics_snapshots: Mapped[list[AnalyticsSnapshot]] = relationship(back_populates="tenant")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="tenant")
    school_settings: Mapped[Optional[SchoolSettings]] = relationship(back_populates="tenant", uselist=False)


class SchoolSettings(Base, TimestampMixin):
    __tablename__ = "school_settings"

    setting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), unique=True
    )
    school_logo: Mapped[Optional[str]] = mapped_column(Text)
    primary_color: Mapped[Optional[str]] = mapped_column(String(20))
    wellness_threshold: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    allow_parent_notifications: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="school_settings")


# ===================================================================
# Users & Profiles
# ===================================================================

class User(Base, FullTimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_tenant_role", "tenant_id", "role"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Nullable: Google-only accounts have no local password.
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    google_sub: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    auth_provider: Mapped[str] = mapped_column(
        String(20), default="password", server_default="password", nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    profile_image: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="users")
    student_profile: Mapped[Optional[StudentProfile]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    parent_profile: Mapped[Optional[ParentProfile]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    counselor_profile: Mapped[Optional[CounselorProfile]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    school_admin_profile: Mapped[Optional[SchoolAdminProfile]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(back_populates="user")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")


class Class(Base, TimestampMixin):
    __tablename__ = "classes"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE")
    )
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(20))
    academic_year: Mapped[Optional[str]] = mapped_column(String(20))

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="classes")
    students: Mapped[list[StudentProfile]] = relationship(back_populates="class_")


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"
    __table_args__ = (
        Index("ix_student_profiles_risk", "risk_level"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True
    )
    class_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.class_id", ondelete="SET NULL")
    )
    admission_number: Mapped[Optional[str]] = mapped_column(String(50))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    gender: Mapped[Optional[str]] = mapped_column(String(30))
    wellness_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[str] = mapped_column(String(20), default="green")
    joined_date: Mapped[Optional[date]] = mapped_column(Date)

    # Relationships
    user: Mapped[User] = relationship(back_populates="student_profile")
    class_: Mapped[Optional[Class]] = relationship(back_populates="students")
    parent_links: Mapped[list[StudentParentLink]] = relationship(back_populates="student")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="student")
    memory_items: Mapped[list[MemoryItem]] = relationship(back_populates="student")
    wellness_records: Mapped[list[WellnessRecord]] = relationship(back_populates="student")
    goals: Mapped[list[Goal]] = relationship(back_populates="student")
    journal_entries: Mapped[list[JournalEntry]] = relationship(back_populates="student")
    risk_assessments: Mapped[list[RiskAssessment]] = relationship(back_populates="student")
    parent_insights: Mapped[list[ParentInsightHistory]] = relationship(back_populates="student")
    counselor_sessions: Mapped[list[CounselorSession]] = relationship(back_populates="student")
    timeline_events: Mapped[list[StudentTimeline]] = relationship(back_populates="student")
    files: Mapped[list[File]] = relationship(back_populates="student")
    invite_codes: Mapped[list[ParentInviteCode]] = relationship(back_populates="student")
    guardians: Mapped[list[StudentGuardian]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    onboarding: Mapped[Optional[StudentOnboarding]] = relationship(
        back_populates="student", uselist=False, cascade="all, delete-orphan"
    )


class ParentProfile(Base, TimestampMixin):
    __tablename__ = "parent_profiles"

    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True
    )
    occupation: Mapped[Optional[str]] = mapped_column(String(100))
    relationship_type: Mapped[Optional[str]] = mapped_column(String(30))

    # Relationships
    user: Mapped[User] = relationship(back_populates="parent_profile")
    student_links: Mapped[list[StudentParentLink]] = relationship(back_populates="parent")


class CounselorProfile(Base, TimestampMixin):
    __tablename__ = "counselor_profiles"

    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True
    )
    specialization: Mapped[Optional[str]] = mapped_column(String(100))
    experience_years: Mapped[Optional[int]] = mapped_column(Integer)
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    # Platform-wide counselor directory fields (Phase 5)
    qualification: Mapped[Optional[str]] = mapped_column(String(200))
    specializations: Mapped[Optional[list]] = mapped_column(JSONB, server_default="[]")
    languages: Mapped[Optional[list]] = mapped_column(JSONB, server_default="[]")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Relationships
    user: Mapped[User] = relationship(back_populates="counselor_profile")
    sessions: Mapped[list[CounselorSession]] = relationship(back_populates="counselor")
    notes: Mapped[list[CounselorNote]] = relationship(back_populates="counselor")
    availability: Mapped[list[CounselorAvailability]] = relationship(
        back_populates="counselor", cascade="all, delete-orphan"
    )


class SchoolAdminProfile(Base, TimestampMixin):
    __tablename__ = "school_admin_profiles"

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True
    )
    designation: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    user: Mapped[User] = relationship(back_populates="school_admin_profile")


# ===================================================================
# Family Relationships
# ===================================================================

class StudentParentLink(Base, TimestampMixin):
    __tablename__ = "student_parent_links"
    __table_args__ = (
        UniqueConstraint("student_id", "parent_id", name="uq_student_parent"),
    )

    link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_profiles.parent_id", ondelete="CASCADE")
    )
    relationship_: Mapped[Optional[str]] = mapped_column(
        "relationship", String(30)
    )

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="parent_links")
    parent: Mapped[ParentProfile] = relationship(back_populates="student_links")


class ParentInviteCode(Base, TimestampMixin):
    """Invite codes generated by students to link parent accounts."""
    __tablename__ = "parent_invite_codes"
    __table_args__ = (
        Index(
            "ix_invite_student_active", "student_id",
            postgresql_where=text("NOT is_used"),
        ),
    )

    code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_profiles.parent_id", ondelete="SET NULL"),
        nullable=True,
    )
    # Optional link to a specific guardian record this code was generated for.
    # NULL for legacy single-code invites (StudentInviteCode page).
    guardian_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_guardians.guardian_id", ondelete="CASCADE"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="invite_codes")
    used_by_parent: Mapped[Optional[ParentProfile]] = relationship()


class StudentGuardian(Base, FullTimestampMixin):
    """A guardian a student adds manually (name/email/phone/relationship).
    One may be marked primary. Each can generate an invite code a parent redeems.
    Distinct from StudentParentLink, which is the actual linked-account relationship."""
    __tablename__ = "student_guardians"
    __table_args__ = (
        Index(
            "uq_guardian_one_primary", "student_id",
            unique=True, postgresql_where=text("is_primary"),
        ),
    )

    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    relationship_: Mapped[str] = mapped_column("relationship", String(30), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    linked_parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_profiles.parent_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="guardians")


class StudentOnboarding(Base):
    """First-login questionnaire responses for a student. Used for AI personalization."""
    __tablename__ = "student_onboarding"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.student_id", ondelete="CASCADE"),
        primary_key=True,
    )
    class_level: Mapped[Optional[str]] = mapped_column(String(30))
    help_goals: Mapped[Optional[list]] = mapped_column(JSONB, server_default="[]")
    hobbies: Mapped[Optional[list]] = mapped_column(JSONB, server_default="[]")
    strengths: Mapped[Optional[list]] = mapped_column(JSONB, server_default="[]")
    interaction_style: Mapped[Optional[str]] = mapped_column(String(50))
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="onboarding")


# ===================================================================
# Conversations & Messages
# ===================================================================

class Conversation(Base, FullTimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_student", "student_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    ai_generated_title: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at"
    )
    tags: Mapped[list[ConversationTag]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    summaries: Mapped[list[ConversationSummary]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    risk_assessments: Mapped[list[RiskAssessment]] = relationship(back_populates="conversation")
    files: Mapped[list[File]] = relationship(back_populates="conversation")


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation", "conversation_id", "created_at"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE")
    )
    sender_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, server_default="{}"
    )
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20))

    # Relationships
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ConversationTag(Base, TimestampMixin):
    __tablename__ = "conversation_tags"

    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE")
    )
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))

    # Relationships
    conversation: Mapped[Conversation] = relationship(back_populates="tags")


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="CASCADE")
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_topics: Mapped[Optional[str]] = mapped_column(Text)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20))
    last_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.message_id", ondelete="SET NULL"),
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(back_populates="summaries")
    last_message: Mapped[Optional[Message]] = relationship(foreign_keys=[last_message_id])


# ===================================================================
# Risk Detection
# ===================================================================

class RiskAssessment(Base, TimestampMixin):
    __tablename__ = "risk_assessments"
    __table_args__ = (
        Index("ix_risk_student_level", "student_id", "risk_level"),
    )

    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="SET NULL")
    )
    risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger_reason: Mapped[Optional[str]] = mapped_column(Text)
    generated_by: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="risk_assessments")
    conversation: Mapped[Optional[Conversation]] = relationship(back_populates="risk_assessments")


# ===================================================================
# Memory System
# ===================================================================

class MemoryItem(Base, FullTimestampMixin):
    __tablename__ = "memory_items"
    __table_args__ = (
        Index("ix_memory_items_student", "student_id"),
    )

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    importance_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    source_conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="memory_items")


# ===================================================================
# Wellness Tracking
# ===================================================================

class WellnessRecord(Base, TimestampMixin):
    __tablename__ = "wellness_records"
    __table_args__ = (
        Index("ix_wellness_student_date", "student_id", "date_recorded"),
    )

    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    mood_score: Mapped[Optional[int]] = mapped_column(Integer)
    stress_score: Mapped[Optional[int]] = mapped_column(Integer)
    confidence_score: Mapped[Optional[int]] = mapped_column(Integer)
    anxiety_score: Mapped[Optional[int]] = mapped_column(Integer)
    energy_score: Mapped[Optional[int]] = mapped_column(Integer)
    date_recorded: Mapped[date] = mapped_column(Date, nullable=False)

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="wellness_records")


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    goal_title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    target_date: Mapped[Optional[date]] = mapped_column(Date)

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="goals")


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    journal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mood_score: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="journal_entries")


# ===================================================================
# Parent Insights
# ===================================================================

class ParentInsightHistory(Base):
    __tablename__ = "parent_insight_history"

    insight_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    wellness_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[Optional[str]] = mapped_column(String(20))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    recommendations: Mapped[Optional[str]] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="parent_insights")


# ===================================================================
# Counselor Sessions
# ===================================================================

class CounselorSession(Base, TimestampMixin):
    __tablename__ = "counselor_sessions"
    __table_args__ = (
        Index("ix_sessions_counselor", "counselor_id", "scheduled_at"),
    )

    counselor_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselor_profiles.counselor_id", ondelete="CASCADE")
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    ai_summary: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="counselor_sessions")
    counselor: Mapped[CounselorProfile] = relationship(back_populates="sessions")
    notes: Mapped[list[CounselorNote]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class CounselorNote(Base, TimestampMixin):
    __tablename__ = "counselor_notes"

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    counselor_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counselor_sessions.counselor_session_id", ondelete="CASCADE"),
    )
    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselor_profiles.counselor_id", ondelete="CASCADE")
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    session: Mapped[CounselorSession] = relationship(back_populates="notes")
    counselor: Mapped[CounselorProfile] = relationship(back_populates="notes")


class CounselorAvailability(Base, TimestampMixin):
    """A bookable time slot offered by a counselor (platform-wide booking)."""
    __tablename__ = "counselor_availability"
    __table_args__ = (
        Index("ix_availability_counselor_start", "counselor_id", "start_at"),
    )

    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    counselor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counselor_profiles.counselor_id", ondelete="CASCADE")
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Relationships
    counselor: Mapped[CounselorProfile] = relationship(back_populates="availability")


# ===================================================================
# Student Timeline
# ===================================================================

class StudentTimeline(Base, TimestampMixin):
    __tablename__ = "student_timeline"
    __table_args__ = (
        Index("ix_timeline_student", "student_id", "created_at"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    event_description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    student: Mapped[StudentProfile] = relationship(back_populates="timeline_events")


# ===================================================================
# Analytics
# ===================================================================

class AnalyticsSnapshot(Base, TimestampMixin):
    __tablename__ = "analytics_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "snapshot_month", name="uq_tenant_snapshot_month"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE")
    )
    snapshot_month: Mapped[date] = mapped_column(Date, nullable=False)
    total_students: Mapped[int] = mapped_column(Integer, default=0)
    avg_wellness: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    avg_risk: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    engagement_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="analytics_snapshots")


# ===================================================================
# Notifications
# ===================================================================

class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    user: Mapped[User] = relationship(back_populates="notifications")


# ===================================================================
# Subscriptions & Payments
# ===================================================================

class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE")
    )
    plan_name: Mapped[str] = mapped_column(String(50), nullable=False)
    student_limit: Mapped[int] = mapped_column(Integer, default=100)
    active_students: Mapped[int] = mapped_column(Integer, default=0)
    billing_cycle: Mapped[str] = mapped_column(String(20), default="monthly")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    renewal_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="subscriptions")
    transactions: Mapped[list[PaymentTransaction]] = relationship(back_populates="subscription")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.subscription_id", ondelete="CASCADE")
    )
    payment_provider: Mapped[Optional[str]] = mapped_column(String(50))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    payment_status: Mapped[str] = mapped_column(String(20), default="pending")
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(255))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    subscription: Mapped[Subscription] = relationship(back_populates="transactions")


# ===================================================================
# Audit Logs
# ===================================================================

class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
    )

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))

    # Relationships
    user: Mapped[Optional[User]] = relationship(back_populates="audit_logs")


# ===================================================================
# Files
# ===================================================================

class File(Base):
    __tablename__ = "files"

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="SET NULL")
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="SET NULL")
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50))
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    student: Mapped[Optional[StudentProfile]] = relationship(back_populates="files")
    conversation: Mapped[Optional[Conversation]] = relationship(back_populates="files")


# ===================================================================
# AI Prompt Versions
# ===================================================================

class AIPromptVersion(Base, TimestampMixin):
    __tablename__ = "ai_prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_name", "prompt_version", name="uq_prompt_name_version"),
    )

    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prompt_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ===================================================================
# Provider-Agnostic AI Layer
# ===================================================================

class AIProviderConfig(Base, FullTimestampMixin):
    """DB-driven registration of an AI provider (gemini, claude, openai, ollama, ...)."""
    __tablename__ = "ai_provider_configs"

    provider_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    default_model: Mapped[str] = mapped_column(String(100), nullable=False)
    extra_config: Mapped[Optional[dict]] = mapped_column(JSONB, server_default="{}")


class AIFeatureRoute(Base, FullTimestampMixin):
    """Maps a feature (chat, memory extraction, title generation, ...) to a provider/model,
    with an optional fallback provider/model used when the primary exhausts its retries."""
    __tablename__ = "ai_feature_routes"

    feature_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    primary_provider: Mapped[str] = mapped_column(
        String(50), ForeignKey("ai_provider_configs.provider_name"), nullable=False
    )
    primary_model: Mapped[str] = mapped_column(String(100), nullable=False)
    fallback_provider: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("ai_provider_configs.provider_name"), nullable=True
    )
    fallback_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class AIUsageLog(Base):
    """One row per provider call attempt -- powers cost/latency/token usage reporting."""
    __tablename__ = "ai_usage_logs"
    __table_args__ = (
        Index("ix_ai_usage_provider_created", "provider", "created_at"),
        Index("ix_ai_usage_feature_created", "feature_name", "created_at"),
    )

    usage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    feature_name: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.conversation_id", ondelete="SET NULL")
    )
    student_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profiles.student_id", ondelete="SET NULL")
    )
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6))
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
