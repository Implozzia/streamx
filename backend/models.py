import enum
from datetime import datetime, date

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, ForeignKey,
    Integer, Numeric, String, Text, ARRAY, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ─── Enums ───────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    lead = "lead"
    manager = "manager"


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    in_process = "in_process"
    approved = "approved"
    rejected = "rejected"


class FunnelStatus(str, enum.Enum):
    NEW = "NEW"
    REQUEST_SENT = "REQUEST_SENT"
    REPLIED = "REPLIED"
    TALKING = "TALKING"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    DEAD = "DEAD"


class Platform(str, enum.Enum):
    TIKTOK = "TIKTOK"
    INSTAGRAM = "INSTAGRAM"
    YOUTUBE = "YOUTUBE"
    TELEGRAM = "TELEGRAM"


class Geo(str, enum.Enum):
    LATAM = "LATAM"
    BRASIL = "BRASIL"
    ARGENTINA = "ARGENTINA"
    COLOMBIA = "COLOMBIA"
    MEXICO = "MEXICO"
    PERU = "PERU"
    CHILE = "CHILE"
    ECUADOR = "ECUADOR"
    BOLIVIA = "BOLIVIA"
    PANAMA = "PANAMA"
    VENEZUELA = "VENEZUELA"
    ESPANA = "ESPANA"
    USA = "USA"
    OTHER = "OTHER"


class WalletType(str, enum.Enum):
    usdt_trc20 = "usdt_trc20"
    usdt_erc20 = "usdt_erc20"
    btc = "btc"
    other = "other"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    cancelled = "cancelled"


# ─── Models ──────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.manager)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('false'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="manager", foreign_keys="Lead.manager_id")
    streamers: Mapped[list["Streamer"]] = relationship("Streamer", back_populates="manager", foreign_keys="Streamer.manager_id")
    streams: Mapped[list["Stream"]] = relationship("Stream", back_populates="manager", foreign_keys="Stream.manager_id")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    geo: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(255))
    contact: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[LeadStatus] = mapped_column(Enum(LeadStatus), nullable=False, default=LeadStatus.new)
    comment: Mapped[str | None] = mapped_column(Text)
    manager_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    manager: Mapped["User | None"] = relationship("User", back_populates="leads", foreign_keys=[manager_id])


class Streamer(Base):
    __tablename__ = "streamers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_url: Mapped[str | None] = mapped_column(String(500), unique=True, nullable=True)
    platform: Mapped[Platform | None] = mapped_column(Enum(Platform, native_enum=False), nullable=True)
    geo: Mapped[Geo | None] = mapped_column(Enum(Geo, native_enum=False), nullable=True)
    followers: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tiktok_link: Mapped[str | None] = mapped_column(String(500))
    tg_link: Mapped[str | None] = mapped_column(String(500))
    tg_channel: Mapped[str | None] = mapped_column(String(255))
    bot_link: Mapped[str | None] = mapped_column(String(500))
    stockity_login: Mapped[str | None] = mapped_column(String(255))
    stockity_password: Mapped[str | None] = mapped_column(String(255))
    price_per_stream: Mapped[float | None] = mapped_column(Numeric(12, 2))
    wallet_address: Mapped[str | None] = mapped_column(String(500))
    wallet_type: Mapped[WalletType | None] = mapped_column(Enum(WalletType))
    status: Mapped[FunnelStatus] = mapped_column(
        Enum(FunnelStatus, native_enum=False), nullable=False, default=FunnelStatus.NEW
    )
    manager_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_status_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    manager: Mapped["User | None"] = relationship("User", back_populates="streamers", foreign_keys=[manager_id])
    streams: Mapped[list["Stream"]] = relationship("Stream", back_populates="streamer")
    schedule: Mapped[list["Schedule"]] = relationship("Schedule", back_populates="streamer")


class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    streamer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    stream_link: Mapped[str | None] = mapped_column(String(500))
    date: Mapped[date | None] = mapped_column(Date)
    views_youtube: Mapped[int | None] = mapped_column(Integer)
    views_tiktok: Mapped[int | None] = mapped_column(Integer)
    users_bot: Mapped[int | None] = mapped_column(Integer)
    users_channel: Mapped[int | None] = mapped_column(Integer)
    registrations: Mapped[int | None] = mapped_column(Integer)
    deposits: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), nullable=False, default=PaymentStatus.pending
    )
    payment_date: Mapped[date | None] = mapped_column(Date)
    manager_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    streamer: Mapped["Streamer"] = relationship("Streamer", back_populates="streams")
    manager: Mapped["User | None"] = relationship("User", back_populates="streams", foreign_keys=[manager_id])


class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    streamer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("streamers.id", ondelete="CASCADE"), nullable=False)
    days_of_week: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))  # 0=Mon … 6=Sun
    stream_time: Mapped[str | None] = mapped_column(String(10))  # "HH:MM"
    tiktok_link: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    streamer: Mapped["Streamer"] = relationship("Streamer", back_populates="schedule")
