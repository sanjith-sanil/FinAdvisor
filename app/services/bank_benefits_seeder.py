import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card, CardBenefit
from app.models.enums import BenefitCategory, CardType


BANK_BENEFIT_TEMPLATES: dict[str, list[dict[str, str]]] = {
    "hdfc": [
        {"benefit_category": "rewards", "title": "10X Reward Points on weekend dining", "value": "10X", "description": "Accelerated points on eligible dining transactions on weekends."},
        {"benefit_category": "lounge", "title": "Complimentary airport lounge access (2 per quarter)", "value": "2/quarter", "description": "Access domestic airport lounges every quarter."},
        {"benefit_category": "cashback", "title": "5% cashback on fuel transactions above Rs400", "value": "5%", "description": "Cashback on qualifying fuel spends above Rs400."},
        {"benefit_category": "fuel", "title": "1% fuel surcharge waiver at all fuel stations", "value": "1%", "description": "Fuel surcharge waiver on eligible fuel transactions."},
        {"benefit_category": "insurance", "title": "Zero lost card liability", "value": "Zero liability", "description": "Protection from unauthorized spends after timely reporting."},
        {"benefit_category": "cashback", "title": "1% cashback on all online spends", "value": "1%", "description": "Flat cashback on eligible online purchases."},
    ],
    "icici": [
        {"benefit_category": "lounge", "title": "2 complimentary domestic lounge visits per quarter", "value": "2/quarter", "description": "Domestic lounge access every quarter."},
        {"benefit_category": "dining", "title": "15% dining discount at partner restaurants", "value": "15%", "description": "Instant partner-restaurant dining discounts."},
        {"benefit_category": "cashback", "title": "1% cashback on all transactions", "value": "1%", "description": "Flat cashback across eligible spends."},
        {"benefit_category": "fuel", "title": "1% fuel surcharge waiver", "value": "1%", "description": "Fuel surcharge waiver at partner fuel stations."},
        {"benefit_category": "emi", "title": "EMI conversion at 0% on select merchants", "value": "0% EMI", "description": "No-cost EMI on selected merchant categories."},
    ],
    "axis": [
        {"benefit_category": "rewards", "title": "EDGE Reward Points on every spend", "value": "EDGE points", "description": "Earn EDGE points across eligible transactions."},
        {"benefit_category": "lounge", "title": "Complimentary domestic lounge access", "value": "Complimentary", "description": "Domestic lounge visits with spend criteria."},
        {"benefit_category": "shopping", "title": "10% instant discount on partner brands", "value": "10%", "description": "Instant discounts at partner merchants."},
        {"benefit_category": "fuel", "title": "Fuel surcharge waiver up to Rs400/month", "value": "Up to Rs400", "description": "Monthly capped waiver on fuel surcharge."},
    ],
    "sbi": [
        {"benefit_category": "rewards", "title": "5X reward points on groceries and dining", "value": "5X", "description": "Higher rewards on grocery and dining categories."},
        {"benefit_category": "other", "title": "Complimentary movie tickets per month", "value": "Monthly", "description": "Free movie ticket benefit based on spend milestones."},
        {"benefit_category": "fuel", "title": "Fuel surcharge waiver", "value": "1%", "description": "Fuel surcharge waiver on eligible transactions."},
        {"benefit_category": "rewards", "title": "Welcome bonus reward points", "value": "Bonus", "description": "One-time welcome points after activation and spends."},
    ],
    "kotak": [
        {"benefit_category": "other", "title": "PVR movie tickets (2 per month)", "value": "2/month", "description": "Complimentary PVR tickets after spend thresholds."},
        {"benefit_category": "dining", "title": "Dining cashback 15% at select restaurants", "value": "15%", "description": "Cashback on selected restaurant partners."},
        {"benefit_category": "lounge", "title": "Lounge access per quarter", "value": "Quarterly", "description": "Quarterly lounge visit entitlement."},
        {"benefit_category": "fuel", "title": "Fuel surcharge waiver 1%", "value": "1%", "description": "Fuel surcharge waiver on eligible fuel spends."},
    ],
}


def _normalize_bank(bank_name: str) -> str:
    return (bank_name or "").strip().lower().replace("bank", "").strip()


async def seed_default_benefits_for_card(session: AsyncSession, card: Card) -> list[CardBenefit]:
    if card.card_type != CardType.credit:
        return []

    bank_key = _normalize_bank(card.bank_name)
    templates = BANK_BENEFIT_TEMPLATES.get(bank_key)
    if not templates:
        return []

    existing_stmt = select(CardBenefit.title).where(
        CardBenefit.card_id == card.id,
        CardBenefit.user_id == card.user_id,
    )
    existing_titles = set((await session.execute(existing_stmt)).scalars().all())

    new_items: list[CardBenefit] = []
    for template in templates:
        if template["title"] in existing_titles:
            continue
        new_items.append(
            CardBenefit(
                id=uuid.uuid4(),
                card_id=card.id,
                user_id=card.user_id,
                benefit_category=BenefitCategory(template["benefit_category"]),
                title=template["title"],
                description=template.get("description"),
                value=template.get("value"),
                conditions=None,
                is_active=True,
            )
        )

    if new_items:
        session.add_all(new_items)

    return new_items
