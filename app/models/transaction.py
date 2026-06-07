import datetime
import uuid

from sqlalchemy import DECIMAL, ForeignKey, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import TransactionSource, TransactionType


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    card_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cards.id"))
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"))
    transaction_type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType, name="transaction_type"), nullable=False)
    amount: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(255))
    merchant_category: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    transaction_date: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    balance_after: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    reference_number: Mapped[str | None] = mapped_column(String(100))
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_code: Mapped[str | None] = mapped_column(String(20))
    sender_email: Mapped[str | None] = mapped_column(String(255))
    sender_phone: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[TransactionSource] = mapped_column(SAEnum(TransactionSource, name="transaction_source"), nullable=False)
    raw_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="transactions")
    card = relationship("Card", back_populates="transactions")
    bank_account = relationship("BankAccount", back_populates="transactions")
    sms_email_raw = relationship("SmsEmailRaw", back_populates="parsed_transaction", uselist=False)
