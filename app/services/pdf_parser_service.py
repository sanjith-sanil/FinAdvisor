"""PDF statement parser for ICICI, HDFC and generic bank credit card statements.

Parsing order
-------------
1. Table-based extraction (pdfplumber.extract_tables) — most reliable when PDF
   was generated with proper table structure.
2. ICICI-specific text parser — handles ICICI's known column layout.
3. HDFC-specific text parser  — handles HDFC's known column layout.
4. Generic right-anchored text parser — fallback for any other bank.
"""
import datetime
import re
import uuid

import pdfplumber
import pdfminer.pdfdocument
from pdfminer.pdfdocument import PDFPasswordIncorrect, PDFEncryptionError

from app.models.enums import TransactionType


# ---------------------------------------------------------------------------
# Date / amount helpers
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y",
    "%d-%b-%Y", "%d-%B-%Y", "%d/%b/%Y", "%d/%B/%Y",
    "%d/%m/%y", "%d-%m-%y",
]

# Matches dates at start or anywhere: DD/MM/YYYY  DD-MM-YYYY  DD Mon YYYY
_DATE_RE = re.compile(
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})"
)

# Amount: optional comma-separated digits, optional decimal
_AMT_RE = re.compile(r"[\d,]+(?:\.\d{1,2})?")


def _parse_date(value: str) -> datetime.datetime | None:
    value = re.sub(r"\s+", " ", value).strip()
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _to_float(value: str | None) -> float | None:
    """Convert a string amount like '1,234.56' to float. Returns None if invalid."""
    if not value:
        return None
    cleaned = value.strip().replace(",", "").replace(" ", "")
    # Remove any trailing Dr/Cr
    cleaned = re.sub(r"(?i)(dr|cr)$", "", cleaned).strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cell_float(cell: str | None) -> float | None:
    if cell is None:
        return None
    return _to_float(cell)


def _make_txn(
    date: datetime.datetime,
    description: str,
    amount: float,
    balance: float | None,
    txn_type: TransactionType,
) -> dict:
    return {
        "id": uuid.uuid4(),
        "transaction_date": date,
        "description": description or "Transaction",
        "amount": amount,
        "balance_after": balance,
        "transaction_type": txn_type,
    }


# ---------------------------------------------------------------------------
# PDF open helper
# ---------------------------------------------------------------------------

def _open_pdf_with_passwords(file_path: str, passwords: list[str] | None = None):
    pwds_to_try = [None]
    if passwords:
        for p in passwords:
            if p and p not in pwds_to_try:
                pwds_to_try.append(p)

    last_err = None
    for pwd in pwds_to_try:
        try:
            return pdfplumber.open(file_path, password=pwd)
        except (PDFPasswordIncorrect, PDFEncryptionError) as e:
            last_err = e
            continue
        except Exception as e:
            err_msg = str(e).lower()
            if "password" in err_msg or "encrypt" in err_msg:
                last_err = e
                continue
            raise e

    if last_err:
        raise last_err
    raise PDFPasswordIncorrect("Failed to decrypt PDF with provided passwords.")


# ---------------------------------------------------------------------------
# Password candidate generator
# ---------------------------------------------------------------------------

