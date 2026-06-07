import datetime
import uuid

from sqlalchemy import Date, ForeignKey, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import PdfStatus


class PdfUpload(Base):
    __tablename__ = "pdf_uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    upload_date: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    bank_name: Mapped[str | None] = mapped_column(String(100))
    statement_period_from: Mapped[Date | None] = mapped_column(Date)
    statement_period_to: Mapped[Date | None] = mapped_column(Date)
    total_transactions_parsed: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[PdfStatus | None] = mapped_column(SAEnum(PdfStatus, name="pdf_status"))

    user = relationship("User", back_populates="pdf_uploads")
