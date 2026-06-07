import datetime
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import SmsSourceType


class SmsEmailRaw(Base):
    __tablename__ = "sms_emails_raw"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[SmsSourceType] = mapped_column(SAEnum(SmsSourceType, name="sms_source_type"), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    sender: Mapped[str | None] = mapped_column(String(255))
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_code: Mapped[str | None] = mapped_column(String(20))
    subject: Mapped[str | None] = mapped_column(String(500))
    message_id: Mapped[str | None] = mapped_column(String(500), unique=True)
    received_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    is_processed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    parsed_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"))
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="sms_emails_raw")
    parsed_transaction = relationship("Transaction", back_populates="sms_email_raw")
