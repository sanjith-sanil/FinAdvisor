import asyncio
import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.email_config import EmailConfig
from app.models.enums import EmailAuthType
from app.services.email_collector_service import process_user_email_account
from app.services.gmail_api_service import GmailAPIService

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


async def _run_imap_checks() -> None:
    async with SessionLocal() as db:
        stmt = select(EmailConfig).where(
            EmailConfig.auth_type == EmailAuthType.imap_password,
            EmailConfig.is_active.is_(True),
        )
        configs = (await db.execute(stmt)).scalars().all()
        for config in configs:
            if not config.first_sync_done:
                continue
            try:
                config.sync_status = "syncing"
                config.last_sync_error = None
                await db.commit()

                await process_user_email_account(config.user_id, config.id, db)

                config.sync_status = "completed"
                await db.commit()
            except Exception as exc:
                config.sync_status = "error"
                config.last_sync_error = str(exc)
                config.last_error = str(exc)
                await db.commit()


async def _run_oauth_checks() -> None:
    async with SessionLocal() as db:
        stmt = select(EmailConfig).where(
            EmailConfig.auth_type == EmailAuthType.oauth,
            EmailConfig.is_active.is_(True),
        )
        configs = (await db.execute(stmt)).scalars().all()
        service = GmailAPIService()
        for config in configs:
            await service.process_gmail_oauth(db, config)


async def _cleanup_logs() -> None:
    async with SessionLocal() as db:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
        await db.execute(
            "DELETE FROM collection_logs WHERE created_at < :cutoff",
            {"cutoff": cutoff},
        )
        await db.commit()


def start_scheduler(interval_minutes: int) -> None:
    scheduler.add_job(_run_imap_checks, "interval", minutes=interval_minutes)
    scheduler.add_job(_run_oauth_checks, "interval", minutes=interval_minutes)
    scheduler.add_job(_cleanup_logs, "cron", hour=3, minute=0)
    scheduler.start()


def shutdown_scheduler() -> None:
    scheduler.shutdown(wait=False)
