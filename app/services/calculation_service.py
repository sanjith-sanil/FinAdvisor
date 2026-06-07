import calendar
import datetime
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.enums import CardType, TransactionType
from app.models.transaction import Transaction


class ManualInputs(BaseModel):
    monthly_income: float | None = None
    other_income: float | None = None
    monthly_expenses: float | None = None
    emi_total: float | None = None
    minimum_due: float | None = None
    savings_balance: float | None = None
    emergency_fund_months: float | None = None


def safe_float(value: float | int | Decimal | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: int | float | Decimal | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    if not b or b == 0:
        return default
    return a / b


def get_utilization_color(utilization_pct: float) -> str:
    if utilization_pct < 30:
        return "#10B981"
    if utilization_pct < 60:
        return "#F59E0B"
    return "#EF4444"


def calculate_minimum_payment_due(current_balance: float) -> float:
    if current_balance <= 0:
        return 0.0
    return round(max(500.0, current_balance * 0.05), 2)


def days_until_due(payment_due_date: int | None, now: datetime.datetime | None = None) -> int | None:
    if not payment_due_date:
        return None

    now = now or datetime.datetime.now(datetime.timezone.utc)
    year = now.year
    month = now.month

    last_day = calendar.monthrange(year, month)[1]
    due_day = min(payment_due_date, last_day)
    due_this_month = datetime.datetime(year, month, due_day, tzinfo=datetime.timezone.utc)

    if due_this_month.date() >= now.date():
        return (due_this_month.date() - now.date()).days

    next_month = 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year
    next_last_day = calendar.monthrange(next_year, next_month)[1]
    next_due_day = min(payment_due_date, next_last_day)
    due_next_month = datetime.datetime(next_year, next_month, next_due_day, tzinfo=datetime.timezone.utc)
    return (due_next_month.date() - now.date()).days


def emi_formula(principal: float, annual_rate: float, tenure_months: int) -> float:
    principal = max(principal, 0.0)
    tenure_months = max(tenure_months, 0)
    annual_rate = max(annual_rate, 0.0)

    if tenure_months <= 0:
        return 0.0

    monthly_rate = annual_rate / 12 / 100
    if monthly_rate == 0:
        return principal / tenure_months

    factor = (1 + monthly_rate) ** tenure_months
    numerator = principal * monthly_rate * factor
    denominator = factor - 1
    if denominator == 0:
        return 0.0
    return numerator / denominator


def generate_emi_schedule(principal: float, annual_rate: float, tenure_months: int, monthly_emi: float | None = None) -> list[dict]:
    principal = max(principal, 0.0)
    tenure_months = max(tenure_months, 0)
    annual_rate = max(annual_rate, 0.0)

    if principal <= 0 or tenure_months <= 0:
        return []

    emi_amount = monthly_emi if monthly_emi and monthly_emi > 0 else emi_formula(principal, annual_rate, tenure_months)
    monthly_rate = annual_rate / 12 / 100

    schedule: list[dict] = []
    balance = principal

    for month in range(1, tenure_months + 1):
        interest = balance * monthly_rate if monthly_rate > 0 else 0.0
        principal_component = max(0.0, emi_amount - interest)

        if principal_component > balance:
            principal_component = balance
        ending_balance = max(0.0, balance - principal_component)

        schedule.append(
            {
                "month": month,
                "emi_amount": round(emi_amount, 2),
                "principal": round(principal_component, 2),
                "interest": round(interest, 2),
                "balance_remaining": round(ending_balance, 2),
            }
        )
        balance = ending_balance
        if balance <= 0:
            break

    return schedule


async def _sum_transactions(session: AsyncSession, user_id, start: datetime.datetime, end: datetime.datetime, card_id=None) -> float:
    filters = [
        Transaction.user_id == user_id,
        Transaction.transaction_type == TransactionType.debit,
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    ]
    if card_id:
        filters.append(Transaction.card_id == card_id)

    stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(and_(*filters))
    return safe_float((await session.execute(stmt)).scalar_one())


async def spending_analytics(session: AsyncSession, user_id: str) -> dict:
    today = datetime.date.today()
    start_month = datetime.datetime(today.year, today.month, 1, tzinfo=datetime.timezone.utc)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    end_month = start_month + datetime.timedelta(days=days_in_month)

    last_month = today.month - 1 or 12
    last_year = today.year if today.month > 1 else today.year - 1
    start_last_month = datetime.datetime(last_year, last_month, 1, tzinfo=datetime.timezone.utc)
    days_last_month = calendar.monthrange(last_year, last_month)[1]
    end_last_month = start_last_month + datetime.timedelta(days=days_last_month)

    total_spent_this_month = await _sum_transactions(session, user_id, start_month, end_month)
    total_spent_last_month = await _sum_transactions(session, user_id, start_last_month, end_last_month)

    days_elapsed = max(today.day, 1)
    daily_average = safe_div(total_spent_this_month, days_elapsed)
    projected = daily_average * days_in_month

    mom_change = 0.0
    if total_spent_last_month > 0:
        mom_change = safe_div(total_spent_this_month - total_spent_last_month, total_spent_last_month) * 100

    category_stmt = (
        select(Transaction.merchant_category, func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.debit,
            Transaction.transaction_date >= start_month,
            Transaction.transaction_date < end_month,
        )
        .group_by(Transaction.merchant_category)
    )

    categories = (await session.execute(category_stmt)).all()
    category_breakdown = {name or "Other": safe_float(total) for name, total in categories}

    return {
        "total_spent_this_month": round(total_spent_this_month, 2),
        "total_spent_last_month": round(total_spent_last_month, 2),
        "month_over_month_change": round(mom_change, 2),
        "category_breakdown": category_breakdown,
        "daily_average_spend": round(daily_average, 2),
        "projected_monthly_spend": round(projected, 2),
    }


async def spending_breakdown(session: AsyncSession, user_id: str, period: str) -> dict:
    if period not in {"monthly", "weekly", "yearly"}:
        period = "monthly"

    trunc_unit = {"monthly": "month", "weekly": "week", "yearly": "year"}[period]
    stmt = (
        select(
            func.date_trunc(trunc_unit, Transaction.transaction_date).label("bucket"),
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .where(Transaction.user_id == user_id, Transaction.transaction_type == TransactionType.debit)
        .group_by("bucket")
        .order_by("bucket")
    )
    rows = (await session.execute(stmt)).all()

    series = []
    for bucket, total in rows:
        if bucket is None:
            continue
        series.append({"bucket": bucket.isoformat(), "total": round(safe_float(total), 2)})

    return {"period": period, "series": series}


async def credit_card_metrics(session: AsyncSession, user_id: str) -> dict:
    stmt = select(Card).where(Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True))
    cards = (await session.execute(stmt)).scalars().all()

    per_card: list[dict] = []
    total_limit = 0.0
    total_outstanding = 0.0
    total_minimum_due = 0.0

    for card in cards:
        limit_val = safe_float(card.credit_limit)
        balance = safe_float(card.current_balance)

        total_limit += limit_val
        total_outstanding += balance

        utilization = safe_div(balance * 100, limit_val, 0.0)
        min_payment = calculate_minimum_payment_due(balance)
        total_minimum_due += min_payment

        annual_rate = safe_float(card.emi_interest_rate)
        interest_if_min = (balance - min_payment) * (annual_rate / 12 / 100) if balance > 0 else 0.0

        per_card.append(
            {
                "card_id": str(card.id),
                "bank_name": card.bank_name,
                "current_balance": round(balance, 2),
                "credit_limit": round(limit_val, 2),
                "credit_utilization_ratio": round(utilization, 2),
                "available_credit": round(limit_val - balance, 2),
                "minimum_payment_due": round(min_payment, 2),
                "interest_if_minimum_paid": round(max(interest_if_min, 0.0), 2),
                "interest_if_full_paid": 0.0,
            }
        )

    return {
        "per_card": per_card,
        "total_credit_limit_all_cards": round(total_limit, 2),
        "total_outstanding_all_cards": round(total_outstanding, 2),
        "total_minimum_due_all_cards": round(total_minimum_due, 2),
    }


async def emi_analysis(session: AsyncSession, user_id: str, monthly_income: float | None = None) -> dict:
    stmt = select(Card).where(Card.user_id == user_id, Card.is_active.is_(True))
    cards = (await session.execute(stmt)).scalars().all()

    total_emi_outflow = 0.0
    total_interest_payable = 0.0

    for card in cards:
        principal = safe_float(card.pending_emi_amount)
        tenure = safe_int(card.emi_tenure_months)
        rate = safe_float(card.emi_interest_rate)
        monthly_emi = safe_float(card.monthly_emi_amount)

        if principal <= 0 or tenure <= 0:
            continue

        if monthly_emi <= 0:
            monthly_emi = emi_formula(principal, rate, tenure)

        total_emi_outflow += monthly_emi
        total_interest_payable += max(0.0, (monthly_emi * tenure) - principal)

    emi_to_income = None
    if monthly_income and monthly_income > 0:
        emi_to_income = safe_div(total_emi_outflow * 100, monthly_income)

    return {
        "total_emi_outflow": round(total_emi_outflow, 2),
        "total_interest_payable": round(total_interest_payable, 2),
        "emi_to_income_ratio": round(emi_to_income, 2) if emi_to_income is not None else None,
    }


def _financial_label(score: int, has_cards: bool) -> tuple[str, str]:
    if not has_cards:
        return ("No Data", "#64748B")
    if score >= 81:
        return ("Excellent", "#10B981")
    if score >= 61:
        return ("Good", "#3B82F6")
    if score >= 41:
        return ("Fair", "#F59E0B")
    if score >= 21:
        return ("Poor", "#EF4444")
    return ("Critical", "#DC2626")


def financial_health_score(cards: list[Card]) -> dict:
    if not cards:
        label, color = _financial_label(50, False)
        return {"score": 50, "score_label": label, "score_color": color}

    total_limit = sum(safe_float(card.credit_limit) for card in cards)
    total_outstanding = sum(safe_float(card.current_balance) for card in cards)
    total_emi = sum(safe_float(card.monthly_emi_amount) for card in cards)

    utilization = safe_div(total_outstanding * 100, total_limit)

    score = 50

    if utilization < 30:
        score += 15
    if utilization < 10:
        score += 10

    max_card_utilization = 0.0
    for card in cards:
        card_util = safe_div(safe_float(card.current_balance) * 100, safe_float(card.credit_limit))
        max_card_utilization = max(max_card_utilization, card_util)

    if max_card_utilization <= 80:
        score += 15

    no_overdue = all((days_until_due(card.payment_due_date) or 999) >= 0 for card in cards)
    if no_overdue:
        score += 10

    emi_to_limit_ratio = safe_div(total_emi * 100, total_limit)
    if emi_to_limit_ratio < 40:
        score += 10

    if max_card_utilization > 90:
        score -= 20
    elif max_card_utilization > 80:
        score -= 15
    elif max_card_utilization > 60:
        score -= 10

    min_due_days = min((days_until_due(card.payment_due_date) for card in cards if card.payment_due_date), default=None)
    if min_due_days is not None:
        if min_due_days <= 3:
            score -= 15
        elif min_due_days <= 7:
            score -= 5

    if emi_to_limit_ratio > 50:
        score -= 10

    score = max(0, min(100, int(round(score))))
    label, color = _financial_label(score, True)
    return {"score": score, "score_label": label, "score_color": color}


async def debt_payoff_projection(session: AsyncSession, user_id: str) -> dict:
    stmt = select(Card).where(Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True))
    cards = (await session.execute(stmt)).scalars().all()

    debts = []
    for card in cards:
        balance = safe_float(card.current_balance)
        rate = safe_float(card.emi_interest_rate)
        min_payment = calculate_minimum_payment_due(balance)
        debts.append(
            {
                "card_id": str(card.id),
                "balance": round(balance, 2),
                "interest_rate": round(rate, 2),
                "minimum_payment": round(min_payment, 2),
            }
        )

    avalanche = sorted(debts, key=lambda d: d["interest_rate"], reverse=True)
    snowball = sorted(debts, key=lambda d: d["balance"])

    total_balance = sum(d["balance"] for d in debts)
    total_min_payment = sum(d["minimum_payment"] for d in debts)
    months_to_free = int(safe_div(total_balance, total_min_payment, 0)) if total_balance > 0 else 0

    return {
        "avalanche_method": avalanche,
        "snowball_method": snowball,
        "months_to_debt_free": months_to_free,
        "total_interest_saved_avalanche_vs_minimum": 0.0,
    }


