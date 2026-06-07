import datetime
import uuid

from sqlalchemy import ForeignKey, Integer, String, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import CollectionLogType, CollectionSource


class CollectionLog(Base):
    __tablename__ = "collection_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    log_type: Mapped[CollectionLogType] = mapped_column(SAEnum(CollectionLogType, name="collection_log_type"), nullable=False)
    source: Mapped[CollectionSource] = mapped_column(SAEnum(CollectionSource, name="collection_source"), nullable=False)
    emails_checked: Mapped[int] = mapped_column(Integer, server_default="0")
    transactions_found: Mapped[int] = mapped_column(Integer, server_default="0")
    non_bank_emails_rejected: Mapped[int] = mapped_column(Integer, server_default="0")
    bank_emails_found: Mapped[int] = mapped_column(Integer, server_default="0")
    duplicates_skipped: Mapped[int] = mapped_column(Integer, server_default="0")
    error_message: Mapped[str | None] = mapped_column(String(500))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="collection_logs")