def generate_candidate_passwords(
    full_name: str,
    date_of_birth: datetime.date | None = None,
    phone_number: str | None = None,
    cards_last4: list[str] | None = None,
) -> list[str]:
    candidates = []

    name_clean = "".join(c for c in full_name if c.isalpha())
    if not name_clean:
        name_clean = "user"

    name_4_lower = name_clean[:4].lower()
    name_4_upper = name_clean[:4].upper()

    ddmm = ""
    ddmmyyyy = ""
    if date_of_birth:
        if isinstance(date_of_birth, str):
            try:
                dt = datetime.datetime.fromisoformat(date_of_birth)
                ddmm = dt.strftime("%d%m")
                ddmmyyyy = dt.strftime("%d%m%Y")
            except Exception:
                pass
        else:
            try:
                ddmm = date_of_birth.strftime("%d%m")
                ddmmyyyy = date_of_birth.strftime("%d%m%Y")
            except Exception:
                pass

    if ddmm:
        candidates += [
            name_4_lower + ddmm,
            name_4_upper + ddmm,
            name_4_lower + ddmmyyyy,
            name_4_upper + ddmmyyyy,
            ddmm + name_4_lower,
            ddmm + name_4_upper,
        ]

    if phone_number:
        digits = re.sub(r"\D", "", phone_number)
        last4_phone = digits[-4:] if len(digits) >= 4 else digits
        candidates += [
            name_4_lower + last4_phone,
            name_4_upper + last4_phone,
            last4_phone + name_4_lower,
            last4_phone + name_4_upper,
        ]

    if cards_last4:
        for last4 in cards_last4:
            candidates += [
                name_4_lower + last4,
                name_4_upper + last4,
                last4 + name_4_lower,
                last4 + name_4_upper,
            ]

    candidates += [name_4_lower, name_4_upper]
    unique_candidates: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    return unique_candidates


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_pdf(file_path: str, passwords: list[str] | None = None) -> list[dict]:
    """Parse a credit-card / bank statement PDF into a list of transaction dicts.

    Tries multiple strategies in order of reliability:
      1. Table-based extraction (best column isolation)
      2. ICICI-specific text parser
      3. HDFC-specific text parser
      4. SBI-specific text parser
      5. Axis Bank-specific text parser
      6. Kotak Mahindra-specific text parser
      7. IndusInd Bank-specific text parser
      8. IDFC First Bank-specific text parser
      9. Yes Bank-specific text parser
     10. Generic right-anchored text parser (fallback)
    """
    with _open_pdf_with_passwords(file_path, passwords) as pdf:
        # Strategy 1 — table extraction
        txns = _parse_via_tables(pdf)
        if txns:
            return txns

        # Collect all page text for text-based strategies
        pages_text = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

        full_text = "\n".join(pages_text)

        # Strategy 2 — ICICI
        txns = _parse_icici(full_text)
        if txns:
            return txns

        # Strategy 3 — HDFC
        txns = _parse_hdfc(full_text)
        if txns:
            return txns

        # Strategy 4 — SBI
        txns = _parse_sbi(full_text)
        if txns:
            return txns

        # Strategy 5 — Axis Bank
        txns = _parse_axis(full_text)
        if txns:
            return txns

        # Strategy 6 — Kotak Mahindra
        txns = _parse_kotak(full_text)
        if txns:
            return txns

        # Strategy 7 — IndusInd
        txns = _parse_indusind(full_text)
        if txns:
            return txns

        # Strategy 8 — IDFC First
        txns = _parse_idfc(full_text)
        if txns:
            return txns

        # Strategy 9 — Yes Bank
        txns = _parse_yes(full_text)
        if txns:
            return txns

        # Strategy 10 — generic fallback
        return _parse_generic(full_text)


# ---------------------------------------------------------------------------
# Strategy 1: Table-based extraction
# ---------------------------------------------------------------------------

_DATE_REGEX = re.compile(
    r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s?[A-Za-z]{3,9}\s?\d{4})"
)
_AMOUNT_CELL = re.compile(r"^[\s]*-?[\d,]+(?:\.\d{1,2})?[\s]*$")


def _find_col(headers: list[str], candidates: list[str]) -> int | None:
    for i, h in enumerate(headers):
        for c in candidates:
            if c in h:
                return i
    return None


