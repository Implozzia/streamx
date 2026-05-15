import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from dependencies import require_lead_access
from models import Schedule, Streamer, User, UserRole
from schemas import ScheduleCreate, ScheduleOut, ScheduleUpdate

router = APIRouter()


@router.get("", response_model=dict)
async def list_schedule(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    streamer_id: int | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    q = select(Schedule).options(
        selectinload(Schedule.streamer).selectinload(Streamer.manager)
    )

    if current_user.role == UserRole.manager:
        q = q.join(Streamer, Schedule.streamer_id == Streamer.id).where(
            Streamer.manager_id == current_user.id
        )

    if streamer_id:
        q = q.where(Schedule.streamer_id == streamer_id)
    if is_active is not None:
        q = q.where(Schedule.is_active == is_active)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Schedule.id).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [ScheduleOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total else 1,
    }


@router.get("/{schedule_id}", response_model=ScheduleOut)
async def get_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(
        select(Schedule)
        .options(selectinload(Schedule.streamer).selectinload(Streamer.manager))
        .where(Schedule.id == schedule_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Schedule entry not found")
    if current_user.role == UserRole.manager and entry.streamer.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return entry


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    streamer_result = await db.execute(select(Streamer).where(Streamer.id == body.streamer_id))
    streamer = streamer_result.scalar_one_or_none()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    if current_user.role == UserRole.manager and streamer.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this streamer")

    entry = Schedule(**body.model_dump())
    db.add(entry)
    await db.flush()

    result = await db.execute(
        select(Schedule)
        .options(selectinload(Schedule.streamer).selectinload(Streamer.manager))
        .where(Schedule.id == entry.id)
    )
    return result.scalar_one()


@router.patch("/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(
        select(Schedule)
        .options(selectinload(Schedule.streamer).selectinload(Streamer.manager))
        .where(Schedule.id == schedule_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Schedule entry not found")
    if current_user.role == UserRole.manager and entry.streamer.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(entry, field, value)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(
        select(Schedule)
        .options(selectinload(Schedule.streamer))
        .where(Schedule.id == schedule_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Schedule entry not found")
    if current_user.role == UserRole.manager and entry.streamer.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.delete(entry)
