"""User accounts, password hashing, and sign-in sessions.

Passwords are hashed with scrypt (standard library). Sessions are random
tokens; only their SHA-256 is stored, so a database leak does not reveal
usable tokens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.documents import AuthToken, User
from app.models.enums import UserRole

logger = logging.getLogger(__name__)

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
_USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
MIN_PASSWORD_LENGTH = 8


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class LoginResult(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class AuthError(Exception):
    """Wrong credentials or an unusable account (deliberately vague)."""


class UserValidationError(ValueError):
    """Invalid username, password, or a username that is taken."""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=64)
    encode = lambda raw: base64.b64encode(raw).decode()  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${encode(salt)}${encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, session: Session, token_ttl_hours: int = 12) -> None:
        self.session = session
        self.token_ttl = timedelta(hours=token_ttl_hours)

    # --- sessions -------------------------------------------------------

    def login(self, username: str, password: str) -> LoginResult:
        user = self.session.scalars(select(User).where(func.lower(User.username) == username.lower())).first()
        # Hash even for unknown users so response time does not reveal which usernames exist.
        valid = verify_password(password, user.password_hash if user else hash_password("unused-dummy"))
        if user is None or not valid or not user.is_active:
            raise AuthError("Invalid username or password")

        now = datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        expires_at = now + self.token_ttl
        self.session.execute(delete(AuthToken).where(AuthToken.expires_at < now))
        self.session.add(AuthToken(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
        user.last_login_at = now
        self.session.commit()
        logger.info("User %s signed in", user.username)
        return LoginResult(access_token=token, expires_at=expires_at, user=UserRead.model_validate(user))

    def authenticate(self, token: str) -> User | None:
        """Return the active user owning a valid, unexpired token."""

        row = self.session.execute(
            select(User, AuthToken.expires_at)
            .join(AuthToken, AuthToken.user_id == User.id)
            .where(AuthToken.token_hash == hash_token(token))
        ).first()
        if row is None:
            return None
        user, expires_at = row
        if expires_at.tzinfo is None:  # SQLite returns naive datetimes
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC) or not user.is_active:
            return None
        return user

    def logout(self, token: str) -> None:
        self.session.execute(delete(AuthToken).where(AuthToken.token_hash == hash_token(token)))
        self.session.commit()

    # --- user management ------------------------------------------------

    def list_users(self) -> list[UserRead]:
        users = self.session.scalars(select(User).order_by(User.username)).all()
        return [UserRead.model_validate(u) for u in users]

    def create_user(self, username: str, password: str, role: UserRole) -> UserRead:
        if not _USERNAME.match(username):
            raise UserValidationError("Username must be 3-64 characters: letters, digits, '.', '_' or '-'")
        self._check_password(password)
        if self.session.scalars(select(User).where(func.lower(User.username) == username.lower())).first():
            raise UserValidationError(f"Username {username!r} is already taken")
        user = User(username=username, password_hash=hash_password(password), role=role, is_active=True)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        logger.info("Created user %s with role %s", username, role.value)
        return UserRead.model_validate(user)

    def update_user(
        self,
        user_id: uuid.UUID,
        *,
        acting_user_id: uuid.UUID | None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        password: str | None = None,
    ) -> UserRead:
        user = self._require(user_id)
        demoting = (role is not None and role != UserRole.ADMIN) or is_active is False
        if user.role == UserRole.ADMIN and demoting:
            self._keep_one_admin(user.id)
        if user_id == acting_user_id and demoting:
            raise UserValidationError("You cannot remove your own admin access")
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        if password is not None:
            self._check_password(password)
            user.password_hash = hash_password(password)
        if password is not None or is_active is False:
            # Force re-login everywhere after a password change or deactivation.
            self.session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
        self.session.commit()
        self.session.refresh(user)
        return UserRead.model_validate(user)

    def delete_user(self, user_id: uuid.UUID, *, acting_user_id: uuid.UUID | None) -> None:
        user = self._require(user_id)
        if user_id == acting_user_id:
            raise UserValidationError("You cannot delete your own account")
        if user.role == UserRole.ADMIN:
            self._keep_one_admin(user.id)
        self.session.delete(user)
        self.session.commit()

    def change_own_password(self, user_id: uuid.UUID, current: str, new: str) -> None:
        user = self._require(user_id)
        if not verify_password(current, user.password_hash):
            raise AuthError("Current password is incorrect")
        self._check_password(new)
        user.password_hash = hash_password(new)
        self.session.execute(delete(AuthToken).where(AuthToken.user_id == user.id))
        self.session.commit()

    def ensure_initial_admin(self, username: str, password: str | None, password_file: Path) -> str | None:
        """Create the first admin when no users exist. Returns a generated password, if any."""

        if self.session.scalar(select(func.count()).select_from(User)):
            return None
        generated = None
        if not password:
            generated = password = secrets.token_urlsafe(12)
        self.create_user(username, password, UserRole.ADMIN)
        if generated:
            password_file.parent.mkdir(parents=True, exist_ok=True)
            password_file.write_text(f"username: {username}\npassword: {generated}\n")
            password_file.chmod(0o600)
        return generated

    def _require(self, user_id: uuid.UUID) -> User:
        user = self.session.get(User, user_id)
        if user is None:
            raise LookupError(f"No user {user_id}")
        return user

    def _keep_one_admin(self, user_id: uuid.UUID) -> None:
        others = self.session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True), User.id != user_id)
        )
        if not others:
            raise UserValidationError("At least one active admin must remain")

    @staticmethod
    def _check_password(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise UserValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
