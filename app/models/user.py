import datetime
import uuid

from sqlalchemy import Boolean, Date, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    phone_number: Mapped[str | None] = mapped_column(String(15))
    sms_webhook_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    sms_configured: Mapped[bool] = mapped_column(Boolean, server_default="false")
    email_collection_configured: Mapped[bool] = mapped_column(Boolean, server_default="false")
    registration_step: Mapped[int] = mapped_column(Integer, server_default="1")
    date_of_birth: Mapped[Date | None] = mapped_column(Date)
    address: Mapped[str | None] = mapped_column(Text)
    profile_picture_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    bank_accounts = relationship("BankAccount", back_populates="user", cascade="all, delete")
    cards = relationship("Card", back_populates="user", cascade="all, delete")
    card_benefits = relationship("CardBenefit", back_populates="user", cascade="all, delete")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete")
    sms_emails_raw = relationship("SmsEmailRaw", back_populates="user", cascade="all, delete")
    pdf_uploads = relationship("PdfUpload", back_populates="user", cascade="all, delete")
    budget_goals = relationship("BudgetGoal", back_populates="user", cascade="all, delete")
    email_configs = relationship("EmailConfig", back_populates="user", cascade="all, delete")
    collection_logs = relationship("CollectionLog", back_populates="user", cascade="all, delete")
    chatbot_sessions = relationship("ChatbotSession", back_populates="user", cascade="all, delete")
    chatbot_messages = relationship("ChatbotMessage", back_populates="user", cascade="all, delete")
    card_emis = relationship("CardEmi", back_populates="user", cascade="all, delete")

