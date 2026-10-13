import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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


class FakeClient:
    """Records each request and returns a fixed expiration."""

    def __init__(self):
        self.requests = []
        self.timeseries = self

    def get_range(self, **kwargs):
        self.requests.append(kwargs)
        return self

    def to_df(self):
        return pd.DataFrame(
            {"expiration": [pd.Timestamp("2026-03-16 14:16", tz="UTC")]}
        )


def test_fetch_expirations_requests_one_day_before_expiry():
    client = FakeClient()
    actual = fetch_expirations(client, PAIRS[:1])
    assert actual == [date(2026, 3, 16)]
    req = client.requests[0]
    assert req["schema"] == "definition"
    assert req["symbols"] == ["6EH6"]
    assert req["start"] == "2026-03-06T00:00:00+00:00"
    assert req["end"] == "2026-03-07T00:00:00+00:00"


def test_known_holiday_expiry_6EM3():
    # Databento: 6EM3 expired Fri 2023-06-16, not Mon 06-19 (Juneteenth).
    from euro_roll.expiries import expiry_date

    assert expiry_date(2023, 6) == date(2023, 6, 19)
    assert expiry_date(2023, 6, holidays={date(2023, 6, 19)}) == date(2023, 6, 16)
    row = compare_expiries(
        [("6EM3", "6EU3", date(2023, 6, 19))], [date(2023, 6, 16)]
    )[0]
    assert row[3] is False


def test_fetch_expirations_retries_transient_server_error():
    import databento as db

    class Flaky(FakeClient):
        def get_range(self, **kwargs):
            self.requests.append(kwargs)
            if len(self.requests) == 1:
                raise db.BentoServerError.__new__(db.BentoServerError)
            return self

    client = Flaky()
    assert fetch_expirations(client, PAIRS[:1]) == [date(2026, 3, 16)]
    assert len(client.requests) == 2


def test_same_raw_symbol_in_different_decades_is_not_merged():
    pairs = [("6EU6", "6EZ6", date(2016, 9, 19)), ("6EU6", "6EZ6", date(2026, 9, 14))]
    rows = compare_expiries(pairs, [date(2016, 9, 19), date(2026, 9, 14)])
    assert [r[3] for r in rows] == [True, True]
