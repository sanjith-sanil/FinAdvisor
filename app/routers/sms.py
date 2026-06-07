import datetime
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.sms_email_raw import SmsEmailRaw
from app.models.transaction import Transaction
from app.models.enums import SmsSourceType, TransactionSource, TransactionType
from app.schemas.sms_email_raw import SmsEmailRawOut, SmsIngestRequest
from app.services.sms_parser_service import parse_sms

router = APIRouter(prefix="/api/v1/sms", tags=["sms"])


@router.post("/ingest")
async def ingest_sms(user_id: uuid.UUID, payload: SmsIngestRequest, db: AsyncSession = Depends(get_db)) -> dict:
    parsed = parse_sms(payload.raw_sms, sender=payload.sender)
    parsed_ok = parsed is not None
    bank_name = parsed.get("bank_name") if parsed else "Unknown Bank"
    bank_code = parsed.get("bank_code") if parsed else "UNKNOWN"

    raw = SmsEmailRaw(
        user_id=user_id,
        source_type=SmsSourceType.sms,
        raw_content=payload.raw_sms,
        sender=payload.sender,
        bank_name=bank_name,
        bank_code=bank_code,
        received_at=payload.received_at,
        is_processed=parsed_ok,
    )
    db.add(raw)

    if parsed_ok:
        duplicate = None
        if parsed.get("reference_number"):
            stmt = select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.reference_number == parsed.get("reference_number"),
            )
            duplicate = (await db.execute(stmt)).scalar_one_or_none()
        if not duplicate:
            txn = Transaction(
                user_id=user_id,
                card_id=None,
                bank_account_id=None,
                transaction_type=TransactionType.credit if parsed.get("transaction_type") == "credit" else TransactionType.debit,
                amount=parsed.get("amount"),
                merchant_name=parsed.get("merchant_name"),
                description=payload.raw_sms,
                transaction_date=parsed.get("transaction_date") or payload.received_at or datetime.datetime.now(datetime.timezone.utc),
                balance_after=parsed.get("balance_after"),
                reference_number=parsed.get("reference_number"),
                bank_name=bank_name,
                bank_code=bank_code,
                sender_phone=payload.sender,
                source=TransactionSource.sms,
                raw_message=payload.raw_sms,
            )
            db.add(txn)
            await db.flush()
            raw.parsed_transaction_id = txn.id

    await db.commit()
    return {
        "parsed": parsed_ok,
        "transaction": {
            "transaction_type": parsed.get("transaction_type") if parsed else None,
            "amount": parsed.get("amount") if parsed else None,
            "merchant_name": parsed.get("merchant_name") if parsed else None,
            "balance_after": parsed.get("balance_after") if parsed else None,
            "reference_number": parsed.get("reference_number") if parsed else None,
            "card_last4": parsed.get("card_last4") if parsed else None,
            "account_last4": parsed.get("account_last4") if parsed else None,
            "bank_name": bank_name,
            "bank_code": bank_code,
        },
    }


@router.post("/ingest-bulk")
async def ingest_bulk(user_id: uuid.UUID, payload: list[SmsIngestRequest], db: AsyncSession = Depends(get_db)) -> dict:
    results = []
    for item in payload:
        parsed = parse_sms(item.raw_sms, sender=item.sender)
        parsed_ok = parsed is not None
        bank_name = parsed.get("bank_name") if parsed else "Unknown Bank"
        bank_code = parsed.get("bank_code") if parsed else "UNKNOWN"
        raw = SmsEmailRaw(
            user_id=user_id,
            source_type=SmsSourceType.sms,
            raw_content=item.raw_sms,
            sender=item.sender,
            bank_name=bank_name,
            bank_code=bank_code,
            received_at=item.received_at,
            is_processed=parsed_ok,
        )
        db.add(raw)

        if parsed_ok:
            txn = Transaction(
                user_id=user_id,
                transaction_type=TransactionType.credit if parsed.get("transaction_type") == "credit" else TransactionType.debit,
                amount=parsed.get("amount"),
                merchant_name=parsed.get("merchant_name"),
                description=item.raw_sms,
                transaction_date=parsed.get("transaction_date") or item.received_at or datetime.datetime.now(datetime.timezone.utc),
                balance_after=parsed.get("balance_after"),
                reference_number=parsed.get("reference_number"),
                bank_name=bank_name,
                bank_code=bank_code,
                sender_phone=item.sender,
                source=TransactionSource.sms,
                raw_message=item.raw_sms,
            )
            db.add(txn)
            await db.flush()
            raw.parsed_transaction_id = txn.id

    results.append({"raw": item.raw_sms, "parsed": parsed_ok})

    await db.commit()
    return {"results": results}


@router.get("/raw", response_model=list[SmsEmailRawOut])
async def list_raw(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[SmsEmailRawOut]:
    stmt = select(SmsEmailRaw).where(SmsEmailRaw.user_id == user_id)
    return (await db.execute(stmt)).scalars().all()


@router.get("/unparsed", response_model=list[SmsEmailRawOut])
async def list_unparsed(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[SmsEmailRawOut]:
    stmt = select(SmsEmailRaw).where(SmsEmailRaw.user_id == user_id, SmsEmailRaw.is_processed.is_(False))
    return (await db.execute(stmt)).scalars().all()
