import enum


class AccountType(str, enum.Enum):
    savings = "savings"
    current = "current"
    salary = "salary"


class CardType(str, enum.Enum):
    credit = "credit"
    debit = "debit"


class CardNetwork(str, enum.Enum):
    visa = "visa"
    mastercard = "mastercard"
    rupay = "rupay"
    amex = "amex"
    other = "other"


class BenefitCategory(str, enum.Enum):
    cashback = "cashback"
    rewards = "rewards"
    lounge = "lounge"
    insurance = "insurance"
    fuel = "fuel"
    dining = "dining"
    shopping = "shopping"
    travel = "travel"
    emi = "emi"
    other = "other"


class TransactionType(str, enum.Enum):
    debit = "debit"
    credit = "credit"


class SmsSourceType(str, enum.Enum):
    sms = "sms"
    email = "email"


class TransactionSource(str, enum.Enum):
    sms = "sms"
    email = "email"
    pdf_upload = "pdf_upload"
    manual = "manual"


class EmailAuthType(str, enum.Enum):
    imap_password = "imap_password"
    oauth = "oauth"


class CollectionLogType(str, enum.Enum):
    email_check = "email_check"
    sms_received = "sms_received"
    error = "error"


class CollectionSource(str, enum.Enum):
    imap = "imap"
    oauth = "oauth"
    sms_webhook = "sms_webhook"
    manual = "manual"


class PdfStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
