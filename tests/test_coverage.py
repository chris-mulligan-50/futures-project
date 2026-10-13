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
    actual = {"6EH6": date(2026, 3, 16), "6EM6": date(2026, 6, 12)}
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
    assert actual == {"6EH6": date(2026, 3, 16)}
    req = client.requests[0]
    assert req["schema"] == "definition"
    assert req["symbols"] == ["6EH6"]
    assert req["start"] == "2026-03-06T00:00:00+00:00"
    assert req["end"] == "2026-03-07T00:00:00+00:00"
