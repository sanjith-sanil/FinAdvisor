import datetime
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import EmailAuthType


class EmailConfig(Base):
    __tablename__ = "email_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_type: Mapped[EmailAuthType] = mapped_column(SAEnum(EmailAuthType, name="email_auth_type"), nullable=False)

    password_encrypted: Mapped[str | None] = mapped_column(Text)
    imap_server: Mapped[str | None] = mapped_column(String(255))
    imap_port: Mapped[int] = mapped_column(Integer, server_default="993")

    oauth_refresh_token_encrypted: Mapped[str | None] = mapped_column(Text)
    oauth_access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    oauth_token_expiry: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    last_checked: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    first_sync_done: Mapped[bool] = mapped_column(Boolean, server_default="false")
    total_emails_scanned: Mapped[int] = mapped_column(Integer, server_default="0")
    sync_status: Mapped[str] = mapped_column(String(50), server_default="idle")
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    emails_processed_total: Mapped[int] = mapped_column(Integer, server_default="0")
    transactions_found_total: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="email_configs")
