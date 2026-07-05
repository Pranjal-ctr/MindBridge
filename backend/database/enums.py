"""
MindBridge Database Enums
Python enum definitions matching PostgreSQL CHECK constraints.
"""

import enum


class UserRole(str, enum.Enum):
    """User roles for RBAC."""
    STUDENT = "student"
    PARENT = "parent"
    COUNSELOR = "counselor"
    SCHOOL_ADMIN = "school_admin"
    ADMIN = "admin"


class TenantStatus(str, enum.Enum):
    """Tenant account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class TenantType(str, enum.Enum):
    """Type of tenant organization."""
    SCHOOL = "school"
    DISTRICT = "district"
    ORGANIZATION = "organization"


class RiskLevel(str, enum.Enum):
    """Student risk classification levels."""
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    CRITICAL = "critical"


class SenderType(str, enum.Enum):
    """Message sender type in conversations."""
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class SentimentType(str, enum.Enum):
    """Sentiment analysis result."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class SessionStatus(str, enum.Enum):
    """Counselor session status."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class GoalStatus(str, enum.Enum):
    """Student goal status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    ABANDONED = "abandoned"


class MemoryType(str, enum.Enum):
    """AI memory item type."""
    PREFERENCE = "preference"
    FACT = "fact"
    EMOTION = "emotion"
    RELATIONSHIP = "relationship"
    ACADEMIC = "academic"
    GOAL = "goal"


class SubscriptionStatus(str, enum.Enum):
    """Subscription lifecycle status."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIAL = "trial"


class BillingCycle(str, enum.Enum):
    """Subscription billing frequency."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class PaymentStatus(str, enum.Enum):
    """Payment transaction status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class EventType(str, enum.Enum):
    """Student timeline event types."""
    CONVERSATION = "conversation"
    WELLNESS_CHECK = "wellness_check"
    GOAL_CREATED = "goal_created"
    GOAL_COMPLETED = "goal_completed"
    JOURNAL_ENTRY = "journal_entry"
    COUNSELOR_SESSION = "counselor_session"
    RISK_ALERT = "risk_alert"
    MOOD_LOG = "mood_log"


class RelationshipType(str, enum.Enum):
    """Parent-student relationship type."""
    FATHER = "father"
    MOTHER = "mother"
    GUARDIAN = "guardian"
    OTHER = "other"


class GenderType(str, enum.Enum):
    """Student gender options."""
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class SubscriptionPlan(str, enum.Enum):
    """Available subscription plans."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class AIFeatureName(str, enum.Enum):
    """AI features that can be independently routed to a provider/model."""
    COMRADE_CHAT = "comrade_chat"
    MEMORY_EXTRACTION = "memory_extraction"
    TITLE_GENERATION = "title_generation"
    RISK_DETECTION = "risk_detection"
    PARENT_INSIGHT = "parent_insight"


class AuthProvider(str, enum.Enum):
    """How a user account authenticates."""
    PASSWORD = "password"
    GOOGLE = "google"


class GuardianRelationship(str, enum.Enum):
    """Guardian relationship to a student."""
    MOTHER = "mother"
    FATHER = "father"
    GUARDIAN = "guardian"
    GRANDPARENT = "grandparent"
    SIBLING = "sibling"
    OTHER = "other"


class GuardianStatus(str, enum.Enum):
    """Whether a guardian record has been linked to a parent account."""
    PENDING = "pending"
    LINKED = "linked"
