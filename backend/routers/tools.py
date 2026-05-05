"""
Tools router — analytics & utility endpoints.
Accessible to: admin, project_manager, analyst (read-only analytics).
"""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from dependencies import require_any
from models import Lead, LeadStatus, PaymentStatus, Stream, Streamer, StreamerStatus, User

router = APIRouter()


@router.get("/stats/overview")
async def overview_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    """High-level KPIs: lead counts by status, streamer counts, revenue totals."""

    lead_by_status = await db.execute(
        select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    )
    lead_stats = {row[0].value: row[1] for row in lead_by_status}

    streamer_counts = await db.execute(
        select(Streamer.status, func.count(Streamer.id)).group_by(Streamer.status)
    )
    streamer_stats = {row[0].value: row[1] for row in streamer_counts}

    revenue = await db.scalar(
        select(func.coalesce(func.sum(Stream.amount), 0)).where(
            Stream.payment_status == PaymentStatus.paid
        )
    )
    pending_revenue = await db.scalar(
        select(func.coalesce(func.sum(Stream.amount), 0)).where(
            Stream.payment_status == PaymentStatus.pending
        )
    )

    total_streams = await db.scalar(select(func.count(Stream.id)))

    return {
        "leads": lead_stats,
        "streamers": streamer_stats,
        "streams": {
            "total": total_streams,
            "revenue_paid": float(revenue),
            "revenue_pending": float(pending_revenue),
        },
    }


@router.get("/stats/streams")
async def stream_stats(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    streamer_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    """Aggregated stream metrics for a date range."""
    q = select(
        func.count(Stream.id).label("stream_count"),
        func.coalesce(func.sum(Stream.views_youtube), 0).label("total_views_youtube"),
        func.coalesce(func.sum(Stream.views_tiktok), 0).label("total_views_tiktok"),
        func.coalesce(func.sum(Stream.registrations), 0).label("total_registrations"),
        func.coalesce(func.sum(Stream.deposits), 0).label("total_deposits"),
        func.coalesce(func.sum(Stream.amount), 0).label("total_amount"),
    )

    if date_from:
        q = q.where(Stream.date >= date_from)
    if date_to:
        q = q.where(Stream.date <= date_to)
    if streamer_id:
        q = q.where(Stream.streamer_id == streamer_id)

    row = (await db.execute(q)).one()
    return {
        "stream_count": row.stream_count,
        "total_views_youtube": int(row.total_views_youtube),
        "total_views_tiktok": int(row.total_views_tiktok),
        "total_registrations": int(row.total_registrations),
        "total_deposits": int(row.total_deposits),
        "total_amount": float(row.total_amount),
    }


@router.get("/stats/leads-funnel")
async def leads_funnel(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    """Conversion funnel: new → contacted → in_process → approved."""
    result = await db.execute(
        select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    )
    counts = {row[0].value: row[1] for row in result}
    funnel = [
        {"stage": s.value, "count": counts.get(s.value, 0)}
        for s in [
            LeadStatus.new, LeadStatus.contacted,
            LeadStatus.in_process, LeadStatus.approved, LeadStatus.rejected,
        ]
    ]
    return {"funnel": funnel}


@router.get("/stats/top-streamers")
async def top_streamers(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_any),
):
    """Top streamers by total paid amount."""
    result = await db.execute(
        select(
            Streamer.id,
            Streamer.nickname,
            func.count(Stream.id).label("stream_count"),
            func.coalesce(func.sum(Stream.amount), 0).label("total_amount"),
        )
        .join(Stream, Stream.streamer_id == Streamer.id, isouter=True)
        .where(Stream.payment_status == PaymentStatus.paid)
        .group_by(Streamer.id, Streamer.nickname)
        .order_by(func.coalesce(func.sum(Stream.amount), 0).desc())
        .limit(limit)
    )
    return {
        "streamers": [
            {
                "id": row.id,
                "nickname": row.nickname,
                "stream_count": row.stream_count,
                "total_amount": float(row.total_amount),
            }
            for row in result
        ]
    }
