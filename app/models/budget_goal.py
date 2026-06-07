import datetime
import uuid

from sqlalchemy import DECIMAL, ForeignKey, Integer, String, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BudgetGoal(Base):
    __tablename__ = "budget_goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    monthly_limit: Mapped[float | None] = mapped_column(DECIMAL(15, 2))
    current_spent: Mapped[float | None] = mapped_column(DECIMAL(15, 2), server_default="0")
    month: Mapped[int | None] = mapped_column(Integer)
    year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="budget_goals")
