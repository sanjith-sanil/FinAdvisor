import datetime
import uuid

from pydantic import BaseModel

from app.models.enums import CollectionLogType, CollectionSource


class CollectionLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    log_type: CollectionLogType
    source: CollectionSource
    emails_checked: int
    transactions_found: int
    error_message: str | None
    duration_ms: int | None
    created_at: datetime.datetime
