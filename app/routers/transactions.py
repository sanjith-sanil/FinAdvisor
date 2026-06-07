import csv
import datetime
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.get("/", response_model=list[TransactionOut])
async def list_transactions(
    user_id: uuid.UUID,
    date_from: str | None = None,
    date_to: str | None = None,
    type: str | None = None,
    category: str | None = None,
    source: str | None = None,
    bank_code: str | None = None,
    sender_email: str | None = None,
    search: str | None = None,
    card_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[TransactionOut]:
    filters = [Transaction.user_id == user_id]
    if date_from:
        filters.append(Transaction.transaction_date >= datetime.datetime.fromisoformat(date_from))
    if date_to:
        filters.append(Transaction.transaction_date <= datetime.datetime.fromisoformat(date_to))
    if type:
        filters.append(Transaction.transaction_type == type)
    if category:
        filters.append(Transaction.merchant_category == category)
    if source:
        filters.append(Transaction.source == source)
    if bank_code:
        if bank_code.upper() == "OTHER":
            filters.append(
                or_(
                    Transaction.bank_code.is_(None),
                    Transaction.bank_code.notin_(
                        ["HDFC", "SBI", "ICICI", "AXIS", "KOTAK", "YES", "INDUSIND", "IDFC", "PNB", "BOI", "BOB"]
                    ),
                )
            )
        else:
            filters.append(Transaction.bank_code == bank_code)
    if sender_email:
        filters.append(
            or_(
                Transaction.sender_email.ilike(f"%{sender_email}%"),
                Transaction.sender_phone.ilike(f"%{sender_email}%"),
            )
        )
    if search:
        filters.append(
            or_(
                Transaction.merchant_name.ilike(f"%{search}%"),
                Transaction.description.ilike(f"%{search}%"),
            )
        )
    if card_id:
        filters.append(Transaction.card_id == card_id)

    stmt = (
        select(Transaction)
        .where(and_(*filters))
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/", response_model=TransactionOut)
async def create_transaction(payload: TransactionCreate, db: AsyncSession = Depends(get_db)) -> TransactionOut:
    txn = Transaction(**payload.model_dump())
    db.add(txn)
    await db.commit()
    await db.refresh(txn)
    return txn


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(transaction_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> TransactionOut:
    txn = await db.get(Transaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.put("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: uuid.UUID, payload: TransactionUpdate, db: AsyncSession = Depends(get_db)
) -> TransactionOut:
    txn = await db.get(Transaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    await db.commit()
    await db.refresh(txn)
    return txn


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    txn = await db.get(Transaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    await db.delete(txn)
    await db.commit()
    return {"status": "deleted"}


@router.get("/export/csv")
async def export_transactions_csv(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
    )
    transactions = (await db.execute(stmt)).scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "id",
        "transaction_date",
        "description",
        "merchant_name",
        "merchant_category",
        "transaction_type",
        "amount",
        "card_id",
        "bank_account_id",
        "source",
        "bank_name",
        "bank_code",
        "sender_email",
        "sender_phone",
        "balance_after",
    ])
    for txn in transactions:
        writer.writerow(
            [
                txn.id,
                txn.transaction_date,
                txn.description,
                txn.merchant_name,
                txn.merchant_category,
                txn.transaction_type,
                txn.amount,
                txn.card_id,
                txn.bank_account_id,
                txn.source,
                txn.bank_name,
                txn.bank_code,
                txn.sender_email,
                txn.sender_phone,
                txn.balance_after,
            ]
        )

    buffer.seek(0)
    response = StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
    return response
