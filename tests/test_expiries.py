import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from euro_roll.expiries import (  # noqa: E402
    contract_symbol,
    expiry_date,
    roll_calendar,
    third_wednesday,
)


def test_third_wednesday():
    assert third_wednesday(2026, 3) == date(2026, 3, 18)
    assert third_wednesday(2026, 6) == date(2026, 6, 17)
    assert third_wednesday(2026, 9) == date(2026, 9, 16)
    assert third_wednesday(2026, 12) == date(2026, 12, 16)


def test_known_expiries_2026():
    assert expiry_date(2026, 3) == date(2026, 3, 16)
    assert expiry_date(2026, 6) == date(2026, 6, 15)
    assert expiry_date(2026, 9) == date(2026, 9, 14)
    assert expiry_date(2026, 12) == date(2026, 12, 14)


def test_known_expiries_2025():
    assert expiry_date(2025, 3) == date(2025, 3, 17)
    assert expiry_date(2025, 12) == date(2025, 12, 15)


def test_expiry_is_two_business_days_before_third_wednesday():
    for y in range(2010, 2027):
        for m in (3, 6, 9, 12):
            e = expiry_date(y, m, holidays=set())
            assert e.weekday() == 0  # always a Monday without holidays
            assert (third_wednesday(y, m) - e).days == 2


def test_holiday_pushes_expiry_earlier():
    # If Monday Mar 16 were a holiday, expiry moves to the prior Friday.
    assert expiry_date(2026, 3, holidays={date(2026, 3, 16)}) == date(2026, 3, 13)


def test_contract_symbol():
    assert contract_symbol(2026, 3) == "6EH6"
    assert contract_symbol(2026, 12) == "6EZ6"
    assert contract_symbol(2027, 3) == "6EH7"


def test_roll_calendar_pairs_and_year_wrap():
    cal = roll_calendar(2026, 2026)
    assert [p[0] for p in cal] == ["6EH6", "6EM6", "6EU6", "6EZ6"]
    assert [p[1] for p in cal] == ["6EM6", "6EU6", "6EZ6", "6EH7"]
    assert cal[0] == ("6EH6", "6EM6", date(2026, 3, 16))


def test_roll_calendar_length_and_order():
    cal = roll_calendar(2010, 2026)
    assert len(cal) == 17 * 4
    expiries = [p[2] for p in cal]
    assert expiries == sorted(expiries)

def test_juneteenth_moves_6em3_expiry():
    assert expiry_date(2023, 6) == date(2023, 6, 16)
    assert expiry_date(2023, 6, holidays=set()) == date(2023, 6, 19)