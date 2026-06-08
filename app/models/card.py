import datetime
import uuid

from sqlalchemy import Boolean, DECIMAL, ForeignKey, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import BenefitCategory, CardNetwork, CardType


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    card_holder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    card_type: Mapped[CardType] = mapped_column(SAEnum(CardType, name="card_type"), nullable=False)
    card_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    card_network: Mapped[CardNetwork | None] = mapped_column(SAEnum(CardNetwork, name="card_network"))
    expiry_month: Mapped[int | None] = mapped_column(Integer)
    expiry_year: Mapped[int | None] = mapped_column(Integer)
    credit_limit: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    current_balance: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    available_balance: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    pending_emi_amount: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    emi_tenure_months: Mapped[int | None] = mapped_column(Integer)
    emi_interest_rate: Mapped[float | None] = mapped_column(DECIMAL(5, 2))
    monthly_emi_amount: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    billing_cycle_date: Mapped[int | None] = mapped_column(Integer)
    payment_due_date: Mapped[int | None] = mapped_column(Integer)
    annual_fee: Mapped[float] = mapped_column(DECIMAL(10, 2), server_default="0", nullable=False)
    joining_fee: Mapped[float] = mapped_column(DECIMAL(10, 2), server_default="0", nullable=False)
    reward_points_balance: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    reward_points_rate: Mapped[str | None] = mapped_column(String(100))
    cashback_rate: Mapped[str | None] = mapped_column(String(100))
    lounge_access: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    lounge_visits_per_quarter: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    fuel_surcharge_waiver: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    credit_score_impact: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    statement_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    color_theme: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    user = relationship("User", back_populates="cards")
    transactions = relationship("Transaction", back_populates="card")
    benefits = relationship("CardBenefit", back_populates="card", cascade="all, delete-orphan")
    emis = relationship("CardEmi", back_populates="card", cascade="all, delete-orphan")


class CardBenefit(Base):
    __tablename__ = "card_benefits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    benefit_category: Mapped[BenefitCategory] = mapped_column(
        SAEnum(BenefitCategory, name="benefit_category", native_enum=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    value: Mapped[str | None] = mapped_column(String(100))
    conditions: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    card = relationship("Card", back_populates="benefits")
    user = relationship("User", back_populates="card_benefits")
