"""
MindBridge Database Seed Script
Creates demo data matching the frontend's hardcoded values.

Usage:
    cd backend
    python -m database.seed
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.auth.utils import hash_password
from database.session import async_session_factory, engine
from database.models import (
    AnalyticsSnapshot,
    Base,
    Class,
    Conversation,
    CounselorProfile,
    CounselorSession,
    Message,
    Notification,
    ParentInsightHistory,
    ParentProfile,
    SchoolAdminProfile,
    SchoolSettings,
    StudentParentLink,
    StudentProfile,
    Subscription,
    Tenant,
    User,
    WellnessRecord,
)


async def seed():
    """Populate database with demo data matching frontend mock values."""

    async with async_session_factory() as db:
        # Check if already seeded
        result = await db.execute(text("SELECT COUNT(*) FROM tenants"))
        if result.scalar() > 0:
            print("Database already seeded. Skipping.")
            return

        print("[SEED] Seeding MindBridge database...")

        # ---------------------------------------------------------------
        # 1. Tenant: Riverside High School
        # ---------------------------------------------------------------
        tenant_id = uuid.uuid4()
        tenant = Tenant(
            tenant_id=tenant_id,
            tenant_name="Riverside High School",
            tenant_type="school",
            school_code="RHS2026",
            subscription_plan="professional",
            student_limit=1000,
            active_students=970,
            status="active",
        )
        db.add(tenant)

        db.add(SchoolSettings(
            tenant_id=tenant_id,
            primary_color="#2563EB",
            wellness_threshold=Decimal("60.00"),
            allow_parent_notifications=True,
        ))

        # ---------------------------------------------------------------
        # 2. Class
        # ---------------------------------------------------------------
        class_id = uuid.uuid4()
        db.add(Class(
            class_id=class_id,
            tenant_id=tenant_id,
            class_name="Grade 11",
            section="A",
            academic_year="2025-2026",
        ))

        # ---------------------------------------------------------------
        # 3. Users (matching frontend hardcoded names)
        # ---------------------------------------------------------------
        default_password = hash_password("MindBridge2026!")

        # Student: Sarah Johnson
        student_user_id = uuid.uuid4()
        student_id = uuid.uuid4()
        db.add(User(
            user_id=student_user_id, tenant_id=tenant_id,
            email="sarah.johnson@student.rhs.edu",
            password_hash=default_password, role="student",
            first_name="Sarah", last_name="Johnson",
        ))
        db.add(StudentProfile(
            student_id=student_id, user_id=student_user_id, class_id=class_id,
            age=16, gender="female", wellness_score=Decimal("72.00"),
            risk_level="yellow", joined_date=date(2025, 8, 15),
        ))

        # Student: Mike Thompson
        mike_user_id = uuid.uuid4()
        mike_student_id = uuid.uuid4()
        db.add(User(
            user_id=mike_user_id, tenant_id=tenant_id,
            email="mike.thompson@student.rhs.edu",
            password_hash=default_password, role="student",
            first_name="Mike", last_name="Thompson",
        ))
        db.add(StudentProfile(
            student_id=mike_student_id, user_id=mike_user_id, class_id=class_id,
            age=17, gender="male", wellness_score=Decimal("78.00"),
            risk_level="green", joined_date=date(2025, 8, 15),
        ))

        # Student: Emily Rodriguez
        emily_user_id = uuid.uuid4()
        emily_student_id = uuid.uuid4()
        db.add(User(
            user_id=emily_user_id, tenant_id=tenant_id,
            email="emily.rodriguez@student.rhs.edu",
            password_hash=default_password, role="student",
            first_name="Emily", last_name="Rodriguez",
        ))
        db.add(StudentProfile(
            student_id=emily_student_id, user_id=emily_user_id, class_id=class_id,
            age=15, gender="female", wellness_score=Decimal("45.00"),
            risk_level="red", joined_date=date(2025, 8, 15),
        ))

        # Parent: Sarah's Parent
        parent_user_id = uuid.uuid4()
        parent_id = uuid.uuid4()
        db.add(User(
            user_id=parent_user_id, tenant_id=tenant_id,
            email="parent.johnson@email.com",
            password_hash=default_password, role="parent",
            first_name="Robert", last_name="Johnson",
        ))
        db.add(ParentProfile(
            parent_id=parent_id, user_id=parent_user_id,
            occupation="Engineer", relationship_type="father",
        ))
        db.add(StudentParentLink(
            student_id=student_id, parent_id=parent_id, relationship_="father",
        ))

        # Counselor: Dr. Jennifer Martinez
        counselor_user_id = uuid.uuid4()
        counselor_id = uuid.uuid4()
        db.add(User(
            user_id=counselor_user_id, tenant_id=tenant_id,
            email="jennifer.martinez@rhs.edu",
            password_hash=default_password, role="counselor",
            first_name="Jennifer", last_name="Martinez",
        ))
        db.add(CounselorProfile(
            counselor_id=counselor_id, user_id=counselor_user_id,
            specialization="Adolescent Psychology",
            experience_years=12, license_number="LPC-2014-0892",
            rating=Decimal("4.80"), bio="Licensed counselor specializing in adolescent wellness.",
        ))

        # School Admin
        admin_user_id = uuid.uuid4()
        db.add(User(
            user_id=admin_user_id, tenant_id=tenant_id,
            email="admin@rhs.edu",
            password_hash=default_password, role="school_admin",
            first_name="Principal", last_name="Williams",
        ))
        db.add(SchoolAdminProfile(
            user_id=admin_user_id, designation="Principal",
        ))

        # Platform Admin
        platform_admin_id = uuid.uuid4()
        db.add(User(
            user_id=platform_admin_id, tenant_id=tenant_id,
            email="admin@mindbridge.ai",
            password_hash=default_password, role="admin",
            first_name="MindBridge", last_name="Admin",
        ))

        await db.flush()

        # ---------------------------------------------------------------
        # 4. Conversations (matching StudentDashboard)
        # ---------------------------------------------------------------
        conv_id = uuid.uuid4()
        db.add(Conversation(
            conversation_id=conv_id, student_id=student_id,
            title="Exam Stress Discussion",
            total_messages=3,
        ))

        now = datetime.now(timezone.utc)
        db.add(Message(
            conversation_id=conv_id, sender_type="ai",
            message_text="Hi! I'm here to support you. How are you feeling today?",
            created_at=now - timedelta(minutes=5),
        ))
        db.add(Message(
            conversation_id=conv_id, sender_type="user", sender_id=student_user_id,
            message_text="I'm feeling stressed about my upcoming exams.",
            sentiment="negative", created_at=now - timedelta(minutes=4),
        ))
        db.add(Message(
            conversation_id=conv_id, sender_type="ai",
            message_text="I understand exam stress can feel overwhelming. Let's work through this together. What specific aspect is causing you the most worry?",
            created_at=now - timedelta(minutes=3),
        ))

        # ---------------------------------------------------------------
        # 5. Wellness Records (7 days for trend chart)
        # ---------------------------------------------------------------
        base_date = date.today() - timedelta(days=6)
        scores = [(65, 5, 6, 4, 6), (68, 4, 7, 3, 7), (62, 6, 5, 5, 5),
                   (70, 4, 7, 3, 7), (72, 3, 7, 3, 8), (75, 3, 8, 2, 8), (72, 4, 7, 3, 7)]

        for i, (mood, stress, conf, anx, energy) in enumerate(scores):
            db.add(WellnessRecord(
                student_id=student_id,
                mood_score=mood // 10, stress_score=stress,
                confidence_score=conf, anxiety_score=anx, energy_score=energy,
                date_recorded=base_date + timedelta(days=i),
            ))

        # ---------------------------------------------------------------
        # 6. Parent Insight
        # ---------------------------------------------------------------
        db.add(ParentInsightHistory(
            student_id=student_id, wellness_score=Decimal("72.00"),
            risk_level="yellow",
            summary="Your child may be experiencing increased stress related to upcoming exams. Good peer connections observed.",
            recommendations="Dedicated one-on-one time|Avoid peer comparisons|Encourage physical activity",
        ))

        # ---------------------------------------------------------------
        # 7. Counselor Sessions
        # ---------------------------------------------------------------
        db.add(CounselorSession(
            student_id=student_id, counselor_id=counselor_id,
            scheduled_at=now + timedelta(hours=2), status="scheduled",
            ai_summary="Student has been experiencing increased anxiety around upcoming final exams.",
        ))
        db.add(CounselorSession(
            student_id=mike_student_id, counselor_id=counselor_id,
            scheduled_at=now + timedelta(hours=4), status="scheduled",
        ))
        db.add(CounselorSession(
            student_id=emily_student_id, counselor_id=counselor_id,
            scheduled_at=now + timedelta(days=1, hours=2), status="scheduled",
            ai_summary="IMMEDIATE FOLLOW-UP RECOMMENDED. Student has expressed persistent feelings of sadness.",
        ))

        # ---------------------------------------------------------------
        # 8. Analytics Snapshots (6 months)
        # ---------------------------------------------------------------
        months = [("Jan", 68), ("Feb", 70), ("Mar", 67), ("Apr", 72), ("May", 75), ("Jun", 73)]
        for i, (name, score) in enumerate(months):
            db.add(AnalyticsSnapshot(
                tenant_id=tenant_id,
                snapshot_month=date(2026, i + 1, 1),
                total_students=970, avg_wellness=Decimal(str(score)),
                avg_risk=Decimal("15.0"), engagement_rate=Decimal("87.0"),
            ))

        # ---------------------------------------------------------------
        # 9. Subscription
        # ---------------------------------------------------------------
        db.add(Subscription(
            tenant_id=tenant_id, plan_name="Professional",
            student_limit=1000, active_students=970,
            billing_cycle="annual", amount=Decimal("4999.00"),
            start_date=date(2025, 8, 1), renewal_date=date(2026, 8, 1),
            status="active",
        ))

        # ---------------------------------------------------------------
        # 10. Notifications
        # ---------------------------------------------------------------
        db.add(Notification(
            user_id=counselor_user_id,
            title="Risk Alert: Emily Rodriguez",
            message="High risk detected. Depression indicators found in recent conversations.",
        ))

        await db.commit()
        print("[OK] Seed data created successfully!")
        print(f"   Tenant: Riverside High School (code: RHS2026)")
        print(f"   Default password for all users: MindBridge2026!")
        print(f"   Student: sarah.johnson@student.rhs.edu")
        print(f"   Parent:  parent.johnson@email.com")
        print(f"   Counselor: jennifer.martinez@rhs.edu")
        print(f"   School Admin: admin@rhs.edu")
        print(f"   Platform Admin: admin@mindbridge.ai")


if __name__ == "__main__":
    asyncio.run(seed())
