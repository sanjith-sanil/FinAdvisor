"""emi_upsert_service.py

Shared helper called by both email_collector_service (IMAP) and
gmail_api_service (OAuth) after an email body is available.

Responsibilities
----------------
1. Detect whether the email body looks like an EMI summary.
2. Parse structured EMI rows from the body.
3. Match each EMI record to the correct Card in the database.
4. UPSERT each EMI into the card_emis table.
5. Recompute and persist the card's aggregate EMI fields.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.card_emi import CardEmi
from app.services.emi_parser_service import (
    extract_card_last4_from_email,
    looks_like_emi_email,
    parse_emi_details,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Card matching
# ---------------------------------------------------------------------------

async def _find_card(
    db: AsyncSession,
    user_id: uuid.UUID,
    bank_code: str,
    card_last4: str | None,
) -> Card | None:
    """Return the best Card match for a given bank_code + optional card_last4."""
    if card_last4:
        stmt = select(Card).where(
            Card.user_id == user_id,
            Card.bank_name.ilike(f"%{bank_code}%") | (Card.notes.ilike(f"%{bank_code}%")),
            Card.card_last4 == card_last4,
            Card.is_active.is_(True),
        )
        result = (await db.execute(stmt)).scalar_one_or_none()
        if result:
            return result

    # Fallback: match by bank_code substring across bank_name
    stmt = select(Card).where(
        Card.user_id == user_id,
        Card.bank_name.ilike(f"%{bank_code}%"),
        Card.is_active.is_(True),
    )
    cards = (await db.execute(stmt)).scalars().all()
    if len(cards) == 1:
        return cards[0]

    if len(cards) > 1 and card_last4:
        # Retry with only the last4 among the bank's cards
        for card in cards:
            if card.card_last4 == card_last4:
                return card

    if len(cards) > 1:
        logger.warning(
            "EMI upsert: ambiguous card match for bank_code=%s user=%s — skipping",
            bank_code,
            user_id,
        )
        return None

    return None


# ---------------------------------------------------------------------------
# Aggregate recalculation
# ---------------------------------------------------------------------------

async def _refresh_card_aggregates(db: AsyncSession, card: Card) -> None:
    """Recompute pending_emi_amount and monthly_emi_amount from child EMI rows."""
    stmt = select(CardEmi).where(CardEmi.card_id == card.id)
    all_emis = (await db.execute(stmt)).scalars().all()

    total_outstanding = sum(
        float(e.outstanding_amount) for e in all_emis if e.outstanding_amount is not None
    )
    total_monthly = sum(
        float(e.monthly_instalment_amount)
        for e in all_emis
        if e.monthly_instalment_amount is not None
    )
    max_pending = max(
        (e.pending_instalments for e in all_emis if e.pending_instalments is not None),
        default=None,
    )

    card.pending_emi_amount = total_outstanding or None
    card.monthly_emi_amount = total_monthly or None
    if max_pending is not None:
        card.emi_tenure_months = max_pending
    card.updated_at = datetime.datetime.now(datetime.timezone.utc)
    logger.info(
        "Card %s aggregates updated: pending=%.2f monthly=%.2f",
        card.id,
        total_outstanding,
        total_monthly,
    )


# ---------------------------------------------------------------------------
# UPSERT logic
# ---------------------------------------------------------------------------

def _make_upsert_key(record: dict[str, Any]) -> dict[str, Any]:
    """Build the filter criteria to look up an existing CardEmi row."""
    if record.get("loan_number"):
        return {"loan_number": record["loan_number"]}
    # Fallback: loan_type + creation_date
    return {
        "loan_type": record.get("loan_type"),
        "creation_date": record.get("creation_date"),
    }


async def _upsert_emi_record(
    db: AsyncSession,
    card: Card,
    user_id: uuid.UUID,
    record: dict[str, Any],
    source_raw_id: uuid.UUID | None,
    raw_snippet: str | None,
) -> CardEmi:
    key = _make_upsert_key(record)
    stmt = select(CardEmi).where(CardEmi.card_id == card.id)

    if key.get("loan_number"):
        stmt = stmt.where(CardEmi.loan_number == key["loan_number"])
    else:
        if key.get("loan_type"):
            stmt = stmt.where(CardEmi.loan_type == key["loan_type"])
        if key.get("creation_date"):
            stmt = stmt.where(CardEmi.creation_date == key["creation_date"])

    existing: CardEmi | None = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        # Update mutable fields
        for field, value in record.items():
            if value is not None:
                setattr(existing, field, value)
        existing.last_updated_at = datetime.datetime.now(datetime.timezone.utc)
        if source_raw_id:
            existing.source_raw_id = source_raw_id
        if raw_snippet:
            existing.raw_snippet = raw_snippet[:2000]
        logger.info("EMI updated: card=%s loan_type=%s", card.id, record.get("loan_type"))
        return existing

    # Insert
    emi = CardEmi(
        card_id=card.id,
        user_id=user_id,
        source_raw_id=source_raw_id,
        raw_snippet=(raw_snippet or "")[:2000],
        **{k: v for k, v in record.items() if v is not None},
    )
    db.add(emi)
    logger.info("EMI created: card=%s loan_type=%s", card.id, record.get("loan_type"))
    return emi


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def process_emi_from_email(
    db: AsyncSession,
    user_id: uuid.UUID,
    bank_code: str,
    email_body: str,
    email_subject: str = "",
    source_raw_id: uuid.UUID | None = None,
) -> int:
    """Detect, parse, and persist EMI data from a bank email.

    Returns the number of EMI records upserted (0 if none found / matched).
    """
    combined_text = f"{email_subject}\n{email_body}".strip()
    if not looks_like_emi_email(combined_text):
        return 0

    records = parse_emi_details(combined_text)
    if not records:
        logger.debug("EMI email detected but no rows parsed (bank_code=%s)", bank_code)
        return 0

    card_last4 = extract_card_last4_from_email(combined_text)
    card = await _find_card(db, user_id, bank_code, card_last4)
    if not card:
        logger.info(
            "EMI rows found but no matching card for bank_code=%s user=%s last4=%s",
            bank_code,
            user_id,
            card_last4,
        )
        return 0

    count = 0
    for record in records:
        await _upsert_emi_record(
            db,
            card,
            user_id,
            record,
            source_raw_id=source_raw_id,
            raw_snippet=combined_text[:2000],
        )
        count += 1

    await db.flush()
    await _refresh_card_aggregates(db, card)
    await db.commit()

    logger.info(
        "EMI upsert complete: %d record(s) for card %s (bank=%s)",
        count,
        card.id,
        bank_code,
    )
    return count


async def process_emi_from_pdf(
    db: AsyncSession,
    user_id: uuid.UUID,
    bank_code: str,
    file_path: str,
    filename: str = "",
) -> int:
    """Detect, parse, and persist EMI data from a credit card statement PDF.

    Returns the number of EMI records upserted.
    """
    from app.services.pdf_parser_service import extract_text_from_pdf

    try:
        pdf_text = extract_text_from_pdf(file_path)
    except Exception as e:
        logger.error("Failed to extract text from PDF statement %s: %s", file_path, e)
        return 0

    if not pdf_text:
        return 0

    records = parse_emi_details(pdf_text)
    if not records:
        logger.debug("No EMI records parsed from PDF %s", filename)
        return 0

    card_last4 = extract_card_last4_from_email(pdf_text)
    card = await _find_card(db, user_id, bank_code, card_last4)
    if not card:
        logger.info(
            "EMI rows found in PDF %s but no matching card for bank_code=%s user=%s last4=%s",
            filename,
            bank_code,
            user_id,
            card_last4,
        )
        return 0

    count = 0
    raw_snippet = f"PDF statement: {filename}\n{pdf_text[:1800]}"
    for record in records:
        await _upsert_emi_record(
            db,
            card,
            user_id,
            record,
            source_raw_id=None,
            raw_snippet=raw_snippet,
        )
        count += 1

    if count > 0:
        await db.flush()
        await _refresh_card_aggregates(db, card)

    logger.info(
        "EMI upsert complete from PDF: %d record(s) for card %s (bank=%s)",
        count,
        card.id,
        bank_code,
    )
    return count


async def process_pdf_attachment_from_email(
    db: AsyncSession,
    user_id: uuid.UUID,
    bank_info: dict[str, str],
    file_path: str,
    filename: str,
    received_at: datetime.datetime,
    sender_email: str,
) -> int:
    """Parse transactions and EMIs from a PDF attachment found in an email.

    Returns the number of standard transactions parsed.
    """
    from app.services.pdf_parser_service import parse_pdf
    from app.models.transaction import Transaction
    from app.models.enums import TransactionType, TransactionSource
    from app.services.balance_sync_service import (
        resolve_transaction_accounts,
        sync_balances_for_transaction,
    )

    # 1. Parse standard transactions from PDF
    try:
        transactions = parse_pdf(file_path)
    except Exception as e:
        logger.error("Failed to parse transactions from PDF attachment %s: %s", filename, e)
        transactions = []

    txns_saved = 0
    for txn in transactions:
        t = Transaction(
            user_id=user_id,
            transaction_type=txn["transaction_type"],
            amount=txn["amount"],
            description=txn["description"][:2000],
            transaction_date=txn["transaction_date"] or received_at,
            balance_after=txn["balance_after"],
            source=TransactionSource.email,
            bank_name=bank_info["bank_name"],
            bank_code=bank_info["bank_code"],
            sender_email=sender_email,
            raw_message=f"PDF attachment transaction: {txn['description']}"[:2000],
        )
        db.add(t)
        await resolve_transaction_accounts(db, t)
        await db.flush()
        if t.card_id or t.bank_account_id:
            await sync_balances_for_transaction(
                db=db,
                user_id=user_id,
                card_id=t.card_id,
                bank_account_id=t.bank_account_id,
                amount=t.amount,
                txn_type=t.transaction_type,
                operation="insert"
            )
        txns_saved += 1

    # 2. Parse EMIs from PDF
    try:
        await process_emi_from_pdf(
            db=db,
            user_id=user_id,
            bank_code=bank_info["bank_code"],
            file_path=file_path,
            filename=filename,
        )
    except Exception as e:
        logger.error("Failed to parse EMIs from PDF attachment %s: %s", filename, e)

    return txns_saved


