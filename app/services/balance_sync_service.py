import datetime
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.models.bank_account import BankAccount
from app.models.transaction import Transaction
from app.models.enums import CardType, TransactionType
from app.services.sms_parser_service import CARD_LAST4_PATTERN, ACCOUNT_LAST4_PATTERN


async def resolve_transaction_accounts(db: AsyncSession, txn: Transaction) -> None:
    """Resolve card_id and bank_account_id for a transaction if they are not already set."""
    if txn.card_id or txn.bank_account_id:
        return

    text = txn.description or ""
    if txn.raw_message:
        text += " " + txn.raw_message

    card_match = CARD_LAST4_PATTERN.search(text)
    account_match = ACCOUNT_LAST4_PATTERN.search(text)

    card_last4 = card_match.group(1) if card_match else None
    account_last4 = account_match.group(1) if account_match else None

    # Try matching using last 4 digits
    if card_last4:
        stmt = select(Card).where(Card.user_id == txn.user_id, Card.card_last4 == card_last4)
        card = (await db.execute(stmt)).scalar_one_or_none()
        if card:
            txn.card_id = card.id
            return

    if account_last4:
        stmt = select(BankAccount).where(
            BankAccount.user_id == txn.user_id,
            BankAccount.account_number_last4 == account_last4
        )
        acc = (await db.execute(stmt)).scalar_one_or_none()
        if acc:
            txn.bank_account_id = acc.id
            return

    # Fallback: if no last4, but bank_code matches and user has exactly one active card/account for that bank
    if txn.bank_code:
        # Check active credit cards
        stmt = select(Card).where(Card.user_id == txn.user_id, Card.is_active.is_(True))
        cards = (await db.execute(stmt)).scalars().all()
        matching_cards = [c for c in cards if txn.bank_code.upper() in c.bank_name.upper()]
        if len(matching_cards) == 1:
            txn.card_id = matching_cards[0].id
            return

        # Check bank accounts
        stmt = select(BankAccount).where(BankAccount.user_id == txn.user_id)
        accounts = (await db.execute(stmt)).scalars().all()
        matching_accs = [a for a in accounts if txn.bank_code.upper() in a.bank_name.upper()]
        if len(matching_accs) == 1:
            txn.bank_account_id = matching_accs[0].id
            return


async def sync_balances_for_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    card_id: uuid.UUID | None,
    bank_account_id: uuid.UUID | None,
    amount: float,
    txn_type: TransactionType | str,
    operation: str,  # "insert" or "delete"
    old_amount: float = 0.0,
    old_type: TransactionType | str | None = None
) -> None:
    """
    Syncs card and bank account balances based on transaction insertions or deletions.
    For updates, we perform a 'delete' of the old transaction state and an 'insert' of the new state.
    """
    amount = float(amount)
    old_amount = float(old_amount)
    
    # Resolve types to strings
    type_str = txn_type.value if hasattr(txn_type, "value") else str(txn_type)
    old_type_str = old_type.value if hasattr(old_type, "value") else str(old_type) if old_type else type_str

    if card_id:
        card = await db.get(Card, card_id)
        if card:
            change = 0.0
            
            # Compute impact of insertion
            if operation in ("insert", "update"):
                multiplier = 1.0 if type_str == "debit" else -1.0
                # If it's a debit card, spending (debit) decreases available balance
                if card.card_type == CardType.debit:
                    multiplier = -1.0 if type_str == "debit" else 1.0
                change += amount * multiplier

            # Compute impact of deletion
            if operation in ("delete", "update"):
                multiplier = -1.0 if old_type_str == "debit" else 1.0
                if card.card_type == CardType.debit:
                    multiplier = 1.0 if old_type_str == "debit" else -1.0
                change += old_amount * multiplier

            curr_val = float(card.current_balance or 0.0)
            new_val = max(0.0, curr_val + change)
            card.current_balance = new_val
            card.updated_at = datetime.datetime.now(datetime.timezone.utc)

    if bank_account_id:
        acc = await db.get(BankAccount, bank_account_id)
        if acc:
            change = 0.0

            # Compute impact of insertion
            if operation in ("insert", "update"):
                # Spending (debit) decreases balance, depositing (credit) increases balance
                multiplier = -1.0 if type_str == "debit" else 1.0
                change += amount * multiplier

            # Compute impact of deletion
            if operation in ("delete", "update"):
                multiplier = 1.0 if old_type_str == "debit" else -1.0
                change += old_amount * multiplier

            curr_val = float(acc.current_balance or 0.0)
            new_val = max(0.0, curr_val + change)
            acc.current_balance = new_val
            acc.last_updated = datetime.datetime.now(datetime.timezone.utc)
