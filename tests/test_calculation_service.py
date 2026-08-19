import datetime
from decimal import Decimal
import pytest

from app.services.calculation_service import (
    safe_float,
    safe_int,
    safe_div,
    get_utilization_color,
    calculate_minimum_payment_due,
    days_until_due,
)


def test_safe_converters():
    # safe_float
    assert safe_float(10.5) == 10.5
    assert safe_float("25.75") == 25.75
    assert safe_float(Decimal("100.25")) == 100.25
    assert safe_float(None, default=5.0) == 5.0
    assert safe_float("invalid", default=0.0) == 0.0

    # safe_int
    assert safe_int(10) == 10
    assert safe_int("42") == 42
    assert safe_int(None, default=1) == 1
    assert safe_int("abc", default=-1) == -1

    # safe_div
    assert safe_div(100.0, 2.0) == 50.0
    assert safe_div(100.0, 0.0, default=0.0) == 0.0
    assert safe_div(100.0, None, default=0.0) == 0.0


def test_get_utilization_color():
    assert get_utilization_color(15.0) == "#10B981"  # green (< 30%)
    assert get_utilization_color(45.0) == "#F59E0B"  # yellow (30-60%)
    assert get_utilization_color(85.0) == "#EF4444"  # red (> 60%)


def test_calculate_minimum_payment_due():
    assert calculate_minimum_payment_due(0.0) == 0.0
    assert calculate_minimum_payment_due(-500.0) == 0.0
    # Minimum is 500 when 5% of balance is less than 500
    assert calculate_minimum_payment_due(4000.0) == 500.0  # 5% is 200 -> 500
    # 5% of 20000 is 1000 (> 500)
    assert calculate_minimum_payment_due(20000.0) == 1000.0


def test_days_until_due():
    assert days_until_due(None) is None
    fixed_now = datetime.datetime(2024, 7, 10, tzinfo=datetime.timezone.utc)
    # Due on 15th -> 5 days remaining
    assert days_until_due(15, now=fixed_now) == 5
    # Due on 10th (today) -> 0 days
    assert days_until_due(10, now=fixed_now) == 0
