from __future__ import annotations

from collections.abc import Iterable


BANK_DOMAINS: dict[str, dict[str, str]] = {
    # HDFC Bank
    "hdfcbank.com": {
        "bank_name": "HDFC Bank",
        "bank_code": "HDFC",
        "logo_color": "#004C8F",
    },
    "hdfcbank.net": {
        "bank_name": "HDFC Bank",
        "bank_code": "HDFC",
        "logo_color": "#004C8F",
    },
    "hdfcbank.bank.in": {
        "bank_name": "HDFC Bank",
        "bank_code": "HDFC",
        "logo_color": "#004C8F",
    },
    # State Bank of India
    "sbi.co.in": {
        "bank_name": "State Bank of India",
        "bank_code": "SBI",
        "logo_color": "#2D6DB5",
    },
    "onlinesbi.com": {
        "bank_name": "State Bank of India",
        "bank_code": "SBI",
        "logo_color": "#2D6DB5",
    },
    "sbiyono.sbi": {
        "bank_name": "State Bank of India",
        "bank_code": "SBI",
        "logo_color": "#2D6DB5",
    },
    # ICICI Bank
    "icicibank.com": {
        "bank_name": "ICICI Bank",
        "bank_code": "ICICI",
        "logo_color": "#F58220",
    },
    "iciciprulife.com": {
        "bank_name": "ICICI Prudential",
        "bank_code": "ICICI",
        "logo_color": "#F58220",
    },
    # Axis Bank
    "axisbank.com": {
        "bank_name": "Axis Bank",
        "bank_code": "AXIS",
        "logo_color": "#97144D",
    },
    "axisbank.co.in": {
        "bank_name": "Axis Bank",
        "bank_code": "AXIS",
        "logo_color": "#97144D",
    },
    # Kotak Mahindra Bank
    "kotak.com": {
        "bank_name": "Kotak Mahindra Bank",
        "bank_code": "KOTAK",
        "logo_color": "#ED1C24",
    },
    "kotakbank.com": {
        "bank_name": "Kotak Mahindra Bank",
        "bank_code": "KOTAK",
        "logo_color": "#ED1C24",
    },
    # Yes Bank
    "yesbank.in": {
        "bank_name": "Yes Bank",
        "bank_code": "YES",
        "logo_color": "#00539B",
    },
    # IndusInd Bank
    "indusind.com": {
        "bank_name": "IndusInd Bank",
        "bank_code": "INDUSIND",
        "logo_color": "#E31837",
    },
    "indusindbank.com": {
        "bank_name": "IndusInd Bank",
        "bank_code": "INDUSIND",
        "logo_color": "#E31837",
    },
    # IDFC First Bank
    "idfcfirstbank.com": {
        "bank_name": "IDFC First Bank",
        "bank_code": "IDFC",
        "logo_color": "#9B1F61",
    },
    "idfc.com": {
        "bank_name": "IDFC First Bank",
        "bank_code": "IDFC",
        "logo_color": "#9B1F61",
    },
    # Punjab National Bank
    "pnb.co.in": {
        "bank_name": "Punjab National Bank",
        "bank_code": "PNB",
        "logo_color": "#FF6600",
    },
    "pnbindia.in": {
        "bank_name": "Punjab National Bank",
        "bank_code": "PNB",
        "logo_color": "#FF6600",
    },
    # Bank of India
    "bankofindia.co.in": {
        "bank_name": "Bank of India",
        "bank_code": "BOI",
        "logo_color": "#003087",
    },
    # Bank of Baroda
    "bankofbaroda.in": {
        "bank_name": "Bank of Baroda",
        "bank_code": "BOB",
        "logo_color": "#F7941D",
    },
    "bankofbaroda.com": {
        "bank_name": "Bank of Baroda",
        "bank_code": "BOB",
        "logo_color": "#F7941D",
    },
    # Canara Bank
    "canarabank.in": {
        "bank_name": "Canara Bank",
        "bank_code": "CANARA",
        "logo_color": "#007DC5",
    },
    "canarabank.com": {
        "bank_name": "Canara Bank",
        "bank_code": "CANARA",
        "logo_color": "#007DC5",
    },
    # Union Bank of India
    "unionbankofindia.co.in": {
        "bank_name": "Union Bank of India",
        "bank_code": "UNION",
        "logo_color": "#6F1D78",
    },
    # Indian Overseas Bank
    "iob.in": {
        "bank_name": "Indian Overseas Bank",
        "bank_code": "IOB",
        "logo_color": "#003087",
    },
    # Federal Bank
    "federalbank.co.in": {
        "bank_name": "Federal Bank",
        "bank_code": "FEDERAL",
        "logo_color": "#004A97",
    },
    # RBL Bank
    "rblbank.com": {
        "bank_name": "RBL Bank",
        "bank_code": "RBL",
        "logo_color": "#ED1C24",
    },
    # South Indian Bank
    "southindianbank.com": {
        "bank_name": "South Indian Bank",
        "bank_code": "SIB",
        "logo_color": "#003087",
    },
    # Karur Vysya Bank
    "kvb.co.in": {
        "bank_name": "Karur Vysya Bank",
        "bank_code": "KVB",
        "logo_color": "#006837",
    },
    # Citibank India
    "citi.com": {
        "bank_name": "Citibank",
        "bank_code": "CITI",
        "logo_color": "#003B8E",
    },
    "citibank.com": {
        "bank_name": "Citibank",
        "bank_code": "CITI",
        "logo_color": "#003B8E",
    },
    # HSBC India
    "hsbc.co.in": {
        "bank_name": "HSBC Bank",
        "bank_code": "HSBC",
        "logo_color": "#DB0011",
    },
    "hsbc.com": {
        "bank_name": "HSBC Bank",
        "bank_code": "HSBC",
        "logo_color": "#DB0011",
    },
    # Standard Chartered
    "sc.com": {
        "bank_name": "Standard Chartered",
        "bank_code": "SCB",
        "logo_color": "#0B7F3E",
    },
    "standardchartered.com": {
        "bank_name": "Standard Chartered",
        "bank_code": "SCB",
        "logo_color": "#0B7F3E",
    },
    # DBS Bank India
    "dbs.com": {
        "bank_name": "DBS Bank",
        "bank_code": "DBS",
        "logo_color": "#DA1710",
    },
    # Bandhan Bank
    "bandhanbank.com": {
        "bank_name": "Bandhan Bank",
        "bank_code": "BANDHAN",
        "logo_color": "#D4202A",
    },
    # AU Small Finance Bank
    "aubank.in": {
        "bank_name": "AU Small Finance Bank",
        "bank_code": "AU",
        "logo_color": "#E31837",
    },
    # Paytm Payments Bank
    "paytmbank.com": {
        "bank_name": "Paytm Payments Bank",
        "bank_code": "PAYTM",
        "logo_color": "#00BAF2",
    },
    # Airtel Payments Bank
    "airtel.in": {
        "bank_name": "Airtel Payments Bank",
        "bank_code": "AIRTEL",
        "logo_color": "#ED1C24",
    },
    # NPCI / UPI related
    "npci.org.in": {
        "bank_name": "NPCI",
        "bank_code": "NPCI",
        "logo_color": "#0066B3",
    },
    # Amazon Pay
    "amazon.in": {
        "bank_name": "Amazon Pay",
        "bank_code": "AMAZON",
        "logo_color": "#FF9900",
    },
    # PhonePe
    "phonepe.com": {
        "bank_name": "PhonePe",
        "bank_code": "PHONEPE",
        "logo_color": "#5F259F",
    },
    # Google Pay
    "google.com": {
        "bank_name": "Google Pay",
        "bank_code": "GPAY",
        "logo_color": "#4285F4",
    },
    # Razorpay
    "razorpay.com": {
        "bank_name": "Razorpay",
        "bank_code": "RAZORPAY",
        "logo_color": "#3395FF",
    },
}

