"""
Audit trail: coverage, append-only enforcement, privacy, and access control.

The threat model these describe is specific. Kio's audit table records who
touched a minor's mental-health record. That makes it valuable in two opposite
directions at once: it must be complete enough to answer "who read this child's
conversation", and empty enough that reading the audit table is not itself a
way to learn what the child said.

So the assertions here come in two halves. One half checks that events are
written, attributed to the right actor and school, and correlated to a request.
The other half checks that specific strings -- passwords, tokens, message text
-- never appear in the table no matter which path wrote the row.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text, update

from app.audit import log_audit_detached, scrub_details
from app.audit_actions import AuditAction, AuditResult, AuditSeverity
from app.auth.utils import create_access_token, hash_password
from database.models import AuditLog, StudentProfile, Tenant, User


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

async def _rows(db, action=None, **where):
    """Audit rows, newest first, optionally filtered by action prefix."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action is not None:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    for key, value in where.items():
        stmt = stmt.where(getattr(AuditLog, key) == value)
    return (await db.execute(stmt)).scalars().all()


async def _one(db, action, **where):
    rows = await _rows(db, action, **where)
    assert rows, f"no audit row written for action {action!r}"
    return rows[0]


@pytest_asyncio.fixture
async def login_account(db_session, test_tenant: Tenant):
    """
    A student who can actually sign in, with a known password.

    Committed, not merely flushed. Auth events are written by
    log_audit_detached, which opens its *own* session precisely so the row
    survives the rollback of a failed login -- and a separate session cannot
    see uncommitted rows, so an un-committed fixture user would make every
    detached write fail its foreign key. That failure is swallowed by design,
    so the symptom would be a silently missing audit row rather than an error.
    """
    password = "AuditPassw0rd!"
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=test_tenant.tenant_id,
        email=f"audit_{uuid.uuid4().hex[:8]}@student.rhs.edu",
        password_hash=hash_password(password),
        role="student",
        first_name="Audit",
        last_name="Subject",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(StudentProfile(user_id=user.user_id, age=16, risk_level="green"))
    await db_session.commit()
    return user, password


@pytest_asyncio.fixture
async def safety_subject(db_session, login_account):
    """
    A committed student + conversation for the safety scanner.

    A hard safety signal also raises a keyword tripwire, which inserts a
    risk_assessment referencing the conversation. With a fabricated
    conversation id that insert violates its foreign key and poisons the
    session, so the audit rows in the same transaction are lost too.
    """
    from database.models import Conversation

    user, _ = login_account
    student_id = (
        await db_session.execute(
            select(StudentProfile.student_id).where(
                StudentProfile.user_id == user.user_id
            )
        )
    ).scalar_one()

    conversation = Conversation(
        conversation_id=uuid.uuid4(),
        student_id=student_id,
        title="Audit fixture conversation",
    )
    db_session.add(conversation)
    await db_session.commit()
    return user, conversation.conversation_id


# -------------------------------------------------------------------
# Append-only enforcement
# -------------------------------------------------------------------

