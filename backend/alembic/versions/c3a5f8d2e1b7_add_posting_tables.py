"""add posting tables

Revision ID: c3a5f8d2e1b7
Revises: b9eeb98702e0
Create Date: 2026-05-21 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "c3a5f8d2e1b7"
down_revision: Union[str, None] = "b9eeb98702e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ENUMS = [
    ("poststatus",     ["draft", "queued", "sending", "sent", "failed", "cancelled"]),
    ("deliverystatus", ["pending", "sent", "failed"]),
    ("channelcode",    ["en", "es", "pt"]),
]


def upgrade() -> None:
    bind = op.get_bind()

    # Check pg_type directly and CREATE TYPE only when missing.
    # No DO $$ blocks — asyncpg rejects dollar-quoted procedural SQL.
    for enum_name, values in _ENUMS:
        exists = bind.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :name"),
            {"name": enum_name},
        ).scalar()
        if not exists:
            values_sql = ", ".join(f"'{v}'" for v in values)
            bind.execute(text(f"CREATE TYPE {enum_name} AS ENUM ({values_sql})"))

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
            postgresql.ENUM(
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
            postgresql.ENUM("en", "es", "pt", name="channelcode", create_type=False),
            nullable=False,
        ),
        sa.Column("channel_chat_id", sa.String(100), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
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
    for enum_name, _ in _ENUMS:
        op.execute(text(f"DROP TYPE IF EXISTS {enum_name}"))
