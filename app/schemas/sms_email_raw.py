import datetime
import uuid

from pydantic import BaseModel, Field
from pydantic import ConfigDict

from app.models.enums import SmsSourceType


class SmsIngestRequest(BaseModel):
    raw_sms: str = Field(min_length=3)
    sender: str | None = None
    received_at: datetime.datetime | None = None


class SmsEmailRawOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source_type: SmsSourceType
    raw_content: str
    sender: str | None = None
    bank_name: str | None = None
    bank_code: str | None = None
    subject: str | None = None
    message_id: str | None = None
    received_at: datetime.datetime | None = None
    is_processed: bool
    parsed_transaction_id: uuid.UUID | None = None
    created_at: datetime.datetime
