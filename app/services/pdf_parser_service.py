import datetime
import re
import uuid

import pdfplumber
import pdfminer.pdfdocument
from pdfminer.pdfdocument import PDFPasswordIncorrect, PDFEncryptionError

from app.models.enums import TransactionType


_DATE_PATTERNS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y",
    "%d-%b-%Y", "%d-%B-%Y", "%d/%b/%Y", "%d/%B/%Y"
]


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


def generate_candidate_passwords(
    full_name: str,
    date_of_birth: datetime.date | None = None,
    phone_number: str | None = None,
    cards_last4: list[str] | None = None,
) -> list[str]:
    candidates = []

    # Clean name: keep only letters
    name_clean = "".join(c for c in full_name if c.isalpha())
    if not name_clean:
        name_clean = "user"

    name_4_lower = name_clean[:4].lower()
    name_4_upper = name_clean[:4].upper()

    # Extract date parts if DOB exists
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
        candidates.append(f"{name_4_lower}{ddmm}")
        candidates.append(f"{name_4_upper}{ddmm}")

    if cards_last4:
        for last4 in cards_last4:
            candidates.append(f"{name_4_upper}{last4}")
            candidates.append(f"{name_4_lower}{last4}")
            if ddmmyyyy:
                candidates.append(f"{ddmmyyyy}{last4}")

    if ddmmyyyy:
        candidates.append(ddmmyyyy)
        candidates.append(ddmm)

    if phone_number:
        phone_clean = "".join(c for c in phone_number if c.isdigit())
        if len(phone_clean) >= 4:
            candidates.append(phone_clean[-4:])
        candidates.append(phone_clean)

    # Maintain uniqueness and order
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    return unique_candidates


def parse_pdf(file_path: str, passwords: list[str] | None = None) -> list[dict]:
    """Parse credit-card / bank statement PDFs into transaction dicts.

    Strategy 1:  Use pdfplumber's table extraction which preserves column
                 boundaries and avoids mixing description numbers with amounts.
    Strategy 2:  Fall back to text-line parsing with a *right-anchored*
                 amount regex so only the trailing numeric columns are captured.
    """
    with _open_pdf_with_passwords(file_path, passwords) as pdf:
        # --- Strategy 1: table-based extraction ---
        transactions = _parse_via_tables(pdf)
        if transactions:
            return transactions

        # --- Strategy 2: improved text-based extraction ---
        return _parse_via_text(pdf)


# ---------------------------------------------------------------------------
# Strategy 1 — table extraction
# ---------------------------------------------------------------------------

_DATE_REGEX = re.compile(
    r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{2}\s?[A-Za-z]{3,9}\s?\d{4})"
)
_AMOUNT_CELL = re.compile(r"^[\s]*-?[\d,]+(?:\.\d{1,2})?[\s]*$")


def _cell_to_float(cell: str | None) -> float | None:
    """Convert a table cell string to float, tolerating commas / whitespace."""
    if cell is None:
        return None
    cleaned = cell.strip().replace(",", "").replace(" ", "")
    if not cleaned or cleaned == "-" or cleaned == "":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_via_tables(pdf) -> list[dict]:
    transactions: list[dict] = []
    last_balance: float | None = None

    for page in pdf.pages:
        tables = page.extract_tables() or []
        for table in tables:
            if not table or len(table) < 2:
                continue

            # Try to identify header row to find column indices
            header_row = table[0]
            if not header_row:
                continue

            # Normalise header cells
            headers = [
                (h or "").strip().lower().replace("\n", " ")
                for h in header_row
            ]

            date_col = _find_col(headers, ["date", "txn date", "transaction date", "trans date", "posting date"])
            desc_col = _find_col(headers, ["description", "narration", "particulars", "details", "transaction details"])
            amt_col  = _find_col(headers, ["amount", "txn amount", "transaction amount", "debit", "dr amount"])
            cr_col   = _find_col(headers, ["credit", "cr amount", "cr"])
            dr_col   = _find_col(headers, ["debit", "dr amount", "dr"])
            bal_col  = _find_col(headers, ["balance", "closing balance", "running balance"])

            # Must at least have date + some amount column
            if date_col is None or (amt_col is None and dr_col is None):
                continue

            for row in table[1:]:
                if not row or len(row) <= max(c for c in [date_col, desc_col, amt_col, cr_col, dr_col, bal_col] if c is not None):
                    continue

                # Parse date
                raw_date = (row[date_col] or "").strip()
                date_match = _DATE_REGEX.search(raw_date)
                if not date_match:
                    continue
                txn_date = _parse_date(date_match.group(1))
                if not txn_date:
                    continue

                # Parse description
                description = (row[desc_col] or "").strip() if desc_col is not None else ""
                description = re.sub(r"\s+", " ", description).strip()

                # Parse amount(s)
                amount_value = 0.0
                txn_type = TransactionType.debit

                if dr_col is not None and cr_col is not None:
                    # Separate Dr / Cr columns
                    dr_val = _cell_to_float(row[dr_col] if dr_col < len(row) else None)
                    cr_val = _cell_to_float(row[cr_col] if cr_col < len(row) else None)
                    if dr_val and dr_val > 0:
                        amount_value = dr_val
                        txn_type = TransactionType.debit
                    elif cr_val and cr_val > 0:
                        amount_value = cr_val
                        txn_type = TransactionType.credit
                    else:
                        continue
                elif amt_col is not None:
                    val = _cell_to_float(row[amt_col] if amt_col < len(row) else None)
                    if val is None:
                        continue
                    amount_value = abs(val)
                    # Negative amounts or Cr suffix → credit
                    raw_amt = (row[amt_col] or "").strip().lower()
                    if val < 0 or "cr" in raw_amt:
                        txn_type = TransactionType.credit
                    else:
                        txn_type = TransactionType.debit
                else:
                    continue

                # Parse balance
                balance = _cell_to_float(row[bal_col] if bal_col is not None and bal_col < len(row) else None)

                # Detect type from balance delta if available
                if balance is not None and last_balance is not None:
                    if balance > last_balance:
                        txn_type = TransactionType.credit
                    elif balance < last_balance:
                        txn_type = TransactionType.debit

                transactions.append({
                    "id": uuid.uuid4(),
                    "transaction_date": txn_date,
                    "description": description or "Transaction",
                    "amount": amount_value,
                    "balance_after": balance,
                    "transaction_type": txn_type,
                })
                if balance is not None:
                    last_balance = balance

    return transactions


