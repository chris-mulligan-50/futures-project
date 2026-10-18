import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from euro_roll import cache, download  # noqa: E402
from euro_roll.download import (  # noqa: E402
    fetch,
    fetch_bbo_1m,
    fetch_daily_bars,
    fetch_definitions,
    spread_symbol,
)
from fakes import FakeClient  # noqa: E402


@pytest.fixture(autouse=True)
def cache_dir(monkeypatch, tmp_path):
    """Keep every test's cache in a temporary folder, never in data/."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    return tmp_path


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
    func(["6EU6", "6EZ6"], date(2026, 8, 10), date(2026, 9, 15), client)

    assert client.requests == [{
        "dataset": "GLBX.MDP3",
        "schema": schema,
        "symbols": ["6EU6", "6EZ6"],
        "stype_in": "raw_symbol",
        "start": "2026-08-10T00:00:00+00:00",
        "end": "2026-09-15T00:00:00+00:00",
    }]


def test_timezone_aware_times_keep_their_offset():
    client = FakeClient()
    start = pd.Timestamp("2026-09-08 10:00", tz="America/Chicago")
    fetch("bbo-1m", ["6EU6"], start, start + pd.Timedelta(minutes=1), client)
    assert client.requests[0]["start"] == "2026-09-08T10:00:00-05:00"


def test_single_symbol_string_is_not_split():
    client = FakeClient()
    fetch("ohlcv-1d", "6EU6", "2026-08-01", "2026-09-01", client)
    assert client.requests[0]["symbols"] == ["6EU6"]


def test_naive_and_aware_times_can_be_mixed():
    client = FakeClient()
    end = pd.Timestamp("2026-09-08 10:00", tz="America/Chicago")
    fetch("bbo-1m", ["6EU6"], "2026-09-08", end, client)
    assert client.requests[0]["start"] == "2026-09-08T00:00:00+00:00"


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


def test_repeated_request_is_read_from_cache():
    client = FakeClient(volume=100)
    first = fetch_daily_bars(["6EU6"], "2026-08-10", "2026-08-11", client)
    second = fetch_daily_bars(["6EU6"], "2026-08-10", "2026-08-11", client)
    assert len(client.requests) == 1
    assert second["volume"].tolist() == first["volume"].tolist() == [100]


def test_cache_hit_needs_no_client_or_key(monkeypatch):
    fetch_daily_bars(["6EU6"], "2026-08-10", "2026-08-11", FakeClient())

    def no_client():
        raise AssertionError("a cache hit must not create a client")

    monkeypatch.setattr(download, "get_client", no_client)
    df = fetch_daily_bars(["6EU6"], "2026-08-10", "2026-08-11")
    assert df["volume"].tolist() == [100]


def test_different_request_is_downloaded():
    client = FakeClient()
    fetch_daily_bars(["6EU6"], "2026-08-10", "2026-08-11", client)
    fetch_bbo_1m(["6EU6"], "2026-08-10", "2026-08-11", client)
    fetch_daily_bars(["6EU6"], "2026-08-10", "2026-08-12", client)
    assert len(client.requests) == 3


def test_cache_false_always_downloads(cache_dir):
    client = FakeClient()
    for _ in range(2):
        fetch_daily_bars(["6EU6"], "2026-08-10", "2026-08-11", client, cache=False)
    assert len(client.requests) == 2
    assert not any(cache_dir.rglob("*.dbn"))
