from __future__ import annotations

import datetime
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.card import Card
from app.models.chatbot import ChatbotMessage, ChatbotQuestionTemplate, ChatbotSession
from app.models.user import User
from app.schemas.chatbot import (
    ChatAskCardRequest,
    ChatAskRequest,
    ChatAskResponse,
    ChatClarifyRequest,
    ChatHistoryResponse,
    ChatMessageHistoryItem,
    ChatQuestion,
    ChatWelcomeResponse,
)
from app.services.chatbot_service import ChatbotService, _looks_like_spend_decision, _parse_amount_from_text

router = APIRouter(prefix="/api/v1/chatbot", tags=["chatbot"])

service = ChatbotService()


def _validate_user_context(x_user_id: str | None, expected_user_id: uuid.UUID) -> None:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing user context")
    try:
        request_user_id = uuid.UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid user context") from exc
    if request_user_id != expected_user_id:
        raise HTTPException(status_code=403, detail="User context mismatch")


def _first_name(full_name: str) -> str:
    parts = (full_name or "").strip().split()
    return parts[0] if parts else "there"


def _card_label(card: Card) -> str:
    card_type = str(card.card_type).split(".")[-1].title() if card.card_type else "Card"
    return f"{card.bank_name} {card_type}"


def _match_card_query_type(text: str) -> str | None:
    value = (text or "").lower()
    if any(token in value for token in ["available", "spend", "limit", "credit limit", "limit left"]):
        return "card_available_balance"
    if any(token in value for token in ["outstanding", "owed", "dues", "balance"]):
        return "card_outstanding"
    if "utilization" in value:
        return "card_utilization"
    if any(token in value for token in ["minimum", "min pay", "min payment"]):
        return "minimum_payment_due"
    if any(token in value for token in ["due date", "payment due", "when is the payment due", "bill due"]):
        return "card_due_date"
    if "days" in value and "due" in value:
        return "days_until_due"
    if any(token in value for token in ["emi remaining", "pending emi", "emi left", "emi pending"]):
        return "card_emi_remaining"
    if any(token in value for token in ["emi months", "months left", "emi tenure"]):
        return "emi_months_remaining"
    if any(token in value for token in ["spent this month", "this month", "monthly spend"]):
        return "card_monthly_spending"
    return None


async def _get_or_create_session(user_id: uuid.UUID, db: AsyncSession) -> ChatbotSession:
    stmt = select(ChatbotSession).where(ChatbotSession.user_id == user_id).order_by(desc(ChatbotSession.last_active))
    session = (await db.execute(stmt)).scalars().first()
    if session:
        return session

    session = ChatbotSession(
        user_id=user_id,
        last_active=datetime.datetime.now(datetime.timezone.utc),
        message_count=0,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _save_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    message_text: str,
    matched_template_id: uuid.UUID | None = None,
    resolved_question: str | None = None,
    data_used: dict | None = None,
) -> ChatbotMessage:
    message = ChatbotMessage(
        session_id=session_id,
        user_id=user_id,
        role=role,
        message_text=message_text,
        matched_template_id=matched_template_id,
        resolved_question=resolved_question,
        data_used=data_used,
    )
    db.add(message)
    await db.flush()
    return message


def _variety_questions(questions: list[dict], limit: int = 6) -> list[dict]:
    selected = []
    seen_categories = set()
    for question in questions:
        if question["category"] in seen_categories:
            continue
        selected.append(question)
        seen_categories.add(question["category"])
        if len(selected) >= limit:
            return selected

    if len(selected) < limit:
        seen_text = {item["resolved_question"] for item in selected}
        for question in questions:
            if question["resolved_question"] in seen_text:
                continue
            selected.append(question)
            seen_text.add(question["resolved_question"])
            if len(selected) >= limit:
                break

    return selected[:limit]


