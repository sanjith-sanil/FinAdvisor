import datetime
import uuid

from sqlalchemy import DECIMAL, ForeignKey, String, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import AccountType


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_number_last4: Mapped[str | None] = mapped_column(String(4))
    account_type: Mapped[AccountType | None] = mapped_column(SAEnum(AccountType, name="account_type"))
    current_balance: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    last_updated: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="bank_accounts")
    transactions = relationship("Transaction", back_populates="bank_account")
