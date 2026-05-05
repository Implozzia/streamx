import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from dependencies import get_current_user, require_any
from models import Streamer, User, UserRole
from schemas import StreamerCreate, StreamerOut, StreamerUpdate

router = APIRouter()


def _apply_manager_filter(q, current_user: User):
    if current_user.role == UserRole.manager:
        q = q.where(Streamer.manager_id == current_user.id)
    return q


@router.get("", response_model=dict)
async def list_streamers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    geo: str | None = None,
    manager_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    q = select(Streamer).options(selectinload(Streamer.manager))
    q = _apply_manager_filter(q, current_user)

    if status:
        q = q.where(Streamer.status == status)
    if geo:
        q = q.where(Streamer.geo.ilike(f"%{geo}%"))
    if manager_id:
        q = q.where(Streamer.manager_id == manager_id)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Streamer.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [StreamerOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total else 1,
    }


@router.get("/{streamer_id}", response_model=StreamerOut)
async def get_streamer(
    streamer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    result = await db.execute(
        select(Streamer).options(selectinload(Streamer.manager)).where(Streamer.id == streamer_id)
    )
    streamer = result.scalar_one_or_none()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    if current_user.role == UserRole.manager and streamer.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return streamer


@router.post("", response_model=StreamerOut, status_code=status.HTTP_201_CREATED)
async def create_streamer(
    body: StreamerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    if current_user.role in (UserRole.analyst, UserRole.lead_manager):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    data = body.model_dump()
    if current_user.role == UserRole.manager:
        data["manager_id"] = current_user.id

    streamer = Streamer(**data)
    db.add(streamer)
    await db.flush()
    await db.refresh(streamer, ["manager"])
    return streamer


@router.patch("/{streamer_id}", response_model=StreamerOut)
async def update_streamer(
    streamer_id: int,
    body: StreamerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    if current_user.role in (UserRole.analyst, UserRole.lead_manager):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(
        select(Streamer).options(selectinload(Streamer.manager)).where(Streamer.id == streamer_id)
    )
    streamer = result.scalar_one_or_none()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    if current_user.role == UserRole.manager and streamer.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(streamer, field, value)
    await db.flush()
    await db.refresh(streamer, ["manager"])
    return streamer


@router.delete("/{streamer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_streamer(
    streamer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    if current_user.role not in (UserRole.admin, UserRole.project_manager):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(select(Streamer).where(Streamer.id == streamer_id))
    streamer = result.scalar_one_or_none()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    await db.delete(streamer)
