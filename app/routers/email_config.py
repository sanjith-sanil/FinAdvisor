import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import SessionLocal, get_db
from app.models.email_config import EmailConfig
from app.models.enums import EmailAuthType, SmsSourceType
from app.models.sms_email_raw import SmsEmailRaw
from app.models.user import User
from app.schemas.email_config import EmailConfigStatusOut, EmailSetupRequest, EmailTestRequest, EmailIngestRequest
from app.services.bank_domain_whitelist import BANK_DOMAINS
from app.services.crypto_service import encrypt_text
from app.services.email_collector_service import (
    EmailCollectorService,
    _imap_server_for,
    process_user_email_account,
    reparse_email_raws,
)
from app.services.gmail_api_service import GmailAPIService

router = APIRouter(prefix="/api/v1/email-config", tags=["email-config"])
logger = logging.getLogger(__name__)


async def run_email_sync(user_id: uuid.UUID, config_id: uuid.UUID, force_full_sync: bool = False) -> None:
    async with SessionLocal() as db:
        config = await db.get(EmailConfig, config_id)
        if not config or config.user_id != user_id:
            return

        try:
            config.sync_status = "syncing"
            config.last_sync_error = None
            await db.commit()

            if config.auth_type == EmailAuthType.oauth:
                service = GmailAPIService()
                result = await service.process_gmail_oauth(db, config, force_full_sync=force_full_sync)
                if result.get("error"):
                    raise RuntimeError(result["error"])
            else:
                await process_user_email_account(user_id, config_id, db, update_status=False)

            await reparse_email_raws(db, user_id, since_days=90)

            config = await db.get(EmailConfig, config_id)
            if config:
                config.sync_status = "completed"
                config.last_sync_error = None
                config.last_error = None
                await db.commit()
        except Exception as exc:
            logger.exception("Background email sync failed for user %s", user_id)
            config = await db.get(EmailConfig, config_id)
            if config:
                config.sync_status = "error"
                config.last_sync_error = str(exc)
                config.last_error = str(exc)
                await db.commit()


@router.post("/test-connection")
async def test_connection(payload: EmailTestRequest) -> dict:
    service = EmailCollectorService()
    return await service.test_connection(payload.email_address, payload.password, payload.imap_server)


