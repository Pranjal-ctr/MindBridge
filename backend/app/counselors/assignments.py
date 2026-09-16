"""
Which schools a counselor serves, and who must be told when a student there
is at risk.

Kio has two ways to provision a counselor, and until this module existed they
behaved differently in a way nothing announced:

  * ``POST /admin/counselors`` (the purpose-built page, and the one whose
    ``is_verified`` flag gates the public booking directory) puts the user in
    the **PLATFORM** tenant, because a platform counselor is bookable by any
    student at any school.
  * ``POST /admin/users`` with an explicit ``tenant_id`` puts them in a
    **school** tenant.

Every alerting and queue query, meanwhile, scoped on ``User.tenant_id ==
student.tenant_id``. A platform counselor is never in that set, so they
received no crisis notification, no keyword tripwire, an empty risk queue and
an empty roster -- and nothing anywhere reported a problem. The audit row for
a crisis fan-out recorded ``recipient_count: 0`` and the alert simply went
nowhere. Which of the two admin pages an operator happened to use silently
decided whether a red assessment reached a human.

``counselor_school_assignments`` already existed to express exactly this
relationship and was only ever read by analytics. It is now the join that
makes a platform counselor reachable from a school without moving them out of
the platform tenant, so booking stays platform-wide while alerting is
school-scoped.

Both rules live here rather than in each caller, because "who counts as staff
for this school" is one question and five call sites answering it separately is
how they drifted apart in the first place.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import CounselorProfile, CounselorSchoolAssignment, User

#: Roles that receive risk and crisis notifications for a school.
STAFF_ROLES = ("counselor", "school_admin")


async def assigned_tenant_ids(db: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Schools this counselor is assigned to serve. Empty for non-counselors."""
    result = await db.execute(
        select(CounselorSchoolAssignment.tenant_id)
        .join(
            CounselorProfile,
            CounselorProfile.counselor_id == CounselorSchoolAssignment.counselor_id,
        )
        .where(CounselorProfile.user_id == user_id)
    )
    return [row[0] for row in result.all()]


async def scope_tenant_ids(db: AsyncSession, viewer: User) -> list[uuid.UUID]:
    """
    The schools whose students this staff member may see.

    The viewer's own tenant is always included alongside any assignments. That
    covers both provisioning paths without the caller needing to know which one
    was used: a school-tenant counselor has no assignment rows and is scoped to
    their own school, a platform counselor is scoped to the schools they are
    assigned to, and including PLATFORM for the latter costs nothing because no
    student is ever created in it.

    School admins and platform admins are unaffected -- they hold no
    assignments, so this returns their own tenant exactly as before.
    """
    tenant_ids = {viewer.tenant_id}
    if viewer.role == "counselor":
        tenant_ids.update(await assigned_tenant_ids(db, viewer.user_id))
    return list(tenant_ids)


async def staff_user_ids_for_tenant(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[uuid.UUID]:
    """
    Everyone who must be alerted about a student at this school.

    Two groups, unioned: staff whose account lives in the school's own tenant,
    and counselors assigned to the school from the platform tenant. Inactive
    accounts are excluded from both -- a deactivated counselor is not a
    recipient, and counting them would make a fan-out look like it reached
    someone it did not.
    """
    in_tenant = await db.execute(
        select(User.user_id).where(
            User.tenant_id == tenant_id,
            User.role.in_(STAFF_ROLES),
            User.is_active.is_(True),
        )
    )
    assigned = await db.execute(
        select(User.user_id)
        .join(CounselorProfile, CounselorProfile.user_id == User.user_id)
        .join(
            CounselorSchoolAssignment,
            CounselorSchoolAssignment.counselor_id == CounselorProfile.counselor_id,
        )
        .where(
            CounselorSchoolAssignment.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
    )
    # Set union: a counselor can legitimately be both in the tenant and
    # assigned to it, and notifying them twice for one event is noise.
    unique = {row[0] for row in in_tenant.all()} | {row[0] for row in assigned.all()}
    return list(unique)


async def set_assignments(
    db: AsyncSession,
    counselor_id: uuid.UUID,
    tenant_ids: Sequence[uuid.UUID],
    *,
    assigned_by: uuid.UUID | None = None,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """
    Make this counselor's assignments exactly ``tenant_ids``.

    Returns ``(added, removed)`` so the caller can audit what changed rather
    than recording that "assignments were set", which answers nothing after the
    fact. Flushes but does not commit -- the caller owns the transaction.
    """
    existing_rows = (
        await db.execute(
            select(CounselorSchoolAssignment).where(
                CounselorSchoolAssignment.counselor_id == counselor_id
            )
        )
    ).scalars().all()

    existing = {row.tenant_id: row for row in existing_rows}
    wanted = set(tenant_ids)

    added = [tenant_id for tenant_id in wanted if tenant_id not in existing]
    removed = [tenant_id for tenant_id in existing if tenant_id not in wanted]

    for tenant_id in added:
        db.add(
            CounselorSchoolAssignment(
                assignment_id=uuid.uuid4(),
                counselor_id=counselor_id,
                tenant_id=tenant_id,
                assigned_by=assigned_by,
            )
        )
    for tenant_id in removed:
        await db.delete(existing[tenant_id])

    await db.flush()
    return added, removed
