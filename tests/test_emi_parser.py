import pytest
from app.services.emi_parser_service import (
    looks_like_emi_email,
    extract_card_last4_from_email,
    parse_emi_details,
)


def test_looks_like_emi_email():
    valid_text = (
        "Smart EMI Loan Summary. Loan Number: LN123456. "
        "Loan Amount: Rs. 50,000.00. Loan Tenure: 12 months. Pending Instalments: 6. "
        "Monthly Instalment Amount: Rs. 4,500.00."
    )
    assert looks_like_emi_email(valid_text) is True

    non_emi_text = "Here is your monthly statement for credit card ending in 1234. Minimum amount due is Rs. 1,000."
    assert looks_like_emi_email(non_emi_text) is False


def test_extract_card_last4_from_email():
    text1 = "Your Smart EMI on credit card ending in 4321 is active."
    assert extract_card_last4_from_email(text1) == "4321"

    text2 = "Transaction on card **1234 has been converted to EMI."
    assert extract_card_last4_from_email(text2) == "1234"

    text3 = "No card details mentioned in this email."
    assert extract_card_last4_from_email(text3) is None


def test_parse_emi_details_empty():
    assert parse_emi_details("") == []
    assert parse_emi_details("Just a normal email with no table data.") == []
