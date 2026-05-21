"""
Posting router — CRUD for Post / PostDelivery + image upload.

All endpoints require a valid JWT (get_current_user).
"""
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from dependencies import get_current_user
from models import (
    ChannelCode, DeliveryStatus, Post, PostDelivery, PostStatus, User,
)
from posting.scheduler import cancel_scheduled, schedule_post

router = APIRouter()

# ─── Schemas ──────────────────────────────────────────────────────────────────

class DeliveryOut(BaseModel):
    id: int
    channel_code: str
    channel_chat_id: str
    telegram_message_id: int | None = None
    status: str
    error: str | None = None
    sent_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class PostOut(BaseModel):
    id: int
    text_en: str
    text_es: str
    text_pt: str
    image_path: str | None = None
    scheduled_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: int | None = None
    deliveries: list[DeliveryOut] = []
    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    text_en: str = ""
    text_es: str = ""
    text_pt: str = ""
    image_path: str | None = None
    scheduled_at: datetime | None = None
    send_now: bool = False


class PostUpdate(BaseModel):
    text_en: str | None = None
    text_es: str | None = None
    text_pt: str | None = None
    image_path: str | None = None
    scheduled_at: datetime | None = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

_CHANNELS: list[tuple[ChannelCode, str]] = [
    (ChannelCode.en, settings.CHANNEL_EN),
    (ChannelCode.es, settings.CHANNEL_ES),
    (ChannelCode.pt, settings.CHANNEL_PT),
]


def _create_deliveries(post: Post) -> None:
    for code, chat_id in _CHANNELS:
        post.deliveries.append(
            PostDelivery(
                channel_code=code,
                channel_chat_id=chat_id,
                status=DeliveryStatus.pending,
            )
        )


async def _get_post_or_404(post_id: int, db: AsyncSession) -> Post:
    result = await db.execute(
        select(Post).where(Post.id == post_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


# ─── Upload ──────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    ext = Path(file.filename or "image.jpg").suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = Path(settings.UPLOAD_DIR) / filename

    content = await file.read()
    dest.write_bytes(content)

    return {"path": filename, "url": f"/uploads/{filename}"}


# ─── Posts CRUD ───────────────────────────────────────────────────────────────

@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_post(
    body: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.text_en and not body.text_es and not body.text_pt:
        raise HTTPException(status_code=400, detail="At least one text field required")

    post = Post(
        text_en=body.text_en,
        text_es=body.text_es,
        text_pt=body.text_pt,
        image_path=body.image_path,
        created_by=current_user.id,
        deliveries=[],
    )

    if body.send_now:
        post.status = PostStatus.queued
        post.scheduled_at = None
    elif body.scheduled_at:
        post.status = PostStatus.queued
        post.scheduled_at = body.scheduled_at
    else:
        post.status = PostStatus.draft

    _create_deliveries(post)
    db.add(post)
    await db.flush()
    await db.refresh(post)

    if body.send_now:
        asyncio.create_task(_publish_bg(post.id))
    elif body.scheduled_at:
        schedule_post(post.id, body.scheduled_at)

    return post


@router.get("/posts", response_model=dict)
async def list_posts(
    status: str | None = Query(None, description="Comma-separated statuses"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(Post)

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.where(Post.status.in_(statuses))

    from sqlalchemy import func, select as sa_select
    count_q = sa_select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q)

    q = q.order_by(Post.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    items = result.scalars().all()

    return {
        "items": [PostOut.model_validate(p) for p in items],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/posts/{post_id}", response_model=PostOut)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await _get_post_or_404(post_id, db)


@router.patch("/posts/{post_id}", response_model=PostOut)
async def update_post(
    post_id: int,
    body: PostUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    post = await _get_post_or_404(post_id, db)

    if post.status not in (PostStatus.draft, PostStatus.queued):
        raise HTTPException(status_code=400, detail="Only draft or queued posts can be edited")

    old_scheduled = post.scheduled_at

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(post, field, value)

    # Reschedule if scheduled_at changed
    if body.scheduled_at is not None and body.scheduled_at != old_scheduled:
        cancel_scheduled(post_id)
        if post.status == PostStatus.queued:
            schedule_post(post_id, body.scheduled_at)

    await db.flush()
    await db.refresh(post)
    return post


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    post = await _get_post_or_404(post_id, db)

    if post.status == PostStatus.sent:
        raise HTTPException(status_code=400, detail="Cannot cancel an already sent post")

    cancel_scheduled(post_id)
    post.status = PostStatus.cancelled
    await db.flush()


@router.post("/posts/{post_id}/send-now", response_model=PostOut)
async def send_post_now(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    post = await _get_post_or_404(post_id, db)

    if post.status in (PostStatus.sent, PostStatus.sending):
        raise HTTPException(status_code=400, detail="Post is already sent or being sent")
    if post.status == PostStatus.cancelled:
        raise HTTPException(status_code=400, detail="Cannot send a cancelled post")

    # Cancel any existing scheduled job
    cancel_scheduled(post_id)

    # Reset failed deliveries so they are retried
    for d in post.deliveries:
        if d.status == DeliveryStatus.failed:
            d.status = DeliveryStatus.pending
            d.error = None

    post.status = PostStatus.queued
    await db.flush()
    await db.refresh(post)

    asyncio.create_task(_publish_bg(post_id))
    return post


@router.post("/posts/{post_id}/retry-delivery/{delivery_id}", response_model=PostOut)
async def retry_delivery(
    post_id: int,
    delivery_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    post = await _get_post_or_404(post_id, db)

    delivery = next((d for d in post.deliveries if d.id == delivery_id), None)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if delivery.status != DeliveryStatus.failed:
        raise HTTPException(status_code=400, detail="Only failed deliveries can be retried")

    delivery.status = DeliveryStatus.pending
    delivery.error = None
    post.status = PostStatus.queued
    await db.flush()
    await db.refresh(post)

    asyncio.create_task(_publish_bg(post_id))
    return post


# ─── Background task wrapper ─────────────────────────────────────────────────

async def _publish_bg(post_id: int) -> None:
    """Fire-and-forget wrapper so publish errors don't crash the request."""
    try:
        from posting.publisher import publish_post
        await publish_post(post_id)
    except Exception as exc:  # noqa: BLE001
        # Log but don't raise — the delivery row already stores the error
        print(f"[posting] publish_post({post_id}) raised: {exc}")
