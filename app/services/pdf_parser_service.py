import datetime
import re
import uuid

import pdfplumber
import pdfminer.pdfdocument
from pdfminer.pdfdocument import PDFPasswordIncorrect, PDFEncryptionError

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
    transactions: list[dict] = []
    last_balance: float | None = None

    date_regex = re.compile(r"(\d{2}[/-]\d{2}[/-]\d{4}|\d{2}\s?[A-Za-z]{3}\s?\d{4}|\d{2}\s?[A-Za-z]+\s?\d{4})")
    # Robust amount regex that doesn't split 4-digit numbers like years
    amount_regex = re.compile(r"([0-9]+(?:,[0-9]+)*(?:\.[0-9]{1,2})?)")
    drcr_regex = re.compile(r"\b(Dr|Cr)\b", re.IGNORECASE)

    with _open_pdf_with_passwords(file_path, passwords) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                stripped = line.strip()
                # Ensure the line starts with a date (filters out headers/summaries)
                date_match = date_regex.match(stripped)
                if not date_match:
                    continue

                date_str = date_match.group(1)
                txn_date = _parse_date(date_str)
                if not txn_date:
                    continue

                # Remove the date string first to prevent date numbers from matching as amounts
                line_content = stripped.replace(date_str, "").strip()
                amounts = amount_regex.findall(line_content)
                if not amounts:
                    continue

                if len(amounts) >= 2:
                    balance = _clean_amount(amounts[-1])
                    amount_value = _clean_amount(amounts[-2])
                else:
                    balance = None
                    amount_value = _clean_amount(amounts[-1])

                # Construct clean description by removing matches of the amounts
                description = line_content.strip()
                for amt in amounts:
                    description = description.replace(amt, "")
                description = re.sub(r"\s+", " ", description).strip()
                description = description.replace("Rs.", "").replace("Rs", "").strip()

                txn_type = _detect_type(amounts[-2:] if len(amounts) >= 2 else amounts, last_balance, balance)
                drcr_match = drcr_regex.search(line)
                if drcr_match:
                    txn_type = TransactionType.credit if drcr_match.group(1).lower() == "cr" else TransactionType.debit

                transactions.append(
                    {
                        "id": uuid.uuid4(),
                        "transaction_date": txn_date,
                        "description": description or line_content,
                        "amount": amount_value,
                        "balance_after": balance,
                        "transaction_type": txn_type,
                    }
                )
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