def _parse_via_tables(pdf) -> list[dict]:
    transactions: list[dict] = []
    last_balance: float | None = None

    for page in pdf.pages:
        tables = page.extract_tables() or []
        for table in tables:
            if not table or len(table) < 2:
                continue

            header_row = table[0]
            if not header_row:
                continue

            headers = [
                (h or "").strip().lower().replace("\n", " ")
                for h in header_row
            ]

            date_col = _find_col(headers, ["date", "txn date", "transaction date", "trans date", "posting date", "value date"])
            desc_col = _find_col(headers, ["description", "narration", "particulars", "details", "transaction details", "merchant description"])
            amt_col  = _find_col(headers, ["amount", "txn amount", "transaction amount"])
            cr_col   = _find_col(headers, ["credit", "cr amount", "cr"])
            dr_col   = _find_col(headers, ["debit", "dr amount", "dr"])
            bal_col  = _find_col(headers, ["balance", "closing balance", "running balance", "available balance"])

            if date_col is None or (amt_col is None and dr_col is None):
                continue

            for row in table[1:]:
                if not row:
                    continue
                max_needed = max(c for c in [date_col, desc_col, amt_col, cr_col, dr_col, bal_col] if c is not None)
                if len(row) <= max_needed:
                    continue

                raw_date = (row[date_col] or "").strip()
                date_match = _DATE_REGEX.search(raw_date)
                if not date_match:
                    continue
                txn_date = _parse_date(date_match.group(1))
                if not txn_date:
                    continue

                description = (row[desc_col] or "").strip() if desc_col is not None else ""
                description = re.sub(r"\s+", " ", description).strip()

                amount_value = 0.0
                txn_type = TransactionType.debit

                if dr_col is not None and cr_col is not None:
                    dr_val = _cell_float(row[dr_col] if dr_col < len(row) else None)
                    cr_val = _cell_float(row[cr_col] if cr_col < len(row) else None)
                    if dr_val and dr_val > 0:
                        amount_value = dr_val
                        txn_type = TransactionType.debit
                    elif cr_val and cr_val > 0:
                        amount_value = cr_val
                        txn_type = TransactionType.credit
                    else:
                        continue
                elif amt_col is not None:
                    val = _cell_float(row[amt_col] if amt_col < len(row) else None)
                    if val is None:
                        continue
                    amount_value = abs(val)
                    raw_amt = (row[amt_col] or "").strip().lower()
                    if val < 0 or "cr" in raw_amt:
                        txn_type = TransactionType.credit
                    else:
                        txn_type = TransactionType.debit
                else:
                    continue

                balance = _cell_float(row[bal_col] if bal_col is not None and bal_col < len(row) else None)

                if balance is not None and last_balance is not None:
                    if balance > last_balance:
                        txn_type = TransactionType.credit
                    elif balance < last_balance:
                        txn_type = TransactionType.debit

                transactions.append(_make_txn(txn_date, description, amount_value, balance, txn_type))
                if balance is not None:
                    last_balance = balance

    return transactions


# ---------------------------------------------------------------------------
# Strategy 2: ICICI Credit Card text parser
#
# ICICI PDF text (after extract_text) typically looks like:
#
#   Date        Transaction Details          Debit      Credit     Balance
#   19/05/2026  AMAZON PAY IN E COMMERC     220.00                440.00
#               BANGALORE
#   14/05/2026  SPOTIFY SI MUMBAI IN 299.              299.00     299.00
#   08/05/2026  IGST-CI@%                              194.04     194.04
#
# Key features:
#  - Date is DD/MM/YYYY at start of line
#  - Debit and Credit are separate columns (one will be blank)
#  - Balance column always present
#  - Description may wrap to the next line (no date prefix)
#  - Blank-column amounts may appear as empty strings in extracted text
# ---------------------------------------------------------------------------

_ICICI_DATE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4})\s+")

# Pattern to find: optional_debit  optional_credit  balance at end of line
# All three are comma-formatted numbers with optional decimal.
# We allow 2 or 3 trailing amounts.
_ICICI_AMOUNTS_3 = re.compile(
    r"([\d,]+(?:\.\d{1,2})?)\s+([\d,]+(?:\.\d{1,2})?)\s+([\d,]+(?:\.\d{1,2})?)\s*$"
)
_ICICI_AMOUNTS_2 = re.compile(
    r"([\d,]+(?:\.\d{1,2})?)\s+([\d,]+(?:\.\d{1,2})?)\s*$"
)
_ICICI_AMOUNTS_1 = re.compile(
    r"([\d,]+(?:\.\d{1,2})?)\s*$"
)


