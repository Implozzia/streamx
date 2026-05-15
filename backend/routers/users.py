"""
Users router — user management CRUD (admin only) + self-service password change.

Endpoints:
  GET    /api/users                      — list users (paginated)    [admin]
  GET    /api/users/managers             — dropdown list             [any]
  POST   /api/users                      — create user (temp pwd)    [admin]
  PATCH  /api/users/{id}                 — update user               [admin]
  POST   /api/users/{id}/reset-password  — reset to temp pwd         [admin]
  POST   /api/users/me/change-password   — change own password       [any]
"""
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import auth as auth_utils
from database import get_db
from dependencies import get_current_user, require_admin
from models import User, UserRole
from schemas import (
    ChangePasswordRequest,
    UserCreate,
    UserCreateResponse,
    UserOut,
    UserPasswordResetResponse,
    UserUpdate,
)
from utils import generate_temporary_password

router = APIRouter()


@router.get("", response_model=dict)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    role: UserRole | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = select(User)

    if role is not None:
        q = q.where(User.role == role)
    if is_active is not None:
        q = q.where(User.is_active == is_active)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [UserOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total else 1,
    }


@router.get("/managers", response_model=list[UserOut])
async def list_managers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Active leads and managers for Manager dropdown fields. Admins excluded."""
    result = await db.execute(
        select(User)
        .where(User.is_active == True)  # noqa: E712
        .where(User.role.in_([UserRole.lead, UserRole.manager]))
        .order_by(User.full_name)
    )
    return result.scalars().all()


@router.post("", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    temp_password = generate_temporary_password()
    user = User(
        email=body.email,
        password_hash=auth_utils.hash_password(temp_password),
        full_name=body.full_name,
        role=body.role,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return UserCreateResponse(
        user=UserOut.model_validate(user),
        temporary_password=temp_password,
    )


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_own_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not auth_utils.verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = auth_utils.hash_password(body.new_password)
    current_user.must_change_password = False
    await db.flush()
    return None


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = body.model_dump(exclude_none=True)

    # Self-lockout protection: admin cannot demote or disable their own account.
    if user_id == current_user.id:
        if "role" in updates and updates["role"] != UserRole.admin:
            raise HTTPException(status_code=400, detail="Cannot demote your own admin role")
        if "is_active" in updates and not updates["is_active"]:
            raise HTTPException(status_code=400, detail="Cannot disable your own account")

    for field, value in updates.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=UserPasswordResetResponse)
async def reset_user_password(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Self-reset via this endpoint is blocked: it would force must_change_password=True
    # on the admin's own session, locking them into the change-password flow immediately.
    # Admins should use POST /me/change-password to change their own password.
    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Use /me/change-password to change your own password",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = generate_temporary_password()
    user.password_hash = auth_utils.hash_password(temp_password)
    user.must_change_password = True
    await db.flush()

    return UserPasswordResetResponse(
        user_id=user.id,
        temporary_password=temp_password,
    )
