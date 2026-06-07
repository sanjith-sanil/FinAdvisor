import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field


class EmailTestRequest(BaseModel):
    email_address: EmailStr
    password: str = Field(min_length=4)
    imap_server: str | None = None


class EmailSetupRequest(BaseModel):
    user_id: uuid.UUID
    email_address: EmailStr
    password: str = Field(min_length=4)
    imap_server: str | None = None


class EmailConfigStatusOut(BaseModel):
    configured: bool
    auth_type: str | None = None
    email_masked: str | None = None
    last_checked: datetime.datetime | None = None
    last_error: str | None = None
    total_processed: int
    total_transactions: int
    is_active: bool
    whitelisted_domains_count: int = 0
    last_scan_stats: dict = Field(default_factory=dict)
    recent_logs: list[dict]


class EmailIngestRequest(BaseModel):
    user_id: uuid.UUID
    sender_email: EmailStr
    subject: str
    email_body: str

