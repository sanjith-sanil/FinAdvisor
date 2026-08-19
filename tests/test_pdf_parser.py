import datetime
import pytest
from app.models.enums import TransactionType
from app.services.pdf_parser_service import (
    _parse_date,
    _to_float,
    _cell_float,
    _make_txn,
    generate_candidate_passwords,
    _parse_generic,
)


def test_pdf_parse_date():
    assert _parse_date("15/08/2024") == datetime.datetime(2024, 8, 15)
    assert _parse_date("15-08-2024") == datetime.datetime(2024, 8, 15)
    assert _parse_date("15 Aug 2024") == datetime.datetime(2024, 8, 15)
    assert _parse_date("invalid-date") is None


def test_pdf_to_float():
    assert _to_float("1,450.50") == 1450.50
    assert _to_float("250.00 Cr") == 250.00
    assert _to_float("99.99 Dr") == 99.99
    assert _to_float(None) is None
    assert _to_float("") is None
    assert _to_float("not a number") is None


def test_pdf_cell_float():
    assert _cell_float("1,200.00") == 1200.00
    assert _cell_float("nil") is None
    assert _cell_float(None) is None


def test_generate_candidate_passwords():
    passwords = generate_candidate_passwords(
        full_name="John Doe",
        date_of_birth=datetime.date(1995, 6, 25),
        phone_number="+919876543210",
        cards_last4=["4321"],
    )
    assert "john4321" in passwords or "JOHN4321" in passwords or "4321john" in passwords
    assert "john2506" in passwords or "JOHN2506" in passwords


def test_make_txn_helper():
    txn = _make_txn(
        date=datetime.datetime(2024, 8, 1, 10, 0),
        description="Swiggy Order",
        amount=450.0,
        balance=12000.0,
        txn_type=TransactionType.debit,
    )
    assert txn["amount"] == 450.0
    assert txn["description"] == "Swiggy Order"
    assert txn["transaction_type"] == TransactionType.debit

