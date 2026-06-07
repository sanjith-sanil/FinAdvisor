"""emi_parser_service.py

Extracts structured EMI / loan details from bank email bodies.

Supports two common Indian-bank email formats:

Format A — "Smart EMI Loan Summary" (e.g. HDFC Bank)
    Columns: Loan Number | Loan Booked Date | Loan Amount | Loan Tenure |
             Rate of Interest | Balance Principal Outstanding |
             Balance Interest Payable | Balance Tenure

Format B — "EMI / Personal Loan on Credit Cards" (e.g. ICICI, Axis)
    Columns: Transaction/Loan Type | Creation Date | Finish Date |
             No. of Installments | EMI/Loan Amount | Pending Installments |
             Outstanding Amount* | Monthly Installment Amount
"""

from __future__ import annotations

import datetime
import re
from typing import Any


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

_EMI_DETECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bsmart\s+emi\b", re.IGNORECASE),
    re.compile(r"\bemi\s+loan\s+summary\b", re.IGNORECASE),
    re.compile(r"\bemi\s*/\s*personal\s+loan\b", re.IGNORECASE),
    re.compile(r"\bemi\s+on\s+(?:call|card)\b", re.IGNORECASE),
    re.compile(r"\bmerchant\s+emi\b", re.IGNORECASE),
    re.compile(r"\bloan\s+(?:number|booked\s+date|tenure|summary)\b", re.IGNORECASE),
    re.compile(r"\bpending\s+instalment", re.IGNORECASE),
    re.compile(r"\bmonthly\s+instalment\s+amount\b", re.IGNORECASE),
    re.compile(r"\boutstanding\s+amount\b", re.IGNORECASE),
    re.compile(r"\bbalance\s+principal\s+outstanding\b", re.IGNORECASE),
    re.compile(r"\bno\.?\s+of\s+instalment", re.IGNORECASE),
]

_EMI_NON_MATCH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bminimum\s+amount\s+due\b", re.IGNORECASE),
    re.compile(r"\bstatement\s+date\b", re.IGNORECASE),
    re.compile(r"\bpayment\s+due\s+date\b", re.IGNORECASE),
]


def looks_like_emi_email(text: str) -> bool:
    """Return True if the email body appears to contain EMI summary data."""
    if not text:
        return False
    normalized = re.sub(r"\s+", " ", text).strip()
    has_emi_signal = sum(
        1 for p in _EMI_DETECTION_PATTERNS if p.search(normalized)
    ) >= 2
    if not has_emi_signal:
        return False
    # At least one amount-like number must appear
    has_amount = bool(re.search(r"[\d,]+\.\d{2}", normalized))
    return has_amount


# ---------------------------------------------------------------------------
# Amount / date helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y",
    "%d/%m/%y", "%d-%m-%y",
)


