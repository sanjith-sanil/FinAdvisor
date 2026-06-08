import datetime
import uuid

from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict

from app.models.enums import BenefitCategory, CardNetwork, CardType


class CardBase(BaseModel):
    user_id: uuid.UUID
    bank_name: str = Field(max_length=100)
    card_holder_name: str = Field(max_length=255)
    card_type: CardType
    card_last4: str = Field(max_length=4)
    card_network: CardNetwork | None = None
    expiry_month: int | None = None
    expiry_year: int | None = None
    credit_limit: float | None = None
    current_balance: float | None = None
    available_balance: float | None = None
    pending_emi_amount: float | None = None
    emi_tenure_months: int | None = None
    emi_interest_rate: float | None = None
    monthly_emi_amount: float | None = None
    billing_cycle_date: int | None = None
    payment_due_date: int | None = None
    annual_fee: float = 0
    joining_fee: float = 0
    reward_points_balance: int = 0
    reward_points_rate: str | None = Field(default=None, max_length=100)
    cashback_rate: str | None = Field(default=None, max_length=100)
    lounge_access: bool = False
    lounge_visits_per_quarter: int = 0
    fuel_surcharge_waiver: bool = False
    credit_score_impact: int = 0
    notes: str | None = None
    is_active: bool = True
    color_theme: str | None = Field(default=None, max_length=20)

    @field_validator("card_last4")
    @classmethod
    def validate_last4(cls, value: str) -> str:
        if len(value) != 4 or not value.isdigit():
            raise ValueError("card_last4 must be 4 digits")
        return value

    @field_validator("expiry_month")
    @classmethod
    def validate_month(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 1 or value > 12:
            raise ValueError("expiry_month must be between 1 and 12")
        return value

    @field_validator("expiry_year")
    @classmethod
    def validate_year(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 2000 or value > 2100:
            raise ValueError("expiry_year must be a 4-digit year")
        return value


class CardCreate(CardBase):
    statement_password: str | None = None


class CardUpdate(BaseModel):
    user_id: uuid.UUID | None = None
    bank_name: str | None = Field(default=None, max_length=100)
    card_holder_name: str | None = Field(default=None, max_length=255)
    card_type: CardType | None = None
    card_last4: str | None = Field(default=None, max_length=4)
    card_network: CardNetwork | None = None
    expiry_month: int | None = None
    expiry_year: int | None = None
    credit_limit: float | None = None
    current_balance: float | None = None
    available_balance: float | None = None
    pending_emi_amount: float | None = None
    emi_tenure_months: int | None = None
    emi_interest_rate: float | None = None
    monthly_emi_amount: float | None = None
    billing_cycle_date: int | None = None
    payment_due_date: int | None = None
    is_active: bool | None = None
    color_theme: str | None = Field(default=None, max_length=20)
    annual_fee: float | None = None
    joining_fee: float | None = None
    reward_points_balance: int | None = None
    reward_points_rate: str | None = Field(default=None, max_length=100)
    cashback_rate: str | None = Field(default=None, max_length=100)
    lounge_access: bool | None = None
    lounge_visits_per_quarter: int | None = None
    fuel_surcharge_waiver: bool | None = None
    credit_score_impact: int | None = None
    notes: str | None = None
    statement_password: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CardOut(CardBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None


class CardBenefitBase(BaseModel):
    benefit_category: BenefitCategory
    title: str = Field(max_length=200)
    description: str | None = None
    value: str | None = Field(default=None, max_length=100)
    conditions: str | None = None
    is_active: bool = True


class CardBenefitCreate(CardBenefitBase):
    pass


class CardBenefitUpdate(BaseModel):
    user_id: uuid.UUID | None = None
    benefit_category: BenefitCategory | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    value: str | None = Field(default=None, max_length=100)
    conditions: str | None = None
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class CardBenefitOut(CardBenefitBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    card_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# CardEmi schemas
# ---------------------------------------------------------------------------

class CardEmiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    card_id: uuid.UUID
    user_id: uuid.UUID
    loan_number: str | None = None
    loan_type: str | None = None
    loan_amount: float | None = None
    outstanding_amount: float | None = None
    monthly_instalment_amount: float | None = None
    balance_interest_payable: float | None = None
    loan_tenure_months: int | None = None
    pending_instalments: int | None = None
    balance_tenure: int | None = None
    interest_rate: float | None = None
    creation_date: datetime.date | None = None
    finish_date: datetime.date | None = None
    raw_snippet: str | None = None
    created_at: datetime.datetime
    last_updated_at: datetime.datetime