class TestAppendOnly:
    """The database refuses to rewrite history, not merely the application."""

    @pytest.mark.asyncio
    async def test_insert_is_allowed(self, db_session):
        audit_id = uuid.uuid4()
        await db_session.execute(
            text(
                "INSERT INTO audit_logs (audit_id, action, result, severity) "
                "VALUES (:i, 'test.insert', 'success', 'info')"
            ),
            {"i": audit_id},
        )
        await db_session.flush()
        assert (await _rows(db_session, "test.insert"))

    @pytest.mark.asyncio
    async def test_update_is_refused_by_the_database(self, db_session):
        """Even a direct UPDATE, bypassing the ORM entirely, is rejected."""
        audit_id = uuid.uuid4()
        await db_session.execute(
            text(
                "INSERT INTO audit_logs (audit_id, action, result, severity) "
                "VALUES (:i, 'test.update', 'success', 'info')"
            ),
            {"i": audit_id},
        )
        await db_session.flush()

        with pytest.raises(Exception) as exc:
            await db_session.execute(
                update(AuditLog)
                .where(AuditLog.audit_id == audit_id)
                .values(action="tampered")
            )
            await db_session.flush()
        assert "append-only" in str(exc.value).lower()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_delete_is_refused_by_the_database(self, db_session):
        audit_id = uuid.uuid4()
        await db_session.execute(
            text(
                "INSERT INTO audit_logs (audit_id, action, result, severity) "
                "VALUES (:i, 'test.delete', 'success', 'info')"
            ),
            {"i": audit_id},
        )
        await db_session.flush()

        with pytest.raises(Exception) as exc:
            await db_session.execute(
                text("DELETE FROM audit_logs WHERE audit_id = :i"), {"i": audit_id}
            )
            await db_session.flush()
        assert "append-only" in str(exc.value).lower()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_truncate_is_refused(self, db_session):
        with pytest.raises(Exception) as exc:
            await db_session.execute(text("TRUNCATE audit_logs"))
            await db_session.flush()
        assert "append-only" in str(exc.value).lower()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_no_mutating_audit_endpoints_exist(self):
        """
        There is no write path to the audit trail over HTTP.

        Asserted against the live route table rather than by reading the
        router, so adding a PUT/PATCH/DELETE under /audit-logs later fails
        here rather than shipping quietly.
        """
        from main import app

        mutating = {"POST", "PUT", "PATCH", "DELETE"}
        offenders = [
            (route.path, sorted(route.methods & mutating))
            for route in app.routes
            if getattr(route, "methods", None)
            and "audit-log" in getattr(route, "path", "")
            and route.methods & mutating
        ]
        assert offenders == [], f"audit trail has mutating endpoints: {offenders}"


# -------------------------------------------------------------------
# Authentication events
# -------------------------------------------------------------------

class TestAuthEvents:
    @pytest.mark.asyncio
    async def test_successful_login_is_audited(
        self, client: AsyncClient, db_session, login_account
    ):
        user, password = login_account
        resp = await client.post(
            "/auth/login", json={"email": user.email, "password": password}
        )
        assert resp.status_code == 200

        row = await _one(db_session, AuditAction.LOGIN_SUCCESS)
        assert row.user_id == user.user_id
        assert row.actor_role == "student"
        assert row.tenant_id == user.tenant_id
        assert row.result == AuditResult.SUCCESS

    @pytest.mark.asyncio
    async def test_failed_login_is_audited_and_survives_the_rollback(
        self, client: AsyncClient, db_session, login_account
    ):
        """
        The failure path raises, which rolls back the request's session.

        This is the whole reason log_audit_detached exists: a failed-login row
        written on the caller's session would disappear at exactly the moment
        it becomes evidence.
        """
        user, _ = login_account
        resp = await client.post(
            "/auth/login", json={"email": user.email, "password": "WrongPassword1!"}
        )
        assert resp.status_code == 401

        row = await _one(db_session, AuditAction.LOGIN_FAILED)
        assert row.result == AuditResult.FAILURE
        assert row.severity == AuditSeverity.WARNING
        assert row.details["reason"] == "bad_password"

    @pytest.mark.asyncio
    async def test_failed_login_for_unknown_email_records_no_actor(
        self, client: AsyncClient, db_session
    ):
        resp = await client.post(
            "/auth/login",
            json={"email": "nobody@nowhere.example.com", "password": "Whatever1!"},
        )
        assert resp.status_code == 401

        rows = await _rows(db_session, AuditAction.LOGIN_FAILED)
        unknown = [r for r in rows if r.details.get("reason") == "unknown_email"]
        assert unknown, "unknown-email login attempt was not recorded"
        assert unknown[0].user_id is None

    @pytest.mark.asyncio
    async def test_logout_is_audited(
        self, client: AsyncClient, db_session, login_account
    ):
        user, password = login_account
        login = await client.post(
            "/auth/login", json={"email": user.email, "password": password}
        )
        refresh = login.json()["tokens"]["refresh_token"]

        resp = await client.post("/auth/logout", json={"refresh_token": refresh})
        assert resp.status_code == 200

        row = await _one(db_session, AuditAction.LOGOUT)
        assert row.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_refresh_rotation_is_audited(
        self, client: AsyncClient, db_session, login_account
    ):
        user, password = login_account
        login = await client.post(
            "/auth/login", json={"email": user.email, "password": password}
        )
        refresh = login.json()["tokens"]["refresh_token"]

        resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        assert await _rows(db_session, AuditAction.REFRESH_TOKEN_ROTATED)

    @pytest.mark.asyncio
    async def test_replayed_refresh_token_is_audited_as_critical(
        self, client: AsyncClient, db_session, login_account
    ):
        """A replayed token means a copy is in circulation. Loudest event here."""
        user, password = login_account
        login = await client.post(
            "/auth/login", json={"email": user.email, "password": password}
        )
        refresh = login.json()["tokens"]["refresh_token"]

        await client.post("/auth/refresh", json={"refresh_token": refresh})
        replay = await client.post("/auth/refresh", json={"refresh_token": refresh})
        assert replay.status_code == 401

        row = await _one(db_session, AuditAction.REFRESH_TOKEN_REVOKED)
        assert row.severity == AuditSeverity.CRITICAL
        assert row.result == AuditResult.FAILURE


