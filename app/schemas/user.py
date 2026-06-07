import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict


class UserBase(BaseModel):
    full_name: str = Field(max_length=255)
    email: EmailStr
    phone_number: str | None = Field(default=None, max_length=15)
    date_of_birth: datetime.date | None = None
    address: str | None = None
    profile_picture_url: str | None = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, max_length=15)
    date_of_birth: datetime.date | None = None
    address: str | None = None
    profile_picture_url: str | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: str
    sms_webhook_key: str | None = None
    sms_configured: bool | None = None
    email_collection_configured: bool | None = None
    registration_step: int | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None