def _parse_icici(full_text: str) -> list[dict]:
    """Parse ICICI credit card statement text."""
    # Heuristic: only try this parser if text contains ICICI markers
    lower_text = full_text.lower()
    if not any(k in lower_text for k in ["icici", "icard", "i mobile"]):
        return []

    transactions: list[dict] = []
    lines = full_text.splitlines()
    i = 0
    last_balance: float | None = None

    while i < len(lines):
        line = lines[i]
        m = _ICICI_DATE.match(line.strip())
        if not m:
            i += 1
            continue

        date_str = m.group(1)
        txn_date = _parse_date(date_str)
        if not txn_date:
            i += 1
            continue

        # Grab this line plus potentially a continuation line
        rest = line.strip()[m.end() - len(line.strip()) + len(date_str) + 1:].strip()
        # Check if next line is a continuation (no date at start)
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not _ICICI_DATE.match(next_line):
                # Likely a description continuation or amount-only line
                # Check if the next line has amounts
                if _ICICI_AMOUNTS_2.search(next_line) or _ICICI_AMOUNTS_1.search(next_line):
                    rest = rest + " " + next_line
                    i += 1
                elif not _DATE_RE.match(next_line):
                    rest = rest + " " + next_line
                    i += 1

        # Now extract amounts from the end of `rest`
        debit = None
        credit = None
        balance = None
        description = rest

        m3 = _ICICI_AMOUNTS_3.search(rest)
        m2 = _ICICI_AMOUNTS_2.search(rest)
        m1 = _ICICI_AMOUNTS_1.search(rest)

        if m3:
            # Three numbers: debit, credit, balance (one of debit/credit may be very small or 0)
            a = _to_float(m3.group(1))
            b = _to_float(m3.group(2))
            c = _to_float(m3.group(3))
            balance = c
            # If a > 0 and b == 0 → debit; if a == 0 and b > 0 → credit
            # Use balance delta to decide
            if a and a > 0 and (b == 0 or b is None):
                debit = a
            elif b and b > 0 and (a == 0 or a is None):
                credit = b
            else:
                # Both non-zero or ambiguous: use balance delta
                if last_balance is not None and c is not None:
                    if c < last_balance:
                        debit = a
                    else:
                        credit = b
                else:
                    debit = a
            description = rest[:m3.start()].strip()
        elif m2:
            # Two numbers: amount + balance
            a = _to_float(m2.group(1))
            b = _to_float(m2.group(2))
            balance = b
            amount_candidate = a
            if last_balance is not None and b is not None:
                if b < last_balance:
                    debit = amount_candidate
                else:
                    credit = amount_candidate
            else:
                debit = amount_candidate
            description = rest[:m2.start()].strip()
        elif m1:
            # Only one number — likely balance or amount only
            a = _to_float(m1.group(1))
            # Can't reliably determine without a second number; skip
            description = rest[:m1.start()].strip()
            i += 1
            continue

        if debit is None and credit is None:
            i += 1
            continue

        amount_value = debit if debit else credit
        txn_type = TransactionType.debit if debit else TransactionType.credit

        # Override with balance delta
        if balance is not None and last_balance is not None:
            if balance < last_balance:
                txn_type = TransactionType.debit
            else:
                txn_type = TransactionType.credit

        description = re.sub(r"\s+", " ", description).strip()
        if amount_value and amount_value > 0:
            transactions.append(_make_txn(txn_date, description, amount_value, balance, txn_type))
        if balance is not None:
            last_balance = balance

        i += 1

    return transactions


# ---------------------------------------------------------------------------
# Strategy 3: HDFC Credit Card text parser
#
# HDFC PDF text typically looks like:
#
#   Date       Narration              Chq/Ref No   Value Date   Withdrawal  Deposit  Closing Balance
#   19/05/2026 UPI-Swiggy Ltd C I     123456789   19/05/2026   42.00                263.00
#
# OR for credit cards:
#   Date       Transaction Description            Amount     Cr/Dr     Balance
#   19/05/2026 AMAZON INDIA                       2,200.00   Dr        44,000.00
#
# ---------------------------------------------------------------------------