def _parse_date(raw: str) -> datetime.date | None:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(raw: str | None) -> float | None:
    if not raw:
        return None
    cleaned = raw.replace(",", "").replace("*", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_int(raw: str | None) -> int | None:
    if not raw:
        return None
    cleaned = raw.replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Format A — Smart EMI Loan Summary
# ---------------------------------------------------------------------------
# Expected row structure (pipe or whitespace separated after header detection):
#   107206651 | 29/05/2024 | 58,000.00 | 12 | 1.43 | 5,219.64 | 74.64 | 1

_FORMAT_A_HEADER = re.compile(
    r"loan\s+number.{0,80}loan\s+(?:booked\s+)?date.{0,80}loan\s+amount.{0,80}(?:loan\s+)?tenure",
    re.IGNORECASE | re.DOTALL,
)

_FORMAT_A_ROW = re.compile(
    r"(\d{5,20})"            # Loan number
    r"\s*[|\t]\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"  # Loan booked date
    r"\s*[|\t]\s*"
    r"([\d,]+(?:\.\d{1,2})?)"  # Loan amount
    r"\s*[|\t]\s*"
    r"(\d{1,3})"              # Tenure
    r"\s*[|\t]\s*"
    r"([\d.]+)"               # Rate of interest
    r"\s*[|\t]\s*"
    r"([\d,]+(?:\.\d{1,2})?)"  # Balance principal
    r"\s*[|\t]\s*"
    r"([\d,]+(?:\.\d{1,2})?)"  # Balance interest
    r"\s*[|\t]\s*"
    r"(\d{1,3})",             # Balance tenure
    re.IGNORECASE,
)

# Fallback: whitespace-separated row (no pipes)
_FORMAT_A_ROW_WS = re.compile(
    r"(\d{5,20})"            # Loan number
    r"\s+"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"  # Loan booked date
    r"\s+"
    r"([\d,]+\.\d{2})"       # Loan amount
    r"\s+"
    r"(\d{1,3})"              # Tenure
    r"\s+"
    r"([\d.]+)"               # Rate of interest
    r"\s+"
    r"([\d,]+\.\d{2})"        # Balance principal
    r"\s+"
    r"([\d,]+\.\d{2})"        # Balance interest
    r"\s+"
    r"(\d{1,3})",             # Balance tenure
)


def _parse_format_a(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not _FORMAT_A_HEADER.search(text):
        return results

    for pattern in (_FORMAT_A_ROW, _FORMAT_A_ROW_WS):
        for m in pattern.finditer(text):
            record: dict[str, Any] = {
                "loan_number": m.group(1).strip(),
                "loan_type": "Smart EMI",
                "creation_date": _parse_date(m.group(2)),
                "loan_amount": _to_float(m.group(3)),
                "loan_tenure_months": _to_int(m.group(4)),
                "interest_rate": _to_float(m.group(5)),
                "outstanding_amount": _to_float(m.group(6)),
                "balance_interest_payable": _to_float(m.group(7)),
                "balance_tenure": _to_int(m.group(8)),
                "pending_instalments": _to_int(m.group(8)),  # balance tenure ≈ pending
                "monthly_instalment_amount": None,
                "finish_date": None,
            }
            results.append(record)

    return results


# ---------------------------------------------------------------------------
# Format B — EMI / Personal Loan on Credit Cards table
# ---------------------------------------------------------------------------
# Columns: Type | Creation Date | Finish Date | No. Instalments |
#          EMI/Loan Amount | Pending Instalments | Outstanding Amount |
#          Monthly Instalment Amount

_FORMAT_B_HEADER = re.compile(
    r"(?:transaction/?\s*loan\s*type|loan\s*type).{0,80}"
    r"creation\s+date.{0,80}finish\s+date.{0,80}"
    r"(?:no\.?\s*of\s*instalment|installment)",
    re.IGNORECASE | re.DOTALL,
)

# Pipe-separated row
_FORMAT_B_ROW = re.compile(
    r"([A-Za-z][A-Za-z0-9 /\-]{1,60}?)"   # Loan type
    r"\s*[|\t]\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"  # Creation date
    r"\s*[|\t]\s*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"  # Finish date
    r"\s*[|\t]\s*"
    r"(\d{1,3})"                            # No. of instalments
    r"\s*[|\t]\s*"
    r"([\d,]+\.\d{2})"                     # EMI/Loan amount
    r"\s*[|\t]\s*"
    r"(\d{1,3})"                            # Pending instalments
    r"\s*[|\t]\s*"
    r"([\d,]+\.\d{2})\*?"                  # Outstanding amount
    r"\s*[|\t]\s*"
    r"([\d,]+\.\d{2})",                    # Monthly instalment amount
    re.IGNORECASE,
)

# Whitespace-separated row (no pipes)
_FORMAT_B_ROW_WS = re.compile(
    r"((?:EMI\s+on\s+call|Merchant\s+EMI\s+conversions|EMI\s+on\s+Card|[A-Za-z][A-Za-z0-9 ]{2,50}?))"
    r"\s{2,}"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"  # Creation date
    r"\s+"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"  # Finish date
    r"\s+"
    r"(\d{1,3})"                            # No. of instalments
    r"\s+"
    r"([\d,]+\.\d{2})"                     # EMI/Loan amount
    r"\s+"
    r"(\d{1,3})"                            # Pending instalments
    r"\s+"
    r"([\d,]+\.\d{2})\*?"                  # Outstanding amount
    r"\s+"
    r"([\d,]+\.\d{2})",                    # Monthly instalment amount
    re.IGNORECASE,
)


def _parse_format_b(text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not _FORMAT_B_HEADER.search(text):
        return results

    for pattern in (_FORMAT_B_ROW, _FORMAT_B_ROW_WS):
        for m in pattern.finditer(text):
            record: dict[str, Any] = {
                "loan_number": None,
                "loan_type": m.group(1).strip(),
                "creation_date": _parse_date(m.group(2)),
                "finish_date": _parse_date(m.group(3)),
                "loan_tenure_months": _to_int(m.group(4)),
                "loan_amount": _to_float(m.group(5)),
                "pending_instalments": _to_int(m.group(6)),
                "outstanding_amount": _to_float(m.group(7)),
                "monthly_instalment_amount": _to_float(m.group(8)),
                "interest_rate": None,
                "balance_interest_payable": None,
                "balance_tenure": _to_int(m.group(6)),
            }
            results.append(record)

    return results


# ---------------------------------------------------------------------------
# Card-number extraction helper (used by callers to match a card)
# ---------------------------------------------------------------------------

_CARD_LAST4_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"card\s*(?:ending|no\.?|number|xx+|\*+)\s*[:\-]?\s*(\d{4})", re.IGNORECASE),
    re.compile(r"(?:xx+|\*+)(\d{4})", re.IGNORECASE),
    re.compile(r"credit\s+card\s*[:\-]?\s*(?:xx+|\*+)?(\d{4})", re.IGNORECASE),
]


def extract_card_last4_from_email(text: str) -> str | None:
    """Try to pull the last-4-digits of a card number mentioned in an email."""
    for pattern in _CARD_LAST4_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_emi_details(text: str) -> list[dict[str, Any]]:
    """Parse EMI records from an email body.

    Tries Format A (Smart EMI Loan Summary) first, then Format B
    (EMI / Personal Loan on Credit Cards table).  Returns a (possibly
    empty) list of dicts, one per EMI row found.  Each dict has keys
    matching the CardEmi model fields.
    """
    normalized = re.sub(r"[ \t]+", " ", text or "").strip()
    records = _parse_format_a(normalized)
    if not records:
        records = _parse_format_b(normalized)
    return records
