"""Authentication, role checks, and per-client rate limiting.

Every protected route depends on ``require(role)``. That resolves the caller
once per request (bearer session token or service API key), applies the rate
limit, then checks the role.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import random
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal, get_session
from app.models.documents import RateLimitWindow
from app.models.enums import UserRole
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Service API key (see API_KEYS)")
bearer_scheme = HTTPBearer(auto_error=False, description="Session token from POST /auth/login")


class Principal(BaseModel):
    """Who is making the request."""

    user_id: uuid.UUID | None = None
    username: str
    role: UserRole
    via: str  # "session", "api_key", or "auth_disabled"


# --- rate limiting -------------------------------------------------------


class SlidingWindowRateLimiter:
    """In-memory sliding-window limiter (per process)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, identity: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(identity, deque())
            while hits and now - hits[0] >= window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(1, int(window_seconds - (now - hits[0])) + 1)
            hits.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class DatabaseRateLimiter:
    """Sliding-window estimate over per-minute counts in the database, shared by all API workers.

    The estimate is ``current + previous * (1 - elapsed fraction of current)``,
    which avoids the burst a plain fixed window allows across a minute boundary.
    """

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self.session_factory = session_factory

    def hit(self, identity: str, limit: int, window_seconds: float = 60.0) -> tuple[bool, int]:
        now = time.time()
        window = int(now // window_seconds)
        with self.session_factory() as session:
            insert = self._insert_for(session)
            statement = (
                insert(RateLimitWindow)
                .values(identity=identity, window_start=window, count=1)
                .on_conflict_do_update(
                    index_elements=["identity", "window_start"],
                    set_={"count": RateLimitWindow.count + 1},
                )
                .returning(RateLimitWindow.count)
            )
            count = session.execute(statement).scalar_one()
            previous = session.scalar(
                select(RateLimitWindow.count).where(
                    RateLimitWindow.identity == identity, RateLimitWindow.window_start == window - 1
                )
            ) or 0
            if random.random() < 0.01:
                session.execute(delete(RateLimitWindow).where(RateLimitWindow.window_start < window - 5))
            session.commit()
        elapsed = (now % window_seconds) / window_seconds
        estimate = count + previous * (1.0 - elapsed)
        if estimate > limit:
            return False, max(1, int((window + 1) * window_seconds - now) + 1)
        return True, 0

    @staticmethod
    def _insert_for(session: Session):
        if session.get_bind().dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert
        return insert


memory_rate_limiter = SlidingWindowRateLimiter()
database_rate_limiter = DatabaseRateLimiter()


def _limiter():
    return database_rate_limiter if settings.rate_limit_backend == "database" else memory_rate_limiter


def check_rate_limit(identity: str, limit: int) -> None:
    if limit <= 0:
        return
    try:
        allowed, retry_after = _limiter().hit(identity, limit)
    except Exception:
        # A rate-limiter outage must not take the API down with it.
        logger.exception("Rate limiter failed; allowing request")
        return
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit of {limit} requests per minute exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# --- authentication ------------------------------------------------------


def _unauthorized(detail: str = "Sign in required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_principal(
    request: Request,
    api_key: str | None = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    session: Session = Depends(get_session),
) -> Principal:
    """Identify the caller and apply the rate limit. Cached per request by FastAPI."""

    if not settings.auth_enabled:
        principal = Principal(username="anonymous", role=UserRole.ADMIN, via="auth_disabled")
        check_rate_limit(f"ip:{client_ip(request)}", settings.rate_limit_per_minute)
        return principal

    principal = _from_api_key(api_key) or (_from_api_key(bearer.credentials) if bearer else None)
    if principal is None and bearer is not None:
        user = AuthService(session).authenticate(bearer.credentials)
        if user is not None:
            principal = Principal(user_id=user.id, username=user.username, role=user.role, via="session")
    if principal is None:
        raise _unauthorized("Invalid or expired credentials" if (api_key or bearer) else "Sign in required")

    identity = f"user:{principal.user_id}" if principal.user_id else f"key:{principal.username}"
    check_rate_limit(identity, settings.rate_limit_per_minute)
    request.state.principal = principal
    return principal


def _from_api_key(candidate: str | None) -> Principal | None:
    if not candidate:
        return None
    for key, role in settings.api_key_roles.items():
        if hmac.compare_digest(candidate, key):
            fingerprint = hashlib.sha256(key.encode()).hexdigest()[:8]
            try:
                return Principal(username=f"api-key-{fingerprint}", role=UserRole(role), via="api_key")
            except ValueError:
                logger.error("API key %s has unknown role %r; ignoring it", fingerprint, role)
                return None
    return None


def require(role: UserRole):
    """Dependency factory: the caller must have at least ``role``."""

    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role.rank < role.rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires the {role.value} role",
            )
        return principal

    dependency.__name__ = f"require_{role.value.lower()}"
    return dependency


require_viewer = require(UserRole.VIEWER)
require_editor = require(UserRole.EDITOR)
require_admin = require(UserRole.ADMIN)