def _find_col(headers: list[str], candidates: list[str]) -> int | None:
    """Find the first header column whose text contains one of the candidates."""
    for i, h in enumerate(headers):
        for c in candidates:
            if c in h:
                return i
    return None


# ---------------------------------------------------------------------------
# Strategy 2 — improved text-line parsing (right-anchored amounts)
# ---------------------------------------------------------------------------

def _parse_via_text(pdf) -> list[dict]:
    transactions: list[dict] = []
    last_balance: float | None = None

    date_regex = re.compile(
        r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{2}\s?[A-Za-z]{3}\s?\d{4}|\d{2}\s?[A-Za-z]+\s?\d{4})"
    )

    # Right-anchored: capture 1–3 trailing amounts at the end of the line.
    # This prevents numbers embedded in descriptions (like "299" in
    # "SPOTIFY SI MUMBAI IN 299") from being treated as transaction amounts.
    trailing_amounts_regex = re.compile(
        r"([\d,]+(?:\.\d{1,2})?)\s+([\d,]+(?:\.\d{1,2})?)\s*$"
    )
    single_amount_regex = re.compile(
        r"([\d,]+(?:\.\d{1,2})?)\s*$"
    )

    drcr_regex = re.compile(r"\b(Dr|Cr)\b", re.IGNORECASE)

    for page in pdf.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            stripped = line.strip()
            date_match = date_regex.match(stripped)
            if not date_match:
                continue

            date_str = date_match.group(1)
            txn_date = _parse_date(date_str)
            if not txn_date:
                continue

            # Work with the part after the date
            line_content = stripped[date_match.end():].strip()

            # Try to find 2 trailing amounts (amount + balance)
            amount_value = None
            balance = None
            description = line_content

            two_match = trailing_amounts_regex.search(line_content)
            if two_match:
                amount_value = _clean_amount(two_match.group(1))
                balance = _clean_amount(two_match.group(2))
                description = line_content[:two_match.start()].strip()
            else:
                one_match = single_amount_regex.search(line_content)
                if one_match:
                    amount_value = _clean_amount(one_match.group(1))
                    description = line_content[:one_match.start()].strip()

            if amount_value is None:
                continue

            # Clean up description
            description = re.sub(r"\s+", " ", description).strip()
            description = description.replace("Rs.", "").replace("Rs", "").strip()
            if not description:
                description = "Transaction"

            # Determine transaction type
            txn_type = TransactionType.debit
            drcr_match = drcr_regex.search(line)
            if drcr_match:
                txn_type = (
                    TransactionType.credit
                    if drcr_match.group(1).lower() == "cr"
                    else TransactionType.debit
                )
            elif balance is not None and last_balance is not None:
                txn_type = (
                    TransactionType.credit
                    if balance > last_balance
                    else TransactionType.debit
                )

            transactions.append({
                "id": uuid.uuid4(),
                "transaction_date": txn_date,
                "description": description,
                "amount": amount_value,
                "balance_after": balance,
                "transaction_type": txn_type,
            })
            if balance is not None:
                last_balance = balance

    return transactions



def extract_text_from_pdf(file_path: str, passwords: list[str] | None = None) -> str:
    """Extract all text from a PDF file."""
    all_text = []
    with _open_pdf_with_passwords(file_path, passwords) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text.append(text)
    return "\n".join(all_text)

