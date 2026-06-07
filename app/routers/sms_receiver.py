import datetime
import uuid
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.config import settings
from app.models.collection_log import CollectionLog
from app.models.enums import CollectionLogType, CollectionSource, SmsSourceType, TransactionSource, TransactionType
from app.models.sms_email_raw import SmsEmailRaw
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.sms_receiver import SmsReceiveRequest
from app.services.sms_parser_service import parse_sms
from app.services.balance_sync_service import (
    resolve_transaction_accounts,
    sync_balances_for_transaction,
)

router = APIRouter(prefix="/api/v1/sms", tags=["sms-webhook"])


def _validate_key(user: User, api_key: str | None) -> None:
    if not api_key or not user.sms_webhook_key or api_key != user.sms_webhook_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/receive")
async def receive_sms(
    payload: SmsReceiveRequest,
    x_finadvisor_key: str | None = Header(default=None, alias="X-FinAdvisor-Key"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _validate_key(user, x_finadvisor_key)
    if not payload.message:
        raise HTTPException(status_code=400, detail="Message is required")

    parsed = parse_sms(payload.message, sender=payload.phone_number)
    parsed_ok = parsed is not None
    bank_name = parsed.get("bank_name") if parsed else "Unknown Bank"
    bank_code = parsed.get("bank_code") if parsed else "UNKNOWN"
    raw = SmsEmailRaw(
        user_id=payload.user_id,
        source_type=SmsSourceType.sms,
        raw_content=payload.message,
        sender=payload.phone_number,
        bank_name=bank_name,
        bank_code=bank_code,
        received_at=payload.received_at or datetime.datetime.now(datetime.timezone.utc),
        is_processed=parsed_ok,
    )
    db.add(raw)

    transaction_id = None
    if parsed_ok:
        duplicate = None
        if parsed.get("reference_number"):
            stmt = select(Transaction).where(
                Transaction.user_id == payload.user_id,
                Transaction.reference_number == parsed.get("reference_number"),
            )
            duplicate = (await db.execute(stmt)).scalar_one_or_none()
        if not duplicate:
            txn = Transaction(
                user_id=payload.user_id,
                transaction_type=TransactionType.credit if parsed.get("transaction_type") == "credit" else TransactionType.debit,
                amount=parsed.get("amount"),
                merchant_name=parsed.get("merchant_name"),
                description=payload.message,
                transaction_date=parsed.get("transaction_date") or payload.received_at or datetime.datetime.now(datetime.timezone.utc),
                balance_after=parsed.get("balance_after"),
                reference_number=parsed.get("reference_number"),
                bank_name=bank_name,
                bank_code=bank_code,
                sender_phone=payload.phone_number,
                source=TransactionSource.sms,
                raw_message=payload.message,
            )
            db.add(txn)
            await resolve_transaction_accounts(db, txn)
            await db.flush()
            if txn.card_id or txn.bank_account_id:
                await sync_balances_for_transaction(
                    db=db,
                    user_id=txn.user_id,
                    card_id=txn.card_id,
                    bank_account_id=txn.bank_account_id,
                    amount=txn.amount,
                    txn_type=txn.transaction_type,
                    operation="insert"
                )
            raw.parsed_transaction_id = txn.id
            transaction_id = txn.id

    user.sms_configured = True
    if user.registration_step:
        user.registration_step = max(user.registration_step, 4)

    log = CollectionLog(
        user_id=payload.user_id,
        log_type=CollectionLogType.sms_received,
        source=CollectionSource.sms_webhook,
        emails_checked=0,
        transactions_found=1 if transaction_id else 0,
        error_message=None,
        duration_ms=0,
    )
    db.add(log)
    await db.commit()

    return {"success": True, "transaction_id": transaction_id, "parsed": parsed_ok}


@router.post("/receive-bulk")
async def receive_bulk(
    payload: list[SmsReceiveRequest],
    x_finadvisor_key: str | None = Header(default=None, alias="X-FinAdvisor-Key"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    results = []
    for item in payload:
        user = await db.get(User, item.user_id)
        if not user:
            results.append({"user_id": item.user_id, "success": False, "error": "User not found"})
            continue
        _validate_key(user, x_finadvisor_key)
        parsed = parse_sms(item.message, sender=item.phone_number)
        parsed_ok = parsed is not None
        bank_name = parsed.get("bank_name") if parsed else "Unknown Bank"
        bank_code = parsed.get("bank_code") if parsed else "UNKNOWN"
        raw = SmsEmailRaw(
            user_id=item.user_id,
            source_type=SmsSourceType.sms,
            raw_content=item.message,
            sender=item.phone_number,
            bank_name=bank_name,
            bank_code=bank_code,
            received_at=item.received_at or datetime.datetime.now(datetime.timezone.utc),
            is_processed=parsed_ok,
        )
        db.add(raw)
        if parsed_ok:
            duplicate = None
            if parsed.get("reference_number"):
                stmt = select(Transaction).where(
                    Transaction.user_id == item.user_id,
                    Transaction.reference_number == parsed.get("reference_number"),
                )
                duplicate = (await db.execute(stmt)).scalar_one_or_none()
            if not duplicate:
                txn = Transaction(
                    user_id=item.user_id,
                    transaction_type=TransactionType.credit if parsed.get("transaction_type") == "credit" else TransactionType.debit,
                    amount=parsed.get("amount"),
                    merchant_name=parsed.get("merchant_name"),
                    description=item.message,
                    transaction_date=parsed.get("transaction_date") or item.received_at or datetime.datetime.now(datetime.timezone.utc),
                    balance_after=parsed.get("balance_after"),
                    reference_number=parsed.get("reference_number"),
                    bank_name=bank_name,
                    bank_code=bank_code,
                    sender_phone=item.phone_number,
                    source=TransactionSource.sms,
                    raw_message=item.message,
                )
                db.add(txn)
                await resolve_transaction_accounts(db, txn)
                await db.flush()
                if txn.card_id or txn.bank_account_id:
                    await sync_balances_for_transaction(
                        db=db,
                        user_id=txn.user_id,
                        card_id=txn.card_id,
                        bank_account_id=txn.bank_account_id,
                        amount=txn.amount,
                        txn_type=txn.transaction_type,
                        operation="insert"
                    )
                raw.parsed_transaction_id = txn.id
        results.append({"user_id": item.user_id, "parsed": parsed_ok})
        user.sms_configured = True

    await db.commit()
    return {"results": results}


@router.get("/setup-info/{user_id}")
async def setup_info(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.sms_webhook_key:
        user.sms_webhook_key = secrets.token_urlsafe(32)
        await db.commit()
        await db.refresh(user)
    base_url = (settings.server_base_url or "").strip()
    if not base_url or base_url.lower() in {"undefined", "null"}:
        base_url = str(request.base_url).rstrip("/")
    return {
        "webhook_url": f"{base_url}/api/v1/sms/receive",
        "api_key": user.sms_webhook_key,
        "user_id": str(user.id),
        "filter_keywords": "debited,credited,Rs.,INR,transaction",
        "json_template": '{"user_id":"UUID","phone_number":"%from%","message":"%body%","received_at":"%date%"}',
        "app_download_url": "https://play.google.com/store/apps/details?id=com.frzinapps.smsforward",
    }


@router.post("/mark-configured/{user_id}")
async def mark_configured(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.sms_configured = True
    user.registration_step = max(user.registration_step or 1, 4)
    await db.commit()
    return {"success": True}
