import datetime
import calendar
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.card import Card, CardBenefit
from app.models.card_emi import CardEmi
from app.models.email_config import EmailConfig
from app.models.enums import EmailAuthType, SmsSourceType, TransactionType
from app.models.sms_email_raw import SmsEmailRaw
from app.models.transaction import Transaction
from app.schemas.card import (
    CardBenefitCreate,
    CardBenefitOut,
    CardBenefitUpdate,
    CardCreate,
    CardEmiOut,
    CardOut,
    CardUpdate,
)
from app.schemas.transaction import TransactionOut
from app.services.bank_benefits_seeder import seed_default_benefits_for_card
from app.services.calculation_service import (
    calculate_minimum_payment_due,
    days_until_due,
    generate_emi_schedule,
    safe_div,
    safe_float,
)
from app.services.emi_upsert_service import process_emi_from_email
from app.services.bank_domain_whitelist import get_bank_info

router = APIRouter(prefix="/api/v1/cards", tags=["cards"])


def _resolve_user_id(query_user_id: uuid.UUID | None, body_user_id: uuid.UUID | None) -> uuid.UUID:
    user_id = query_user_id or body_user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if query_user_id and body_user_id and query_user_id != body_user_id:
        raise HTTPException(status_code=400, detail="user_id mismatch between query and body")
    return user_id


async def _get_card_by_owner(db: AsyncSession, card_id: uuid.UUID, user_id: uuid.UUID) -> Card:
    stmt = select(Card).where(Card.id == card_id, Card.user_id == user_id)
    card = (await db.execute(stmt)).scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("/", response_model=list[CardOut])
async def list_cards(user_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)) -> list[CardOut]:
    stmt = select(Card).where(Card.user_id == user_id).order_by(desc(Card.created_at))
    return (await db.execute(stmt)).scalars().all()


