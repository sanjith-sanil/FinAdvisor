import datetime
import re
from typing import Any


SMS_SENDER_MAP: dict[str, dict[str, str]] = {
    "BK-HDFC": {"bank_name": "HDFC Bank", "bank_code": "HDFC"},
    "HDFCBK": {"bank_name": "HDFC Bank", "bank_code": "HDFC"},
    "BK-SBI": {"bank_name": "State Bank of India", "bank_code": "SBI"},
    "SBISMS": {"bank_name": "State Bank of India", "bank_code": "SBI"},
    "BK-ICICI": {"bank_name": "ICICI Bank", "bank_code": "ICICI"},
    "ICICIB": {"bank_name": "ICICI Bank", "bank_code": "ICICI"},
    "BK-AXIS": {"bank_name": "Axis Bank", "bank_code": "AXIS"},
    "AXISBK": {"bank_name": "Axis Bank", "bank_code": "AXIS"},
    "BK-KOTAK": {"bank_name": "Kotak Mahindra Bank", "bank_code": "KOTAK"},
    "KOTAKB": {"bank_name": "Kotak Mahindra Bank", "bank_code": "KOTAK"},
    "BK-YES": {"bank_name": "Yes Bank", "bank_code": "YES"},
    "YESBNK": {"bank_name": "Yes Bank", "bank_code": "YES"},
    "BK-INDB": {"bank_name": "IndusInd Bank", "bank_code": "INDUSIND"},
    "INDBNK": {"bank_name": "IndusInd Bank", "bank_code": "INDUSIND"},
    "BK-IDFC": {"bank_name": "IDFC First Bank", "bank_code": "IDFC"},
    "IDFCBK": {"bank_name": "IDFC First Bank", "bank_code": "IDFC"},
    "BK-PNB": {"bank_name": "Punjab National Bank", "bank_code": "PNB"},
    "PNBSMS": {"bank_name": "Punjab National Bank", "bank_code": "PNB"},
    "BK-BOI": {"bank_name": "Bank of India", "bank_code": "BOI"},
    "BOISMS": {"bank_name": "Bank of India", "bank_code": "BOI"},
    "BK-BOB": {"bank_name": "Bank of Baroda", "bank_code": "BOB"},
    "BOBSMS": {"bank_name": "Bank of Baroda", "bank_code": "BOB"},
    "BK-RBL": {"bank_name": "RBL Bank", "bank_code": "RBL"},
    "RBLBNK": {"bank_name": "RBL Bank", "bank_code": "RBL"},
    "BK-FED": {"bank_name": "Federal Bank", "bank_code": "FEDERAL"},
    "FEDBK": {"bank_name": "Federal Bank", "bank_code": "FEDERAL"},
}


_SENDER_KEYWORD_FALLBACK: dict[str, dict[str, str]] = {
    "HDFC": {"bank_name": "HDFC Bank", "bank_code": "HDFC"},
    "SBI": {"bank_name": "State Bank of India", "bank_code": "SBI"},
    "ICICI": {"bank_name": "ICICI Bank", "bank_code": "ICICI"},
    "AXIS": {"bank_name": "Axis Bank", "bank_code": "AXIS"},
    "KOTAK": {"bank_name": "Kotak Mahindra Bank", "bank_code": "KOTAK"},
    "YES": {"bank_name": "Yes Bank", "bank_code": "YES"},
    "INDUS": {"bank_name": "IndusInd Bank", "bank_code": "INDUSIND"},
    "IDFC": {"bank_name": "IDFC First Bank", "bank_code": "IDFC"},
    "PNB": {"bank_name": "Punjab National Bank", "bank_code": "PNB"},
    "BOI": {"bank_name": "Bank of India", "bank_code": "BOI"},
    "BOB": {"bank_name": "Bank of Baroda", "bank_code": "BOB"},
    "RBL": {"bank_name": "RBL Bank", "bank_code": "RBL"},
    "FED": {"bank_name": "Federal Bank", "bank_code": "FEDERAL"},
}


