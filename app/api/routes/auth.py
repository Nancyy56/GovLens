"""Sign-in, sign-out, and the current user's account."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.security import Principal, bearer_scheme, check_rate_limit, client_ip, require_viewer
from app.core.config import settings
from app.db.database import get_session
from app.services import audit
from app.services.auth import AuthError, AuthLockedError, AuthService, LoginResult, UserValidationError

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


def _auth_service(session: Session = Depends(get_session)) -> AuthService:
    return AuthService(session, token_ttl_hours=settings.token_ttl_hours)


@router.post("/login", response_model=LoginResult)
def login(request: LoginRequest, http_request: Request, service: AuthService = Depends(_auth_service)):
    """Exchange a username and password for a session token (send it as `Authorization: Bearer <token>`)."""

    # Limit attempts per IP to slow down password guessing.
    check_rate_limit(f"login:{client_ip(http_request)}", settings.login_rate_limit_per_minute)
    ip = client_ip(http_request)
    try:
        result = service.login(request.username, request.password)
        audit.record(request.username, "auth.login", ip=ip)
        return result
    except AuthError as exc:
        audit.record(request.username, "auth.locked" if isinstance(exc, AuthLockedError) else "auth.login_failed", ip=ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    bearer: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthService = Depends(_auth_service),
):
    if bearer is not None:
        service.logout(bearer.credentials)


@router.get("/me", response_model=Principal)
def me(principal: Principal = Depends(require_viewer)):
    return principal


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    request: PasswordChangeRequest,
    principal: Principal = Depends(require_viewer),
    service: AuthService = Depends(_auth_service),
):
    """Change your own password. All your sessions are signed out."""

    if principal.user_id is None:
        raise HTTPException(status_code=400, detail="Service API keys have no password")
    try:
        service.change_own_password(principal.user_id, request.current_password, request.new_password)
        audit.record(principal.username, "auth.password_changed")
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except UserValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
