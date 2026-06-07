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
