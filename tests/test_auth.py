"""Accounts, sessions, roles, and the shared rate limiter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.security import DatabaseRateLimiter
from app.core.config import settings
from app.db.database import get_session
from app.main import app
from app.models.documents import AuthToken
from app.models.enums import UserRole
from app.services import dependencies
from app.services.auth import AuthError, AuthService, UserValidationError, hash_password, verify_password


def test_password_hashing_round_trip_and_salting() -> None:
    first, second = hash_password("correct horse"), hash_password("correct horse")
    assert first != second  # random salt
    assert verify_password("correct horse", first)
    assert not verify_password("wrong horse", first)
    assert not verify_password("anything", "not-a-hash")


def test_login_issues_token_and_authenticate_resolves_it(sqlite_session) -> None:
    service = AuthService(sqlite_session)
    service.create_user("alice", "password-1", UserRole.EDITOR)

    result = service.login("ALICE", "password-1")  # usernames are case-insensitive

    assert service.authenticate(result.access_token).username == "alice"
    stored = sqlite_session.scalars(select(AuthToken)).one()
    assert stored.token_hash != result.access_token  # only the hash is stored


def test_wrong_password_and_inactive_user_rejected(sqlite_session) -> None:
    service = AuthService(sqlite_session)
    user = service.create_user("bob", "password-1", UserRole.VIEWER)
    with pytest.raises(AuthError):
        service.login("bob", "nope-nope")
    with pytest.raises(AuthError):
        service.login("nobody", "password-1")

    admin = service.create_user("root", "password-1", UserRole.ADMIN)
    service.update_user(user.id, acting_user_id=admin.id, is_active=False)
    with pytest.raises(AuthError):
        service.login("bob", "password-1")


def test_expired_token_is_rejected(sqlite_session) -> None:
    service = AuthService(sqlite_session)
    service.create_user("carol", "password-1", UserRole.VIEWER)
    token = service.login("carol", "password-1").access_token
    row = sqlite_session.scalars(select(AuthToken)).one()
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    sqlite_session.commit()

    assert service.authenticate(token) is None


def test_password_change_and_deactivation_end_sessions(sqlite_session) -> None:
    service = AuthService(sqlite_session)
    admin = service.create_user("root", "password-1", UserRole.ADMIN)
    user = service.create_user("dave", "password-1", UserRole.VIEWER)
    token = service.login("dave", "password-1").access_token

    service.change_own_password(user.id, "password-1", "password-2")
    assert service.authenticate(token) is None
    with pytest.raises(AuthError):
        service.change_own_password(user.id, "wrong-one", "password-3")

    token = service.login("dave", "password-2").access_token
    service.update_user(user.id, acting_user_id=admin.id, is_active=False)
    assert service.authenticate(token) is None


def test_last_admin_cannot_be_removed(sqlite_session) -> None:
    service = AuthService(sqlite_session)
    admin = service.create_user("root", "password-1", UserRole.ADMIN)
    other = service.create_user("helper", "password-1", UserRole.ADMIN)

    with pytest.raises(UserValidationError):
        service.update_user(admin.id, acting_user_id=admin.id, role=UserRole.VIEWER)  # self-demotion
    service.delete_user(other.id, acting_user_id=admin.id)
    with pytest.raises(UserValidationError):
        service.update_user(admin.id, acting_user_id=None, role=UserRole.EDITOR)  # last admin


def test_user_validation(sqlite_session) -> None:
    service = AuthService(sqlite_session)
    service.create_user("erin", "password-1", UserRole.VIEWER)
    with pytest.raises(UserValidationError):
        service.create_user("Erin", "password-1", UserRole.VIEWER)  # taken (case-insensitive)
    with pytest.raises(UserValidationError):
        service.create_user("x", "password-1", UserRole.VIEWER)  # too short
    with pytest.raises(UserValidationError):
        service.create_user("frank", "short", UserRole.VIEWER)


def test_initial_admin_created_once_with_generated_password(sqlite_session, tmp_path) -> None:
    service = AuthService(sqlite_session)
    password_file = tmp_path / "admin.txt"

    generated = service.ensure_initial_admin("admin", None, password_file)

    assert generated and generated in password_file.read_text()
    assert service.login("admin", generated).user.role == UserRole.ADMIN
    assert service.ensure_initial_admin("admin", None, password_file) is None


@pytest.fixture
def frozen_clock(monkeypatch):
    clock = {"now": 1_000_020.0}  # 20 s into a minute
    monkeypatch.setattr("app.api.security.time.time", lambda: clock["now"])
    return clock


def test_database_rate_limiter_counts_across_instances(sqlite_session_factory, frozen_clock) -> None:
    first, second = DatabaseRateLimiter(sqlite_session_factory), DatabaseRateLimiter(sqlite_session_factory)

    results = [first.hit("user:1", 3)[0], second.hit("user:1", 3)[0], first.hit("user:1", 3)[0], second.hit("user:1", 3)]

    assert results[:3] == [True, True, True]
    allowed, retry_after = results[3]
    assert allowed is False and 1 <= retry_after <= 61
    assert first.hit("user:2", 3)[0] is True  # separate identity


def test_database_rate_limiter_has_no_burst_at_minute_boundary(sqlite_session_factory, frozen_clock) -> None:
    limiter = DatabaseRateLimiter(sqlite_session_factory)
    frozen_clock["now"] = 1_000_019.0  # 59 s into a minute (minute starts at 1_000_020 - 60 = 999_960)
    assert [limiter.hit("ip:1", 3)[0] for _ in range(3)] == [True, True, True]

    frozen_clock["now"] = 1_000_021.0  # 1 s into the next minute
    # A fixed window would allow 3 more; the sliding estimate still counts most of the last minute.
    assert limiter.hit("ip:1", 3)[0] is False

    frozen_clock["now"] = 1_000_079.0  # end of the next minute: the old hits have aged out
    assert limiter.hit("ip:1", 3)[0] is True


@pytest.fixture
def auth_client(monkeypatch, sqlite_session_factory):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "")
    monkeypatch.setattr(settings, "rate_limit_backend", "database")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 100)
    monkeypatch.setattr(settings, "login_rate_limit_per_minute", 3)
    monkeypatch.setattr("app.api.security.database_rate_limiter", DatabaseRateLimiter(sqlite_session_factory))

    def session_override():
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = session_override
    with sqlite_session_factory() as session:
        AuthService(session).create_user("admin", "Tr0ub4dor-pass1", UserRole.ADMIN)
        AuthService(session).create_user("viewer", "Zebra-pass-77x", UserRole.VIEWER)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _login(client, username, password) -> dict:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_login_me_and_logout_over_http(auth_client) -> None:
    headers = _login(auth_client, "viewer", "Zebra-pass-77x")

    assert auth_client.get("/api/v1/auth/me", headers=headers).json()["role"] == "VIEWER"
    assert auth_client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert auth_client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_roles_enforced_over_http(auth_client) -> None:
    viewer = _login(auth_client, "viewer", "Zebra-pass-77x")
    admin = _login(auth_client, "admin", "Tr0ub4dor-pass1")

    assert auth_client.get("/api/v1/users", headers=viewer).status_code == 403
    assert auth_client.get("/api/v1/metrics", headers=viewer).status_code == 403
    assert auth_client.post("/api/v1/ingest", json={"file_path": "/app/x.pdf"}, headers=viewer).status_code == 403

    created = auth_client.post(
        "/api/v1/users", json={"username": "editor1", "password": "Quartz-pass-42y", "role": "EDITOR"}, headers=admin
    )
    assert created.status_code == 201
    assert [u["username"] for u in auth_client.get("/api/v1/users", headers=admin).json()] == ["admin", "editor1", "viewer"]
    assert "govlens_http_requests_total" in auth_client.get("/api/v1/metrics", headers=admin).text


def test_login_attempts_are_rate_limited(auth_client, frozen_clock) -> None:
    codes = [
        auth_client.post("/api/v1/auth/login", json={"username": "admin", "password": "guess"}).status_code
        for _ in range(4)
    ]
    assert codes == [401, 401, 401, 429]


def test_unexpected_errors_hide_details_but_return_request_id(auth_client, monkeypatch) -> None:
    headers = _login(auth_client, "admin", "Tr0ub4dor-pass1")

    class Exploding:
        def list(self, **kwargs):
            raise RuntimeError("secret internal detail")

    app.dependency_overrides[dependencies.get_document_service] = lambda: Exploding()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/documents", headers={**headers, "X-Request-ID": "trace-123"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "request_id": "trace-123"}
