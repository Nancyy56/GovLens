"""User management (admins only)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.security import Principal, require_admin
from app.db.database import get_session
from app.models.enums import UserRole
from app.services import audit
from app.services.auth import AuthService, UserRead, UserValidationError

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.VIEWER


class UserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = None
    unlock: bool = False


def _service(session: Session = Depends(get_session)) -> AuthService:
    return AuthService(session)


@router.get("", response_model=list[UserRead])
def list_users(service: AuthService = Depends(_service)):
    return service.list_users()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(request: UserCreateRequest, principal: Principal = Depends(require_admin), service: AuthService = Depends(_service)):
    try:
        user = service.create_user(request.username, request.password, request.role)
        audit.record(principal.username, "user.create", target=request.username, detail=f"role {request.role.value}")
        return user
    except UserValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    request: UserUpdateRequest,
    principal: Principal = Depends(require_admin),
    service: AuthService = Depends(_service),
):
    try:
        user = service.update_user(
            user_id,
            acting_user_id=principal.user_id,
            role=request.role,
            is_active=request.is_active,
            password=request.password,
            unlock=request.unlock,
        )
        changed = [n for n, v in (("role", request.role), ("active", request.is_active), ("password", request.password), ("unlocked", True if request.unlock else None)) if v is not None]
        audit.record(principal.username, "user.update", target=user.username, detail="changed: " + ", ".join(changed))
        return user
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UserValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_admin),
    service: AuthService = Depends(_service),
):
    try:
        service.delete_user(user_id, acting_user_id=principal.user_id)
        audit.record(principal.username, "user.delete", target=str(user_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UserValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