_HDFC_DATE = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4})\s+")
_HDFC_CRDDR = re.compile(r"\b(Cr|Dr)\b", re.IGNORECASE)


def _parse_hdfc(full_text: str) -> list[dict]:
    """Parse HDFC credit card / bank statement text."""
    lower_text = full_text.lower()
    if not any(k in lower_text for k in ["hdfc", "hdfcbank"]):
        return []

    transactions: list[dict] = []
    lines = full_text.splitlines()
    last_balance: float | None = None

    for line in lines:
        stripped = line.strip()
        m = _HDFC_DATE.match(stripped)
        if not m:
            continue

        date_str = m.group(1)
        txn_date = _parse_date(date_str)
        if not txn_date:
            continue

        rest = stripped[m.end():].strip()

        # Check for Cr/Dr marker
        crddr_match = _HDFC_CRDDR.search(rest)
        is_credit = False
        if crddr_match:
            is_credit = crddr_match.group(1).lower() == "cr"
            # Remove the marker from the string for cleaner amount parsing
            rest = rest[:crddr_match.start()] + rest[crddr_match.end():]

        # Extract trailing 2 amounts (amount + balance)
        m2 = _ICICI_AMOUNTS_2.search(rest.strip())
        if m2:
            a = _to_float(m2.group(1))
            b = _to_float(m2.group(2))
            description = rest[:m2.start()].strip()
            balance = b
            amount_value = a

            # Determine type from Cr/Dr marker or balance delta
            if crddr_match:
                txn_type = TransactionType.credit if is_credit else TransactionType.debit
            elif last_balance is not None and b is not None:
                txn_type = TransactionType.credit if b > last_balance else TransactionType.debit
            else:
                txn_type = TransactionType.debit

            description = re.sub(r"\s+", " ", description).strip()
            if amount_value and amount_value > 0:
                transactions.append(_make_txn(txn_date, description, amount_value, balance, txn_type))
            if balance is not None:
                last_balance = balance
        else:
            m1 = _ICICI_AMOUNTS_1.search(rest)
            if m1:
                a = _to_float(m1.group(1))
                description = rest[:m1.start()].strip()
                description = re.sub(r"\s+", " ", description).strip()
                if a and a > 0:
                    txn_type = TransactionType.credit if is_credit else TransactionType.debit
                    transactions.append(_make_txn(txn_date, description, a, None, txn_type))

    return transactions


# ---------------------------------------------------------------------------
# Strategy 4 — SBI Credit Card text parser
#
# SBI credit card statement format:
#   Date         Description                  Debit     Credit    Balance
#   19/05/2026   AMAZON INDIA PVT LTD         2,200.00            44,000.00
#   14/05/2026   CASHBACK CREDIT                        299.00    44,299.00
#
# SBI also uses DD-MON-YYYY format in some versions.
# ---------------------------------------------------------------------------

def _parse_sbi(full_text: str) -> list[dict]:
    """Parse SBI credit card statement text."""
    lower = full_text.lower()
    if not any(k in lower for k in ["sbi", "state bank", "sbicard"]):
        return []
    return _parse_two_col_bank(full_text)


# ---------------------------------------------------------------------------
# Strategy 5 — Axis Bank text parser
#
# Axis Bank credit card statement format:
#   Date         Transaction Details              Amount (INR)  Cr/Dr
#   19/05/2026   AMAZON INDIA                     2,200.00      Dr
#   14/05/2026   REFUND - AMAZON                  299.00        Cr
#
# OR with separate debit / credit columns + balance:
#   Date         Particulars        Chq No   Debit      Credit   Balance
#   19/05/2026   UPI-Swiggy                  42.00               5,263.00
# ---------------------------------------------------------------------------

def _parse_axis(full_text: str) -> list[dict]:
    """Parse Axis Bank credit card / savings statement text."""
    lower = full_text.lower()
    if not any(k in lower for k in ["axis bank", "axis credit", "axisbank"]):
        return []
    return _parse_two_col_bank(full_text)


