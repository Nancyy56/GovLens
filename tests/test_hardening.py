"""Account lockout, the password policy, security headers, and data retention."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.database import get_session
from app.main import app, security_headers
from app.models.documents import AuditLog, QueryLog, User
from app.models.enums import UserRole
from app.services.auth import AuthError, AuthLockedError, AuthService, UserValidationError
from app.services.retention import purge_old_records

GOOD = "correct-horse-battery"


@pytest.fixture
def auth(sqlite_session, monkeypatch):
    monkeypatch.setattr(settings, "login_max_failures", 3)
    monkeypatch.setattr(settings, "login_lockout_minutes", 15)
    service = AuthService(sqlite_session)
    service.create_user("alice", GOOD, UserRole.VIEWER)
    return service


def test_account_locks_after_repeated_failures_and_hides_it(auth) -> None:
    for _ in range(2):
        with pytest.raises(AuthError) as err:
            auth.login("alice", "wrong-password-1")
        assert not isinstance(err.value, AuthLockedError)
    with pytest.raises(AuthLockedError) as locked:
        auth.login("alice", "wrong-password-1")
    # The right password is refused while locked, with the same generic message as any failure.
    with pytest.raises(AuthLockedError) as still:
        auth.login("alice", GOOD)
    assert str(locked.value) == str(still.value) == "Invalid username or password"


def test_lock_expires_and_success_resets_the_counter(auth, sqlite_session) -> None:
    for _ in range(2):
        with pytest.raises(AuthError):
            auth.login("alice", "wrong-password-1")
    assert auth.login("alice", GOOD).user.username == "alice"  # a success resets the count
    user = sqlite_session.query(User).one()
    assert user.failed_attempts == 0

    user.locked_until = datetime.now(UTC) - timedelta(minutes=1)  # lock already over
    sqlite_session.commit()
    assert auth.login("alice", GOOD).access_token


def test_admin_can_unlock_an_account(auth, sqlite_session) -> None:
    for _ in range(3):
        with pytest.raises(AuthError):
            auth.login("alice", "wrong-password-1")
    user = sqlite_session.query(User).one()
    assert user.locked_until is not None
    auth.update_user(user.id, acting_user_id=None, unlock=True)
    assert auth.login("alice", GOOD).access_token


def test_unknown_users_cannot_be_locked_or_distinguished(auth) -> None:
    with pytest.raises(AuthError) as err:
        auth.login("nobody", "whatever-password")
    assert str(err.value) == "Invalid username or password"


def test_lockout_can_be_disabled(sqlite_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "login_max_failures", 0)
    service = AuthService(sqlite_session)
    service.create_user("bob", GOOD, UserRole.VIEWER)
    for _ in range(10):
        with pytest.raises(AuthError):
            service.login("bob", "wrong-password-1")
    assert service.login("bob", GOOD).access_token


@pytest.mark.parametrize(
    "password, message",
    [
        ("short1", "at least 10"),
        ("password123", "too easy"),
        ("aaaaaaaaaaaa", "too easy"),
        ("alice-is-great", "username"),
    ],
)
def test_weak_passwords_are_rejected(sqlite_session, password, message) -> None:
    with pytest.raises(UserValidationError, match=message):
        AuthService(sqlite_session).create_user("alice", password, UserRole.VIEWER)


def test_security_headers() -> None:
    api = security_headers("/api/v1/health")
    assert api["X-Content-Type-Options"] == "nosniff" and api["X-Frame-Options"] == "DENY"
    assert api["Cache-Control"] == "no-store" and "Content-Security-Policy" not in api

    page = security_headers("/documents")
    assert "script-src 'self'" in page["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in page["Content-Security-Policy"]
    assert "'unsafe-inline'" not in page["Content-Security-Policy"].split("script-src")[1].split(";")[0]

    for path in ("/docs", "/legacy", "/static/app.js"):
        assert "Content-Security-Policy" not in security_headers(path)


def test_headers_are_sent_on_real_responses(monkeypatch) -> None:
    monkeypatch.setattr(settings, "env", "production")
    app.dependency_overrides[get_session] = lambda: MagicMock()
    try:
        response = TestClient(app).get("/api/v1/health")
    finally:
        app.dependency_overrides.clear()
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_retention_deletes_only_old_rows(sqlite_session) -> None:
    now = datetime.now(UTC)
    old, fresh = now - timedelta(days=200), now - timedelta(days=5)
    sqlite_session.add_all([
        QueryLog(username="a", question="old", result={}, created_at=old),
        QueryLog(username="a", question="fresh", result={}, created_at=fresh),
        AuditLog(username="a", action="x", created_at=old),
        AuditLog(username="a", action="y", created_at=fresh),
    ])
    sqlite_session.commit()

    removed = purge_old_records(sqlite_session, query_days=90, audit_days=365)
    assert removed == {"query_logs": 1, "audit_logs": 0}  # the 200-day-old audit entry is inside 365 days
    assert [q.question for q in sqlite_session.query(QueryLog)] == ["fresh"]

    assert purge_old_records(sqlite_session, query_days=0, audit_days=0) == {"query_logs": 0, "audit_logs": 0}
    assert sqlite_session.query(AuditLog).count() == 2


def test_production_refuses_an_admin_password_the_policy_would_reject() -> None:
    from app.core.config import Settings

    base = dict(env="production", postgres_password="a-long-unique-password", qdrant_api_key="unique-qdrant-key", debug=False, auth_enabled=True, cors_origins="", rate_limit_per_minute=60)
    # Contains the username: previously the app started "healthy" with no admin account at all.
    bad = Settings(**base, admin_username="admin", admin_password="Smoke-Test-Admin-789!").production_problems()
    assert len(bad) == 1 and "ADMIN_PASSWORD" in bad[0] and "username" in bad[0]
    assert Settings(**base, admin_username="admin", admin_password="Tulip-Harbor-5521").production_problems() == []
    assert Settings(**base, admin_password=None).production_problems() == []  # a generated password is fine
