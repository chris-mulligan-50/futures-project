import sys
from datetime import date
from pathlib import Path

import databento as db
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from euro_roll import coverage  # noqa: E402
from euro_roll.coverage import compare_expiries, fetch_expirations  # noqa: E402

PAIRS = [
    ("6EH6", "6EM6", date(2026, 3, 16)),
    ("6EM6", "6EU6", date(2026, 6, 15)),
]


def test_compare_expiries_flags_mismatch():
    actual = [date(2026, 3, 16), date(2026, 6, 12)]
    assert compare_expiries(PAIRS, actual) == [
        ("6EH6", date(2026, 3, 16), date(2026, 3, 16), True),
        ("6EM6", date(2026, 6, 15), date(2026, 6, 12), False),
    ]


def stub_definitions(monkeypatch, failures=0):
    """Replace ``fetch_definitions`` so no client, network or cache is used.

    Returns the list of recorded (symbols, start, end) calls. The first
    ``failures`` calls raise a server error.
    """
    calls = []

    def fake(symbols, start, end, client=None):
        calls.append((symbols, start, end))
        if len(calls) <= failures:
            raise db.BentoServerError.__new__(db.BentoServerError)
        return pd.DataFrame(
            {"expiration": [pd.Timestamp("2026-03-16 14:16", tz="UTC")]}
        )

    monkeypatch.setattr(coverage, "fetch_definitions", fake)
    return calls


def test_fetch_expirations_requests_one_day_before_expiry(monkeypatch):
    calls = stub_definitions(monkeypatch)
    assert fetch_expirations(None, PAIRS[:1]) == [date(2026, 3, 16)]
    assert calls == [(["6EH6"], date(2026, 3, 6), date(2026, 3, 7))]


def test_known_holiday_expiry_6EM3():
    # Databento: 6EM3 expired Fri 2023-06-16, not Mon 06-19 (Juneteenth).
    from euro_roll.expiries import expiry_date

    assert expiry_date(2023, 6) == date(2023, 6, 19)
    assert expiry_date(2023, 6, holidays={date(2023, 6, 19)}) == date(2023, 6, 16)
    row = compare_expiries(
        [("6EM3", "6EU3", date(2023, 6, 19))], [date(2023, 6, 16)]
    )[0]
    assert row[3] is False


def test_fetch_expirations_retries_transient_server_error(monkeypatch):
    calls = stub_definitions(monkeypatch, failures=1)
    assert fetch_expirations(None, PAIRS[:1]) == [date(2026, 3, 16)]
    assert len(calls) == 2


def test_same_raw_symbol_in_different_decades_is_not_merged():
    pairs = [("6EU6", "6EZ6", date(2016, 9, 19)), ("6EU6", "6EZ6", date(2026, 9, 14))]
    rows = compare_expiries(pairs, [date(2016, 9, 19), date(2026, 9, 14)])
    assert [r[3] for r in rows] == [True, True]
