import datetime
import uuid

from pydantic import BaseModel, Field
from pydantic import ConfigDict

from app.models.enums import AccountType


class BankAccountCreate(BaseModel):
    user_id: uuid.UUID
    bank_name: str = Field(max_length=100)
    account_number_last4: str | None = Field(default=None, max_length=4)
    account_type: AccountType | None = None
    current_balance: float | None = None
    last_updated: datetime.datetime | None = None


class BankAccountUpdateBalance(BaseModel):
    current_balance: float
    last_updated: datetime.datetime | None = None


class BankAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    bank_name: str
    account_number_last4: str | None = None
    account_type: AccountType | None = None
    current_balance: float | None = None
    last_updated: datetime.datetime | None = None
    created_at: datetime.datetime
