import datetime
import uuid

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class BudgetGoalCreate(BaseModel):
    user_id: uuid.UUID
    category: str | None = Field(default=None, max_length=100)
    monthly_limit: float | None = None
    current_spent: float | None = None
    month: int | None = None
    year: int | None = None


class BudgetGoalOut(BudgetGoalCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
