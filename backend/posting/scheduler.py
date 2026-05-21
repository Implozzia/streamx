"""
APScheduler wrapper — AsyncIOScheduler with PostgreSQL job store.

The job store uses a synchronous psycopg2 connection (separate from the
async asyncpg pool used by the main app). This is required because
APScheduler 3.x SQLAlchemyJobStore is synchronous.
"""
from datetime import datetime

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings

_scheduler: AsyncIOScheduler | None = None


def _build_scheduler() -> AsyncIOScheduler:
    jobstores = {
        "default": SQLAlchemyJobStore(url=settings.sync_database_url)
    }
    return AsyncIOScheduler(jobstores=jobstores, timezone="UTC")


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = _build_scheduler()
    return _scheduler


async def start_scheduler() -> None:
    s = get_scheduler()
    if not s.running:
        s.start()


async def shutdown_scheduler() -> None:
    s = get_scheduler()
    if s.running:
        s.shutdown(wait=False)


def schedule_post(post_id: int, run_date: datetime) -> None:
    """Add (or replace) a one-shot job that fires publish_post at run_date."""
    from posting.publisher import publish_post  # lazy to avoid circular import

    get_scheduler().add_job(
        publish_post,
        trigger="date",
        run_date=run_date,
        args=[post_id],
        id=f"post_{post_id}",
        replace_existing=True,
        misfire_grace_time=300,  # allow up to 5-min delay on container restart
    )


def cancel_scheduled(post_id: int) -> bool:
    """Remove the scheduled job for a post. Returns True if it existed."""
    job = get_scheduler().get_job(f"post_{post_id}")
    if job:
        job.remove()
        return True
    return False
