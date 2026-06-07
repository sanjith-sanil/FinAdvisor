from pydantic import BaseModel


class NotificationEvent(BaseModel):
    type: str
    merchant: str | None = None
    amount: float | None = None
    source: str | None = None
    timestamp: str | None = None
