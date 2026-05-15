import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from dependencies import require_lead_access
from models import Stream, Streamer, User, UserRole
from schemas import StreamCreate, StreamOut, StreamUpdate

router = APIRouter()


def _apply_manager_filter(q, current_user: User):
    if current_user.role == UserRole.manager:
        q = q.where(Stream.manager_id == current_user.id)
    return q


@router.get("", response_model=dict)
async def list_streams(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    streamer_id: int | None = None,
    payment_status: str | None = None,
    manager_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    q = select(Stream).options(
        selectinload(Stream.streamer).selectinload(Streamer.manager),
        selectinload(Stream.manager),
    )
    q = _apply_manager_filter(q, current_user)

    if streamer_id:
        q = q.where(Stream.streamer_id == streamer_id)
    if payment_status:
        q = q.where(Stream.payment_status == payment_status)
    if manager_id:
        q = q.where(Stream.manager_id == manager_id)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Stream.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [StreamOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total else 1,
    }


@router.get("/{stream_id}", response_model=StreamOut)
async def get_stream(
    stream_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(
        select(Stream)
        .options(
            selectinload(Stream.streamer).selectinload(Streamer.manager),
            selectinload(Stream.manager),
        )
        .where(Stream.id == stream_id)
    )
    stream = result.scalar_one_or_none()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    if current_user.role == UserRole.manager and stream.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return stream


@router.post("", response_model=StreamOut, status_code=status.HTTP_201_CREATED)
async def create_stream(
    body: StreamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    # verify streamer exists and manager owns it
    streamer_result = await db.execute(select(Streamer).where(Streamer.id == body.streamer_id))
    streamer = streamer_result.scalar_one_or_none()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    if current_user.role == UserRole.manager and streamer.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this streamer")

    data = body.model_dump()
    if current_user.role == UserRole.manager:
        data["manager_id"] = current_user.id

    stream = Stream(**data)
    db.add(stream)
    await db.flush()

    result = await db.execute(
        select(Stream)
        .options(
            selectinload(Stream.streamer).selectinload(Streamer.manager),
            selectinload(Stream.manager),
        )
        .where(Stream.id == stream.id)
    )
    return result.scalar_one()


@router.patch("/{stream_id}", response_model=StreamOut)
async def update_stream(
    stream_id: int,
    body: StreamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(
        select(Stream)
        .options(
            selectinload(Stream.streamer).selectinload(Streamer.manager),
            selectinload(Stream.manager),
        )
        .where(Stream.id == stream_id)
    )
    stream = result.scalar_one_or_none()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    if current_user.role == UserRole.manager and stream.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(stream, field, value)
    await db.flush()
    await db.refresh(stream)
    return stream


@router.delete("/{stream_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stream(
    stream_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(select(Stream).where(Stream.id == stream_id))
    stream = result.scalar_one_or_none()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    await db.delete(stream)
