import datetime
import uuid

from sqlalchemy import DECIMAL, Date, ForeignKey, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CardEmi(Base):
    """Stores individual active EMI / loan records for a credit card.

    Each row represents one EMI plan extracted from a bank statement email.
    A single card may have multiple concurrent EMIs (e.g. an EMI-on-call
    alongside a merchant EMI conversion).
    """

    __tablename__ = "card_emis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Identifiers ---
    loan_number: Mapped[str | None] = mapped_column(String(100))
    loan_type: Mapped[str | None] = mapped_column(String(200))

    # --- Amounts ---
    loan_amount: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    outstanding_amount: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    monthly_instalment_amount: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    balance_interest_payable: Mapped[float | None] = mapped_column(DECIMAL(15, 2))

    # --- Tenure ---
    loan_tenure_months: Mapped[int | None] = mapped_column(Integer)
    pending_instalments: Mapped[int | None] = mapped_column(Integer)
    balance_tenure: Mapped[int | None] = mapped_column(Integer)

    # --- Rate ---
    interest_rate: Mapped[float | None] = mapped_column(DECIMAL(8, 4))

    # --- Dates ---
    creation_date: Mapped[datetime.date | None] = mapped_column(Date)
    finish_date: Mapped[datetime.date | None] = mapped_column(Date)

    # --- Traceability ---
    source_raw_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sms_emails_raw.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_snippet: Mapped[str | None] = mapped_column(Text)

    # --- Timestamps ---
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    last_updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- Relationships ---
    card = relationship("Card", back_populates="emis")
    user = relationship("User", back_populates="card_emis")
