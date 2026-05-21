"""add posting tables

Revision ID: c3a5f8d2e1b7
Revises: b9eeb98702e0
Create Date: 2026-05-21 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3a5f8d2e1b7"
down_revision: Union[str, None] = "b9eeb98702e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create PostgreSQL enum types
    op.execute(
        "CREATE TYPE poststatus AS ENUM "
        "('draft', 'queued', 'sending', 'sent', 'failed', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE deliverystatus AS ENUM ('pending', 'sent', 'failed')"
    )
    op.execute(
        "CREATE TYPE channelcode AS ENUM ('en', 'es', 'pt')"
    )

    # 2. posts
    op.create_table(
        "posts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("text_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("text_es", sa.Text(), nullable=False, server_default=""),
        sa.Column("text_pt", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "queued", "sending", "sent", "failed", "cancelled",
                name="poststatus", create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3. post_deliveries
    op.create_table(
        "post_deliveries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "post_id",
            sa.BigInteger(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_code",
            sa.Enum("en", "es", "pt", name="channelcode", create_type=False),
            nullable=False,
        ),
        sa.Column("channel_chat_id", sa.String(100), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "sent", "failed",
                name="deliverystatus", create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_posts_status", "posts", ["status"])
    op.create_index("ix_posts_scheduled_at", "posts", ["scheduled_at"])
    op.create_index("ix_post_deliveries_post_id", "post_deliveries", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_post_deliveries_post_id", "post_deliveries")
    op.drop_index("ix_posts_scheduled_at", "posts")
    op.drop_index("ix_posts_status", "posts")
    op.drop_table("post_deliveries")
    op.drop_table("posts")
    op.execute("DROP TYPE poststatus")
    op.execute("DROP TYPE deliverystatus")
    op.execute("DROP TYPE channelcode")