@router.get("/welcome/{user_id}", response_model=ChatWelcomeResponse)
async def chatbot_welcome(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> ChatWelcomeResponse:
    _validate_user_context(x_user_id, user_id)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session = await _get_or_create_session(user_id, db)
    welcome_message = (
        f"Hi {_first_name(user.full_name)}! I am your FinAdvisor assistant. "
        "I can answer questions about your cards, spending, balances, and EMIs using your real financial data. "
        "What would you like to know?"
    )

    questions = await service.get_dynamic_questions(user_id, db)
    varied = _variety_questions(questions, limit=6)

    return ChatWelcomeResponse(
        session_id=str(session.id),
        welcome_message=welcome_message,
        suggested_questions=[ChatQuestion(**{k: q[k] for k in ChatQuestion.model_fields.keys()}) for q in varied],
    )


@router.post("/ask", response_model=ChatAskResponse)
async def chatbot_ask(
    payload: ChatAskRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> ChatAskResponse:
    _validate_user_context(x_user_id, payload.user_id)
    session = await db.get(ChatbotSession, payload.session_id)
    if not session or session.user_id != payload.user_id:
        raise HTTPException(status_code=404, detail="Chat session not found")

    template: ChatbotQuestionTemplate | None = None
    resolved_question = payload.resolved_question
    data_query_type = payload.data_query_type
    entity_value = payload.entity_value

    if payload.question_type == "typed":
        if not payload.typed_text:
            raise HTTPException(status_code=400, detail="typed_text is required for typed questions")
        matched = await service.match_typed_question(payload.typed_text, payload.user_id, db)
        await _save_message(
            db,
            session.id,
            payload.user_id,
            "user",
            payload.typed_text,
            resolved_question=payload.typed_text,
        )

        if matched and matched.get("no_match"):
            fallback = await service.answer_from_online(payload.typed_text, payload.user_id, db)
            bot_message = await _save_message(
                db,
                session.id,
                payload.user_id,
                "bot",
                fallback["answer_text"],
                data_used=fallback.get("data"),
            )
            session.last_active = datetime.datetime.now(datetime.timezone.utc)
            session.message_count += 2
            await db.commit()
            return ChatAskResponse(
                answer=fallback["answer_text"],
                data=fallback.get("data", {}),
                suggested_questions=[
                    ChatQuestion(**{k: q[k] for k in ChatQuestion.model_fields.keys()})
                    for q in matched["suggested_questions"]
                ],
                message_id=str(bot_message.id),
            )

        if matched and matched.get("needs_clarification"):
            bot_message = await _save_message(
                db,
                session.id,
                payload.user_id,
                "bot",
                matched["message"],
                matched_template_id=uuid.UUID(matched["template_id"]),
                data_used={"clarification_options": matched["clarification_options"]},
            )
            session.last_active = datetime.datetime.now(datetime.timezone.utc)
            session.message_count += 2
            await db.commit()
            return ChatAskResponse(
                needs_clarification=True,
                message=matched["message"],
                clarification_options=matched["clarification_options"],
                template_id=matched["template_id"],
                message_id=str(bot_message.id),
            )

        if not matched:
            raise HTTPException(status_code=400, detail="Unable to match question")

        resolved_question = matched["resolved_question"]
        data_query_type = matched["data_query_type"]
        entity_value = matched.get("entity_value")
        template_id = matched.get("template_id")
        template = await db.get(ChatbotQuestionTemplate, uuid.UUID(template_id)) if template_id else None

    elif payload.question_type == "suggested":
        if not payload.template_id or not payload.data_query_type or not payload.resolved_question:
            raise HTTPException(status_code=400, detail="template_id, data_query_type, and resolved_question are required")
        template = await db.get(ChatbotQuestionTemplate, payload.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Question template not found")

        await _save_message(
            db,
            session.id,
            payload.user_id,
            "user",
            payload.resolved_question,
            matched_template_id=template.id,
            resolved_question=payload.resolved_question,
            data_used={"entity_value": payload.entity_value},
        )
    else:
        raise HTTPException(status_code=400, detail="question_type must be 'typed' or 'suggested'")

    result = await service.resolve_answer(payload.user_id, str(data_query_type), entity_value, db)

    bot_message = await _save_message(
        db,
        session.id,
        payload.user_id,
        "bot",
        result["answer_text"],
        matched_template_id=template.id if template else None,
        resolved_question=resolved_question,
        data_used=result.get("data"),
    )

    session.last_active = datetime.datetime.now(datetime.timezone.utc)
    session.message_count += 2
    await db.commit()

    follow_ups = await service.get_follow_up_questions(payload.user_id, template, db, limit=4)

    return ChatAskResponse(
        answer=result["answer_text"],
        data=result.get("data", {}),
        follow_up_questions=[ChatQuestion(**{k: q[k] for k in ChatQuestion.model_fields.keys()}) for q in follow_ups],
        message_id=str(bot_message.id),
    )


@router.post("/ask-card", response_model=ChatAskResponse)
async def chatbot_ask_card(
    payload: ChatAskCardRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> ChatAskResponse:
    _validate_user_context(x_user_id, payload.user_id)
    session = await db.get(ChatbotSession, payload.session_id)
    if not session or session.user_id != payload.user_id:
        raise HTTPException(status_code=404, detail="Chat session not found")

    card = await db.get(Card, payload.card_id)
    if not card or card.user_id != payload.user_id:
        raise HTTPException(status_code=404, detail="Card not found")

    if _looks_like_spend_decision(payload.typed_text):
        amount = _parse_amount_from_text(payload.typed_text)
        if amount:
            result = service._card_spend_decision(card, amount)
            bot_message = await _save_message(
                db,
                session.id,
                payload.user_id,
                "bot",
                result["answer_text"],
                resolved_question=payload.typed_text,
                data_used=result.get("data"),
            )
            session.last_active = datetime.datetime.now(datetime.timezone.utc)
            session.message_count += 2
            await db.commit()
            return ChatAskResponse(
                answer=result["answer_text"],
                data=result.get("data", {}),
                message_id=str(bot_message.id),
            )

    query_type = _match_card_query_type(payload.typed_text)
    if query_type:
        entity_value = _card_label(card)
        result = await service.resolve_answer(payload.user_id, query_type, entity_value, db)
        bot_message = await _save_message(
            db,
            session.id,
            payload.user_id,
            "bot",
            result["answer_text"],
            resolved_question=payload.typed_text,
            data_used=result.get("data"),
        )
        session.last_active = datetime.datetime.now(datetime.timezone.utc)
        session.message_count += 2
        await db.commit()
        return ChatAskResponse(
            answer=result["answer_text"],
            data=result.get("data", {}),
            message_id=str(bot_message.id),
        )

    enriched_text = f"{payload.typed_text} for {_card_label(card)} card"
    matched = await service.match_typed_question(enriched_text, payload.user_id, db)

    await _save_message(
        db,
        session.id,
        payload.user_id,
        "user",
        payload.typed_text,
        resolved_question=payload.typed_text,
    )

    if matched and matched.get("no_match"):
        help_text = (
            "I can answer questions about this card's balance, credit limit, utilization, due date, "
            "minimum payment, EMI, and monthly spending. Try one of the suggestions above."
        )
        bot_message = await _save_message(
            db,
            session.id,
            payload.user_id,
            "bot",
            help_text,
            resolved_question=payload.typed_text,
            data_used={"source": "card_assistant"},
        )
        session.last_active = datetime.datetime.now(datetime.timezone.utc)
        session.message_count += 2
        await db.commit()
        return ChatAskResponse(
            no_match=True,
            message=help_text,
            suggested_questions=[
                ChatQuestion(**{k: q[k] for k in ChatQuestion.model_fields.keys()})
                for q in matched["suggested_questions"]
            ],
            message_id=str(bot_message.id),
        )

    if matched and matched.get("needs_clarification"):
        template = await db.get(ChatbotQuestionTemplate, uuid.UUID(matched["template_id"]))
        if not template:
            raise HTTPException(status_code=404, detail="Question template not found")
        entity_value = _card_label(card)
        resolved_question = template.template_text.replace("{card_name}", entity_value)
        result = await service.resolve_answer(payload.user_id, template.data_query_type, entity_value, db)

        bot_message = await _save_message(
            db,
            session.id,
            payload.user_id,
            "bot",
            result["answer_text"],
            matched_template_id=template.id,
            resolved_question=resolved_question,
            data_used=result.get("data"),
        )
        session.last_active = datetime.datetime.now(datetime.timezone.utc)
        session.message_count += 2
        await db.commit()

        follow_ups = await service.get_follow_up_questions(payload.user_id, template, db, limit=4)
        return ChatAskResponse(
            answer=result["answer_text"],
            data=result.get("data", {}),
            follow_up_questions=[ChatQuestion(**{k: q[k] for k in ChatQuestion.model_fields.keys()}) for q in follow_ups],
            message_id=str(bot_message.id),
        )

    if not matched:
        raise HTTPException(status_code=400, detail="Unable to match question")

    resolved_question = matched["resolved_question"]
    data_query_type = matched["data_query_type"]
    entity_value = matched.get("entity_value") or _card_label(card)
    template_id = matched.get("template_id")
    template = await db.get(ChatbotQuestionTemplate, uuid.UUID(template_id)) if template_id else None

    result = await service.resolve_answer(payload.user_id, str(data_query_type), entity_value, db)
    bot_message = await _save_message(
        db,
        session.id,
        payload.user_id,
        "bot",
        result["answer_text"],
        matched_template_id=template.id if template else None,
        resolved_question=resolved_question,
        data_used=result.get("data"),
    )

    session.last_active = datetime.datetime.now(datetime.timezone.utc)
    session.message_count += 2
    await db.commit()

    follow_ups = await service.get_follow_up_questions(payload.user_id, template, db, limit=4)
    return ChatAskResponse(
        answer=result["answer_text"],
        data=result.get("data", {}),
        follow_up_questions=[ChatQuestion(**{k: q[k] for k in ChatQuestion.model_fields.keys()}) for q in follow_ups],
        message_id=str(bot_message.id),
    )


@router.post("/clarify", response_model=ChatAskResponse)
async def chatbot_clarify(
    payload: ChatClarifyRequest,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> ChatAskResponse:
    _validate_user_context(x_user_id, payload.user_id)
    session = await db.get(ChatbotSession, payload.session_id)
    if not session or session.user_id != payload.user_id:
        raise HTTPException(status_code=404, detail="Chat session not found")

    template = await db.get(ChatbotQuestionTemplate, payload.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Question template not found")

    resolved_question = (
        template.template_text.replace("{card_name}", payload.entity_value)
        .replace("{bank_name}", payload.entity_value)
        .replace("{category}", payload.entity_value)
    )

    await _save_message(
        db,
        session.id,
        payload.user_id,
        "user",
        payload.entity_value,
        matched_template_id=template.id,
        resolved_question=resolved_question,
        data_used={"entity_value": payload.entity_value},
    )

    result = await service.resolve_answer(payload.user_id, template.data_query_type, payload.entity_value, db)
    bot_message = await _save_message(
        db,
        session.id,
        payload.user_id,
        "bot",
        result["answer_text"],
        matched_template_id=template.id,
        resolved_question=resolved_question,
        data_used=result.get("data"),
    )

    session.last_active = datetime.datetime.now(datetime.timezone.utc)
    session.message_count += 2
    await db.commit()

    follow_ups = await service.get_follow_up_questions(payload.user_id, template, db, limit=4)
    return ChatAskResponse(
        answer=result["answer_text"],
        data=result.get("data", {}),
        follow_up_questions=[ChatQuestion(**{k: q[k] for k in ChatQuestion.model_fields.keys()}) for q in follow_ups],
        message_id=str(bot_message.id),
    )


@router.get("/questions/{user_id}")
async def chatbot_questions(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> dict:
    _validate_user_context(x_user_id, user_id)
    questions = await service.get_dynamic_questions(user_id, db)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for question in questions:
        grouped[question["category"]].append(
            {
                "template_id": question["template_id"],
                "resolved_question": question["resolved_question"],
                "category": question["category"],
                "data_query_type": question["data_query_type"],
                "entity_value": question["entity_value"],
            }
        )

    for key in ["balance", "spending", "cards", "emi", "transactions", "health", "budget"]:
        grouped.setdefault(key, [])

    return grouped


@router.get("/history/{user_id}", response_model=ChatHistoryResponse)
async def chatbot_history(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> ChatHistoryResponse:
    _validate_user_context(x_user_id, user_id)
    session = (
        (await db.execute(select(ChatbotSession).where(ChatbotSession.user_id == user_id).order_by(desc(ChatbotSession.last_active))))
        .scalars()
        .first()
    )
    if not session:
        return ChatHistoryResponse(messages=[])

    messages = (
        (
            await db.execute(
                select(ChatbotMessage)
                .where(ChatbotMessage.session_id == session.id)
                .order_by(desc(ChatbotMessage.created_at))
                .limit(20)
            )
        )
        .scalars()
        .all()
    )

    messages = list(reversed(messages))
    return ChatHistoryResponse(
        messages=[
            ChatMessageHistoryItem(
                role=message.role,
                text=message.message_text,
                timestamp=message.created_at,
                resolved_question=message.resolved_question,
            )
            for message in messages
        ]
    )