# ---------------------------------------------------------------------------
# Strategy 6 — Kotak Mahindra Bank text parser
#
# Kotak credit card statement format:
#   Txn Date     Description                     Amount      Cr/Dr    Balance
#   19 May 2026  AMAZON INDIA PVT LTD            2,200.00    Dr       44,000.00
#   14 May 2026  INTEREST REVERSAL               150.00      Cr       44,150.00
# ---------------------------------------------------------------------------

def _parse_kotak(full_text: str) -> list[dict]:
    """Parse Kotak Mahindra Bank credit card statement text."""
    lower = full_text.lower()
    if not any(k in lower for k in ["kotak", "kotak mahindra", "811"]):
        return []
    return _parse_two_col_bank(full_text)


# ---------------------------------------------------------------------------
# Strategy 7 — IndusInd Bank text parser
#
# IndusInd credit card statement format:
#   Date         Merchant / Transaction           Amount      Dr/Cr    Balance
#   19/05/2026   AMAZON PAY INDIA                 1,500.00    Dr       38,500.00
# ---------------------------------------------------------------------------

def _parse_indusind(full_text: str) -> list[dict]:
    """Parse IndusInd Bank credit card statement text."""
    lower = full_text.lower()
    if not any(k in lower for k in ["indusind", "indus ind"]):
        return []
    return _parse_two_col_bank(full_text)


# ---------------------------------------------------------------------------
# Strategy 8 — IDFC First Bank text parser
#
# IDFC First credit card / account statement format:
#   Value Date   Description                     Debit       Credit   Balance
#   19/05/2026   UPI/SWIGGY/REF123               85.00                12,415.00
#   14/05/2026   SALARY CREDIT                               50,000   62,415.00
# ---------------------------------------------------------------------------

def _parse_idfc(full_text: str) -> list[dict]:
    """Parse IDFC First Bank statement text."""
    lower = full_text.lower()
    if not any(k in lower for k in ["idfc", "idfc first", "idfcfirst"]):
        return []
    return _parse_two_col_bank(full_text)


# ---------------------------------------------------------------------------
# Strategy 9 — Yes Bank text parser
#
# Yes Bank statement format (credit card and savings):
#   Date         Particulars                     Withdrawals  Deposits  Balance
#   19/05/2026   UPI/AMAZON/REF456               3,500.00              46,500.00
#   14/05/2026   NEFT INWARD - SALARY                         55,000   1,01,500.00
# ---------------------------------------------------------------------------

def _parse_yes(full_text: str) -> list[dict]:
    """Parse Yes Bank statement text."""
    lower = full_text.lower()
    if not any(k in lower for k in ["yes bank", "yesbank", "yes bank ltd"]):
        return []
    return _parse_two_col_bank(full_text)


# ---------------------------------------------------------------------------
# Shared helper: two-column bank parser
#
# Most Indian banks (SBI, Axis, Kotak, IndusInd, IDFC, Yes) follow the same
# general layout when rendered as text:
#   <Date>  <Description>  [optional ref]  <Amount>  [Cr/Dr marker]  <Balance>
#
# This helper handles all of them identically.
# ---------------------------------------------------------------------------

_DRCR_RE = re.compile(r"\b(Dr|Cr)\b", re.IGNORECASE)
_AMOUNTS_2 = re.compile(r"([\d,]+(?:\.\d{1,2})?)\s+([\d,]+(?:\.\d{1,2})?)\s*$")
_AMOUNTS_1 = re.compile(r"([\d,]+(?:\.\d{1,2})?)\s*$")
_START_DATE = re.compile(r"^(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\s+")


