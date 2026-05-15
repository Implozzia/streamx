from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from dependencies import require_lead_access
from models import FunnelStatus, Geo, Platform, Streamer, User, UserRole
from schemas import StreamerCreate, StreamerOut, StreamerUpdate
from utils import extract_nickname_from_url

router = APIRouter()


def _apply_manager_filter(q, current_user: User):
    if current_user.role == UserRole.manager:
        q = q.where(Streamer.manager_id == current_user.id)
    return q


@router.get("", response_model=dict)
async def list_streamers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: FunnelStatus | None = None,
    platform: Platform | None = None,
    geo: Geo | None = None,
    manager_id: int | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    q = select(Streamer).options(selectinload(Streamer.manager))
    q = _apply_manager_filter(q, current_user)

    if status:
        q = q.where(Streamer.status == status)
    if platform:
        q = q.where(Streamer.platform == platform)
    if geo:
        q = q.where(Streamer.geo == geo)
    if manager_id:
        q = q.where(Streamer.manager_id == manager_id)
    if search:
        q = q.where(Streamer.nickname.ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Streamer.updated_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [jsonable_encoder(StreamerOut.model_validate(i)) for i in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{streamer_id}", response_model=StreamerOut)
async def get_streamer(
    streamer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_streamer(
    body: StreamerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    # Antiduplicate check by profile_url
    dup_result = await db.execute(
        select(Streamer)
        .options(selectinload(Streamer.manager))
        .where(Streamer.profile_url == body.profile_url)
    )
    existing = dup_result.scalar_one_or_none()
    if existing:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "duplicate",
                "existing": jsonable_encoder(StreamerOut.model_validate(existing)),
            },
        )

    data = body.model_dump()

    # Always derive nickname from profile_url, ignoring any client-provided value
    nickname = extract_nickname_from_url(data.get("profile_url") or "")
    if not nickname:
        raise HTTPException(status_code=422, detail="Cannot extract nickname from URL")
    data["nickname"] = nickname

    # Auto-assign current user as manager if not explicitly provided
    if not data.get("manager_id"):
        data["manager_id"] = current_user.id
    data["last_status_change_at"] = datetime.now(timezone.utc)

    streamer = Streamer(**data)
    db.add(streamer)
    await db.flush()
    await db.refresh(streamer, ["manager"])
    return JSONResponse(
        status_code=201,
        content=jsonable_encoder(StreamerOut.model_validate(streamer)),
    )


@router.patch("/{streamer_id}", response_model=StreamerOut)
async def update_streamer(
    streamer_id: int,
    body: StreamerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(
        select(Streamer).options(selectinload(Streamer.manager)).where(Streamer.id == streamer_id)
    )
    streamer = result.scalar_one_or_none()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    if current_user.role == UserRole.manager and streamer.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    updates = body.model_dump(exclude_none=True)

    if "profile_url" in updates:
        nickname = extract_nickname_from_url(updates["profile_url"] or "")
        if not nickname:
            raise HTTPException(status_code=422, detail="Cannot extract nickname from URL")
        updates["nickname"] = nickname

    if "status" in updates and updates["status"] != streamer.status:
        updates["last_status_change_at"] = datetime.now(timezone.utc)

    for field, value in updates.items():
        setattr(streamer, field, value)
    await db.flush()
    await db.refresh(streamer)  # refreshes all expired cols incl. updated_at (onupdate=func.now())
    return StreamerOut.model_validate(streamer)


@router.delete("/{streamer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_streamer(
    streamer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(select(Streamer).where(Streamer.id == streamer_id))
    streamer = result.scalar_one_or_none()
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    await db.delete(streamer)
