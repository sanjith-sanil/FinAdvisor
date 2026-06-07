import datetime
import re
import uuid

import pdfplumber

from app.models.enums import TransactionType


_DATE_PATTERNS = ["%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]


def _parse_date(value: str) -> datetime.datetime | None:
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _clean_amount(value: str) -> float:
    return float(value.replace(",", ""))


def _detect_type(amounts: list[str], balance_before: float | None, balance_after: float | None) -> TransactionType:
    if len(amounts) >= 2:
        debit_val = _clean_amount(amounts[0]) if amounts[0] else 0
        credit_val = _clean_amount(amounts[1]) if amounts[1] else 0
        return TransactionType.debit if debit_val > 0 else TransactionType.credit
    if balance_before is not None and balance_after is not None:
        return TransactionType.credit if balance_after > balance_before else TransactionType.debit
    return TransactionType.debit


def parse_pdf(file_path: str) -> list[dict]:
    transactions: list[dict] = []
    last_balance: float | None = None

    date_regex = re.compile(r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{2}\s?[A-Za-z]{3}\s?\d{4}|\d{2}\s?[A-Za-z]+\s?\d{4})")
    amount_regex = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)")
    drcr_regex = re.compile(r"\b(Dr|Cr)\b", re.IGNORECASE)

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                date_match = date_regex.search(line)
                if not date_match:
                    continue

                date_str = date_match.group(1)
                txn_date = _parse_date(date_str)
                if not txn_date:
                    continue

                amounts = amount_regex.findall(line)
                if len(amounts) < 2:
                    continue

                balance = _clean_amount(amounts[-1])
                amount_value = _clean_amount(amounts[-2])

                description = line.replace(date_str, "").strip()
                txn_type = _detect_type(amounts[-2:], last_balance, balance)
                drcr_match = drcr_regex.search(line)
                if drcr_match:
                    txn_type = TransactionType.credit if drcr_match.group(1).lower() == "cr" else TransactionType.debit

                transactions.append(
                    {
                        "id": uuid.uuid4(),
                        "transaction_date": txn_date,
                        "description": description,
                        "amount": amount_value,
                        "balance_after": balance,
                        "transaction_type": txn_type,
                    }
                )
                last_balance = balance

    return transactions
