"""
Seed script — creates initial admin user.

Usage:
    cd backend
    python seed.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import hash_password, verify_password
from config import settings
from database import AsyncSessionLocal, engine
from models import Base, User, UserRole


async def seed() -> None:
    # Ensure tables exist (useful for first run without Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        )
        if existing:
            if not verify_password(settings.ADMIN_PASSWORD, existing.password_hash):
                existing.password_hash = hash_password(settings.ADMIN_PASSWORD)
                await session.commit()
                print(f"Admin password updated: {settings.ADMIN_EMAIL}")
            else:
                print(f"Admin user already exists, password up to date: {settings.ADMIN_EMAIL}")
            return

        admin = User(
            email=settings.ADMIN_EMAIL,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            full_name=settings.ADMIN_FULL_NAME,
            role=UserRole.admin,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print(f"Admin user created: {settings.ADMIN_EMAIL}")


if __name__ == "__main__":
    asyncio.run(seed())
