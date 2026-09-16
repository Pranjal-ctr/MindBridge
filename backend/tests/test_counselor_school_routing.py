"""
A counselor registered through /admin/counselors must actually reach the
students they serve.

This file exists because of a defect found in the pre-pilot audit, and the
first test reproduces it exactly. `POST /admin/counselors` places the user in
the PLATFORM tenant -- correct, because booking is platform-wide -- while every
alerting and queue query scoped on `User.tenant_id == student.tenant_id`. A
platform counselor is never in that set, so:

  * the crisis fan-out selected zero recipients and audited
    `recipient_count: 0`
  * the keyword tripwire notified nobody
  * /risk/queue returned an empty queue
  * /counselors/students returned an empty roster

and nothing anywhere reported a problem. Which of the two admin provisioning
pages an operator happened to use silently decided whether a red assessment
reached a human.

The fix routes all four through `counselor_school_assignments`. The tests below
assert the *consequences* -- who is notified, what the queue contains -- rather
than the shape of the helper, because the helper is not what broke.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import create_access_token, hash_password
from app.counselors.assignments import (
    scope_tenant_ids,
    staff_user_ids_for_tenant,
)
from database.models import (
    Conversation,
    CounselorProfile,
    CounselorSchoolAssignment,
    Notification,
    RiskAssessment,
    StudentProfile,
    Tenant,
    User,
)


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

async def _register_counselor(
    client: AsyncClient,
    admin_auth_headers: dict[str, str],
    *,
    tenant_ids: list[str] | None = None,
) -> dict:
    """Register a counselor exactly the way the admin UI does."""
    payload = {
        "email": f"counselor_{uuid.uuid4().hex[:8]}@kio-test.com",
        "password": "CounselorPass123!",
        "first_name": "Casey",
        "last_name": "Counselor",
        "qualification": "M.A. Counselling Psychology",
        "is_verified": True,
    }
    if tenant_ids is not None:
        payload["tenant_ids"] = tenant_ids

    response = await client.post(
        "/admin/counselors", json=payload, headers=admin_auth_headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _platform_tenant_id(db_session: AsyncSession) -> uuid.UUID:
    tenant = (
        await db_session.execute(select(Tenant).where(Tenant.school_code == "PLATFORM"))
    ).scalar_one()
    return tenant.tenant_id


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({
        "sub": str(user.user_id),
        "tenant_id": str(user.tenant_id),
        "role": user.role,
    })
    return {"Authorization": f"Bearer {token}"}


async def _user_for(db_session: AsyncSession, user_id: uuid.UUID) -> User:
    return (
        await db_session.execute(select(User).where(User.user_id == user_id))
    ).scalar_one()


async def _conversation_for(db_session: AsyncSession, student_user_id: uuid.UUID) -> uuid.UUID:
    """A real conversation row -- risk_assessments.conversation_id is a FK."""
    profile = (
        await db_session.execute(
            select(StudentProfile).where(StudentProfile.user_id == student_user_id)
        )
    ).scalar_one()
    conversation = Conversation(
        conversation_id=uuid.uuid4(), student_id=profile.student_id, title="Test"
    )
    db_session.add(conversation)
    await db_session.flush()
    return conversation.conversation_id


# -------------------------------------------------------------------
# The defect, reproduced
# -------------------------------------------------------------------

class TestRegisteredCounselorIsReachable:
    @pytest.mark.asyncio
    async def test_counselor_registered_for_a_school_is_alerted_about_its_students(
        self, client, db_session, test_tenant, admin_auth_headers
    ):
        """
        The exact broken flow: register through /admin/counselors, then ask who
        gets told when a student at that school is at risk.

        Before the fix this returned an empty list, because the counselor's own
        account lives in the PLATFORM tenant and the query scoped on the
        student's tenant.
        """
        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )

        # The counselor really is in the platform tenant -- the fix does not
        # move them, because booking is platform-wide.
        counselor_user = await _user_for(db_session, uuid.UUID(counselor["user_id"]))
        assert counselor_user.tenant_id == await _platform_tenant_id(db_session)
        assert counselor_user.tenant_id != test_tenant.tenant_id

        recipients = await staff_user_ids_for_tenant(db_session, test_tenant.tenant_id)
        assert counselor_user.user_id in recipients

    @pytest.mark.asyncio
    async def test_counselor_with_no_school_receives_nothing(
        self, client, db_session, test_tenant, admin_auth_headers
    ):
        """
        Registering without a school is allowed but leaves the counselor
        unreachable. Asserted so the consequence stays deliberate rather than
        becoming a second silent failure.
        """
        counselor = await _register_counselor(client, admin_auth_headers, tenant_ids=[])

        recipients = await staff_user_ids_for_tenant(db_session, test_tenant.tenant_id)
        assert uuid.UUID(counselor["user_id"]) not in recipients

    @pytest.mark.asyncio
    async def test_counselor_is_not_alerted_about_a_school_they_do_not_serve(
        self, client, db_session, test_tenant, admin_auth_headers
    ):
        """Assignment grants access to one school, not to every school."""
        other_school = Tenant(
            tenant_id=uuid.uuid4(),
            tenant_name="Other School",
            tenant_type="school",
            school_code=f"OTHER{uuid.uuid4().hex[:5].upper()}",
            status="active",
        )
        db_session.add(other_school)
        await db_session.flush()

        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )

        recipients = await staff_user_ids_for_tenant(db_session, other_school.tenant_id)
        assert uuid.UUID(counselor["user_id"]) not in recipients

    @pytest.mark.asyncio
    async def test_deactivated_counselor_is_not_counted_as_a_recipient(
        self, client, db_session, test_tenant, admin_auth_headers
    ):
        """
        A deactivated account must not inflate the recipient count -- a crisis
        audit row saying an alert reached someone who cannot sign in is worse
        than one saying it reached nobody.
        """
        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )
        counselor_user = await _user_for(db_session, uuid.UUID(counselor["user_id"]))
        counselor_user.is_active = False
        await db_session.flush()

        recipients = await staff_user_ids_for_tenant(db_session, test_tenant.tenant_id)
        assert counselor_user.user_id not in recipients


# -------------------------------------------------------------------
# The counselor's own surfaces
# -------------------------------------------------------------------

class TestCounselorWorkingSurfaces:
    @pytest.mark.asyncio
    async def test_risk_queue_shows_students_from_the_assigned_school(
        self, client, db_session, test_tenant, test_student_user, admin_auth_headers
    ):
        """Before the fix this queue was empty for every platform counselor."""
        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )
        counselor_user = await _user_for(db_session, uuid.UUID(counselor["user_id"]))

        profile = (
            await db_session.execute(
                select(StudentProfile).where(
                    StudentProfile.user_id == test_student_user.user_id
                )
            )
        ).scalar_one()
        db_session.add(RiskAssessment(
            student_id=profile.student_id,
            risk_level="red",
            trigger_reason="test fixture",
            generated_by="keyword_tripwire",
            review_status="pending",
        ))
        await db_session.flush()

        response = await client.get("/risk/queue", headers=_auth_headers(counselor_user))
        assert response.status_code == 200, response.text
        assert response.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_roster_shows_students_from_the_assigned_school(
        self, client, db_session, test_tenant, test_student_user, admin_auth_headers
    ):
        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )
        counselor_user = await _user_for(db_session, uuid.UUID(counselor["user_id"]))

        profile = (
            await db_session.execute(
                select(StudentProfile).where(
                    StudentProfile.user_id == test_student_user.user_id
                )
            )
        ).scalar_one()

        response = await client.get(
            "/counselors/students", headers=_auth_headers(counselor_user)
        )
        assert response.status_code == 200, response.text
        student_ids = {row["student_id"] for row in response.json()["students"]}
        assert str(profile.student_id) in student_ids

    @pytest.mark.asyncio
    async def test_unassigned_counselor_sees_no_other_schools_students(
        self, client, db_session, test_tenant, test_student_user, admin_auth_headers
    ):
        """The scope widens to assigned schools -- it does not become global."""
        counselor = await _register_counselor(client, admin_auth_headers, tenant_ids=[])
        counselor_user = await _user_for(db_session, uuid.UUID(counselor["user_id"]))

        profile = (
            await db_session.execute(
                select(StudentProfile).where(
                    StudentProfile.user_id == test_student_user.user_id
                )
            )
        ).scalar_one()

        response = await client.get(
            "/counselors/students", headers=_auth_headers(counselor_user)
        )
        assert response.status_code == 200, response.text
        student_ids = {row["student_id"] for row in response.json()["students"]}
        assert str(profile.student_id) not in student_ids

    @pytest.mark.asyncio
    async def test_school_tenant_counselor_still_works_without_assignments(
        self, db_session, test_tenant
    ):
        """
        The other provisioning path (POST /admin/users with a tenant_id) creates
        a counselor inside the school itself. They hold no assignment rows, and
        must keep working exactly as before.
        """
        user = User(
            user_id=uuid.uuid4(),
            tenant_id=test_tenant.tenant_id,
            email=f"inschool_{uuid.uuid4().hex[:8]}@kio-test.com",
            password_hash=hash_password("TestPassword123!"),
            role="counselor",
            first_name="In",
            last_name="School",
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(CounselorProfile(counselor_id=uuid.uuid4(), user_id=user.user_id))
        await db_session.flush()

        assert user.user_id in await staff_user_ids_for_tenant(
            db_session, test_tenant.tenant_id
        )
        assert await scope_tenant_ids(db_session, user) == [test_tenant.tenant_id]


# -------------------------------------------------------------------
# Crisis fan-out, end to end
# -------------------------------------------------------------------

class TestCrisisFanOutReachesTheCounselor:
    @pytest.mark.asyncio
    async def test_keyword_tripwire_notifies_the_assigned_counselor(
        self, client, db_session, test_tenant, test_student_user, admin_auth_headers
    ):
        """
        The instant tripwire is the fastest path from a student's words to a
        human. It notified nobody for a platform counselor.
        """
        from app.ai.safety import _raise_keyword_tripwire

        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )
        counselor_user_id = uuid.UUID(counselor["user_id"])

        await _raise_keyword_tripwire(
            db_session,
            conversation_id=await _conversation_for(
                db_session, test_student_user.user_id
            ),
            student_user_id=test_student_user.user_id,
            tripped={"self_harm"},
        )
        await db_session.flush()

        notified = {
            row[0]
            for row in (
                await db_session.execute(
                    select(Notification.user_id).where(
                        Notification.user_id == counselor_user_id
                    )
                )
            ).all()
        }
        assert counselor_user_id in notified

    @pytest.mark.asyncio
    async def test_notification_carries_no_message_content(
        self, client, db_session, test_tenant, test_student_user, admin_auth_headers
    ):
        """Widening the recipient set must not widen what they are told."""
        from app.ai.safety import _raise_keyword_tripwire

        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )

        await _raise_keyword_tripwire(
            db_session,
            conversation_id=await _conversation_for(
                db_session, test_student_user.user_id
            ),
            student_user_id=test_student_user.user_id,
            tripped={"self_harm"},
        )
        await db_session.flush()

        rows = (
            await db_session.execute(
                select(Notification).where(
                    Notification.user_id == uuid.UUID(counselor["user_id"])
                )
            )
        ).scalars().all()
        assert rows
        for row in rows:
            assert "self_harm" not in row.message
            assert "review required" in row.message


# -------------------------------------------------------------------
# Managing assignments
# -------------------------------------------------------------------

class TestAssignmentManagement:
    @pytest.mark.asyncio
    async def test_admin_can_assign_an_existing_counselor_to_a_school(
        self, client, db_session, test_tenant, admin_auth_headers
    ):
        """The remedy for counselors registered before this field existed."""
        counselor = await _register_counselor(client, admin_auth_headers, tenant_ids=[])
        counselor_id = counselor["counselor_id"]

        response = await client.put(
            f"/admin/counselors/{counselor_id}/schools",
            json={"tenant_ids": [str(test_tenant.tenant_id)]},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["tenant_ids"] == [str(test_tenant.tenant_id)]

        assert uuid.UUID(counselor["user_id"]) in await staff_user_ids_for_tenant(
            db_session, test_tenant.tenant_id
        )

    @pytest.mark.asyncio
    async def test_removing_an_assignment_stops_the_alerts(
        self, client, db_session, test_tenant, admin_auth_headers
    ):
        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )
        response = await client.put(
            f"/admin/counselors/{counselor['counselor_id']}/schools",
            json={"tenant_ids": []},
            headers=admin_auth_headers,
        )
        assert response.status_code == 200, response.text

        assert uuid.UUID(counselor["user_id"]) not in await staff_user_ids_for_tenant(
            db_session, test_tenant.tenant_id
        )

    @pytest.mark.asyncio
    async def test_reassigning_is_idempotent(
        self, client, db_session, test_tenant, admin_auth_headers
    ):
        """
        The unique constraint on (counselor_id, tenant_id) means a naive
        re-insert would 500 on the second save.
        """
        counselor = await _register_counselor(
            client, admin_auth_headers, tenant_ids=[str(test_tenant.tenant_id)]
        )
        for _ in range(2):
            response = await client.put(
                f"/admin/counselors/{counselor['counselor_id']}/schools",
                json={"tenant_ids": [str(test_tenant.tenant_id)]},
                headers=admin_auth_headers,
            )
            assert response.status_code == 200, response.text

        rows = (
            await db_session.execute(
                select(CounselorSchoolAssignment).where(
                    CounselorSchoolAssignment.counselor_id
                    == uuid.UUID(counselor["counselor_id"])
                )
            )
        ).scalars().all()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_unknown_school_is_refused_with_422(
        self, client, admin_auth_headers
    ):
        """A mistyped id must not surface as a foreign-key 500."""
        counselor = await _register_counselor(client, admin_auth_headers, tenant_ids=[])
        response = await client.put(
            f"/admin/counselors/{counselor['counselor_id']}/schools",
            json={"tenant_ids": [str(uuid.uuid4())]},
            headers=admin_auth_headers,
        )
        assert response.status_code == 422, response.text

    @pytest.mark.asyncio
    async def test_assignments_are_platform_admin_only(
        self, client, db_session, test_tenant, admin_auth_headers, student_auth_headers
    ):
        counselor = await _register_counselor(client, admin_auth_headers, tenant_ids=[])
        response = await client.put(
            f"/admin/counselors/{counselor['counselor_id']}/schools",
            json={"tenant_ids": [str(test_tenant.tenant_id)]},
            headers=student_auth_headers,
        )
        assert response.status_code == 403