AMOUNT_PATTERNS = [
    re.compile(
        r"(?:debited|credited|received|refund|cashback|payment|purchase|withdrawn|spent|charged|paid)\b[^\d]{0,40}(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?).{0,40}(?:credited|received|refund|cashback)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:amount|transaction amount)[\s:]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"(?:debit|credit)\s+of\s+(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
]


BALANCE_PATTERNS = [
    re.compile(r"(?:available\s+balance|avl\.?\s*bal(?:ance)?|avail\.?\s*bal(?:ance)?|total\s+avl\.?\s*bal(?:ance)?|total\s+avail\.?\s*bal(?:ance)?)\s*[:\-]?\s*(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"(?:current\s+balance|outstanding|balance\s+after|bal(?:ance)?\s+is|total\s+balance)\s*[:\-]?\s*(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"(?:total\s+avl\.?\s*bal(?:ance)?|avl\.?\s*bal(?:ance)?)\s*(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    re.compile(r"available\s+credit\s+limit\s+(?:is\s+)?(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
]


MERCHANT_PATTERNS = [
    re.compile(r"merchant(?:\s+name)?\s*[:\-]\s*([A-Za-z0-9 &._\-]{2,80})", re.IGNORECASE),
    re.compile(r"\bat\s+([A-Za-z0-9 &._\-]{2,80})", re.IGNORECASE),
    re.compile(r"\btowards\s+([A-Za-z0-9 &._\-]{2,80})", re.IGNORECASE),
    re.compile(r"info\s*[:\-]\s*([A-Za-z0-9 &._\-]{2,80})", re.IGNORECASE),
    re.compile(r"payee\s*[:\-]\s*([A-Za-z0-9 &._\-]{2,80})", re.IGNORECASE),
    re.compile(r"payment\s+of\s+(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d{1,2})?\s+made\s+to\s+([A-Za-z0-9 &._\-]{2,80})", re.IGNORECASE),
    re.compile(r"purchase\s+of\s+(?:Rs\.?|INR|₹)\s*[\d,]+(?:\.\d{1,2})?\s+at\s+([A-Za-z0-9 &._\-]{2,80})", re.IGNORECASE),
]


REFERENCE_PATTERNS = [
    re.compile(r"ref\s*no\.?\s*[:\-]?\s*([A-Za-z0-9]{6,})", re.IGNORECASE),
    re.compile(r"reference\s+number\s*[:\-]?\s*([A-Za-z0-9]{6,})", re.IGNORECASE),
    re.compile(r"upi\s*ref\s*[:\-]?\s*([A-Za-z0-9]{6,})", re.IGNORECASE),
    re.compile(r"transaction\s*id\s*[:\-]?\s*([A-Za-z0-9]{6,})", re.IGNORECASE),
    re.compile(r"(?:rrn|utr|txn)\s*(?:no\.?|id)?\s*[:\-]?\s*([A-Za-z0-9]{6,})", re.IGNORECASE),
]


DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})\b"),
    re.compile(r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\b"),
]


CARD_LAST4_PATTERN = re.compile(r"(?:card\s*(?:ending|xx|x{2,4}|\*{2,4})\s*[:\-]?)\s*(\d{4})", re.IGNORECASE)
ACCOUNT_LAST4_PATTERN = re.compile(r"(?:a/?c|account)\s*(?:no\.?|number|xx|x{2,4}|\*{2,4})\s*[:\-]?\s*(\d{4})", re.IGNORECASE)


TRANSACTION_ALERT_PATTERNS = [
    re.compile(r"\b(?:has\s+been\s+)?(?:debited|credited)\b", re.IGNORECASE),
    re.compile(r"\b(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d{1,2})?.{0,80}\b(?:debited|credited)\b", re.IGNORECASE),
    re.compile(r"\bamount\s+of\s+(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d{1,2})?.{0,80}\b(?:debited|credited)\b", re.IGNORECASE),
    re.compile(r"\b(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d{1,2})?.{0,80}\breceived\b.{0,80}\b(?:account|a/c|upi)\b", re.IGNORECASE),
    re.compile(r"\breceived\b.{0,80}\b(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d{1,2})?.{0,80}\b(?:account|a/c|upi)\b", re.IGNORECASE),
    re.compile(r"\b(?:refund|cashback)\b.{0,80}\b(?:rs\.?|inr|₹)\s*[\d,]+(?:\.\d{1,2})?", re.IGNORECASE),
    re.compile(r"\b(?:upi|imps|neft|atm)\s+transaction\s+(?:alert|reference|ref)", re.IGNORECASE),
    re.compile(r"\btransaction\s+(?:alert|reference|ref|id)\b", re.IGNORECASE),
]


NON_TRANSACTION_EMAIL_PATTERNS = [
    re.compile(r"\blifetime\s+free\b", re.IGNORECASE),
    re.compile(r"\b(?:amazon\s+)?voucher\b", re.IGNORECASE),
    re.compile(r"\bapply\s+(?:today|now)\b", re.IGNORECASE),
    re.compile(r"\boffer\s+(?:valid|ends|expires)\b", re.IGNORECASE),
    re.compile(r"\bcredit\s+card\s+(?:is\s+)?(?:waiting|offer|mailer)\b", re.IGNORECASE),
    re.compile(r"\bgmail\s+(?:storage|will\s+stop\s+working)\b", re.IGNORECASE),
    re.compile(r"\bgoogle\s+account\s+storage\b", re.IGNORECASE),
    re.compile(r"\bsecurity\s+alert\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+maintenance\b", re.IGNORECASE),
    re.compile(r"\bpayment\s+requested\b", re.IGNORECASE),
    re.compile(r"\bamount\s+due\b", re.IGNORECASE),
]


DEBIT_KEYWORDS = [
    "debited",
    "debit",
    "spent",
    "payment",
    "purchase",
    "withdrawn",
    "used for",
    "transaction of",
    "charged",
    "paid",
    "outward",
]

CREDIT_KEYWORDS = [
    "credited",
    "credit",
    "received",
    "deposited",
    "refund",
    "cashback",
    "inward",
    "transfer in",
    "credited to",
    "received from",
    "neft credit",
    "imps credit",
    "upi credit",
    "salary",
    "interest",
]


def _find_first_keyword_index(text: str, keywords: list[str]) -> int | None:
    lowest = None
    for keyword in keywords:
        idx = text.find(keyword)
        if idx >= 0:
            lowest = idx if lowest is None else min(lowest, idx)
    return lowest


def _detect_txn_type(text: str) -> str | None:
    lowered = text.lower()
    debit_idx = _find_first_keyword_index(lowered, DEBIT_KEYWORDS)
    credit_idx = _find_first_keyword_index(lowered, CREDIT_KEYWORDS)

    cr_match = re.search(r"\bcr\b", lowered)
    dr_match = re.search(r"\bdr\b", lowered)
    if cr_match:
        credit_idx = cr_match.start() if credit_idx is None else min(credit_idx, cr_match.start())
    if dr_match:
        debit_idx = dr_match.start() if debit_idx is None else min(debit_idx, dr_match.start())

    if debit_idx is None and credit_idx is None:
        return None
    if debit_idx is None:
        return "credit"
    if credit_idx is None:
        return "debit"
    return "credit" if credit_idx < debit_idx else "debit"


def _sentence_window(text: str, index: int) -> str:
    if index < 0:
        return text
    left = text.rfind(". ", 0, index)
    left_nl = text.rfind("\n", 0, index)
    left = max(left, left_nl)
    right = text.find(". ", index)
    right_nl = text.find("\n", index)
    candidates = [value for value in [right, right_nl] if value != -1]
    right = min(candidates) if candidates else len(text)
    start = left + 2 if left != -1 else 0
    end = right if right != -1 else len(text)
    return text[start:end].strip()


def _extract_amount_with_index(text: str) -> tuple[float | None, int | None]:
    balance_context = re.compile(r"bal|balance|available\s+balance|avl\.?\s*bal|avail\.?\s*bal", re.IGNORECASE)
    for pattern in AMOUNT_PATTERNS:
        for match in pattern.finditer(text):
            amount_text = match.group(1)
            amount = _to_float(amount_text)
            if amount is None:
                continue
            context_start = max(0, match.start() - 20)
            context_end = min(len(text), match.end() + 20)
            context = text[context_start:context_end]
            if balance_context.search(context):
                continue
            return amount, match.start()
    return None, None


def _to_float(amount_text: str | None) -> float | None:
    if not amount_text:
        return None
    try:
        return float(amount_text.replace(",", "").strip())
    except ValueError:
        return None


def _extract_first(text: str, patterns: list[re.Pattern[str]]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            if value:
                return value.rstrip(".,")
    return None


def _extract_transaction_date(text: str) -> datetime.datetime | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(1)
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y", "%d %b %Y", "%d %B %Y", "%d %b %y", "%d %B %y"):
            try:
                return datetime.datetime.strptime(raw, fmt)
            except ValueError:
                continue
    return None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def looks_like_transaction_alert(text: str) -> bool:
    normalized = _normalize_text(text or "")
    if not normalized:
        return False

    has_transaction_evidence = any(pattern.search(normalized) for pattern in TRANSACTION_ALERT_PATTERNS)
    if not has_transaction_evidence:
        return False

    return not any(pattern.search(normalized) for pattern in NON_TRANSACTION_EMAIL_PATTERNS)


def detect_bank_from_sender(sender: str | None) -> dict[str, str]:
    sender_upper = (sender or "").upper().strip()
    if sender_upper in SMS_SENDER_MAP:
        return SMS_SENDER_MAP[sender_upper]

    for keyword, bank_info in _SENDER_KEYWORD_FALLBACK.items():
        if keyword in sender_upper:
            return bank_info

    return {"bank_name": "Unknown Bank", "bank_code": "UNKNOWN"}


def parse_sms(text: str, sender: str | None = None) -> dict[str, Any] | None:
    normalized = _normalize_text(text or "")
    if not normalized:
        return None

    amount, amount_idx = _extract_amount_with_index(normalized)
    if amount is None:
        return None

    sentence = _sentence_window(normalized, amount_idx or 0)
    window_start = max(0, (amount_idx or 0) - 80)
    window_end = min(len(normalized), (amount_idx or 0) + 80)
    window_text = normalized[window_start:window_end]

    txn_type = (
        _detect_txn_type(sentence)
        or _detect_txn_type(window_text)
        or _detect_txn_type(normalized)
        or "debit"
    )

    bank_info = detect_bank_from_sender(sender or normalized)
    card_match = CARD_LAST4_PATTERN.search(normalized)
    account_match = ACCOUNT_LAST4_PATTERN.search(normalized)

    return {
        "transaction_type": txn_type,
        "amount": amount,
        "merchant_name": _extract_first(normalized, MERCHANT_PATTERNS),
        "balance_after": _to_float(_extract_first(normalized, BALANCE_PATTERNS)),
        "reference_number": _extract_first(normalized, REFERENCE_PATTERNS),
        "transaction_date": _extract_transaction_date(normalized),
        "card_last4": card_match.group(1) if card_match else None,
        "account_last4": account_match.group(1) if account_match else None,
        "bank_name": bank_info["bank_name"],
        "bank_code": bank_info["bank_code"],
    }