async def dashboard_summary(session: AsyncSession, user_id: str) -> dict:
    spending = await spending_analytics(session, user_id)
    credit_metrics = await credit_card_metrics(session, user_id)
    emi_metrics = await emi_analysis(session, user_id)

    cards_stmt = select(Card).where(Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True))
    cards = (await session.execute(cards_stmt)).scalars().all()

    score_meta = financial_health_score(cards)

    total_outstanding = safe_float(credit_metrics["total_outstanding_all_cards"])
    total_credit_limit = safe_float(credit_metrics["total_credit_limit_all_cards"])
    available_credit = max(0.0, total_credit_limit - total_outstanding)
    overall_utilization = safe_div(total_outstanding * 100, total_credit_limit)

    this_month_spending = safe_float(spending["total_spent_this_month"])
    last_month_spending = safe_float(spending["total_spent_last_month"])
    month_change_percentage = safe_div((this_month_spending - last_month_spending) * 100, last_month_spending)

    total_monthly_emi = safe_float(emi_metrics["total_emi_outflow"])
    cards_count = len(cards)

    alerts: list[dict] = []
    for card in cards:
        util = safe_div(safe_float(card.current_balance) * 100, safe_float(card.credit_limit))
        if util > 80:
            alerts.append(
                {
                    "type": "utilization",
                    "severity": "warning" if util <= 90 else "danger",
                    "message": f"High utilization on {card.bank_name} card ({round(util, 1)}%).",
                }
            )
        due_days = days_until_due(card.payment_due_date)
        if due_days is not None and due_days <= 7:
            alerts.append(
                {
                    "type": "payment_due",
                    "severity": "danger" if due_days <= 3 else "warning",
                    "message": f"{card.bank_name} payment due in {due_days} day(s).",
                }
            )

    return {
        "financial_health_score": score_meta["score"],
        "score_label": score_meta["score_label"],
        "score_color": score_meta["score_color"],
        "total_outstanding": round(total_outstanding, 2),
        "total_credit_limit": round(total_credit_limit, 2),
        "available_credit": round(available_credit, 2),
        "overall_utilization_percentage": round(overall_utilization, 2),
        "this_month_spending": round(this_month_spending, 2),
        "last_month_spending": round(last_month_spending, 2),
        "month_change_percentage": round(month_change_percentage, 2),
        "total_monthly_emi": round(total_monthly_emi, 2),
        "cards_count": cards_count,
        "alerts": alerts,
        "spending": spending,
        "credit_metrics": credit_metrics,
        "emi_metrics": emi_metrics,
    }


def manual_calculate(inputs: ManualInputs) -> dict:
    monthly_income = safe_float(inputs.monthly_income)
    other_income = safe_float(inputs.other_income)
    total_income = monthly_income + other_income

    monthly_expenses = safe_float(inputs.monthly_expenses)
    emi_total = safe_float(inputs.emi_total)

    savings_rate = safe_div((total_income - monthly_expenses) * 100, total_income) if total_income > 0 else None
    emi_ratio = safe_div(emi_total * 100, total_income) if total_income > 0 else None

    score = 50
    if emi_ratio is not None and emi_ratio < 40:
        score += 10
    if emi_ratio is not None and emi_ratio > 60:
        score -= 10
    if savings_rate is not None and savings_rate > 20:
        score += 15
    if inputs.emergency_fund_months and inputs.emergency_fund_months >= 6:
        score += 10

    score = max(0, min(100, int(round(score))))

    return {
        "total_income": round(total_income, 2),
        "savings_rate": round(savings_rate, 2) if savings_rate is not None else None,
        "emi_to_income_ratio": round(emi_ratio, 2) if emi_ratio is not None else None,
        "minimum_due": round(safe_float(inputs.minimum_due), 2),
        "financial_health_score": score,
    }
