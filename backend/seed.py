"""
Seed script — creates initial admin user.

Usage:
    cd backend
    python seed.py

Requires Alembic migrations to have been applied first.
If the users table does not exist, exits with code 1 so the deploy fails visibly.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from auth import hash_password, verify_password
from config import settings
from database import AsyncSessionLocal
from models import User, UserRole


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        try:
            existing = await session.scalar(
                select(User).where(User.email == settings.ADMIN_EMAIL)
            )
        except ProgrammingError as e:
            print(
                f"[seed] ERROR: Could not query users table — migrations have not been applied.\n"
                f"       Run 'alembic upgrade head' before seeding.\n"
                f"       Detail: {e.orig}"
            )
            sys.exit(1)

        if existing:
            if not verify_password(settings.ADMIN_PASSWORD, existing.password_hash):
                existing.password_hash = hash_password(settings.ADMIN_PASSWORD)
                await session.commit()
                print(f"[seed] Admin password updated: {settings.ADMIN_EMAIL}")
            else:
                print(f"[seed] Admin already exists, password up to date: {settings.ADMIN_EMAIL}")
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
        print(f"[seed] Admin user created: {settings.ADMIN_EMAIL}")


if __name__ == "__main__":
    asyncio.run(seed())
