import datetime
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, TIMESTAMP, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatRole(str):
    bot = "bot"
    user = "user"


class ChatbotQuestionTemplate(Base):
    __tablename__ = "chatbot_question_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    data_query_type: Mapped[str] = mapped_column(String(100), nullable=False)
    requires_placeholder: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    placeholder_source: Mapped[str] = mapped_column(String(50), server_default="none", nullable=False)
    placeholder_field: Mapped[str | None] = mapped_column(String(50))
    keywords: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    follow_up_categories: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    messages = relationship("ChatbotMessage", back_populates="matched_template")


class ChatbotSession(Base):
    __tablename__ = "chatbot_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    last_active: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    message_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)

    user = relationship("User", back_populates="chatbot_sessions")
    messages = relationship("ChatbotMessage", back_populates="session", cascade="all, delete")


class ChatbotMessage(Base):
    __tablename__ = "chatbot_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chatbot_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(SAEnum("bot", "user", name="chatbot_message_role"), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    matched_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chatbot_question_templates.id")
    )
    resolved_question: Mapped[str | None] = mapped_column(Text)
    data_used: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    session = relationship("ChatbotSession", back_populates="messages")
    user = relationship("User", back_populates="chatbot_messages")
    matched_template = relationship("ChatbotQuestionTemplate", back_populates="messages")