# -------------------------------------------------------------------
# Admin / RBAC / school events
# -------------------------------------------------------------------

class TestAdminEvents:
    @pytest.mark.asyncio
    async def test_school_creation_is_attributed_to_the_new_school(
        self, client: AsyncClient, db_session, admin_auth_headers
    ):
        code = f"AUD{uuid.uuid4().hex[:5].upper()}"
        resp = await client.post(
            "/admin/tenants",
            headers=admin_auth_headers,
            json={"tenant_name": "Audited High", "school_code": code},
        )
        assert resp.status_code in (200, 201), resp.text
        new_tenant_id = uuid.UUID(resp.json()["tenant_id"])

        row = await _one(db_session, AuditAction.SCHOOL_CREATED)
        # The event belongs to the school that was created, not to the
        # platform admin's own tenant.
        assert row.tenant_id == new_tenant_id
        assert row.actor_role == "admin"

    @pytest.mark.asyncio
    async def test_user_deactivation_is_audited_against_the_subject_school(
        self, client: AsyncClient, db_session, admin_auth_headers, test_student_user
    ):
        resp = await client.patch(
            f"/admin/users/{test_student_user.user_id}",
            headers=admin_auth_headers,
            json={"is_active": False},
        )
        assert resp.status_code == 200, resp.text

        row = await _one(db_session, AuditAction.USER_DEACTIVATED)
        assert row.entity_id == test_student_user.user_id
        assert row.tenant_id == test_student_user.tenant_id
        assert row.severity == AuditSeverity.WARNING

    @pytest.mark.asyncio
    async def test_admin_password_reset_never_stores_the_password(
        self, client: AsyncClient, db_session, admin_auth_headers, test_student_user
    ):
        secret = "SuperSecretReset9!"
        resp = await client.patch(
            f"/admin/users/{test_student_user.user_id}",
            headers=admin_auth_headers,
            json={"new_password": secret},
        )
        assert resp.status_code == 200, resp.text

        row = await _one(db_session, AuditAction.PASSWORD_RESET_BY_ADMIN)
        assert secret not in str(row.details)
        assert secret not in (str(row.action) + str(row.entity_type))

    @pytest.mark.asyncio
    async def test_break_glass_keeps_the_reason_out_of_the_action_name(
        self, client: AsyncClient, db_session, admin_auth_headers, test_student_user
    ):
        """
        The reason is structured metadata, not part of the action.

        It used to be interpolated into the action string, which made the
        indexed column a free-text field and meant no two break-glass events
        ever shared an action.
        """
        student_id = (
            await db_session.execute(
                select(StudentProfile.student_id).where(
                    StudentProfile.user_id == test_student_user.user_id
                )
            )
        ).scalar_one()

        reason = "Counselor escalation, case 12345"
        resp = await client.get(
            f"/admin/students/{student_id}/conversations",
            headers=admin_auth_headers,
            params={"reason": reason},
        )
        assert resp.status_code == 200, resp.text

        row = await _one(db_session, AuditAction.BREAK_GLASS_CHAT_ACCESS)
        assert row.action == AuditAction.BREAK_GLASS_CHAT_ACCESS
        assert reason not in row.action
        assert row.details["reason"] == reason
        assert row.severity == AuditSeverity.CRITICAL
        # Attributed to the student's school, not the platform admin's.
        assert row.tenant_id == test_student_user.tenant_id


