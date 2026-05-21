"""
Telegram publisher — sends or retries a Post to all 3 channels.

Rules:
- Only processes PostDelivery rows with status=pending
- Does NOT roll back already-sent deliveries on partial failure
- Post.status → sent if all 3 sent, failed if at least 1 failed
"""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from telegram import Bot
from telegram.error import TelegramError

from config import settings
from database import AsyncSessionLocal
from models import ChannelCode, DeliveryStatus, Post, PostDelivery, PostStatus


_CHANNEL_TEXT: dict[str, str] = {
    ChannelCode.en: "text_en",
    ChannelCode.es: "text_es",
    ChannelCode.pt: "text_pt",
}


async def publish_post(post_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Post).where(Post.id == post_id)
        )
        post = result.scalar_one_or_none()

        if not post or post.status == PostStatus.cancelled:
            return

        post.status = PostStatus.sending
        await db.flush()

        pending = [d for d in post.deliveries if d.status == DeliveryStatus.pending]
        if not pending:
            return

        bot = Bot(token=settings.BOT_TOKEN)
        async with bot:
            for delivery in pending:
                text_field = _CHANNEL_TEXT.get(delivery.channel_code, "text_en")
                text = getattr(post, text_field, "") or ""
                try:
                    if post.image_path:
                        img_path = Path(settings.UPLOAD_DIR) / post.image_path
                        with open(img_path, "rb") as fh:
                            msg = await bot.send_photo(
                                chat_id=delivery.channel_chat_id,
                                photo=fh,
                                caption=text or None,
                                parse_mode="HTML",
                            )
                    else:
                        msg = await bot.send_message(
                            chat_id=delivery.channel_chat_id,
                            text=text,
                            parse_mode="HTML",
                        )
                    delivery.telegram_message_id = msg.message_id
                    delivery.status = DeliveryStatus.sent
                    delivery.sent_at = datetime.now(timezone.utc)
                    delivery.error = None
                except TelegramError as exc:
                    delivery.status = DeliveryStatus.failed
                    delivery.error = str(exc)
                except Exception as exc:
                    delivery.status = DeliveryStatus.failed
                    delivery.error = f"{type(exc).__name__}: {exc}"

        all_sent = all(d.status == DeliveryStatus.sent for d in post.deliveries)
        any_failed = any(d.status == DeliveryStatus.failed for d in post.deliveries)

        if all_sent:
            post.status = PostStatus.sent
        elif any_failed:
            post.status = PostStatus.failed

        await db.commit()
