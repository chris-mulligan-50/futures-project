import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from euro_roll import download  # noqa: E402
from euro_roll.download import (  # noqa: E402
    fetch,
    fetch_bbo_1m,
    fetch_daily_bars,
    fetch_definitions,
    spread_symbol,
)


class FakeClient:
    """Stands in for databento.Historical; records each request."""

    def __init__(self):
        self.requests = []
        self.timeseries = self

    def get_range(self, **kwargs):
        self.requests.append(kwargs)
        return self

    def to_df(self):
        return pd.DataFrame({"symbol": ["6EU6"], "volume": [100]})


def test_spread_symbol_lists_deferred_first():
    assert spread_symbol("6EU6", "6EZ6") == "6EZ6-6EU6"


@pytest.mark.parametrize(
    "func, schema",
    [
        (fetch_daily_bars, "ohlcv-1d"),
        (fetch_bbo_1m, "bbo-1m"),
        (fetch_definitions, "definition"),
    ],
)
def test_each_schema_requests_named_contracts(func, schema):
    client = FakeClient()
    df = func(["6EU6", "6EZ6"], date(2026, 8, 10), date(2026, 9, 15), client)

    assert client.requests == [{
        "dataset": "GLBX.MDP3",
        "schema": schema,
        "symbols": ["6EU6", "6EZ6"],
        "stype_in": "raw_symbol",
        "start": "2026-08-10T00:00:00",
        "end": "2026-09-15T00:00:00",
    }]
    assert list(df.columns) == ["symbol", "volume"]


def test_timezone_aware_times_keep_their_offset():
    client = FakeClient()
    start = pd.Timestamp("2026-09-08 10:00", tz="America/Chicago")
    fetch("bbo-1m", ["6EU6"], start, start + pd.Timedelta(minutes=1), client)
    assert client.requests[0]["start"] == "2026-09-08T10:00:00-05:00"


def test_rejects_empty_symbols():
    with pytest.raises(ValueError, match="symbols"):
        fetch("ohlcv-1d", [], "2026-08-01", "2026-09-01", FakeClient())


def test_rejects_start_not_before_end():
    with pytest.raises(ValueError, match="before"):
        fetch("ohlcv-1d", ["6EU6"], "2026-09-01", "2026-09-01", FakeClient())


def test_uses_shared_client_when_none_given(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(download, "get_client", lambda: client)
    fetch_daily_bars(["6EU6"], "2026-08-01", "2026-09-01")
    assert len(client.requests) == 1