NON_TRANSACTIONAL_DOMAINS = {
    "accounts.google.com",
    "notifications.google.com",
}


def _domain_candidates(host: str) -> Iterable[str]:
    parts = [part for part in host.split(".") if part]
    if not parts:
        return []

    candidates: list[str] = [host]
    if len(parts) >= 2:
        candidates.append(".".join(parts[-2:]))
    if len(parts) >= 3:
        candidates.append(".".join(parts[-3:]))

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return ordered


def extract_domain_from_email(email_address: str) -> str | None:
    if not email_address or "@" not in email_address:
        return None

    domain_part = email_address.rsplit("@", 1)[-1].strip().lower()
    if not domain_part:
        return None
    if domain_part in NON_TRANSACTIONAL_DOMAINS:
        return None

    for candidate in _domain_candidates(domain_part):
        if candidate in BANK_DOMAINS:
            return candidate
    return None


def is_bank_email(email_address: str) -> bool:
    return extract_domain_from_email(email_address) is not None


def get_bank_info(email_address: str) -> dict[str, str] | None:
    matched_domain = extract_domain_from_email(email_address)
    if not matched_domain:
        return None

    bank = BANK_DOMAINS[matched_domain]
    return {
        "bank_name": bank["bank_name"],
        "bank_code": bank["bank_code"],
        "logo_color": bank["logo_color"],
        "sender_email": email_address.strip().lower(),
        "domain": matched_domain,
    }


def get_all_bank_domains() -> list[str]:
    return sorted(BANK_DOMAINS.keys())