# -------------------------------------------------------------------
# Reading the audit trail is itself audited
# -------------------------------------------------------------------

class TestAuditOfAuditAccess:
    @pytest.mark.asyncio
    async def test_viewing_the_audit_log_is_recorded(
        self, client: AsyncClient, db_session, admin_auth_headers
    ):
        resp = await client.get("/admin/audit-logs", headers=admin_auth_headers)
        assert resp.status_code == 200

        row = await _one(db_session, AuditAction.AUDIT_LOG_VIEWED)
        assert row.actor_role == "admin"

    @pytest.mark.asyncio
    async def test_export_is_recorded_and_returns_csv(
        self, client: AsyncClient, db_session, admin_auth_headers
    ):
        resp = await client.get(
            "/admin/audit-logs/export",
            headers=admin_auth_headers,
            params={"severity": "critical"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.text.splitlines()[0].startswith("timestamp,request_id,")

        row = await _one(db_session, AuditAction.AUDIT_LOG_EXPORTED)
        assert row.severity == AuditSeverity.WARNING
        assert row.details["filters"]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_export_csv_carries_no_authorization_header(
        self, client: AsyncClient, admin_auth_headers
    ):
        """The bearer token used to make the request must not end up in the file."""
        token = admin_auth_headers["Authorization"].split(" ", 1)[1]
        resp = await client.get("/admin/audit-logs/export", headers=admin_auth_headers)
        assert resp.status_code == 200
        assert token not in resp.text
        assert "Bearer " not in resp.text


# -------------------------------------------------------------------
# Access control
# -------------------------------------------------------------------

class TestAuditRbac:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", ["student", "parent", "counselor", "school_admin"])
    async def test_non_platform_admins_cannot_read_the_audit_trail(
        self, client: AsyncClient, test_tenant: Tenant, db_session, role
    ):
        """
        Enforced server-side, not by hiding the page.

        School admins are included deliberately: they can see their own
        roster, and an audit row naming which counselor opened which student's
        risk case is sensitive staff data even inside one school. Granting
        them a tenant-scoped view is a product decision, not a default.
        """
        user = User(
            user_id=uuid.uuid4(),
            tenant_id=test_tenant.tenant_id,
            email=f"{role}_{uuid.uuid4().hex[:8]}@test.com",
            password_hash=hash_password("TestPassword123!"),
            role=role,
            first_name="Role",
            last_name="Test",
        )
        db_session.add(user)
        await db_session.flush()

        headers = {
            "Authorization": "Bearer "
            + create_access_token(
                {
                    "sub": str(user.user_id),
                    "tenant_id": str(user.tenant_id),
                    "role": role,
                }
            )
        }

        assert (await client.get("/admin/audit-logs", headers=headers)).status_code == 403
        assert (
            await client.get("/admin/audit-logs/export", headers=headers)
        ).status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_access_is_refused(self, client: AsyncClient):
        assert (await client.get("/admin/audit-logs")).status_code in (401, 403)


# -------------------------------------------------------------------
# Filtering, paging, tenant scoping
# -------------------------------------------------------------------

class TestFilteringAndPaging:
    @pytest_asyncio.fixture(autouse=True)
    async def seeded(self, db_session, test_tenant, test_admin_user):
        """A known set of rows across two schools, three severities."""
        other = Tenant(
            tenant_id=uuid.uuid4(),
            tenant_name="Other School",
            tenant_type="school",
            school_code=f"OTH{uuid.uuid4().hex[:6].upper()}",
            status="active",
        )
        db_session.add(other)
        await db_session.flush()

        base = datetime.now(timezone.utc)
        for i in range(6):
            db_session.add(
                AuditLog(
                    audit_id=uuid.uuid4(),
                    user_id=test_admin_user.user_id,
                    action=f"seeded.event_{i}",
                    entity_type="config",
                    actor_role="admin",
                    tenant_id=test_tenant.tenant_id if i % 2 == 0 else other.tenant_id,
                    result="failure" if i == 5 else "success",
                    severity="critical" if i < 2 else "info",
                    request_id=f"seededreq{i}",
                    created_at=base - timedelta(minutes=i),
                )
            )
        await db_session.flush()
        self.tenant_a = test_tenant.tenant_id
        self.tenant_b = other.tenant_id
        return other

    @pytest.mark.asyncio
    async def test_filter_by_severity(self, client, admin_auth_headers):
        resp = await client.get(
            "/admin/audit-logs",
            headers=admin_auth_headers,
            params={"action": "seeded.", "severity": "critical"},
        )
        assert resp.status_code == 200
        logs = resp.json()["logs"]
        assert len(logs) == 2
        assert all(row["severity"] == "critical" for row in logs)

    @pytest.mark.asyncio
    async def test_filter_by_result(self, client, admin_auth_headers):
        resp = await client.get(
            "/admin/audit-logs",
            headers=admin_auth_headers,
            params={"action": "seeded.", "result": "failure"},
        )
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_filter_by_school_scopes_to_that_tenant(
        self, client, admin_auth_headers
    ):
        """Tenant isolation: a school filter returns only that school's events."""
        resp = await client.get(
            "/admin/audit-logs",
            headers=admin_auth_headers,
            params={"action": "seeded.", "tenant_id": str(self.tenant_b)},
        )
        logs = resp.json()["logs"]
        assert logs, "expected rows for the second school"
        assert all(row["tenant_id"] == str(self.tenant_b) for row in logs)
        assert all(row["school_name"] == "Other School" for row in logs)

    @pytest.mark.asyncio
    async def test_filter_by_request_id(self, client, admin_auth_headers):
        resp = await client.get(
            "/admin/audit-logs",
            headers=admin_auth_headers,
            params={"request_id": "seededreq3"},
        )
        assert resp.json()["total"] == 1
        assert resp.json()["logs"][0]["action"] == "seeded.event_3"

    @pytest.mark.asyncio
    async def test_pagination_does_not_repeat_or_skip_rows(
        self, client, admin_auth_headers
    ):
        """
        Rows seeded a minute apart, paged two at a time.

        created_at alone is not unique, so the query orders by (created_at,
        audit_id); without the tiebreak, pages can overlap.
        """
        seen: list[str] = []
        for page in (1, 2, 3):
            resp = await client.get(
                "/admin/audit-logs",
                headers=admin_auth_headers,
                params={"action": "seeded.", "page": page, "page_size": 2},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 6
            seen.extend(row["audit_id"] for row in body["logs"])

        assert len(seen) == 6
        assert len(set(seen)) == 6, "pagination returned a duplicate row"


# -------------------------------------------------------------------
# Privacy: what must never reach the table
# -------------------------------------------------------------------

class TestNoSensitiveContent:
    def test_scrubber_redacts_secrets_by_key_name(self):
        out = scrub_details(
            {
                "password": "hunter2",
                "access_token": "eyJhbGciOi.payload.sig",
                "refresh_token": "abc",
                "otp": "123456",
                "api_key": "sk-live-xyz",
                "authorization": "Bearer abc",
                "oauth_code": "4/0Ax...",
                "risk_level": "high",
            }
        )
        assert out["risk_level"] == "high"
        for key in (
            "password", "access_token", "refresh_token", "otp",
            "api_key", "authorization", "oauth_code",
        ):
            assert out[key] == "[redacted]", key

    def test_scrubber_redacts_message_content_keys(self):
        out = scrub_details(
            {"student_message": "I want to hurt myself", "transcript": "...",
             "narrative": "...", "reflection": "..."}
        )
        assert all(v == "[redacted]" for v in out.values())

    def test_scrubber_walks_nested_structures(self):
        out = scrub_details({"outer": {"inner": {"password_hash": "$2b$12$abc"}}})
        assert out["outer"]["inner"]["password_hash"] == "[redacted]"

    def test_scrubber_caps_long_strings(self):
        out = scrub_details({"reason": "x" * 5000})
        assert len(out["reason"]) < 300
        assert out["reason"].endswith("[truncated]")

    @pytest.mark.asyncio
    async def test_no_audit_row_contains_a_jwt(self, db_session, client, login_account):
        """
        Sweep every row written during a real login/refresh/logout cycle.

        A JWT is recognisable by its three dot-separated base64 segments and
        its "eyJ" header prefix; this asserts none of those reach the table by
        any path, rather than checking the handful we happen to have wired.
        """
        user, password = login_account
        login = await client.post(
            "/auth/login", json={"email": user.email, "password": password}
        )
        tokens = login.json()["tokens"]
        await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

        for row in await _rows(db_session):
            blob = f"{row.action}{row.entity_type}{row.details}{row.user_agent}"
            assert "eyJ" not in blob, f"JWT-shaped string in audit row {row.audit_id}"
            assert tokens["access_token"] not in blob
            assert tokens["refresh_token"] not in blob

    @pytest.mark.asyncio
    async def test_no_audit_row_contains_the_login_password(
        self, db_session, client, login_account
    ):
        user, password = login_account
        await client.post("/auth/login", json={"email": user.email, "password": password})
        await client.post(
            "/auth/login", json={"email": user.email, "password": "WrongPassword1!"}
        )

        for row in await _rows(db_session):
            blob = f"{row.action}{row.details}"
            assert password not in blob
            assert "WrongPassword1!" not in blob

    @pytest.mark.asyncio
    async def test_safety_events_record_the_category_not_the_message(
        self, db_session, safety_subject
    ):
        """
        A safety tripwire must say *what kind* of signal fired, never the
        sentence that fired it. This is the single most important privacy
        assertion in the file.
        """
        from app.ai.safety import log_safety_events

        user, conversation_id = safety_subject
        message = "sometimes I want to die and nobody cares about me"

        await log_safety_events(conversation_id, user.user_id, message)

        rows = await _rows(db_session, "safety_")
        assert rows, "safety scan wrote no audit row"
        for row in rows:
            blob = f"{row.action}{row.details}"
            assert "want to die" not in blob
            assert message not in blob
        assert any(r.details and r.details.get("category") for r in rows)


# -------------------------------------------------------------------
# Correlation and system actors
# -------------------------------------------------------------------

class TestCorrelationAndSystemActor:
    @pytest.mark.asyncio
    async def test_request_id_is_propagated_from_the_header(
        self, client: AsyncClient, db_session, admin_auth_headers
    ):
        """
        audit event -> request id -> structured log -> Sentry.

        The client-supplied id is echoed by the existing observability
        middleware; the audit row must pick up that same value rather than
        minting a second correlation scheme of its own.
        """
        correlation = "audittrace123"
        resp = await client.get(
            "/admin/audit-logs",
            headers={**admin_auth_headers, "X-Request-ID": correlation},
        )
        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"] == correlation

        rows = await _rows(db_session, AuditAction.AUDIT_LOG_VIEWED)
        assert any(r.request_id == correlation for r in rows)

    @pytest.mark.asyncio
    async def test_background_events_are_marked_as_system_actors(
        self, db_session, safety_subject
    ):
        """
        A pipeline-generated event says so, rather than looking like an event
        whose actor we simply failed to record.
        """
        from app.ai.safety import log_safety_events

        user, conversation_id = safety_subject
        await log_safety_events(conversation_id, user.user_id, "I want to kill myself")

        rows = await _rows(db_session, "safety_event:")
        assert rows
        assert rows[0].actor_role == "system"
        # Outside an HTTP request there is no correlation id to carry.
        assert rows[0].request_id is None

    @pytest.mark.asyncio
    async def test_detached_writer_never_raises_on_failure(self, monkeypatch):
        """
        The fail-open path must swallow its own errors.

        If this regressed, a database blip on the audit table would turn every
        login into a 500 -- the exact outcome the detached writer exists to
        prevent.
        """
        import app.audit as audit_module

        def exploding_factory():
            raise RuntimeError("audit store unavailable")

        monkeypatch.setattr(
            "database.session.async_session_factory", exploding_factory
        )

        # Must not raise.
        await log_audit_detached(
            user_id=uuid.uuid4(),
            action=AuditAction.LOGIN_SUCCESS,
            entity_type="user",
        )
