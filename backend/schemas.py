from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, EmailStr, field_validator

from models import FunnelStatus, Geo, LeadStatus, PaymentStatus, Platform, UserRole, WalletType


# ─── Base helpers ─────────────────────────────────────────────────────────────

class OrmBase(BaseModel):
    model_config = {"from_attributes": True}


# ─── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.manager


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(OrmBase):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class ManagerInfo(OrmBase):
    id: int
    full_name: str
    email: str


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Lead ─────────────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    nickname: str
    geo: Optional[str] = None
    source: Optional[str] = None
    contact: Optional[str] = None
    status: LeadStatus = LeadStatus.new
    comment: Optional[str] = None
    manager_id: Optional[int] = None


class LeadUpdate(BaseModel):
    nickname: Optional[str] = None
    geo: Optional[str] = None
    source: Optional[str] = None
    contact: Optional[str] = None
    status: Optional[LeadStatus] = None
    comment: Optional[str] = None
    manager_id: Optional[int] = None


class LeadOut(OrmBase):
    id: int
    nickname: str
    geo: Optional[str]
    source: Optional[str]
    contact: Optional[str]
    status: LeadStatus
    comment: Optional[str]
    manager_id: Optional[int]
    manager: Optional[UserOut]
    created_at: datetime
    updated_at: datetime


# ─── Streamer ─────────────────────────────────────────────────────────────────

class StreamerCreate(BaseModel):
    nickname: str
    profile_url: str
    platform: Platform
    geo: Geo
    followers: Optional[int] = None
    notes: Optional[str] = None
    status: FunnelStatus = FunnelStatus.NEW
    manager_id: Optional[int] = None

    @field_validator("profile_url")
    @classmethod
    def validate_profile_url(cls, v: str) -> str:
        try:
            AnyHttpUrl(v)
        except Exception:
            raise ValueError("profile_url must be a valid HTTP/HTTPS URL")
        return v


class StreamerUpdate(BaseModel):
    nickname: Optional[str] = None
    profile_url: Optional[str] = None
    platform: Optional[Platform] = None
    geo: Optional[Geo] = None
    followers: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[FunnelStatus] = None
    manager_id: Optional[int] = None
    # ACTIVE-stage fields (filled once streamer reaches ACTIVE status)
    tiktok_link: Optional[str] = None
    tg_link: Optional[str] = None
    tg_channel: Optional[str] = None
    bot_link: Optional[str] = None
    stockity_login: Optional[str] = None
    stockity_password: Optional[str] = None
    price_per_stream: Optional[Decimal] = None
    wallet_address: Optional[str] = None
    wallet_type: Optional[WalletType] = None

    @field_validator("profile_url")
    @classmethod
    def validate_profile_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                AnyHttpUrl(v)
            except Exception:
                raise ValueError("profile_url must be a valid HTTP/HTTPS URL")
        return v


class StreamerOut(OrmBase):
    id: int
    nickname: str
    profile_url: Optional[str]
    platform: Optional[Platform]
    geo: Optional[Geo]
    followers: Optional[int]
    notes: Optional[str]
    status: FunnelStatus
    manager_id: Optional[int]
    manager: Optional[ManagerInfo]
    # ACTIVE-stage fields
    tiktok_link: Optional[str]
    tg_link: Optional[str]
    tg_channel: Optional[str]
    bot_link: Optional[str]
    stockity_login: Optional[str]
    stockity_password: Optional[str]
    price_per_stream: Optional[Decimal]
    wallet_address: Optional[str]
    wallet_type: Optional[WalletType]
    created_at: datetime
    updated_at: datetime
    last_status_change_at: Optional[datetime]


# ─── Stream (payouts) ─────────────────────────────────────────────────────────

class StreamCreate(BaseModel):
    streamer_id: int
    stream_link: Optional[str] = None
    date: Optional[date] = None
    views_youtube: Optional[int] = None
    views_tiktok: Optional[int] = None
    users_bot: Optional[int] = None
    users_channel: Optional[int] = None
    registrations: Optional[int] = None
    deposits: Optional[int] = None
    amount: Optional[Decimal] = None
    payment_status: PaymentStatus = PaymentStatus.pending
    payment_date: Optional[date] = None
    manager_id: Optional[int] = None
    notes: Optional[str] = None


class StreamUpdate(BaseModel):
    stream_link: Optional[str] = None
    date: Optional[date] = None
    views_youtube: Optional[int] = None
    views_tiktok: Optional[int] = None
    users_bot: Optional[int] = None
    users_channel: Optional[int] = None
    registrations: Optional[int] = None
    deposits: Optional[int] = None
    amount: Optional[Decimal] = None
    payment_status: Optional[PaymentStatus] = None
    payment_date: Optional[date] = None
    manager_id: Optional[int] = None
    notes: Optional[str] = None


class StreamOut(OrmBase):
    id: int
    streamer_id: int
    streamer: Optional[StreamerOut]
    stream_link: Optional[str]
    date: Optional[date]
    views_youtube: Optional[int]
    views_tiktok: Optional[int]
    users_bot: Optional[int]
    users_channel: Optional[int]
    registrations: Optional[int]
    deposits: Optional[int]
    amount: Optional[Decimal]
    payment_status: PaymentStatus
    payment_date: Optional[date]
    manager_id: Optional[int]
    notes: Optional[str]
    created_at: datetime


# ─── Schedule ─────────────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    streamer_id: int
    days_of_week: Optional[list[int]] = None
    stream_time: Optional[str] = None
    tiktok_link: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v):
        if v is not None:
            for d in v:
                if d not in range(7):
                    raise ValueError("days_of_week values must be 0–6")
        return v


class ScheduleUpdate(BaseModel):
    days_of_week: Optional[list[int]] = None
    stream_time: Optional[str] = None
    tiktok_link: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class ScheduleOut(OrmBase):
    id: int
    streamer_id: int
    streamer: Optional[StreamerOut]
    days_of_week: Optional[list[int]]
    stream_time: Optional[str]
    tiktok_link: Optional[str]
    is_active: bool
    notes: Optional[str]
    created_at: datetime


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    size: int
    pages: int
