import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from dependencies import get_current_user, require_lead_access
from models import Lead, User, UserRole
from schemas import LeadCreate, LeadOut, LeadUpdate

router = APIRouter()


def _apply_manager_filter(query, current_user: User):
    """Managers see only their own leads; others see all."""
    if current_user.role == UserRole.manager:
        query = query.where(Lead.manager_id == current_user.id)
    return query


@router.get("", response_model=dict)
async def list_leads(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    geo: str | None = None,
    manager_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    q = select(Lead).options(selectinload(Lead.manager))
    q = _apply_manager_filter(q, current_user)

    if status:
        q = q.where(Lead.status == status)
    if geo:
        q = q.where(Lead.geo.ilike(f"%{geo}%"))
    if manager_id:
        q = q.where(Lead.manager_id == manager_id)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Lead.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [LeadOut.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": math.ceil(total / size) if total else 1,
    }


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(
        select(Lead).options(selectinload(Lead.manager)).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if current_user.role == UserRole.manager and lead.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return lead


@router.post("", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    data = body.model_dump()
    # managers can only create leads assigned to themselves
    if current_user.role == UserRole.manager:
        data["manager_id"] = current_user.id

    lead = Lead(**data)
    db.add(lead)
    await db.flush()
    await db.refresh(lead, ["manager"])
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: int,
    body: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(
        select(Lead).options(selectinload(Lead.manager)).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if current_user.role == UserRole.manager and lead.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(lead, field, value)
    await db.flush()
    await db.refresh(lead, ["manager"])
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_lead_access),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if current_user.role == UserRole.manager and lead.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    await db.delete(lead)
