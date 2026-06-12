import datetime
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.utils.files import save_upload_file

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _generate_customer_id() -> str:
    return f"CUST{uuid.uuid4().int % 10**8:08d}"


@router.post("/", response_model=UserOut)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> UserOut:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    customer_id = _generate_customer_id()
    user = User(customer_id=customer_id, **payload.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> UserOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{user_id}/stats")
async def get_user_stats(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    from sqlalchemy import func
    from app.models.card import Card
    from app.models.transaction import Transaction
    
    card_count = (await db.execute(
        select(func.count(Card.id)).where(Card.user_id == user_id, Card.is_active.is_(True))
    )).scalar() or 0
    
    txn_count = (await db.execute(
        select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
    )).scalar() or 0
    
    return {
        "cards_count": card_count,
        "transactions_count": txn_count
    }


@router.put("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db)) -> UserOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}")
async def soft_delete_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    return {"status": "soft-deleted"}


@router.post("/{user_id}/avatar", response_model=UserOut)
async def upload_avatar(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    file_path = save_upload_file(file, prefix="avatar-")
    user.profile_picture_url = file_path
    await db.commit()
    await db.refresh(user)
    return user


from pydantic import BaseModel

class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


@router.post("/{user_id}/change-password")
async def change_password(
    user_id: uuid.UUID,
    payload: ChangePasswordPayload,
    db: AsyncSession = Depends(get_db)
) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.password_hash:
        raise HTTPException(status_code=400, detail="User password not configured")

    from app.routers.auth import pwd_context, _hash_password
    if not pwd_context.verify(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user.password_hash = _hash_password(payload.new_password)
    user.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()

    return {"success": True, "message": "Password changed successfully"}


import csv
import io
from fastapi.responses import StreamingResponse
from app.models.transaction import Transaction

@router.get("/{user_id}/export-data")
async def export_data(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch all user transactions
    stmt = select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.transaction_date.desc())
    txns = (await db.execute(stmt)).scalars().all()

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Transaction Date", "Description", "Amount", "Type", "Source", "Bank Name", "Bank Code"
    ])

    # Write rows
    for txn in txns:
        writer.writerow([
            txn.transaction_date.isoformat() if txn.transaction_date else "",
            txn.description or "",
            txn.amount or 0.0,
            txn.transaction_type.value if txn.transaction_type else "",
            txn.source.value if txn.source else "",
            txn.bank_name or "",
            txn.bank_code or ""
        ])

    output.seek(0)

    filename = f"finadvisor_export_{user_id}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

