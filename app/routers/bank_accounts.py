import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.bank_account import BankAccount
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.bank_account import BankAccountCreate, BankAccountOut, BankAccountUpdateBalance

router = APIRouter(prefix="/api/v1/bank-accounts", tags=["bank-accounts"])


@router.get("/", response_model=list[BankAccountOut])
async def list_accounts(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BankAccountOut]:
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    stmt = select(BankAccount).where(BankAccount.user_id == user_id)
    return (await db.execute(stmt)).scalars().all()


@router.post("/", response_model=BankAccountOut)
async def create_account(
    payload: BankAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BankAccountOut:
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    account = BankAccount(**payload.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.put("/{account_id}/balance", response_model=BankAccountOut)
async def update_balance(
    account_id: uuid.UUID,
    payload: BankAccountUpdateBalance,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BankAccountOut:
    account = await db.get(BankAccount, account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    account.current_balance = payload.current_balance
    account.last_updated = payload.last_updated
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}")
async def delete_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    account = await db.get(BankAccount, account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(account)
    await db.commit()
    return {"status": "deleted"}
