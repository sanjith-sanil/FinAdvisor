import datetime
import uuid

from pydantic import BaseModel
from pydantic import ConfigDict

from app.models.enums import PdfStatus


class PdfUploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    file_path: str
    upload_date: datetime.datetime
    bank_name: str | None = None
    statement_period_from: datetime.date | None = None
    statement_period_to: datetime.date | None = None
    total_transactions_parsed: int
    status: PdfStatus | None = None
