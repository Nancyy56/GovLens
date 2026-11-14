"""User management (admins only)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.security import Principal, require_admin
from app.db.database import get_session
from app.models.enums import UserRole
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


def _service(session: Session = Depends(get_session)) -> AuthService:
    return AuthService(session)


@router.get("", response_model=list[UserRead])
def list_users(service: AuthService = Depends(_service)):
    return service.list_users()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(request: UserCreateRequest, service: AuthService = Depends(_service)):
    try:
        return service.create_user(request.username, request.password, request.role)
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
        return service.update_user(
            user_id,
            acting_user_id=principal.user_id,
            role=request.role,
            is_active=request.is_active,
            password=request.password,
        )
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
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UserValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