def _parse_two_col_bank(full_text: str) -> list[dict]:
    """Shared text parser for Indian banks with Debit/Credit/Balance column layout."""
    transactions: list[dict] = []
    last_balance: float | None = None

    for line in full_text.splitlines():
        stripped = line.strip()
        m = _START_DATE.match(stripped)
        if not m:
            continue

        date_str = m.group(1)
        txn_date = _parse_date(date_str)
        if not txn_date:
            continue

        rest = stripped[m.end():].strip()

        # Detect Dr/Cr marker
        drcr = _DRCR_RE.search(rest)
        is_credit: bool | None = None
        if drcr:
            is_credit = drcr.group(1).lower() == "cr"
            # Remove marker so it doesn't confuse the amount regex
            rest = rest[:drcr.start()] + rest[drcr.end():]

        # Extract trailing amounts
        m2 = _AMOUNTS_2.search(rest.strip())
        if m2:
            amount_value = _to_float(m2.group(1))
            balance = _to_float(m2.group(2))
            description = rest[:m2.start()].strip()

            if is_credit is not None:
                txn_type = TransactionType.credit if is_credit else TransactionType.debit
            elif last_balance is not None and balance is not None:
                txn_type = (
                    TransactionType.credit if balance > last_balance
                    else TransactionType.debit
                )
            else:
                txn_type = TransactionType.debit

            description = re.sub(r"\s+", " ", description).strip()
            if amount_value and amount_value > 0:
                transactions.append(_make_txn(txn_date, description, amount_value, balance, txn_type))
            if balance is not None:
                last_balance = balance
        else:
            m1 = _AMOUNTS_1.search(rest)
            if m1:
                amount_value = _to_float(m1.group(1))
                description = rest[:m1.start()].strip()
                description = re.sub(r"\s+", " ", description).strip()
                if amount_value and amount_value > 0:
                    txn_type = TransactionType.credit if is_credit else TransactionType.debit
                    transactions.append(_make_txn(txn_date, description, amount_value, None, txn_type))

    return transactions


# ---------------------------------------------------------------------------
# Strategy 10: Generic right-anchored text parser (fallback)

def _parse_generic(full_text: str) -> list[dict]:
    """Generic fallback: right-anchored amount extraction."""
    transactions: list[dict] = []
    last_balance: float | None = None

    date_re = re.compile(
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{1,2}\s?[A-Za-z]{3}\s?\d{4})"
    )
    trailing2 = re.compile(r"([\d,]+(?:\.\d{1,2})?)\s+([\d,]+(?:\.\d{1,2})?)\s*$")
    trailing1 = re.compile(r"([\d,]+(?:\.\d{1,2})?)\s*$")
    drcr_re = re.compile(r"\b(Dr|Cr)\b", re.IGNORECASE)

    for line in full_text.splitlines():
        stripped = line.strip()
        date_match = date_re.match(stripped)
        if not date_match:
            continue

        date_str = date_match.group(1)
        txn_date = _parse_date(date_str)
        if not txn_date:
            continue

        content = stripped[date_match.end():].strip()

        amount_value = None
        balance = None
        description = content

        m2 = trailing2.search(content)
        if m2:
            amount_value = _to_float(m2.group(1))
            balance = _to_float(m2.group(2))
            description = content[:m2.start()].strip()
        else:
            m1 = trailing1.search(content)
            if m1:
                amount_value = _to_float(m1.group(1))
                description = content[:m1.start()].strip()

        if not amount_value:
            continue

        description = re.sub(r"\s+", " ", description).strip()
        if not description:
            description = "Transaction"

        txn_type = TransactionType.debit
        drcr_match = drcr_re.search(line)
        if drcr_match:
            txn_type = (
                TransactionType.credit
                if drcr_match.group(1).lower() == "cr"
                else TransactionType.debit
            )
        elif balance is not None and last_balance is not None:
            txn_type = (
                TransactionType.credit if balance > last_balance else TransactionType.debit
            )

        transactions.append(_make_txn(txn_date, description, amount_value, balance, txn_type))
        if balance is not None:
            last_balance = balance

    return transactions


# ---------------------------------------------------------------------------
# Utility: extract raw text
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str, passwords: list[str] | None = None) -> str:
    """Extract all text from a PDF file."""
    all_text = []
    with _open_pdf_with_passwords(file_path, passwords) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text.append(text)
    return "\n".join(all_text)
