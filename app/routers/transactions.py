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
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate
from app.services.balance_sync_service import (
    resolve_transaction_accounts,
    sync_balances_for_transaction,
)

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
    current_user: User = Depends(get_current_user),
) -> list[TransactionOut]:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

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
        # Prevent accessing another user's card transactions
        from app.models.card import Card
        card = await db.get(Card, card_id)
        if card and card.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden: You do not own this card")
        filters.append(Transaction.card_id == card_id)

    from app.models.transaction import scope_active_transactions
    stmt = (
        select(Transaction)
        .where(and_(*filters))
    )
    stmt = scope_active_transactions(stmt)
    stmt = (
        stmt.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/", response_model=TransactionOut)
async def create_transaction(
    payload: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionOut:
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    txn = Transaction(**payload.model_dump())
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
    await db.commit()
    await db.refresh(txn)
    return txn


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionOut:
    txn = await db.get(Transaction, transaction_id)
    if not txn or txn.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.put("/{transaction_id}", response_model=TransactionOut)
async def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TransactionOut:
    txn = await db.get(Transaction, transaction_id)
    if not txn or txn.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    old_amount = float(txn.amount)
    old_type = txn.transaction_type
    old_card_id = txn.card_id
    old_bank_account_id = txn.bank_account_id

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
        
    await resolve_transaction_accounts(db, txn)
    await db.flush()

    if old_card_id or old_bank_account_id:
        await sync_balances_for_transaction(
            db=db,
            user_id=txn.user_id,
            card_id=old_card_id,
            bank_account_id=old_bank_account_id,
            amount=0.0,
            txn_type=old_type,
            operation="delete",
            old_amount=old_amount,
            old_type=old_type
        )
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
        
    await db.commit()
    await db.refresh(txn)
    return txn


@router.delete("/{transaction_id}")
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    txn = await db.get(Transaction, transaction_id)
    if not txn or txn.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if txn.card_id or txn.bank_account_id:
        await sync_balances_for_transaction(
            db=db,
            user_id=txn.user_id,
            card_id=txn.card_id,
            bank_account_id=txn.bank_account_id,
            amount=0.0,
            txn_type=txn.transaction_type,
            operation="delete",
            old_amount=txn.amount,
            old_type=txn.transaction_type
        )
        
    await db.delete(txn)
    await db.commit()
    return {"status": "deleted"}


@router.get("/export/csv")
async def export_transactions_csv(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    from app.models.transaction import scope_active_transactions
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
    )
    stmt = scope_active_transactions(stmt)
    stmt = stmt.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
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
