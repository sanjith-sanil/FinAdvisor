import pytest
from app.services.sms_parser_service import parse_sms, detect_bank_from_sender, looks_like_transaction_alert


def test_detect_bank_from_sender():
    assert detect_bank_from_sender("HDFCBK")["bank_code"] == "HDFC"
    assert detect_bank_from_sender("SBISMS")["bank_code"] == "SBI"
    assert detect_bank_from_sender("ICICIB")["bank_code"] == "ICICI"
    assert detect_bank_from_sender("AXISBK")["bank_code"] == "AXIS"
    assert detect_bank_from_sender("KOTAKB")["bank_code"] == "KOTAK"
    assert detect_bank_from_sender("UNKNOWN_SENDER")["bank_code"] == "UNKNOWN"


def test_looks_like_transaction_alert():
    # Valid transaction alerts
    assert looks_like_transaction_alert("Rs. 1,450.00 debited from HDFC Bank A/c xx1234 on 15-Aug-24") is True
    assert looks_like_transaction_alert("INR 500 credited to your account ending 5678 as cashback") is True
    
    # Non-transactional messages
    assert looks_like_transaction_alert("Your OTP for login is 492810. Do not share with anyone.") is False
    assert looks_like_transaction_alert("Dear Customer, your password has been successfully reset.") is False


def test_parse_hdfc_debit_sms():
    msg = "Rs. 2,499.00 debited from A/c xx4321 on 12-Jul-24 at AMAZON INDIA. Avl Bal: Rs. 45,210.50. Ref: 419201928"
    result = parse_sms(msg, sender="HDFCBK")
    assert result is not None
    assert result["transaction_type"] == "debit"
    assert result["amount"] == 2499.00
    assert result["card_last4"] == "4321" or result["account_last4"] == "4321"
    assert result["bank_code"] == "HDFC"


def test_parse_icici_credit_sms():
    msg = "Dear Customer, INR 10,000.00 credited to Card ending in 9876 on 10-May-2024. Avl Limit: INR 90,000.00."
    result = parse_sms(msg, sender="ICICIB")
    assert result is not None
    assert result["transaction_type"] == "credit"
    assert result["amount"] == 10000.00
    assert result["bank_code"] == "ICICI"


def test_parse_non_transaction_returns_none():
    msg = "Welcome to FinAdvisor! Please verify your phone number using OTP 889900."
    result = parse_sms(msg)
    assert result is None
