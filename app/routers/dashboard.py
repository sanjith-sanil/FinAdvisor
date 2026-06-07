import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.card import Card
from app.services.calculation_service import (
    ManualInputs,
    dashboard_summary,
    emi_analysis,
    manual_calculate,
    spending_analytics,
    spending_breakdown,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _resolve_user_id(query_user_id: uuid.UUID | None, body_user_id: uuid.UUID | None = None) -> uuid.UUID:
    user_id = query_user_id or body_user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if query_user_id and body_user_id and query_user_id != body_user_id:
        raise HTTPException(status_code=400, detail="user_id mismatch between query and body")
    return user_id


@router.get("/summary")
async def get_summary(
    user_id: uuid.UUID | None = Query(default=None),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    resolved_user_id = _resolve_user_id(user_id, payload.get("user_id") if payload else None)
    return await dashboard_summary(db, resolved_user_id)


@router.get("/spending-breakdown")
async def spending_breakdown_endpoint(
    user_id: uuid.UUID | None = Query(default=None),
    payload: dict | None = Body(default=None),
    period: str = "monthly",
    db: AsyncSession = Depends(get_db),
) -> dict:
    resolved_user_id = _resolve_user_id(user_id, payload.get("user_id") if payload else None)
    return await spending_breakdown(db, resolved_user_id, period)


@router.get("/card-metrics/{card_id}")
async def card_metrics(card_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    limit_val = float(card.credit_limit or 0)
    balance = float(card.current_balance or 0)
    utilization = (balance / limit_val) * 100 if limit_val > 0 else 0
    min_payment = max(500, balance * 0.05) if balance > 0 else 0
    annual_rate = float(card.emi_interest_rate or 0)
    interest_if_min = (balance - min_payment) * (annual_rate / 12 / 100) if balance > 0 else 0
    return {
        "card_id": str(card.id),
        "bank_name": card.bank_name,
        "current_balance": balance,
        "credit_limit": limit_val,
        "credit_utilization_ratio": utilization,
        "available_credit": limit_val - balance,
        "minimum_payment_due": min_payment,
        "interest_if_minimum_paid": interest_if_min,
        "interest_if_full_paid": 0,
    }


@router.get("/emi-analysis")
async def emi_metrics(
    user_id: uuid.UUID | None = Query(default=None),
    payload: dict | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    resolved_user_id = _resolve_user_id(user_id, payload.get("user_id") if payload else None)
    return await emi_analysis(db, resolved_user_id)


@router.post("/manual-calculate")
async def manual_calc(payload: ManualInputs) -> dict:
    return manual_calculate(payload)
