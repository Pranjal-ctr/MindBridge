"""
One-time production bootstrap: the first school and the first platform admin.

    python -m database.bootstrap

Why this exists
---------------
A freshly migrated production database has no tenants and no users, and every
route in is closed:

  * ``seed`` is refused when ``ENVIRONMENT=production`` -- correctly, because it
    creates one account per role sharing a password published in this
    repository and its git history.
  * self-signup is limited to ``student|parent`` by schema, and both roles
    require a ``school_code`` that resolves to an existing tenant.
  * every ``/admin/*`` endpoint requires ``role == "admin"`` -- a role nobody
    can hold yet.

So the deploy would succeed, the health check would pass, and the product would
be unusable, with nothing in the logs to say why. This closes that gap without
opening a new one.

What keeps it from becoming a back door
---------------------------------------
1. **It refuses when any platform admin already exists.** That is the property
   that makes it one-time rather than a general admin-creation path, and it is
   checked inside one transaction with the insert so two concurrent runs cannot
   both pass it.
2. **It is not reachable over HTTP.** There is no endpoint, no route, nothing
   in the OpenAPI schema. It runs as a container command or a one-off shell.
3. **Credentials come from the environment and are never echoed.** The password
   is read, hashed and dropped; nothing prints it, and the audit row records
   the email only.
4. **It refuses a weak or well-known password**, so the seed password cannot be
   reused here to reach the same outcome by another name.

Operational steps are in ``docs/deployment.md``; rotate the password after
first sign-in.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

from sqlalchemy import func, select

from app.auth.utils import hash_password
from database.models import SchoolAdminProfile, Tenant, User
from database.session import async_session_factory, engine

#: Passwords that must never reach production, whatever the length rule says.
#: The seed password is published in this repo; the rest are what gets typed
#: when someone is in a hurry.
_FORBIDDEN_PASSWORDS = frozenset({
    "mindbridge2026!",
    "password",
    "password123",
    "admin",
    "admin123",
    "changeme",
    "kio2026!",
})

#: Longer than the 8 the signup schema allows. This account can read every
#: school on the platform and open break-glass access to a student's chat.
_MIN_PASSWORD_LENGTH = 12


class BootstrapRefused(RuntimeError):
    """Raised when bootstrapping is not allowed or the input is unusable."""


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise BootstrapRefused(
            f"{name} is required. See docs/deployment.md - Bootstrap."
        )
    return value


def _validate_password(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise BootstrapRefused(
            f"BOOTSTRAP_ADMIN_PASSWORD must be at least {_MIN_PASSWORD_LENGTH} "
            "characters. This account can reach every school on the platform."
        )
    if password.strip().lower() in _FORBIDDEN_PASSWORDS:
        raise BootstrapRefused(
            "BOOTSTRAP_ADMIN_PASSWORD is a known or published password. "
            "Choose one that has never been committed anywhere."
        )


async def bootstrap(session_factory=async_session_factory) -> dict[str, str]:
    """
    Create the first school and platform admin. Returns what was created.

    Idempotent in the only sense that matters: the second run refuses rather
    than creating a second admin. Commits once, at the end.
    """
    admin_email = _require_env("BOOTSTRAP_ADMIN_EMAIL").lower()
    admin_password = _require_env("BOOTSTRAP_ADMIN_PASSWORD")
    school_name = _require_env("BOOTSTRAP_SCHOOL_NAME")
    school_code = _require_env("BOOTSTRAP_SCHOOL_CODE").upper()

    _validate_password(admin_password)

    admin_first = (os.getenv("BOOTSTRAP_ADMIN_FIRST_NAME") or "Platform").strip()
    admin_last = (os.getenv("BOOTSTRAP_ADMIN_LAST_NAME") or "Admin").strip()

    async with session_factory() as db:
        # The guard and the insert share one transaction: checked outside it,
        # two containers starting together could both see zero admins.
        existing_admins = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.role == "admin")
            )
        ).scalar() or 0
        if existing_admins:
            raise BootstrapRefused(
                f"REFUSING to bootstrap: {existing_admins} platform admin "
                "account(s) already exist. This command creates the FIRST "
                "admin only. Use /admin/users to add more, or reset the "
                "existing admin's password."
            )

        if (
            await db.execute(select(User).where(User.email == admin_email))
        ).scalar_one_or_none() is not None:
            raise BootstrapRefused(
                f"An account already exists for {admin_email}."
            )

        tenant = (
            await db.execute(select(Tenant).where(Tenant.school_code == school_code))
        ).scalar_one_or_none()
        created_school = tenant is None
        if tenant is None:
            tenant = Tenant(
                tenant_id=uuid.uuid4(),
                tenant_name=school_name,
                tenant_type="school",
                school_code=school_code,
                status="active",
            )
            db.add(tenant)
            await db.flush()

        admin = User(
            user_id=uuid.uuid4(),
            tenant_id=tenant.tenant_id,
            email=admin_email,
            password_hash=hash_password(admin_password),
            role="admin",
            first_name=admin_first,
            last_name=admin_last,
            is_active=True,
            # Verified on creation: the operator typed this address into the
            # server's own environment, which is stronger evidence of control
            # than clicking a link in an inbox. It also avoids a chicken-and-egg
            # where the first admin cannot clear the verification banner
            # because outbound email is not configured yet.
            is_verified=True,
        )
        db.add(admin)
        await db.flush()
        db.add(SchoolAdminProfile(user_id=admin.user_id))

        # Audited like any other account creation. Written directly rather than
        # through log_audit(): there is no request, no actor but the operator
        # at the shell, and the helper's ContextVar lookup would record a
        # request id of "-" for an event that never had one.
        from app.audit import build_audit_row
        from app.audit_actions import AuditAction, AuditEntity, AuditSeverity

        db.add(build_audit_row(
            user_id=admin.user_id,
            action=AuditAction.USER_CREATED,
            entity_type=AuditEntity.USER,
            entity_id=admin.user_id,
            details={
                "role": "admin",
                "email": admin_email,
                "via": "database.bootstrap",
                "school_created": created_school,
            },
            actor_role="system",
            tenant_id=tenant.tenant_id,
            severity=AuditSeverity.CRITICAL,
        ))

        await db.commit()

    return {
        "admin_email": admin_email,
        "school_code": school_code,
        "school_name": tenant.tenant_name,
        "school_created": str(created_school),
    }


async def _main() -> int:
    try:
        result = await bootstrap()
    except BootstrapRefused as exc:
        print(f"[BOOTSTRAP] {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    print("[BOOTSTRAP] Platform admin created.")
    print(f"            email       : {result['admin_email']}")
    print(f"            school      : {result['school_name']} ({result['school_code']})")
    print("            password    : (as supplied; not echoed)")
    print()
    print("Next steps:")
    print("  1. Sign in and change this password.")
    print("  2. Remove BOOTSTRAP_* variables from the environment.")
    print("  3. Register counselors at /admin/counselors and assign them to")
    print("     the school, or they will receive no risk alerts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
