import datetime
import uuid
from typing import Any

from pydantic import BaseModel


class ChatQuestion(BaseModel):
    template_id: str
    resolved_question: str
    category: str
    data_query_type: str
    entity_value: str | None = None


class ChatWelcomeResponse(BaseModel):
    session_id: str
    welcome_message: str
    suggested_questions: list[ChatQuestion]


class ChatAskRequest(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    question_type: str
    template_id: uuid.UUID | None = None
    entity_value: str | None = None
    data_query_type: str | None = None
    resolved_question: str | None = None
    typed_text: str | None = None


class ChatAskCardRequest(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    card_id: uuid.UUID
    typed_text: str


class ChatClarifyRequest(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    template_id: uuid.UUID
    entity_value: str


class ChatMessageHistoryItem(BaseModel):
    role: str
    text: str
    timestamp: datetime.datetime
    resolved_question: str | None = None


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageHistoryItem]


class ChatAskResponse(BaseModel):
    answer: str | None = None
    data: dict[str, Any] | None = None
    follow_up_questions: list[ChatQuestion] | None = None
    message_id: str | None = None
    no_match: bool | None = None
    needs_clarification: bool | None = None
    message: str | None = None
    clarification_options: list[str] | None = None
    template_id: str | None = None
    suggested_questions: list[ChatQuestion] | None = None
