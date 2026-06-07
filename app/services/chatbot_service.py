from __future__ import annotations

import calendar
import datetime
import re
import textwrap
import uuid
from collections import defaultdict

import httpx

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.data.chatbot_seed import SPENDING_CATEGORIES
from app.models.bank_account import BankAccount
from app.models.budget_goal import BudgetGoal
from app.models.card import Card, CardBenefit
from app.models.chatbot import ChatbotQuestionTemplate
from app.models.enums import AccountType, CardType, TransactionType
from app.models.transaction import Transaction
from app.models.user import User
from app.services.calculation_service import financial_health_score


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _inr(value: float) -> str:
    sign = "-" if value < 0 else ""
    amount = abs(float(value))
    integer_part = int(amount)
    decimal_part = int(round((amount - integer_part) * 100))
    s = str(integer_part)
    if len(s) <= 3:
        grouped = s
    else:
        grouped = s[-3:]
        s = s[:-3]
        while s:
            grouped = s[-2:] + "," + grouped
            s = s[:-2]
    return f"{sign}₹{grouped}.{decimal_part:02d}" if decimal_part else f"{sign}₹{grouped}"


def _ordinal(day: int) -> str:
    if 11 <= (day % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _card_label(card: Card) -> str:
    return f"{card.bank_name} {str(card.card_type).split('.')[-1].title()}"


def _parse_amount_from_text(text: str | None) -> float | None:
    if not text:
        return None
    value = text.lower()

    match_k = re.search(r"(\d+(?:\.\d+)?)\s*k", value)
    if match_k:
        try:
            return float(match_k.group(1)) * 1000
        except ValueError:
            return None

    matches = list(re.finditer(r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*\.?\d*)", value))
    if not matches:
        return None

    for match in matches:
        raw = match.group(0)
        num = match.group(1).replace(",", "")
        try:
            amount = float(num)
        except ValueError:
            continue
        if any(token in raw for token in ["₹", "rs", "inr"]):
            return amount

    for match in matches:
        num = match.group(1).replace(",", "")
        try:
            amount = float(num)
        except ValueError:
            continue
        if amount >= 100:
            return amount
    return None


def _looks_like_spend_decision(text: str | None) -> bool:
    if not text:
        return False
    value = text.lower()
    trigger = [
        "can i spend",
        "should i spend",
        "is it safe to spend",
        "is it okay to spend",
        "can i afford",
        "should i buy",
        "can i buy",
        "afford to spend",
    ]
    if any(token in value for token in trigger):
        return True
    return "spend" in value and "can i" in value


def _looks_like_card_recommendation(text: str | None) -> bool:
    if not text:
        return False
    value = text.lower()
    trigger = [
        "which card",
        "best card",
        "recommend a card",
        "card recommendation",
        "which card should i use",
        "card should i use",
        "which card shall i use",
        "which card is safer",
        "which card is safe",
    ]
    return any(token in value for token in trigger)


def _month_bounds(now: datetime.datetime | None = None) -> tuple[datetime.datetime, datetime.datetime]:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    start = datetime.datetime(now.year, now.month, 1, tzinfo=datetime.timezone.utc)
    days = calendar.monthrange(now.year, now.month)[1]
    end = start + datetime.timedelta(days=days)
    return start, end


def _last_month_bounds(now: datetime.datetime | None = None) -> tuple[datetime.datetime, datetime.datetime]:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    year = now.year if now.month > 1 else now.year - 1
    month = now.month - 1 if now.month > 1 else 12
    start = datetime.datetime(year, month, 1, tzinfo=datetime.timezone.utc)
    days = calendar.monthrange(year, month)[1]
    end = start + datetime.timedelta(days=days)
    return start, end


class ChatbotService:
    async def _build_ai_context(self, user_id: uuid.UUID, db: AsyncSession) -> str:
        user = await db.get(User, user_id)

        cards = (
            (await db.execute(select(Card).where(Card.user_id == user_id, Card.is_active.is_(True)))).scalars().all()
        )
        accounts = (await db.execute(select(BankAccount).where(BankAccount.user_id == user_id))).scalars().all()
        transactions = (
            (
                await db.execute(
                    select(Transaction)
                    .where(Transaction.user_id == user_id)
                    .order_by(desc(Transaction.transaction_date))
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )

        credit_cards = [card for card in cards if card.card_type == CardType.credit]
        total_outstanding = sum(_to_float(card.current_balance) for card in credit_cards)
        total_credit_limit = sum(_to_float(card.credit_limit) for card in credit_cards)
        total_monthly_emi = sum(_to_float(card.monthly_emi_amount) for card in credit_cards)

        available_credit = 0.0
        for card in credit_cards:
            if card.available_balance is not None:
                available_credit += _to_float(card.available_balance)
                continue
            limit_val = _to_float(card.credit_limit)
            used = _to_float(card.current_balance)
            pending_emi = _to_float(card.pending_emi_amount)
            available_credit += max(limit_val - used - pending_emi, 0)

        month_start, month_end = _month_bounds(datetime.datetime.now(datetime.timezone.utc))
        last_month_start, last_month_end = _last_month_bounds(datetime.datetime.now(datetime.timezone.utc))
        this_month_spent = await self._sum_spending(user_id, month_start, month_end, db)
        last_month_spent = await self._sum_spending(user_id, last_month_start, last_month_end, db)

        health_score = None
        health_grade = None
        if credit_cards:
            score_meta = financial_health_score(credit_cards)
            health_score = score_meta["score"]
            if health_score >= 80:
                health_grade = "Excellent"
            elif health_score >= 65:
                health_grade = "Good"
            elif health_score >= 50:
                health_grade = "Fair"
            else:
                health_grade = "Needs Attention"

        lines = []

        lines.append("USER PROFILE:")
        if user:
            lines.append(f"Name: {user.full_name}")
            lines.append(f"Customer ID: {user.customer_id}")
        else:
            lines.append("Name: unknown")
            lines.append("Customer ID: unknown")

        lines.append("")
        lines.append(f"CARDS ({len(cards)} total):")
        if cards:
            for idx, card in enumerate(cards, start=1):
                label = _card_label(card)
                last4 = card.card_last4 or "----"
                if card.card_type == CardType.credit:
                    limit_val = _to_float(card.credit_limit)
                    used = _to_float(card.current_balance)
                    if card.available_balance is not None:
                        available = _to_float(card.available_balance)
                    else:
                        available = max(limit_val - used - _to_float(card.pending_emi_amount), 0)
                    util = (used / limit_val * 100) if limit_val > 0 else 0
                    due_day = int(card.payment_due_date) if card.payment_due_date else None
                    due_text = _ordinal(due_day) if due_day else "unknown"
                    parts = [
                        f"{idx}. {label}",
                        f"Last4: {last4}",
                        f"Limit: {_inr(limit_val)}",
                        f"Used: {_inr(used)}",
                        f"Available: {_inr(available)}",
                        f"Due: {due_text}",
                        f"Utilization: {util:.2f}%",
                    ]
                    if _to_float(card.monthly_emi_amount) > 0 or _to_float(card.pending_emi_amount) > 0:
                        emi_parts = []
                        if card.monthly_emi_amount:
                            emi_parts.append(f"{_inr(_to_float(card.monthly_emi_amount))}/mo")
                        if card.pending_emi_amount:
                            emi_parts.append(f"Pending {_inr(_to_float(card.pending_emi_amount))}")
                        if card.emi_tenure_months:
                            emi_parts.append(f"Tenure {card.emi_tenure_months}m")
                        if card.emi_interest_rate:
                            emi_parts.append(f"Rate {float(card.emi_interest_rate):.2f}%")
                        parts.append("EMI: " + ", ".join(emi_parts))
                    lines.append(" | ".join(parts))
                else:
                    balance_val = card.available_balance
                    if balance_val is None:
                        balance_val = card.current_balance
                    balance_text = _inr(_to_float(balance_val)) if balance_val is not None else "unknown"
                    lines.append(f"{idx}. {label} | Last4: {last4} | Balance: {balance_text}")
        else:
            lines.append("No cards found.")

        lines.append("")
        lines.append(f"BANK ACCOUNTS ({len(accounts)} total):")
        if accounts:
            for idx, account in enumerate(accounts, start=1):
                acct_type = str(account.account_type).split(".")[-1].title() if account.account_type else "Account"
                balance = _inr(_to_float(account.current_balance))
                updated = account.last_updated.strftime("%d %b %Y %I:%M %p") if account.last_updated else "unknown"
                lines.append(
                    f"{idx}. {account.bank_name} {acct_type} | Balance: {balance} | Updated: {updated}"
                )
        else:
            lines.append("No bank accounts found.")

        lines.append("")
        lines.append("RECENT TRANSACTIONS (last 20):")
        if transactions:
            for idx, txn in enumerate(transactions, start=1):
                date_text = txn.transaction_date.strftime("%d %b %Y")
                merchant = txn.merchant_name or txn.description or "Unknown"
                category = txn.merchant_category or "Uncategorized"
                amount_val = _to_float(txn.amount)
                if txn.transaction_type == TransactionType.debit:
                    amount_text = _inr(-abs(amount_val))
                else:
                    amount_text = _inr(abs(amount_val))
                balance_text = _inr(_to_float(txn.balance_after)) if txn.balance_after is not None else "unknown"
                lines.append(
                    f"{idx}. {date_text} | {merchant} | {category} | {amount_text} | Balance: {balance_text}"
                )
        else:
            lines.append("No recent transactions found.")

        lines.append("")
        lines.append("DASHBOARD:")
        lines.append(f"Total Outstanding: {_inr(total_outstanding)}")
        lines.append(f"Available Credit: {_inr(available_credit)}")
        lines.append(f"This Month Spending: {_inr(this_month_spent)}")
        lines.append(f"Last Month Spending: {_inr(last_month_spent)}")
        lines.append(f"Total EMI Outflow: {_inr(total_monthly_emi)}")
        if health_score is not None:
            lines.append(f"Health Score: {health_score}/100 ({health_grade})")
        else:
            lines.append("Health Score: unknown")

        return "\n".join(lines)

    async def _estimate_monthly_income(self, user_id: uuid.UUID, db: AsyncSession) -> float | None:
        now = datetime.datetime.now(datetime.timezone.utc)
        start = now - datetime.timedelta(days=90)

        salary_filter = or_(
            func.lower(func.coalesce(Transaction.merchant_name, "")).like("%salary%"),
            func.lower(func.coalesce(Transaction.description, "")).like("%salary%"),
            func.lower(func.coalesce(Transaction.merchant_name, "")).like("%payroll%"),
            func.lower(func.coalesce(Transaction.description, "")).like("%payroll%"),
            func.lower(func.coalesce(Transaction.description, "")).like("%income%"),
            func.lower(func.coalesce(Transaction.description, "")).like("%stipend%"),
        )

        salary_txns = (
            (
                await db.execute(
                    select(Transaction).where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == TransactionType.credit,
                        Transaction.transaction_date >= start,
                        salary_filter,
                    )
                )
            )
            .scalars()
            .all()
        )

        if not salary_txns:
            salary_accounts = (
                (
                    await db.execute(
                        select(BankAccount.id).where(
                            BankAccount.user_id == user_id, BankAccount.account_type == AccountType.salary
                        )
                    )
                )
                .scalars()
                .all()
            )
            if salary_accounts:
                salary_txns = (
                    (
                        await db.execute(
                            select(Transaction).where(
                                Transaction.user_id == user_id,
                                Transaction.transaction_type == TransactionType.credit,
                                Transaction.transaction_date >= start,
                                Transaction.bank_account_id.in_(salary_accounts),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

        if not salary_txns:
            return None

        monthly_totals: dict[tuple[int, int], float] = defaultdict(float)
        for txn in salary_txns:
            key = (txn.transaction_date.year, txn.transaction_date.month)
            monthly_totals[key] += _to_float(txn.amount)

        if not monthly_totals:
            return None

        sorted_months = sorted(monthly_totals.items(), key=lambda item: item[0], reverse=True)
        recent = [amount for _, amount in sorted_months[:3] if amount > 0]
        if not recent:
            return None
        return sum(recent) / len(recent)

    async def _financial_snapshot(self, user_id: uuid.UUID, db: AsyncSession) -> dict:
        now = datetime.datetime.now(datetime.timezone.utc)
        month_start, month_end = _month_bounds(now)
        last_month_start, last_month_end = _last_month_bounds(now)

        cards = (
            (await db.execute(select(Card).where(Card.user_id == user_id, Card.is_active.is_(True)))).scalars().all()
        )
        credit_cards = [card for card in cards if card.card_type == CardType.credit]

        total_credit_limit = sum(_to_float(card.credit_limit) for card in credit_cards)
        total_credit_used = sum(_to_float(card.current_balance) for card in credit_cards)
        total_monthly_emi = sum(_to_float(card.monthly_emi_amount) for card in credit_cards)
        total_pending_emi = sum(_to_float(card.pending_emi_amount) for card in credit_cards)

        utilization = (total_credit_used / total_credit_limit * 100) if total_credit_limit > 0 else 0
        score_meta = financial_health_score(credit_cards)
        health_score = score_meta["score"]
        if health_score >= 80:
            health_grade = "Excellent"
        elif health_score >= 65:
            health_grade = "Good"
        elif health_score >= 50:
            health_grade = "Fair"
        else:
            health_grade = "Needs Attention"

        bank_total = _to_float(
            (
                await db.execute(
                    select(func.coalesce(func.sum(BankAccount.current_balance), 0)).where(BankAccount.user_id == user_id)
                )
            ).scalar_one()
        )

        monthly_spent = await self._sum_spending(user_id, month_start, month_end, db)
        weekly_spent = await self._sum_spending(user_id, now - datetime.timedelta(days=7), now, db)
        last_month_spent = await self._sum_spending(user_id, last_month_start, last_month_end, db)

        days_elapsed = max(now.day, 1)
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        avg_daily_spend = monthly_spent / days_elapsed if days_elapsed else 0
        projected_monthly_spend = avg_daily_spend * days_in_month

        budget_total = _to_float(
            (
                await db.execute(
                    select(func.coalesce(func.sum(BudgetGoal.monthly_limit), 0)).where(
                        BudgetGoal.user_id == user_id,
                        BudgetGoal.month == now.month,
                        BudgetGoal.year == now.year,
                    )
                )
            ).scalar_one()
        )

        due_soon = []
        due_total = 0.0
        for card in credit_cards:
            due_day = int(card.payment_due_date or 1)
            due_day = max(1, min(due_day, 28))
            candidate = datetime.date(now.year, now.month, due_day)
            if candidate < now.date():
                month = now.month + 1 if now.month < 12 else 1
                year = now.year if now.month < 12 else now.year + 1
                candidate = datetime.date(year, month, due_day)
            days_left = (candidate - now.date()).days
            if days_left <= 7:
                balance = _to_float(card.current_balance)
                due_total += balance
                due_soon.append(
                    {"card": _card_label(card), "due_date": candidate.isoformat(), "days_left": days_left, "amount": balance}
                )

        salary_estimate = await self._estimate_monthly_income(user_id, db)

        return {
            "bank_total": bank_total,
            "total_credit_limit": total_credit_limit,
            "total_credit_used": total_credit_used,
            "utilization": utilization,
            "health_score": health_score,
            "health_grade": health_grade,
            "total_monthly_emi": total_monthly_emi,
            "total_pending_emi": total_pending_emi,
            "monthly_spent": monthly_spent,
            "weekly_spent": weekly_spent,
            "last_month_spent": last_month_spent,
            "avg_daily_spend": avg_daily_spend,
            "projected_monthly_spend": projected_monthly_spend,
            "budget_total": budget_total,
            "due_soon": due_soon,
            "due_total": due_total,
            "salary_estimate": salary_estimate,
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
        }

    def _safe_spend_buffer(self, snapshot: dict) -> float:
        available_cash = snapshot["bank_total"] - snapshot["due_total"] - snapshot["total_monthly_emi"]
        remaining_days = max(snapshot["days_in_month"] - snapshot["days_elapsed"], 0)
        remaining_spend = snapshot["avg_daily_spend"] * remaining_days
        safe_spend = available_cash - remaining_spend
        return max(safe_spend, 0)

    def _spend_decision_response(self, amount: float, snapshot: dict) -> dict:
        safe_spend = self._safe_spend_buffer(snapshot)
        available_cash = max(snapshot["bank_total"] - snapshot["due_total"] - snapshot["total_monthly_emi"], 0)
        projected = snapshot["projected_monthly_spend"]
        risk = "low"
        verdict = "manageable"

        if amount > available_cash:
            risk = "high"
            verdict = "not advisable"
        elif amount > safe_spend:
            risk = "medium"
            verdict = "risky"

        tone = "success" if risk == "low" else "warning" if risk == "medium" else "danger"
        recommendation = f"Based on your balances and obligations, spending {_inr(amount)} is {verdict}."
        if risk == "medium":
            recommendation += " It may reduce your savings buffer for the month."
        if risk == "high":
            recommendation += " It exceeds your safe cash buffer after EMIs and due payments."

        if snapshot.get("salary_estimate"):
            recommendation += f" Estimated monthly income: {_inr(snapshot['salary_estimate'])}."
        else:
            recommendation += " I could not detect salary credits yet, so this is based on spending history and balances."

        insights = [
            {"title": "Safe spend buffer", "value": _inr(safe_spend), "tone": tone},
            {"title": "Upcoming dues (7 days)", "value": _inr(snapshot["due_total"]), "tone": "warning"},
            {"title": "Projected month spend", "value": _inr(projected), "tone": "neutral"},
        ]

        if snapshot.get("salary_estimate"):
            insights.append(
                {"title": "Estimated monthly income", "value": _inr(snapshot["salary_estimate"]), "tone": "neutral"}
            )

        recommendations = [
            {
                "title": "Keep utilization under 30%",
                "detail": "Pay down credit balances to protect your credit score.",
                "tone": "warning",
            },
            {
                "title": "Protect your savings buffer",
                "detail": "Maintain at least 20% of your bank balance as a buffer.",
                "tone": "neutral",
            },
        ]

        return {
            "answer_text": recommendation,
            "data": {
                "amount": amount,
                "risk": risk,
                "safe_spend": safe_spend,
                "available_cash": available_cash,
                "insights": insights,
                "recommendations": recommendations,
            },
        }

    def _card_spend_decision(self, card: Card, amount: float) -> dict:
        limit_val = _to_float(card.credit_limit)
        used = _to_float(card.current_balance)
        pending_emi = _to_float(card.pending_emi_amount)
        available = max(limit_val - used - pending_emi, 0)
        projected_used = used + amount
        projected_util = (projected_used / limit_val * 100) if limit_val > 0 else 0

        risk = "low"
        if amount > available:
            risk = "high"
        elif projected_util > 75:
            risk = "high"
        elif projected_util > 50:
            risk = "medium"

        verdict = "manageable" if risk == "low" else "risky" if risk == "medium" else "not advisable"
        tone = "success" if risk == "low" else "warning" if risk == "medium" else "danger"

        answer = (
            f"Your {_card_label(card)} card has {_inr(available)} available credit. "
            f"Spending {_inr(amount)} is {verdict} based on your utilization."
        )
        if risk != "low":
            level = "high" if risk == "high" else "elevated"
            answer += f" Projected utilization would be {projected_util:.2f}% which is {level}."

        insights = [
            {"title": "Available credit", "value": _inr(available), "tone": tone},
            {"title": "Projected utilization", "value": f"{projected_util:.2f}%", "tone": tone},
            {"title": "Current balance", "value": _inr(used), "tone": "neutral"},
        ]

        recommendations = [
            {
                "title": "Keep utilization below 30%",
                "detail": "High utilization can affect your credit score.",
                "tone": "warning" if projected_util > 30 else "neutral",
            },
            {
                "title": "Consider EMI only if needed",
                "detail": "EMIs reduce available credit and add interest costs.",
                "tone": "neutral",
            },
        ]

        return {
            "answer_text": answer,
            "data": {
                "amount": amount,
                "risk": risk,
                "available_credit": available,
                "projected_utilization": projected_util,
                "insights": insights,
                "recommendations": recommendations,
            },
        }

    async def _card_recommendation_response(
        self, user_id: uuid.UUID, amount: float, db: AsyncSession
    ) -> dict:
        cards = (
            (
                await db.execute(
                    select(Card).where(
                        Card.user_id == user_id,
                        Card.card_type == CardType.credit,
                        Card.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not cards:
            return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}

        card_ids = [card.id for card in cards]
        benefits = (
            (
                await db.execute(
                    select(CardBenefit).where(
                        CardBenefit.card_id.in_(card_ids),
                        CardBenefit.user_id == user_id,
                        CardBenefit.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        benefits_by_card: dict[uuid.UUID, list[CardBenefit]] = defaultdict(list)
        for benefit in benefits:
            benefits_by_card[benefit.card_id].append(benefit)

        ranked = []
        for card in cards:
            limit_val = _to_float(card.credit_limit)
            used = _to_float(card.current_balance)
            pending_emi = _to_float(card.pending_emi_amount)
            available = max(limit_val - used - pending_emi, 0)
            util = (used / limit_val * 100) if limit_val > 0 else 0
            projected_util = ((used + amount) / limit_val * 100) if limit_val > 0 else 0

            due_day = int(card.payment_due_date or 1)
            due_day = max(1, min(due_day, 28))
            today = datetime.datetime.now(datetime.timezone.utc).date()
            candidate = datetime.date(today.year, today.month, due_day)
            if candidate < today:
                month = today.month + 1 if today.month < 12 else 1
                year = today.year if today.month < 12 else today.year + 1
                candidate = datetime.date(year, month, due_day)
            days_left = (candidate - today).days

            score = 100.0
            reasons = []
            warnings = []

            if available < amount:
                score -= 120
                warnings.append("Insufficient available credit")

            score -= util * 0.4
            if projected_util > 90:
                score -= 50
                warnings.append(f"Utilization would jump to {projected_util:.1f}%")
            elif projected_util > 75:
                score -= 30
                warnings.append(f"Utilization would reach {projected_util:.1f}%")
            elif projected_util > 50:
                score -= 15

            if days_left <= 3:
                score -= 35
                warnings.append(f"Payment due in {days_left} days")
            elif days_left <= 7:
                score -= 20
                warnings.append(f"Payment due in {days_left} days")

            rate = _to_float(card.emi_interest_rate)
            if rate >= 40:
                score -= 20
            elif rate >= 30:
                score -= 10

            score -= min(_to_float(card.credit_score_impact), 15)

            reward_boost = 0
            if card.cashback_rate:
                reward_boost += 12
            if card.reward_points_rate:
                reward_boost += 8
            if benefits_by_card.get(card.id):
                reward_boost += 10
            score += reward_boost

            if available >= amount:
                reasons.append(f"Available credit: {_inr(available)}")
            reasons.append(f"Utilization: {util:.1f}%")
            if card.cashback_rate:
                reasons.append(f"Cashback: {card.cashback_rate}")
            if card.reward_points_rate:
                reasons.append(f"Rewards: {card.reward_points_rate}")
            if benefits_by_card.get(card.id):
                top_benefit = benefits_by_card[card.id][0]
                reasons.append(f"Benefit: {top_benefit.title}")

            ranked.append(
                {
                    "card": card,
                    "score": score,
                    "available": available,
                    "util": util,
                    "projected_util": projected_util,
                    "days_left": days_left,
                    "reasons": reasons,
                    "warnings": warnings,
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        best = ranked[0]

        best_card = best["card"]
        best_label = _card_label(best_card)
        reasons_text = "\n".join([f"- {reason}" for reason in best["reasons"][:4]])
        warning_text = ""
        if best["warnings"]:
            warning_text = "\n" + "\n".join([f"- {warning}" for warning in best["warnings"][:2]])

        response = (
            f"For your {_inr(amount)} transaction, the best option is your {best_label} card.\n"
            f"Reason:\n{reasons_text}"
        )
        if warning_text:
            response += f"\nRisk notes:{warning_text}"

        insights = [
            {"title": "Available credit", "value": _inr(best["available"]), "tone": "success"},
            {"title": "Projected utilization", "value": f"{best['projected_util']:.1f}%", "tone": "neutral"},
            {"title": "Due in", "value": f"{best['days_left']} days", "tone": "warning" if best['days_left'] <= 7 else "neutral"},
        ]

        recommendations = []
        for alt in ranked[1:3]:
            alt_card = alt["card"]
            alt_label = _card_label(alt_card)
            summary = f"Available {_inr(alt['available'])}, utilization {alt['util']:.1f}%"
            if alt["warnings"]:
                summary += f", warning: {alt['warnings'][0]}"
            recommendations.append(
                {"title": f"Alternative: {alt_label}", "detail": summary, "tone": "neutral"}
            )

        return {
            "answer_text": response,
            "data": {
                "amount": amount,
                "recommended_card_id": str(best_card.id),
                "insights": insights,
                "recommendations": recommendations,
            },
        }

    async def answer_from_online(
        self,
        question: str,
        user_id: uuid.UUID | None = None,
        db: AsyncSession | None = None,
    ) -> dict:
        if not settings.groq_api_key:
            return {
                "answer_text": "I can help with your financial data, balances, transactions, and EMIs. Ask me about those any time.",
                "data": {"source": "online", "configured": False},
            }

        system_prompt = textwrap.dedent(
            """
            You are FinAdvisor AI, a smart personal finance assistant built into the FinAdvisor platform. You help users understand their finances, advise them, and answer any question they have.

            ---

            ## YOUR IDENTITY
            - Name: FinAdvisor AI
            - Role: Financial Advisor + Recommender + General Assistant + Data Analyst
            - Tone: Friendly, professional, and simple - no heavy jargon unless the user is clearly finance-savvy
            - Language: Always reply in the same language the user writes in (English, Hindi, Hinglish, Kannada, etc.)

            ---

            ## WHAT YOU CAN DO

            ### 1. READ THE USER'S FINANCIAL DATA (Read-Only)
            You have read-only access to the user's data. Use it to:
            - Answer questions about their transactions, card balances, EMIs, dues, spending history
            - Show summaries, breakdowns, patterns, and trends
            - Detect anomalies (e.g. "You spent 3x more on food this month")
            - Cross-reference data across cards and bank accounts

            ### 2. FINANCIAL ADVISOR
            - Give personalized advice based on their actual data
            - Help improve credit score, reduce debt, manage EMIs
            - Advise on which bill to pay first (by due date + interest rate)
            - Suggest budget goals and savings strategies
            - Explain credit utilization, CIBIL score, interest calculations

            ### 3. RECOMMENDER
            - Recommend which card to use for which type of spending
            - Suggest best cashback or reward redemption strategy
            - Recommend debt payoff order (avalanche vs snowball method)
            - Suggest when to pay bills for maximum benefit

            ### 4. GENERAL KNOWLEDGE ASSISTANT
            - Answer ANY general question like Google - distances, definitions, calculations, how-to, news, finance concepts
            - Examples:
              - "How far is Bangalore to Mangalore?" -> "By road ~352 km, about 6-7 hours"
              - "What is CIBIL score?" -> Explain clearly
              - "What is EMI?" -> Explain with formula
              - "How does credit utilization affect credit score?" -> Full explanation
            - Never refuse a question just because it is not about their data

            ---

            ## DATABASE ACCESS RULES - STRICTLY ENFORCED

            You have SELECT (read-only) access to the database. This means:

            YOU CAN:
            - Read transactions, card details, bank accounts, EMI info, spending summaries
            - Analyze, summarize, compare, and find patterns in the data
            - Answer any question based on the data provided to you

            YOU CANNOT - under any circumstances:
            - Insert, update, delete, or modify any record
            - Suggest or execute INSERT / UPDATE / DELETE / DROP / ALTER queries
            - Change balances, card details, transaction records, or any user setting
            - Even if the user explicitly asks you to edit something - refuse politely

            If asked to edit or delete data, always say:
            "I can only read and analyze your data. To make changes, please use the app directly or contact support."

            ---

            ## HOW TO USE THE DATABASE CONTEXT

            When the user's data is provided to you (as JSON or text):
            1. Read it carefully before answering
            2. Base your answer strictly on that data - never make up numbers or records
            3. If data is missing or empty, say: "I don't see that in your current records. It may not have been added yet."
            4. Always go beyond the question - add one useful insight or tip after answering

            ---

            ## DATA PROVIDED TO YOU

            You will receive the user's data in this format before their question:

            USER PROFILE:
            - Name, Customer ID, phone, email, member since

            BANK ACCOUNTS:
            - Bank name, account type, current balance, last updated

            CARDS:
            - Card name, type (credit/debit), last 4 digits, bank
            - Credit limit, current balance, available balance
            - EMI amount, tenure remaining, interest rate
            - Billing cycle date, payment due date, utilization %

            TRANSACTIONS (recent):
            - Date, merchant, category, amount, type (debit/credit), source (SMS/email/PDF/manual), balance after

            DASHBOARD METRICS:
            - Total outstanding, available credit, this month spending, last month spending
            - Financial health score, category breakdown, EMI outflow

            Use ALL of this to give accurate, personalized answers.

            ---

            ## RESPONSE STYLE

            - Always respond in natural, conversational sentences
            - Avoid report-like formatting or section headers such as "Cards:" or "Transactions:"
            - Use a short sentence or a simple bullet list only when the user asks for a list
            - For financial advice, always briefly explain WHY
              Example: "Pay the Axis card first - it has the highest interest rate at 36% p.a., costing you more every month you delay"
            - Add one helpful tip or next action at the end when relevant
            - Be warm and human - not robotic
            - Never show raw UUIDs or internal database IDs to the user
            - Use financial context only when the user asks about their finances
            - If data is missing, respond conversationally (e.g., "I don't see any cards added yet. You can add one from the My Cards page.")

            ---

            ## CALCULATION RULES

            When doing any financial calculation, use these standard formulas:

            EMI Formula:
              EMI = P x r x (1+r)^n / ((1+r)^n - 1)
              where P = principal, r = monthly interest rate, n = tenure in months

            Credit Utilization:
              Utilization % = (Current Balance / Credit Limit) x 100
              Good: below 30% | Warning: 30-60% | Critical: above 60%

            Minimum Payment Due:
              MAX(₹500, Current Balance x 5%)

            Interest if only minimum paid:
              (Current Balance - Minimum Payment) x (Annual Rate / 12 / 100)

            Financial Health Score (0-100):
              +25 if credit utilization < 30%
              +20 if no missed payments
              +20 if EMI-to-income ratio < 40%
              +20 if savings rate > 20%
              +15 if emergency fund >= 6 months expenses
              Deduct points for high utilization, missed payments, high EMI ratio

            ---

            ## EXAMPLE BEHAVIORS

            User: "How much did I spend this month?"
            -> Check transactions data -> Give total -> Break by category -> Flag anything unusual -> Suggest improvement

            User: "Which card should I pay first?"
            -> Check all card dues, due dates, interest rates -> Rank and recommend with reason

            User: "Am I spending too much on food?"
            -> Check food category this month vs last month -> Compare to total income if available -> Give recommendation

            User: "How far is Chennai to Mumbai?"
            -> Answer directly: "By road ~1,338 km (about 20-22 hours). By flight ~2 hours."

            User: "What is a good credit score?"
            -> Explain CIBIL score ranges: 300-549 Poor | 550-649 Average | 650-749 Good | 750-900 Excellent

            User: "Delete my last transaction"
            -> "I can only read your data, not modify it. To delete a transaction, please go to the History page in the app."

            User: "My salary is ₹60,000. Am I spending too much on EMIs?"
            -> Check total EMI outflow from data -> Calculate EMI-to-income ratio -> Give specific advice based on their actual numbers

            ---

            ## IMPORTANT DISCLAIMERS
            - You are not a SEBI-registered advisor. For major investment decisions, recommend consulting a certified financial advisor.
            - You do not process payments or transfers. You are advisory only.
            - Never share one user's data with another user.
            - If no data context is provided, say: "I don't have your account data right now. Please make sure you are logged in."

            ---

            ## WHAT YOU ARE NOT
            - You are NOT a payment processor
            - You are NOT a bank
            - You are NOT a chatbot with hardcoded Q&A - you reason from real user data
            - You do NOT hallucinate transactions, balances, or numbers - only use data given to you
            """
        ).strip()

        data_context = None
        if user_id and db:
            data_context = await self._build_ai_context(user_id, db)

        messages = [{"role": "system", "content": system_prompt}]
        if data_context:
            messages.append({"role": "system", "content": data_context})
        messages.append({"role": "user", "content": question})

        payload = {
            "model": settings.groq_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 512,
        }

        headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not content:
                content = "I could not find a helpful answer online right now."
            return {"answer_text": content, "data": {"source": "online", "model": settings.groq_model}}
        except httpx.HTTPError:
            return {
                "answer_text": "I could not fetch external context right now. Ask about your balances, spending, EMIs, or cards.",
                "data": {"source": "online", "error": "http_error"},
            }
    async def get_dynamic_questions(self, user_id: uuid.UUID, db: AsyncSession) -> list[dict]:
        templates = (
            (
                await db.execute(
                    select(ChatbotQuestionTemplate)
                    .where(ChatbotQuestionTemplate.is_active.is_(True))
                    .order_by(ChatbotQuestionTemplate.display_order)
                )
            )
            .scalars()
            .all()
        )

        cards = (
            (await db.execute(select(Card).where(Card.user_id == user_id, Card.is_active.is_(True)))).scalars().all()
        )
        accounts = (await db.execute(select(BankAccount).where(BankAccount.user_id == user_id))).scalars().all()

        questions: list[dict] = []
        for template in templates:
            if not template.requires_placeholder:
                questions.append(
                    {
                        "template_id": str(template.id),
                        "resolved_question": template.template_text,
                        "category": template.category,
                        "data_query_type": template.data_query_type,
                        "entity_value": None,
                        "display_order": template.display_order,
                    }
                )
                continue

            if template.placeholder_source == "user_cards":
                for card in cards:
                    label = _card_label(card)
                    questions.append(
                        {
                            "template_id": str(template.id),
                            "resolved_question": template.template_text.replace("{card_name}", label),
                            "category": template.category,
                            "data_query_type": template.data_query_type,
                            "entity_value": label,
                            "display_order": template.display_order,
                        }
                    )

            elif template.placeholder_source == "user_banks":
                for account in accounts:
                    questions.append(
                        {
                            "template_id": str(template.id),
                            "resolved_question": template.template_text.replace("{bank_name}", account.bank_name),
                            "category": template.category,
                            "data_query_type": template.data_query_type,
                            "entity_value": account.bank_name,
                            "display_order": template.display_order,
                        }
                    )

            elif template.placeholder_source == "spending_categories":
                for category in SPENDING_CATEGORIES:
                    questions.append(
                        {
                            "template_id": str(template.id),
                            "resolved_question": template.template_text.replace("{category}", category),
                            "category": template.category,
                            "data_query_type": template.data_query_type,
                            "entity_value": category,
                            "display_order": template.display_order,
                        }
                    )

        return sorted(questions, key=lambda item: item["display_order"])

    async def _find_card_by_label(self, user_id: uuid.UUID, label: str | None, db: AsyncSession) -> Card | None:
        cards = (
            (await db.execute(select(Card).where(Card.user_id == user_id, Card.is_active.is_(True)))).scalars().all()
        )
        if not cards:
            return None
        if not label:
            return cards[0]

        target = label.lower().strip()
        for card in cards:
            if _card_label(card).lower() == target:
                return card

        for card in cards:
            bank_name = card.bank_name.lower()
            card_type = str(card.card_type).split(".")[-1].lower()
            if bank_name in target and card_type in target:
                return card

        for card in cards:
            if card.bank_name.lower() in target:
                return card

        return None

    async def _find_accounts_by_bank_name(self, user_id: uuid.UUID, bank_name: str | None, db: AsyncSession) -> list[BankAccount]:
        accounts = (await db.execute(select(BankAccount).where(BankAccount.user_id == user_id))).scalars().all()
        if not bank_name:
            return accounts
        key = bank_name.lower()
        matched = [account for account in accounts if key in account.bank_name.lower() or account.bank_name.lower() in key]
        return matched

    async def _sum_spending(self, user_id: uuid.UUID, start: datetime.datetime, end: datetime.datetime, db: AsyncSession) -> float:
        total = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.debit,
                Transaction.transaction_date >= start,
                Transaction.transaction_date < end,
            )
        )
        return _to_float(total.scalar_one())

    async def _spending_breakdown_source(
        self, user_id: uuid.UUID, start: datetime.datetime, end: datetime.datetime, db: AsyncSession
    ) -> list[dict]:
        stmt = (
            select(
                func.coalesce(Card.bank_name, BankAccount.bank_name, Transaction.bank_name, "Unknown").label("source_name"),
                func.coalesce(func.sum(Transaction.amount), 0).label("total"),
            )
            .select_from(Transaction)
            .join(Card, Card.id == Transaction.card_id, isouter=True)
            .join(BankAccount, BankAccount.id == Transaction.bank_account_id, isouter=True)
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_type == TransactionType.debit,
                Transaction.transaction_date >= start,
                Transaction.transaction_date < end,
            )
            .group_by("source_name")
            .order_by(desc("total"))
        )
        rows = (await db.execute(stmt)).all()
        return [{"source": name, "amount": _to_float(total)} for name, total in rows]

    async def resolve_answer(
        self,
        user_id: uuid.UUID,
        data_query_type: str,
        entity_value: str | None,
        db: AsyncSession,
    ) -> dict:
        now = datetime.datetime.now(datetime.timezone.utc)
        month_start, month_end = _month_bounds(now)
        last_month_start, last_month_end = _last_month_bounds(now)
        today_start = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)
        tomorrow_start = today_start + datetime.timedelta(days=1)

        if data_query_type == "card_available_balance":
            card = await self._find_card_by_label(user_id, entity_value, db)
            if not card:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            limit_val = _to_float(card.credit_limit)
            used = _to_float(card.current_balance)
            available = max(limit_val - used, 0)
            utilization = (used / limit_val * 100) if limit_val > 0 else 0
            label = _card_label(card)
            return {
                "answer_text": (
                    f"Your {label} card has {_inr(available)} available to spend out of {_inr(limit_val)} credit limit. "
                    f"You have used {_inr(used)} ({utilization:.2f}%)."
                ),
                "data": {"available": available, "limit": limit_val, "used": used, "utilization": utilization},
            }

        if data_query_type == "card_recommendation":
            amount = _parse_amount_from_text(entity_value)
            if amount is None:
                return {
                    "answer_text": "Tell me the transaction amount and I will recommend the best card.",
                    "data": {},
                }
            return await self._card_recommendation_response(user_id, amount, db)

        if data_query_type == "bank_balance_specific":
            accounts = await self._find_accounts_by_bank_name(user_id, entity_value, db)
            if not accounts:
                return {
                    "answer_text": "You haven't added any bank accounts yet. Go to Profile → Bank Accounts to add one.",
                    "data": {},
                }
            total_balance = sum(_to_float(account.current_balance) for account in accounts)
            latest = max((account.last_updated for account in accounts if account.last_updated), default=None)
            bank_name = entity_value or accounts[0].bank_name
            last_updated = latest.strftime("%d %b %Y %I:%M %p") if latest else "not available"
            return {
                "answer_text": (
                    f"Your {bank_name} account balance is {_inr(total_balance)} (last updated {last_updated})."
                ),
                "data": {"bank_name": bank_name, "balance": total_balance, "last_updated": last_updated},
            }

        if data_query_type == "bank_balance_all":
            accounts = (await db.execute(select(BankAccount).where(BankAccount.user_id == user_id))).scalars().all()
            if not accounts:
                return {
                    "answer_text": "You haven't added any bank accounts yet. Go to Profile → Bank Accounts to add one.",
                    "data": {},
                }
            lines = []
            payload = []
            total = 0.0
            for account in accounts:
                bal = _to_float(account.current_balance)
                total += bal
                label = f"{account.bank_name} {str(account.account_type).split('.')[-1].title() if account.account_type else 'Account'}"
                lines.append(f"• {label}: {_inr(bal)}")
                payload.append({"name": label, "balance": bal})
            text = "Here are your bank account balances:\n" + "\n".join(lines) + f"\nTotal across all accounts: {_inr(total)}"
            return {"answer_text": text, "data": {"accounts": payload, "total_balance": total}}

        if data_query_type == "total_credit_limit":
            cards = (
                (
                    await db.execute(
                        select(Card).where(
                            Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True)
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not cards:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            total_limit = sum(_to_float(card.credit_limit) for card in cards)
            total_used = sum(_to_float(card.current_balance) for card in cards)
            total_available = max(total_limit - total_used, 0)
            return {
                "answer_text": (
                    f"Your total credit limit across all credit cards is {_inr(total_limit)}. "
                    f"You have used {_inr(total_used)} in total."
                ),
                "data": {"total_limit": total_limit, "total_used": total_used, "total_available": total_available},
            }

        if data_query_type == "card_outstanding":
            card = await self._find_card_by_label(user_id, entity_value, db)
            if not card:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            balance = _to_float(card.current_balance)
            min_payment = max(500, balance * 0.05) if balance > 0 else 0
            label = _card_label(card)
            return {
                "answer_text": (
                    f"Your {label} card has an outstanding balance of {_inr(balance)}. "
                    f"Minimum payment due: {_inr(min_payment)}."
                ),
                "data": {"balance": balance, "min_payment": min_payment, "card_label": label},
            }

        if data_query_type == "weekly_spending":
            start = now - datetime.timedelta(days=7)
            total = await self._sum_spending(user_id, start, now, db)
            breakdown = await self._spending_breakdown_source(user_id, start, now, db)
            if total <= 0:
                return {"answer_text": "No transactions found yet.", "data": {"total": 0, "breakdown": []}}
            lines = "\n".join([f"• {row['source']}: {_inr(row['amount'])}" for row in breakdown])
            return {
                "answer_text": f"You have spent {_inr(total)} in the last 7 days.\nBreakdown by source:\n{lines}",
                "data": {"total": total, "breakdown": breakdown, "period": "last 7 days"},
            }

        if data_query_type == "monthly_spending":
            total = await self._sum_spending(user_id, month_start, month_end, db)
            if total <= 0:
                return {"answer_text": "No transactions found yet.", "data": {"total": 0, "breakdown": []}}
            breakdown = await self._spending_breakdown_source(user_id, month_start, month_end, db)
            lines = "\n".join([f"• {row['source']}: {_inr(row['amount'])}" for row in breakdown])
            return {
                "answer_text": (
                    f"You have spent {_inr(total)} this month ({now.strftime('%B %Y')}).\n{lines}"
                ),
                "data": {"total": total, "breakdown": breakdown, "month": now.month, "year": now.year},
            }

        if data_query_type == "last_month_spending":
            total = await self._sum_spending(user_id, last_month_start, last_month_end, db)
            return {
                "answer_text": (
                    f"Last month you spent {_inr(total)} in {last_month_start.strftime('%B %Y')}."
                ),
                "data": {"total": total, "month": last_month_start.month, "year": last_month_start.year},
            }

        if data_query_type == "today_spending":
            total = await self._sum_spending(user_id, today_start, tomorrow_start, db)
            count = (
                await db.execute(
                    select(func.count(Transaction.id)).where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == TransactionType.debit,
                        Transaction.transaction_date >= today_start,
                        Transaction.transaction_date < tomorrow_start,
                    )
                )
            ).scalar_one()
            return {
                "answer_text": f"You have spent {_inr(total)} today so far. ({int(count)} transactions)",
                "data": {"total": total, "count": int(count)},
            }

        if data_query_type == "top_spending_category":
            stmt = (
                select(Transaction.merchant_category, func.coalesce(func.sum(Transaction.amount), 0).label("amount"))
                .where(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == TransactionType.debit,
                    Transaction.transaction_date >= month_start,
                    Transaction.transaction_date < month_end,
                )
                .group_by(Transaction.merchant_category)
                .order_by(desc("amount"))
            )
            rows = (await db.execute(stmt)).all()
            if not rows:
                return {"answer_text": "No transactions found yet.", "data": {"all_categories": []}}
            category, amount = rows[0]
            total = sum(_to_float(r[1]) for r in rows)
            pct = (_to_float(amount) / total * 100) if total > 0 else 0
            return {
                "answer_text": (
                    f"Your highest spending category this month is {category or 'Others'} with {_inr(_to_float(amount))} "
                    f"spent ({pct:.2f}% of total spending)."
                ),
                "data": {
                    "category": category or "Others",
                    "amount": _to_float(amount),
                    "percentage": pct,
                    "all_categories": [{"category": c or "Others", "amount": _to_float(a)} for c, a in rows],
                },
            }

        if data_query_type == "category_spending_month":
            category = entity_value or "Others"
            amount = (
                await db.execute(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == TransactionType.debit,
                        Transaction.transaction_date >= month_start,
                        Transaction.transaction_date < month_end,
                        func.lower(func.coalesce(Transaction.merchant_category, "Others")) == category.lower(),
                    )
                )
            ).scalar_one()
            total = await self._sum_spending(user_id, month_start, month_end, db)
            pct = (_to_float(amount) / total * 100) if total > 0 else 0
            return {
                "answer_text": (
                    f"You have spent {_inr(_to_float(amount))} on {category} this month. "
                    f"That is {pct:.2f}% of your total spending."
                ),
                "data": {"category": category, "amount": _to_float(amount), "percentage": pct},
            }

        if data_query_type == "daily_average_spend":
            total = await self._sum_spending(user_id, month_start, month_end, db)
            days_elapsed = max(now.day, 1)
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            avg = total / days_elapsed
            projected = avg * days_in_month
            return {
                "answer_text": (
                    f"Your average daily spend this month is {_inr(avg)}. Based on this, "
                    f"you are projected to spend {_inr(projected)} by end of month."
                ),
                "data": {"daily_avg": avg, "projected_total": projected, "days_elapsed": days_elapsed},
            }

        if data_query_type == "month_over_month_comparison":
            this_month = await self._sum_spending(user_id, month_start, month_end, db)
            last_month = await self._sum_spending(user_id, last_month_start, last_month_end, db)
            diff = this_month - last_month
            pct = (abs(diff) / last_month * 100) if last_month > 0 else 0
            if diff > 0:
                text = (
                    f"You are spending MORE than last month. This month: {_inr(this_month)} vs last month: {_inr(last_month)}. "
                    f"That is {_inr(diff)} more (+{pct:.2f}%)."
                )
                trend = "more"
            elif diff < 0:
                text = (
                    f"You are spending LESS than last month. This month: {_inr(this_month)} vs last month: {_inr(last_month)}. "
                    f"That is {_inr(abs(diff))} less (-{pct:.2f}%). Great job!"
                )
                trend = "less"
            else:
                text = (
                    f"Your spending is the same as last month at {_inr(this_month)}."
                )
                trend = "same"
            return {
                "answer_text": text,
                "data": {"this_month": this_month, "last_month": last_month, "diff": diff, "pct": pct, "trend": trend},
            }

        if data_query_type == "card_monthly_spending":
            card = await self._find_card_by_label(user_id, entity_value, db)
            if not card:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            amount = (
                await db.execute(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == TransactionType.debit,
                        Transaction.card_id == card.id,
                        Transaction.transaction_date >= month_start,
                        Transaction.transaction_date < month_end,
                    )
                )
            ).scalar_one()
            count = (
                await db.execute(
                    select(func.count(Transaction.id)).where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_type == TransactionType.debit,
                        Transaction.card_id == card.id,
                        Transaction.transaction_date >= month_start,
                        Transaction.transaction_date < month_end,
                    )
                )
            ).scalar_one()
            label = _card_label(card)
            return {
                "answer_text": (
                    f"You have spent {_inr(_to_float(amount))} using your {label} card this month "
                    f"across {int(count)} transactions."
                ),
                "data": {"amount": _to_float(amount), "count": int(count), "card_label": label},
            }

        if data_query_type == "highest_outstanding_card":
            cards = (
                (
                    await db.execute(
                        select(Card)
                        .where(Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True))
                        .order_by(desc(Card.current_balance))
                    )
                )
                .scalars()
                .all()
            )
            if not cards:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            card = cards[0]
            balance = _to_float(card.current_balance)
            limit_val = _to_float(card.credit_limit)
            util = (balance / limit_val * 100) if limit_val > 0 else 0
            label = _card_label(card)
            return {
                "answer_text": (
                    f"Your {label} card has the highest outstanding balance of {_inr(balance)} "
                    f"(utilization: {util:.2f}%)."
                ),
                "data": {"card_label": label, "balance": balance, "utilization": util},
            }

        if data_query_type == "card_utilization":
            card = await self._find_card_by_label(user_id, entity_value, db)
            if not card:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            used = _to_float(card.current_balance)
            limit_val = _to_float(card.credit_limit)
            util = (used / limit_val * 100) if limit_val > 0 else 0
            if util < 10:
                status = "Excellent"
            elif util < 30:
                status = "Good"
            elif util < 50:
                status = "Fair"
            elif util < 75:
                status = "High"
            else:
                status = "Critical"
            label = _card_label(card)
            return {
                "answer_text": (
                    f"Your {label} card utilization is {util:.2f}% which is {status}. "
                    f"You have used {_inr(used)} of {_inr(limit_val)}."
                ),
                "data": {"util": util, "status": status, "used": used, "limit": limit_val},
            }

        if data_query_type == "utilization_health_check":
            cards = (
                (
                    await db.execute(
                        select(Card).where(
                            Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True)
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not cards:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            breakdown = []
            total_used = 0.0
            total_limit = 0.0
            high_cards = []
            critical_cards = []
            for card in cards:
                used = _to_float(card.current_balance)
                limit_val = _to_float(card.credit_limit)
                util = (used / limit_val * 100) if limit_val > 0 else 0
                label = _card_label(card)
                breakdown.append({"card": label, "utilization": util})
                total_used += used
                total_limit += limit_val
                if util > 30:
                    high_cards.append(label)
                if util > 75:
                    critical_cards.append(label)
            avg_util = (total_used / total_limit * 100) if total_limit > 0 else 0
            if critical_cards:
                status_message = f"Warning: {', '.join(critical_cards)} are above 75% utilization."
            elif avg_util < 30:
                status_message = "Your utilization is in a healthy range."
            else:
                status_message = "Try to keep utilization under 30% for better credit health."
            return {
                "answer_text": (
                    f"Overall credit utilization is {avg_util:.2f}%. {status_message} "
                    f"Cards above 30% limit: {', '.join(high_cards) if high_cards else 'None'}."
                ),
                "data": {"avg_utilization": avg_util, "card_breakdown": breakdown},
            }

        if data_query_type in {"card_due_date", "days_until_due"}:
            card = await self._find_card_by_label(user_id, entity_value, db)
            if not card:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            due_day = int(card.payment_due_date or 1)
            due_day = max(1, min(due_day, 28))
            candidate = datetime.date(now.year, now.month, due_day)
            if candidate < now.date():
                next_month = now.month + 1 if now.month < 12 else 1
                year = now.year if now.month < 12 else now.year + 1
                candidate = datetime.date(year, next_month, due_day)
            days_left = (candidate - now.date()).days
            label = _card_label(card)
            balance = _to_float(card.current_balance)
            if data_query_type == "card_due_date":
                answer = (
                    f"Your {label} card payment is due on {candidate.strftime('%d %b %Y')} "
                    f"({days_left} days from today). Outstanding: {_inr(balance)}."
                )
            else:
                answer = (
                    f"You have {days_left} days left to pay your {label} card bill of {_inr(balance)}. "
                    f"Due date: {candidate.strftime('%d %b %Y')}."
                )
            return {
                "answer_text": answer,
                "data": {"due_date": candidate.isoformat(), "days_left": days_left, "balance": balance},
            }

        if data_query_type == "minimum_payment_due":
            card = await self._find_card_by_label(user_id, entity_value, db)
            if not card:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            balance = _to_float(card.current_balance)
            min_payment = max(500, balance * 0.05) if balance > 0 else 0
            monthly_rate = _to_float(card.emi_interest_rate) / 12 / 100
            interest_cost = max(balance - min_payment, 0) * monthly_rate
            label = _card_label(card)
            return {
                "answer_text": (
                    f"Minimum payment due on your {label} card is {_inr(min_payment)}. "
                    f"Full outstanding: {_inr(balance)}. Paying only minimum will cost you {_inr(interest_cost)} in interest."
                ),
                "data": {"min_payment": min_payment, "full_balance": balance, "interest_cost": interest_cost},
            }

        if data_query_type == "total_monthly_emi":
            cards = (
                (
                    await db.execute(
                        select(Card).where(Card.user_id == user_id, Card.is_active.is_(True), Card.monthly_emi_amount.is_not(None))
                    )
                )
                .scalars()
                .all()
            )
            if not cards:
                return {"answer_text": "No active EMIs found on your cards.", "data": {"total_emi": 0, "breakdown": []}}
            breakdown = []
            total = 0.0
            for card in cards:
                emi = _to_float(card.monthly_emi_amount)
                total += emi
                label = _card_label(card)
                tenure = int(card.emi_tenure_months or 0)
                breakdown.append({"card": label, "emi": emi, "tenure": tenure})
            lines = "\n".join([f"• {row['card']}: {_inr(row['emi'])} ({row['tenure']} months left)" for row in breakdown])
            return {
                "answer_text": f"Your total monthly EMI outflow is {_inr(total)}.\nBreakdown:\n{lines}",
                "data": {"total_emi": total, "breakdown": breakdown},
            }

        if data_query_type == "card_emi_remaining":
            card = await self._find_card_by_label(user_id, entity_value, db)
            if not card:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            remaining = _to_float(card.pending_emi_amount)
            tenure = int(card.emi_tenure_months or 0)
            monthly = _to_float(card.monthly_emi_amount)
            label = _card_label(card)
            return {
                "answer_text": (
                    f"Remaining EMI on your {label} card: {_inr(remaining)} over {tenure} months. "
                    f"Monthly EMI: {_inr(monthly)}."
                ),
                "data": {"remaining": remaining, "tenure": tenure, "monthly_emi": monthly},
            }

        if data_query_type == "emi_months_remaining":
            card = await self._find_card_by_label(user_id, entity_value, db)
            if not card:
                return {"answer_text": "You haven't added any cards yet. Go to My Cards to add one.", "data": {}}
            tenure = int(card.emi_tenure_months or 0)
            finish_date = now + datetime.timedelta(days=30 * tenure)
            label = _card_label(card)
            return {
                "answer_text": (
                    f"Your {label} card has {tenure} months of EMI remaining. "
                    f"You will finish paying in {finish_date.strftime('%B %Y')}."
                ),
                "data": {"tenure": tenure, "finish_date": finish_date.isoformat()},
            }

        if data_query_type == "total_emi_interest":
            cards = (
                (
                    await db.execute(
                        select(Card).where(
                            Card.user_id == user_id,
                            Card.is_active.is_(True),
                            Card.monthly_emi_amount.is_not(None),
                            Card.emi_tenure_months.is_not(None),
                            Card.pending_emi_amount.is_not(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not cards:
                return {"answer_text": "No active EMIs found on your cards.", "data": {"total_interest": 0, "breakdown": []}}
            breakdown = []
            total_interest = 0.0
            for card in cards:
                monthly = _to_float(card.monthly_emi_amount)
                tenure = int(card.emi_tenure_months or 0)
                principal = _to_float(card.pending_emi_amount)
                interest = max(monthly * tenure - principal, 0)
                total_interest += interest
                breakdown.append({"card": _card_label(card), "interest": interest})
            lines = "\n".join([f"• {row['card']}: {_inr(row['interest'])}" for row in breakdown])
            return {
                "answer_text": (
                    f"You are paying a total of {_inr(total_interest)} in interest across all your EMIs. "
                    f"This breaks down as:\n{lines}"
                ),
                "data": {"total_interest": total_interest, "breakdown": breakdown},
            }

        if data_query_type == "recent_transactions":
            txns = (
                (
                    await db.execute(
                        select(Transaction)
                        .where(Transaction.user_id == user_id)
                        .order_by(desc(Transaction.transaction_date))
                        .limit(5)
                    )
                )
                .scalars()
                .all()
            )
            if not txns:
                return {"answer_text": "No transactions found yet.", "data": {"transactions": []}}
            lines = []
            payload = []
            for idx, txn in enumerate(txns, start=1):
                merchant = txn.merchant_name or txn.description or "Unknown"
                card_label = "-"
                if txn.card_id:
                    card = await db.get(Card, txn.card_id)
                    card_label = _card_label(card) if card else "-"
                lines.append(
                    f"{idx}. {merchant} — {_inr(_to_float(txn.amount))} ({txn.transaction_date.strftime('%d %b %Y')}) [{card_label}]"
                )
                payload.append(
                    {
                        "merchant": merchant,
                        "amount": _to_float(txn.amount),
                        "date": txn.transaction_date.isoformat(),
                        "card": card_label,
                    }
                )
            return {"answer_text": "Here are your last 5 transactions:\n" + "\n".join(lines), "data": {"transactions": payload}}

        if data_query_type == "largest_transaction_month":
            txn = (
                (
                    await db.execute(
                        select(Transaction)
                        .where(
                            Transaction.user_id == user_id,
                            Transaction.transaction_type == TransactionType.debit,
                            Transaction.transaction_date >= month_start,
                            Transaction.transaction_date < month_end,
                        )
                        .order_by(desc(Transaction.amount))
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            if not txn:
                return {"answer_text": "No transactions found yet.", "data": {}}
            card_label = "-"
            if txn.card_id:
                card = await db.get(Card, txn.card_id)
                card_label = _card_label(card) if card else "-"
            merchant = txn.merchant_name or txn.description or "Unknown"
            amount = _to_float(txn.amount)
            return {
                "answer_text": (
                    f"Your largest transaction this month was {_inr(amount)} at {merchant} on "
                    f"{txn.transaction_date.strftime('%d %b %Y')} using {card_label}."
                ),
                "data": {"amount": amount, "merchant": merchant, "date": txn.transaction_date.isoformat(), "card": card_label},
            }

        if data_query_type == "transaction_count_today":
            count = (
                await db.execute(
                    select(func.count(Transaction.id)).where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_date >= today_start,
                        Transaction.transaction_date < tomorrow_start,
                    )
                )
            ).scalar_one()
            total = (
                await db.execute(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_date >= today_start,
                        Transaction.transaction_date < tomorrow_start,
                    )
                )
            ).scalar_one()
            return {
                "answer_text": f"You have made {int(count)} transactions today totalling {_inr(_to_float(total))}.",
                "data": {"count": int(count), "total": _to_float(total)},
            }

        if data_query_type == "transaction_count_all":
            count = (
                await db.execute(
                    select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
                )
            ).scalar_one()
            return {
                "answer_text": (
                    f"You currently have {int(count)} transactions in your history, including card payments, EMI deductions, and bank transfers."
                ),
                "data": {"count": int(count)},
            }

        if data_query_type == "transaction_count_month":
            count = (
                await db.execute(
                    select(func.count(Transaction.id)).where(
                        Transaction.user_id == user_id,
                        Transaction.transaction_date >= month_start,
                        Transaction.transaction_date < month_end,
                    )
                )
            ).scalar_one()
            return {
                "answer_text": (
                    f"You have {int(count)} transactions recorded so far this month."
                ),
                "data": {"count": int(count), "month": now.month, "year": now.year},
            }

        if data_query_type == "card_count":
            total = (
                await db.execute(select(func.count(Card.id)).where(Card.user_id == user_id))
            ).scalar_one()
            active = (
                await db.execute(
                    select(func.count(Card.id)).where(Card.user_id == user_id, Card.is_active.is_(True))
                )
            ).scalar_one()
            return {
                "answer_text": f"You currently have {int(active)} active cards in your account (total: {int(total)}).",
                "data": {"active": int(active), "total": int(total)},
            }

        if data_query_type == "top_merchant_month":
            stmt = (
                select(
                    func.coalesce(Transaction.merchant_name, Transaction.description, "Unknown").label("merchant"),
                    func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
                    func.count(Transaction.id).label("count"),
                )
                .where(
                    Transaction.user_id == user_id,
                    Transaction.transaction_type == TransactionType.debit,
                    Transaction.transaction_date >= month_start,
                    Transaction.transaction_date < month_end,
                )
                .group_by("merchant")
                .order_by(desc("amount"))
                .limit(1)
            )
            row = (await db.execute(stmt)).first()
            if not row:
                return {"answer_text": "No transactions found yet.", "data": {}}
            merchant, amount, count = row
            return {
                "answer_text": (
                    f"You have spent the most at {merchant} this month — {_inr(_to_float(amount))} "
                    f"across {int(count)} transactions."
                ),
                "data": {"merchant": merchant, "amount": _to_float(amount), "count": int(count)},
            }

        if data_query_type == "financial_health_score":
            cards = (
                (
                    await db.execute(
                        select(Card).where(Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True))
                    )
                )
                .scalars()
                .all()
            )
            total_limit = sum(_to_float(c.credit_limit) for c in cards)
            total_used = sum(_to_float(c.current_balance) for c in cards)
            utilization = (total_used / total_limit * 100) if total_limit > 0 else 0
            emi_total = sum(_to_float(c.monthly_emi_amount) for c in cards)
            monthly_spent = await self._sum_spending(user_id, month_start, month_end, db)
            bank_total = _to_float(
                (
                    await db.execute(
                        select(func.coalesce(func.sum(BankAccount.current_balance), 0)).where(BankAccount.user_id == user_id)
                    )
                ).scalar_one()
            )
            savings_rate = ((bank_total - monthly_spent) / bank_total * 100) if bank_total > 0 else 0
            score_meta = financial_health_score(cards)
            score = score_meta["score"]
            if score >= 80:
                grade = "Excellent"
            elif score >= 65:
                grade = "Good"
            elif score >= 50:
                grade = "Fair"
            else:
                grade = "Needs Attention"
            strengths = []
            weaknesses = []
            if utilization < 30:
                strengths.append("Credit utilization is under 30%")
            else:
                weaknesses.append("Reduce card utilization below 30%")
            if monthly_spent > 0:
                strengths.append("Regular transaction history is available")
            if emi_total > 0:
                weaknesses.append("Lower EMI burden where possible")
            return {
                "answer_text": (
                    f"Your financial health score is {score}/100 which is {grade}.\n"
                    f"Strengths: {', '.join(strengths) if strengths else 'Limited strong indicators yet'}\n"
                    f"Areas to improve: {', '.join(weaknesses) if weaknesses else 'No major risks detected'}"
                ),
                "data": {"score": score, "grade": grade, "strengths": strengths, "weaknesses": weaknesses},
            }

        if data_query_type == "credit_score_tips":
            cards = (
                (
                    await db.execute(
                        select(Card).where(Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True))
                    )
                )
                .scalars()
                .all()
            )
            tips = []
            issues = []
            for card in cards:
                limit_val = _to_float(card.credit_limit)
                used = _to_float(card.current_balance)
                util = (used / limit_val * 100) if limit_val > 0 else 0
                if util > 30:
                    tips.append(f"Pay down {_card_label(card)} below 30% utilization")
                    issues.append(f"{_card_label(card)} utilization is {util:.2f}%")
                due_day = int(card.payment_due_date or 1)
                due_day = max(1, min(due_day, 28))
                due_date = datetime.date(now.year, now.month, due_day)
                if due_date < now.date():
                    month = now.month + 1 if now.month < 12 else 1
                    year = now.year if now.month < 12 else now.year + 1
                    due_date = datetime.date(year, month, due_day)
                days_left = (due_date - now.date()).days
                if days_left <= 7:
                    tips.append(f"Pay {_card_label(card)} before {due_date.strftime('%d %b')} to avoid late marks")
                    issues.append(f"{_card_label(card)} due in {days_left} days")

            base_tips = [
                "Keep overall credit utilization below 30%",
                "Pay all card dues before due dates",
                "Avoid applying for multiple new cards in a short period",
                "Keep old credit accounts active for longer credit history",
                "Review statements monthly for errors and disputes",
            ]
            for tip in base_tips:
                if len(tips) >= 5:
                    break
                if tip not in tips:
                    tips.append(tip)

            tips = tips[:5]
            numbered = "\n".join([f"{idx}. {tip}" for idx, tip in enumerate(tips, start=1)])
            return {
                "answer_text": f"Here are personalized tips to improve your CIBIL score:\n{numbered}",
                "data": {"tips": tips, "current_issues": issues},
            }

        if data_query_type == "total_debt":
            card_debt = _to_float(
                (
                    await db.execute(
                        select(func.coalesce(func.sum(Card.current_balance), 0)).where(
                            Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True)
                        )
                    )
                ).scalar_one()
            )
            emi_debt = _to_float(
                (
                    await db.execute(
                        select(func.coalesce(func.sum(Card.pending_emi_amount), 0)).where(
                            Card.user_id == user_id, Card.is_active.is_(True)
                        )
                    )
                ).scalar_one()
            )
            total = card_debt + emi_debt
            return {
                "answer_text": (
                    f"Your total debt right now is {_inr(total)}.\n"
                    f"• Credit card outstanding: {_inr(card_debt)}\n"
                    f"• EMI remaining: {_inr(emi_debt)}"
                ),
                "data": {"total": total, "card_debt": card_debt, "emi_debt": emi_debt},
            }

        if data_query_type == "overall_financial_summary":
            cards = (
                (
                    await db.execute(
                        select(Card).where(Card.user_id == user_id, Card.is_active.is_(True))
                    )
                )
                .scalars()
                .all()
            )
            limit_total = _to_float(
                (
                    await db.execute(
                        select(func.coalesce(func.sum(Card.credit_limit), 0)).where(
                            Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True)
                        )
                    )
                ).scalar_one()
            )
            outstanding = _to_float(
                (
                    await db.execute(
                        select(func.coalesce(func.sum(Card.current_balance), 0)).where(
                            Card.user_id == user_id, Card.card_type == CardType.credit, Card.is_active.is_(True)
                        )
                    )
                ).scalar_one()
            )
            bank_balance = _to_float(
                (await db.execute(select(func.coalesce(func.sum(BankAccount.current_balance), 0)).where(BankAccount.user_id == user_id))).scalar_one()
            )
            spent = await self._sum_spending(user_id, month_start, month_end, db)
            utilization = (outstanding / limit_total * 100) if limit_total > 0 else 0
            score_meta = financial_health_score(
                [card for card in cards if card.card_type == CardType.credit]
            )
            score = score_meta["score"]
            if score >= 80:
                grade = "Excellent"
            elif score >= 65:
                grade = "Good"
            elif score >= 50:
                grade = "Fair"
            else:
                grade = "Needs Attention"
            data = {
                "total_credit_limit": limit_total,
                "total_outstanding": outstanding,
                "total_bank_balance": bank_balance,
                "monthly_spent": spent,
                "health_score": score,
                "grade": grade,
            }
            return {
                "answer_text": (
                    f"Summary of your finances: total credit limit is {_inr(limit_total)}, "
                    f"total outstanding is {_inr(outstanding)}, total bank balance is {_inr(bank_balance)}, "
                    f"this month's spending is {_inr(spent)}, and your health score is {score}/100 ({grade})."
                ),
                "data": data,
            }

        if data_query_type in {"remaining_budget_month", "over_budget_check", "projected_monthly_spend"}:
            goals = (
                (
                    await db.execute(
                        select(BudgetGoal).where(BudgetGoal.user_id == user_id, BudgetGoal.month == now.month, BudgetGoal.year == now.year)
                    )
                )
                .scalars()
                .all()
            )
            budget = sum(_to_float(goal.monthly_limit) for goal in goals)
            spent = await self._sum_spending(user_id, month_start, month_end, db)
            if data_query_type == "remaining_budget_month":
                if budget <= 0:
                    return {
                        "answer_text": "You haven't set a monthly budget yet. Go to Dashboard to set spending limits.",
                        "data": {},
                    }
                remaining = budget - spent
                return {
                    "answer_text": (
                        f"You have {_inr(remaining)} left in your monthly budget. "
                        f"You have spent {_inr(spent)} of {_inr(budget)} this month."
                    ),
                    "data": {"remaining": remaining, "spent": spent, "budget": budget},
                }
            if data_query_type == "over_budget_check":
                if budget <= 0:
                    return {
                        "answer_text": "You haven't set a monthly budget yet. Go to Dashboard to set spending limits.",
                        "data": {},
                    }
                over_by = spent - budget
                if over_by > 0:
                    text = f"Yes, you are over budget by {_inr(over_by)} this month."
                else:
                    text = f"No, you are within budget. You still have {_inr(abs(over_by))} remaining."
                return {"answer_text": text, "data": {"over_by": over_by, "spent": spent, "budget": budget}}

            days_elapsed = max(now.day, 1)
            days_total = calendar.monthrange(now.year, now.month)[1]
            projected = (spent / days_elapsed) * days_total if days_elapsed else spent
            return {
                "answer_text": (
                    f"Based on your spending so far ({_inr(spent)} in {days_elapsed} days), "
                    f"you are projected to spend {_inr(projected)} by end of {now.strftime('%B')}."
                ),
                "data": {"spent": spent, "days": days_elapsed, "projected": projected, "month": now.month},
            }

        if data_query_type == "safe_spending_limit":
            snapshot = await self._financial_snapshot(user_id, db)
            safe_spend = self._safe_spend_buffer(snapshot)
            weekly_safe = min(safe_spend, snapshot["avg_daily_spend"] * 7)
            insights = [
                {"title": "Safe spend buffer", "value": _inr(safe_spend), "tone": "success" if safe_spend > 0 else "warning"},
                {"title": "Weekly safe limit", "value": _inr(weekly_safe), "tone": "neutral"},
                {"title": "Upcoming dues (7 days)", "value": _inr(snapshot["due_total"]), "tone": "warning"},
            ]
            return {
                "answer_text": (
                    f"Based on your balances, EMIs, and current spending pace, your safe spend limit for this month is "
                    f"{_inr(safe_spend)}. A safe weekly limit is about {_inr(weekly_safe)}."
                ),
                "data": {"safe_spend": safe_spend, "weekly_safe": weekly_safe, "insights": insights},
            }

        if data_query_type == "spend_decision":
            amount = _parse_amount_from_text(entity_value)
            if amount is None:
                return {
                    "answer_text": "Tell me how much you want to spend and I will analyze it against your balances and obligations.",
                    "data": {},
                }
            snapshot = await self._financial_snapshot(user_id, db)
            return self._spend_decision_response(amount, snapshot)

        if data_query_type == "savings_status":
            snapshot = await self._financial_snapshot(user_id, db)
            buffer = snapshot["bank_total"] - snapshot["monthly_spent"] - snapshot["due_total"]
            buffer = max(buffer, 0)
            insights = [
                {"title": "Estimated savings buffer", "value": _inr(buffer), "tone": "success" if buffer > 0 else "warning"},
                {"title": "Monthly spend", "value": _inr(snapshot["monthly_spent"]), "tone": "neutral"},
                {"title": "Upcoming dues", "value": _inr(snapshot["due_total"]), "tone": "warning"},
            ]
            return {
                "answer_text": (
                    f"Your estimated savings buffer after this month's spending and upcoming dues is {_inr(buffer)}."
                ),
                "data": {"buffer": buffer, "insights": insights},
            }

        if data_query_type == "upcoming_dues_summary":
            snapshot = await self._financial_snapshot(user_id, db)
            if not snapshot["due_soon"]:
                return {
                    "answer_text": "You have no card payments due in the next 7 days.",
                    "data": {"due_soon": []},
                }
            lines = "\n".join(
                [
                    f"• {item['card']}: {_inr(item['amount'])} due in {item['days_left']} days"
                    for item in snapshot["due_soon"]
                ]
            )
            return {
                "answer_text": f"Upcoming dues in the next 7 days:\n{lines}",
                "data": {"due_soon": snapshot["due_soon"], "due_total": snapshot["due_total"]},
            }

        return {
            "answer_text": "I couldn't resolve that question yet. Please try another one from suggestions.",
            "data": {},
        }

    async def match_typed_question(self, user_input: str, user_id: uuid.UUID, db: AsyncSession) -> dict | None:
        text = user_input.lower().strip()

        if _looks_like_card_recommendation(text):
            amount = _parse_amount_from_text(text)
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "cards",
                "data_query_type": "card_recommendation",
                "entity_value": str(amount) if amount else None,
                "display_order": 0,
            }

        if _looks_like_spend_decision(text):
            amount = _parse_amount_from_text(text)
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "health",
                "data_query_type": "spend_decision",
                "entity_value": str(amount) if amount else None,
                "display_order": 0,
            }

        if any(token in text for token in ["safe spending", "safe spend", "spending limit", "how much can i spend"]):
            if "card" not in text:
                return {
                    "template_id": None,
                    "resolved_question": user_input,
                    "category": "health",
                    "data_query_type": "safe_spending_limit",
                    "entity_value": None,
                    "display_order": 0,
                }

        if any(token in text for token in ["savings", "savings buffer", "how much can i save"]):
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "health",
                "data_query_type": "savings_status",
                "entity_value": None,
                "display_order": 0,
            }

        if any(token in text for token in ["due payments", "upcoming dues", "pending dues", "dues pending"]):
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "cards",
                "data_query_type": "upcoming_dues_summary",
                "entity_value": None,
                "display_order": 0,
            }

        if any(token in text for token in ["how many transactions", "transaction count", "transactions in history", "transaction history"]):
            if "month" in text:
                query_type = "transaction_count_month"
            elif "today" in text:
                query_type = "transaction_count_today"
            else:
                query_type = "transaction_count_all"
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "transactions",
                "data_query_type": query_type,
                "entity_value": None,
                "display_order": 0,
            }

        if any(token in text for token in ["how many cards", "card count", "total cards", "cards in my account", "cards page"]):
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "cards",
                "data_query_type": "card_count",
                "entity_value": None,
                "display_order": 0,
            }

        if any(
            token in text
            for token in [
                "which card should i use",
                "best card",
                "recommend a card",
                "card recommendation",
                "which card is safer",
                "which card is safe",
            ]
        ):
            amount = _parse_amount_from_text(text)
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "cards",
                "data_query_type": "card_recommendation",
                "entity_value": str(amount) if amount else None,
                "display_order": 0,
            }

        if "emi" in text and "card" not in text:
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "emi",
                "data_query_type": "total_monthly_emi",
                "entity_value": None,
                "display_order": 0,
            }

        if "balance" in text and "card" not in text:
            return {
                "template_id": None,
                "resolved_question": user_input,
                "category": "balance",
                "data_query_type": "bank_balance_all",
                "entity_value": None,
                "display_order": 0,
            }

        templates = (
            (
                await db.execute(
                    select(ChatbotQuestionTemplate)
                    .where(ChatbotQuestionTemplate.is_active.is_(True))
                    .order_by(ChatbotQuestionTemplate.display_order)
                )
            )
            .scalars()
            .all()
        )

        best_template = None
        best_score = 0
        for template in templates:
            keywords = [kw.strip().lower() for kw in (template.keywords or "").split(",") if kw.strip()]
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_template = template

        if not best_template or best_score < 2:
            questions = await self.get_dynamic_questions(user_id, db)
            return {
                "no_match": True,
                "message": "I didn't understand that question. Here are some things I can help with:",
                "suggested_questions": questions[:5],
            }

        template = best_template
        entity_value = None
        if template.requires_placeholder:
            if template.placeholder_source == "user_cards":
                cards = (
                    (await db.execute(select(Card).where(Card.user_id == user_id, Card.is_active.is_(True)))).scalars().all()
                )
                labels = [_card_label(card) for card in cards]
                for card, label in zip(cards, labels):
                    if card.bank_name.lower() in text or label.lower() in text:
                        entity_value = label
                        break
                if entity_value is None:
                    return {
                        "needs_clarification": True,
                        "clarification_options": labels,
                        "template_id": str(template.id),
                        "message": "Which card do you mean?",
                    }

            elif template.placeholder_source == "user_banks":
                accounts = (await db.execute(select(BankAccount).where(BankAccount.user_id == user_id))).scalars().all()
                options = [account.bank_name for account in accounts]
                for bank in options:
                    if bank.lower() in text:
                        entity_value = bank
                        break
                if entity_value is None:
                    return {
                        "needs_clarification": True,
                        "clarification_options": options,
                        "template_id": str(template.id),
                        "message": "Which bank account do you mean?",
                    }

            elif template.placeholder_source == "spending_categories":
                for category in SPENDING_CATEGORIES:
                    if category.lower() in text or any(token in text for token in category.lower().split()):
                        entity_value = category
                        break
                if entity_value is None:
                    return {
                        "needs_clarification": True,
                        "clarification_options": SPENDING_CATEGORIES,
                        "template_id": str(template.id),
                        "message": "Which spending category do you mean?",
                    }

        resolved_question = template.template_text
        if entity_value:
            resolved_question = resolved_question.replace("{card_name}", entity_value)
            resolved_question = resolved_question.replace("{bank_name}", entity_value)
            resolved_question = resolved_question.replace("{category}", entity_value)

        return {
            "template_id": str(template.id),
            "resolved_question": resolved_question,
            "category": template.category,
            "data_query_type": template.data_query_type,
            "entity_value": entity_value,
            "display_order": template.display_order,
        }

    async def get_follow_up_questions(
        self,
        user_id: uuid.UUID,
        template: ChatbotQuestionTemplate | None,
        db: AsyncSession,
        limit: int = 4,
    ) -> list[dict]:
        all_questions = await self.get_dynamic_questions(user_id, db)
        if not template or not template.follow_up_categories:
            return all_questions[:limit]

        categories = [item.strip() for item in template.follow_up_categories.split(",") if item.strip()]
        selected = [q for q in all_questions if q["category"] in categories]
        if len(selected) < limit:
            existing = {q["resolved_question"] for q in selected}
            for question in all_questions:
                if question["resolved_question"] in existing:
                    continue
                selected.append(question)
                if len(selected) >= limit:
                    break
        return selected[:limit]