@router.post("/", response_model=CardOut)
async def create_card(
    payload: CardCreate,
    user_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> CardOut:
    resolved_user_id = _resolve_user_id(user_id, payload.user_id)
    card_data = payload.model_dump()
    card_data["user_id"] = resolved_user_id

    card = Card(**card_data)
    db.add(card)
    await db.flush()

    await seed_default_benefits_for_card(db, card)

    await db.commit()
    await db.refresh(card)
    return card


@router.get("/{card_id}", response_model=CardOut)
async def get_card(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> CardOut:
    return await _get_card_by_owner(db, card_id, user_id)


@router.put("/{card_id}", response_model=CardOut)
async def update_card(
    card_id: uuid.UUID,
    payload: CardUpdate,
    user_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> CardOut:
    resolved_user_id = _resolve_user_id(user_id, payload.user_id)
    card = await _get_card_by_owner(db, card_id, resolved_user_id)

    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("user_id", None)

    for field, value in update_data.items():
        setattr(card, field, value)

    card.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await db.commit()
    await db.refresh(card)
    return card


@router.delete("/{card_id}")
async def deactivate_card(
    card_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(default=None),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    body_user_id = payload.get("user_id") if payload else None
    resolved_user_id = _resolve_user_id(user_id, body_user_id)
    card = await _get_card_by_owner(db, card_id, resolved_user_id)

    card.is_active = False
    card.updated_at = datetime.datetime.now(datetime.timezone.utc)

    await db.commit()
    return {
        "success": True,
        "message": "Card deactivated successfully",
        "card_id": str(card_id),
    }


@router.delete("/{card_id}/permanent")
async def permanent_delete_card(
    card_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(default=None),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    body_user_id = payload.get("user_id") if payload else None
    resolved_user_id = _resolve_user_id(user_id, body_user_id)
    card = await _get_card_by_owner(db, card_id, resolved_user_id)

    if card.is_active:
        raise HTTPException(status_code=400, detail="Deactivate card before permanent delete")

    await db.delete(card)
    await db.commit()
    return {"success": True, "message": "Card deleted permanently", "card_id": str(card_id)}


@router.get("/{card_id}/benefits", response_model=list[CardBenefitOut])
async def list_card_benefits(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[CardBenefitOut]:
    await _get_card_by_owner(db, card_id, user_id)

    stmt = (
        select(CardBenefit)
        .where(CardBenefit.card_id == card_id, CardBenefit.user_id == user_id, CardBenefit.is_active.is_(True))
        .order_by(desc(CardBenefit.created_at))
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/{card_id}/benefits", response_model=CardBenefitOut)
async def create_card_benefit(
    card_id: uuid.UUID,
    payload: CardBenefitCreate,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> CardBenefitOut:
    await _get_card_by_owner(db, card_id, user_id)

    benefit = CardBenefit(
        card_id=card_id,
        user_id=user_id,
        **payload.model_dump(),
    )
    db.add(benefit)
    await db.commit()
    await db.refresh(benefit)
    return benefit


@router.put("/{card_id}/benefits/{benefit_id}", response_model=CardBenefitOut)
async def update_card_benefit(
    card_id: uuid.UUID,
    benefit_id: uuid.UUID,
    payload: CardBenefitUpdate,
    user_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> CardBenefitOut:
    resolved_user_id = _resolve_user_id(user_id, payload.user_id)
    await _get_card_by_owner(db, card_id, resolved_user_id)

    stmt = select(CardBenefit).where(
        CardBenefit.id == benefit_id,
        CardBenefit.card_id == card_id,
        CardBenefit.user_id == resolved_user_id,
    )
    benefit = (await db.execute(stmt)).scalar_one_or_none()
    if not benefit:
        raise HTTPException(status_code=404, detail="Benefit not found")

    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("user_id", None)
    for field, value in update_data.items():
        setattr(benefit, field, value)

    await db.commit()
    await db.refresh(benefit)
    return benefit


@router.delete("/{card_id}/benefits/{benefit_id}")
async def delete_card_benefit(
    card_id: uuid.UUID,
    benefit_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_card_by_owner(db, card_id, user_id)

    stmt = select(CardBenefit).where(
        CardBenefit.id == benefit_id,
        CardBenefit.card_id == card_id,
        CardBenefit.user_id == user_id,
    )
    benefit = (await db.execute(stmt)).scalar_one_or_none()
    if not benefit:
        raise HTTPException(status_code=404, detail="Benefit not found")

    await db.delete(benefit)
    await db.commit()
    return {"success": True, "message": "Benefit removed"}


@router.get("/{card_id}/details")
async def get_card_details(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    card = await _get_card_by_owner(db, card_id, user_id)

    benefits_stmt = (
        select(CardBenefit)
        .where(CardBenefit.card_id == card_id, CardBenefit.user_id == user_id)
        .order_by(desc(CardBenefit.created_at))
    )
    benefits = (await db.execute(benefits_stmt)).scalars().all()

    limit_val = safe_float(card.credit_limit)
    current_balance = safe_float(card.current_balance)
    utilization_percentage = round(safe_div(current_balance * 100, limit_val), 2)
    minimum_payment_due = calculate_minimum_payment_due(current_balance)

    emi_principal = safe_float(card.pending_emi_amount)
    emi_tenure = int(safe_float(card.emi_tenure_months, 0))
    emi_rate = safe_float(card.emi_interest_rate)
    monthly_emi = safe_float(card.monthly_emi_amount)
    emi_schedule = generate_emi_schedule(emi_principal, emi_rate, emi_tenure, monthly_emi)

    total_emi_remaining = round(emi_principal, 2)
    total_interest_payable = round(sum(row["interest"] for row in emi_schedule), 2)

    txn_stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.card_id == card_id)
        .order_by(desc(Transaction.transaction_date))
        .limit(5)
    )
    recent_transactions = (await db.execute(txn_stmt)).scalars().all()

    today = datetime.date.today()
    start_month = datetime.datetime(today.year, today.month, 1, tzinfo=datetime.timezone.utc)
    end_month = start_month + datetime.timedelta(days=calendar.monthrange(today.year, today.month)[1])

    last_month = today.month - 1 or 12
    last_year = today.year if today.month > 1 else today.year - 1
    start_last_month = datetime.datetime(last_year, last_month, 1, tzinfo=datetime.timezone.utc)
    end_last_month = start_last_month + datetime.timedelta(days=calendar.monthrange(last_year, last_month)[1])

    spend_this_stmt = select(Transaction).where(
        and_(
            Transaction.user_id == user_id,
            Transaction.card_id == card_id,
            Transaction.transaction_type == TransactionType.debit,
            Transaction.transaction_date >= start_month,
            Transaction.transaction_date < end_month,
        )
    )
    spend_last_stmt = select(Transaction).where(
        and_(
            Transaction.user_id == user_id,
            Transaction.card_id == card_id,
            Transaction.transaction_type == TransactionType.debit,
            Transaction.transaction_date >= start_last_month,
            Transaction.transaction_date < end_last_month,
        )
    )

    this_month_txns = (await db.execute(spend_this_stmt)).scalars().all()
    last_month_txns = (await db.execute(spend_last_stmt)).scalars().all()

    spending_this_month = round(sum(safe_float(txn.amount) for txn in this_month_txns), 2)
    spending_last_month = round(sum(safe_float(txn.amount) for txn in last_month_txns), 2)

    return {
        "card": CardOut.model_validate(card).model_dump(),
        "benefits": [CardBenefitOut.model_validate(item).model_dump() for item in benefits],
        "utilization_percentage": utilization_percentage,
        "minimum_payment_due": round(minimum_payment_due, 2),
        "days_until_payment_due": days_until_due(card.payment_due_date),
        "total_emi_remaining": total_emi_remaining,
        "total_interest_payable": total_interest_payable,
        "emi_schedule": emi_schedule,
        "recent_transactions": [TransactionOut.model_validate(txn).model_dump() for txn in recent_transactions],
        "spending_this_month": spending_this_month,
        "spending_last_month": spending_last_month,
    }


@router.get("/{card_id}/transactions", response_model=list[TransactionOut])
async def card_transactions(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionOut]:
    await _get_card_by_owner(db, card_id, user_id)
    stmt = select(Transaction).where(Transaction.card_id == card_id, Transaction.user_id == user_id)
    return (await db.execute(stmt)).scalars().all()


# ---------------------------------------------------------------------------
# EMI endpoints
# ---------------------------------------------------------------------------

@router.get("/{card_id}/emis", response_model=list[CardEmiOut])
async def list_card_emis(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[CardEmiOut]:
    """Return all active EMI records for a card, latest first."""
    await _get_card_by_owner(db, card_id, user_id)
    stmt = (
        select(CardEmi)
        .where(CardEmi.card_id == card_id, CardEmi.user_id == user_id)
        .order_by(desc(CardEmi.last_updated_at))
    )
    return (await db.execute(stmt)).scalars().all()


@router.post("/{card_id}/emis/refresh")
async def refresh_card_emis(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-scan previously collected bank emails for EMI data for this card.

    Useful when a user adds a card after emails have already been collected,
    or when the EMI parser is improved and historical emails should be reprocessed.
    """
    card = await _get_card_by_owner(db, card_id, user_id)

    # Fetch all raw bank emails for this user
    stmt = (
        select(SmsEmailRaw)
        .where(
            SmsEmailRaw.user_id == user_id,
            SmsEmailRaw.source_type == SmsSourceType.email,
        )
        .order_by(desc(SmsEmailRaw.received_at))
    )
    raws = (await db.execute(stmt)).scalars().all()

    total_upserted = 0
    for raw in raws:
        combined = f"{raw.subject or ''} {raw.raw_content or ''}".strip()
        if not combined:
            continue
        bank_code = raw.bank_code or ""
        # Only process emails that match this card's bank
        if bank_code and bank_code.upper() not in card.bank_name.upper():
            continue
        try:
            count = await process_emi_from_email(
                db=db,
                user_id=user_id,
                bank_code=bank_code,
                email_body=raw.raw_content or "",
                email_subject=raw.subject or "",
                source_raw_id=raw.id,
            )
            total_upserted += count
        except Exception:
            pass  # Logged inside process_emi_from_email

    return {
        "success": True,
        "card_id": str(card_id),
        "emails_scanned": len(raws),
        "emi_records_upserted": total_upserted,
    }
