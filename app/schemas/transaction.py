import datetime
import uuid

from pydantic import BaseModel, Field
from pydantic import ConfigDict

from app.models.enums import TransactionSource, TransactionType


class TransactionCreate(BaseModel):
    user_id: uuid.UUID
    card_id: uuid.UUID | None = None
    bank_account_id: uuid.UUID | None = None
    transaction_type: TransactionType
    amount: float
    merchant_name: str | None = Field(default=None, max_length=255)
    merchant_category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    transaction_date: datetime.datetime
    balance_after: float | None = None
    reference_number: str | None = Field(default=None, max_length=100)
    bank_name: str | None = Field(default=None, max_length=100)
    bank_code: str | None = Field(default=None, max_length=20)
    sender_email: str | None = Field(default=None, max_length=255)
    sender_phone: str | None = Field(default=None, max_length=50)
    source: TransactionSource
    raw_message: str | None = None


class TransactionUpdate(BaseModel):
    transaction_type: TransactionType | None = None
    amount: float | None = None
    merchant_name: str | None = Field(default=None, max_length=255)
    merchant_category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    transaction_date: datetime.datetime | None = None
    balance_after: float | None = None
    reference_number: str | None = Field(default=None, max_length=100)
    bank_name: str | None = Field(default=None, max_length=100)
    bank_code: str | None = Field(default=None, max_length=20)
    sender_email: str | None = Field(default=None, max_length=255)
    sender_phone: str | None = Field(default=None, max_length=50)


class TransactionOut(TransactionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
