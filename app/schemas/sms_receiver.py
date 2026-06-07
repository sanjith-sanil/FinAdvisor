import datetime
import uuid

from pydantic import BaseModel, Field


class SmsReceiveRequest(BaseModel):
    user_id: uuid.UUID
    phone_number: str | None = Field(default=None, max_length=50)
    message: str = Field(min_length=1)
    received_at: datetime.datetime | None = None