@router.post("/setup-imap")
async def setup_imap(
    payload: EmailSetupRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    service = EmailCollectorService()
    test = await service.test_connection(payload.email_address, payload.password, payload.imap_server)
    if not test.get("success"):
        raise HTTPException(status_code=400, detail=test.get("message", "Connection failed"))

    server, port = _imap_server_for(payload.email_address)
    if payload.imap_server:
        server = payload.imap_server

    encrypted = encrypt_text(payload.password)
    existing = await db.execute(select(EmailConfig).where(EmailConfig.user_id == payload.user_id))
    config = existing.scalar_one_or_none()

    if not config:
        config = EmailConfig(
            user_id=payload.user_id,
            email_address=payload.email_address,
            auth_type=EmailAuthType.imap_password,
            password_encrypted=encrypted,
            imap_server=server,
            imap_port=port,
            sync_status="syncing",
            last_sync_error=None,
        )
        db.add(config)
    else:
        config.email_address = payload.email_address
        config.auth_type = EmailAuthType.imap_password
        config.password_encrypted = encrypted
        config.imap_server = server
        config.imap_port = port
        config.is_active = True
        config.sync_status = "syncing"
        config.last_sync_error = None
        config.last_error = None

    user.email_collection_configured = True
    user.registration_step = max(user.registration_step or 1, 3)

    await db.commit()
    await db.refresh(config)

    background_tasks.add_task(run_email_sync, payload.user_id, config.id)

    return {
        "success": True,
        "message": "Email connected. Fetching all transactions...",
        "sync_started": True,
    }


@router.get("/sync-status")
async def sync_status(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(EmailConfig).where(EmailConfig.user_id == user_id)
    config = (await db.execute(stmt)).scalar_one_or_none()
    if not config:
        return {
            "sync_status": "idle",
            "transactions_found": 0,
            "bank_emails_found": 0,
            "total_scanned": 0,
            "last_error": None,
            "first_sync_done": False,
            "last_checked": None,
        }

    latest = await db.execute(
        text(
            "SELECT COALESCE(bank_emails_found, 0), COALESCE(emails_checked, 0) "
            "FROM collection_logs WHERE user_id = :user_id ORDER BY created_at DESC LIMIT 1"
        ),
        {"user_id": user_id},
    )
    row = latest.fetchone()
    bank_emails_found = int(row[0]) if row else 0
    emails_checked = int(row[1]) if row else 0

    return {
        "sync_status": config.sync_status or "idle",
        "transactions_found": int(config.transactions_found_total or 0),
        "bank_emails_found": bank_emails_found,
        "total_scanned": int(config.total_emails_scanned or emails_checked),
        "last_error": config.last_sync_error or config.last_error,
        "first_sync_done": bool(config.first_sync_done),
        "last_checked": config.last_checked,
    }


@router.get("/status", response_model=EmailConfigStatusOut)
async def status(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> EmailConfigStatusOut:
    stmt = select(EmailConfig).where(EmailConfig.user_id == user_id)
    config = (await db.execute(stmt)).scalar_one_or_none()
    if not config:
        return EmailConfigStatusOut(
            configured=False,
            auth_type=None,
            email_masked=None,
            last_checked=None,
            last_error=None,
            total_processed=0,
            total_transactions=0,
            is_active=False,
            whitelisted_domains_count=len(BANK_DOMAINS),
            last_scan_stats={
                "total_scanned": 0,
                "bank_emails_found": 0,
                "non_bank_skipped": 0,
                "transactions_saved": 0,
            },
            recent_logs=[],
        )

    email_masked = config.email_address[0] + "***@" + config.email_address.split("@")[-1]
    logs = []
    logs_result = await db.execute(
        text(
            "SELECT created_at, emails_checked, transactions_found, non_bank_emails_rejected, "
            "bank_emails_found, duplicates_skipped, error_message "
            "FROM collection_logs WHERE user_id = :user_id "
            "ORDER BY created_at DESC LIMIT 5"
        ),
        {"user_id": user_id},
    )

    for row in logs_result.fetchall():
        logs.append(
            {
                "time": row[0],
                "emails_checked": row[1],
                "transactions_found": row[2],
                "non_bank_emails_rejected": row[3],
                "bank_emails_found": row[4],
                "duplicates_skipped": row[5],
                "error_message": row[6],
            }
        )

    latest = logs[0] if logs else None
    last_scan_stats = {
        "total_scanned": latest.get("emails_checked", 0) if latest else 0,
        "bank_emails_found": latest.get("bank_emails_found", 0) if latest else 0,
        "non_bank_skipped": latest.get("non_bank_emails_rejected", 0) if latest else 0,
        "transactions_saved": latest.get("transactions_found", 0) if latest else 0,
    }

    return EmailConfigStatusOut(
        configured=True,
        auth_type=config.auth_type.value,
        email_masked=email_masked,
        last_checked=config.last_checked,
        last_error=config.last_sync_error or config.last_error,
        total_processed=config.emails_processed_total or 0,
        total_transactions=config.transactions_found_total or 0,
        is_active=config.is_active,
        whitelisted_domains_count=len(BANK_DOMAINS),
        last_scan_stats=last_scan_stats,
        recent_logs=logs,
    )


@router.get("/bank-domains")
async def bank_domains() -> dict:
    domains = [
        {
            "domain": domain,
            "bank_name": info["bank_name"],
            "bank_code": info["bank_code"],
            "logo_color": info["logo_color"],
        }
        for domain, info in sorted(BANK_DOMAINS.items(), key=lambda item: (item[1]["bank_name"], item[0]))
    ]
    return {"total": len(domains), "domains": domains}


@router.post("/check-now")
async def check_now(
    user_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(EmailConfig).where(EmailConfig.user_id == user_id)
    config = (await db.execute(stmt)).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Email config not found")

    config.sync_status = "syncing"
    config.last_sync_error = None
    config.last_error = None
    await db.commit()

    background_tasks.add_task(run_email_sync, user_id, config.id, True)
    return {"sync_started": True}


@router.delete("/disconnect")
async def disconnect(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(EmailConfig).where(EmailConfig.user_id == user_id)
    config = (await db.execute(stmt)).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Email config not found")
    await db.delete(config)
    user = await db.get(User, user_id)
    if user:
        user.email_collection_configured = False
    await db.commit()
    return {"success": True}


@router.put("/toggle")
async def toggle(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    stmt = select(EmailConfig).where(EmailConfig.user_id == user_id)
    config = (await db.execute(stmt)).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Email config not found")
    config.is_active = not bool(config.is_active)
    await db.commit()
    return {"is_active": config.is_active}


@router.post("/ingest-test")
async def ingest_test_email(
    payload: EmailIngestRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    import datetime
    from app.services.bank_domain_whitelist import get_bank_info
    from app.services.emi_upsert_service import process_emi_from_email
    from app.services.sms_parser_service import looks_like_transaction_alert, parse_sms
    from app.models.transaction import Transaction
    from app.models.enums import TransactionType, TransactionSource

    sender_email = payload.sender_email.strip().lower()
    bank_info = get_bank_info(sender_email)
    if not bank_info:
        raise HTTPException(
            status_code=400,
            detail=(
                "Sender email domain is not in the bank whitelist. "
                "Choose an email ending in a supported domain "
                "(e.g., hdfcbank.net, icicibank.com, axisbank.com)."
            )
        )

    # Insert raw email record
    raw = SmsEmailRaw(
        user_id=payload.user_id,
        source_type=SmsSourceType.email,
        raw_content=payload.email_body,
        sender=sender_email,
        bank_name=bank_info["bank_name"],
        bank_code=bank_info["bank_code"],
        subject=payload.subject,
        message_id=f"test-mail-{uuid.uuid4()}",
        received_at=datetime.datetime.now(datetime.timezone.utc),
        is_processed=False
    )
    db.add(raw)
    await db.flush()

    # Process EMI
    emi_count = await process_emi_from_email(
        db=db,
        user_id=payload.user_id,
        bank_code=bank_info["bank_code"],
        email_body=payload.email_body,
        email_subject=payload.subject,
        source_raw_id=raw.id
    )

    if emi_count > 0:
        raw.is_processed = True
        await db.commit()
        return {
            "success": True,
            "message": f"Successfully parsed and upserted {emi_count} EMI record(s)!",
            "bank_name": bank_info["bank_name"],
            "bank_code": bank_info["bank_code"],
            "emi_records_count": emi_count
        }
    else:
        # Try if it looks like a standard transaction alert
        combined_text = f"{payload.subject} {payload.email_body}".strip()
        parsed = parse_sms(combined_text, sender=sender_email) if looks_like_transaction_alert(combined_text) else None
        if parsed and parsed.get("amount") is not None:
            transaction_type = TransactionType.credit if parsed.get("transaction_type") == "credit" else TransactionType.debit
            transaction = Transaction(
                user_id=payload.user_id,
                transaction_type=transaction_type,
                amount=parsed.get("amount"),
                merchant_name=parsed.get("merchant_name"),
                description=payload.email_body[:2000],
                balance_after=parsed.get("balance_after"),
                reference_number=parsed.get("reference_number"),
                transaction_date=parsed.get("transaction_date") or datetime.datetime.now(datetime.timezone.utc),
                source=TransactionSource.email,
                bank_name=bank_info["bank_name"],
                bank_code=bank_info["bank_code"],
                sender_email=sender_email,
                raw_message=combined_text[:2000],
            )
            db.add(transaction)
            from app.services.balance_sync_service import (
                resolve_transaction_accounts,
                sync_balances_for_transaction,
            )
            await resolve_transaction_accounts(db, transaction)
            await db.flush()
            if transaction.card_id or transaction.bank_account_id:
                await sync_balances_for_transaction(
                    db=db,
                    user_id=payload.user_id,
                    card_id=transaction.card_id,
                    bank_account_id=transaction.bank_account_id,
                    amount=transaction.amount,
                    txn_type=transaction.transaction_type,
                    operation="insert"
                )
            
            raw.is_processed = True
            raw.parsed_transaction_id = transaction.id
            await db.commit()
            return {
                "success": True,
                "message": "Successfully parsed and saved standard transaction from email!",
                "bank_name": bank_info["bank_name"],
                "bank_code": bank_info["bank_code"],
                "transaction": {
                    "merchant": parsed.get("merchant_name"),
                    "amount": parsed.get("amount"),
                    "type": transaction_type.value
                }
            }

        await db.commit()
        return {
            "success": False,
            "message": (
                "Email matched a bank domain, but no EMI details or transaction alerts "
                "could be parsed. Check the email format."
            ),
            "bank_name": bank_info["bank_name"],
            "bank_code": bank_info["bank_code"]
        }

