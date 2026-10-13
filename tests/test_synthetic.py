"""Checks that the synthetic data matches what ``synthetic.py`` documents."""
from datetime import date

import pandas as pd
import pytest

import synthetic
from synthetic import DEFERRED, FRONT, TICK, snapshot_time

# Columns of real fetch_bbo_1m / fetch_daily_bars output (checked against Databento).
BBO_COLUMNS = [
    "ts_event", "rtype", "publisher_id", "instrument_id", "side", "price", "size",
    "flags", "sequence", "bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00",
    "bid_ct_00", "ask_ct_00", "symbol",
]
DAILY_COLUMNS = [
    "rtype", "publisher_id", "instrument_id", "open", "high", "low", "close",
    "volume", "symbol",
]


def quote_at(bbo, symbol, when):
    """Latest row for ``symbol`` at or before ``when`` (an as-of lookup)."""
    rows = bbo[(bbo["symbol"] == symbol) & (bbo.index <= when)]
    return rows.iloc[-1], when - rows.index[-1]


def mid(row):
    return (row["bid_px_00"] + row["ask_px_00"]) / 2


def test_columns_match_real_data(synthetic_bbo, synthetic_daily):
    assert list(synthetic_bbo.columns) == BBO_COLUMNS
    assert synthetic_bbo.index.name == "ts_recv"
    assert str(synthetic_bbo.index.tz) == "UTC"
    assert list(synthetic_daily.columns) == DAILY_COLUMNS
    assert set(synthetic_bbo["symbol"]) == set(synthetic_daily["symbol"]) == {FRONT, DEFERRED}


def test_missing_day_has_no_data(synthetic_bbo, synthetic_daily):
    day = synthetic.MISSING_DAY
    assert not (synthetic_bbo.index.date == day).any()
    assert not (synthetic_daily.index.date == day).any()


def test_snapshot_moves_from_15_to_16_utc_when_dst_ends():
    assert snapshot_time(date(2026, 10, 30)) == pd.Timestamp("2026-10-30 15:00", tz="UTC")
    assert snapshot_time(date(2026, 11, 2)) == pd.Timestamp("2026-11-02 16:00", tz="UTC")


def test_10am_quotes_give_the_documented_spread_and_ages(synthetic_bbo, synthetic_expected):
    for day, want in synthetic_expected.drop(synthetic.MISSING_DAY).iterrows():
        snap = snapshot_time(day)
        front, front_age = quote_at(synthetic_bbo, FRONT, snap)
        deferred, deferred_age = quote_at(synthetic_bbo, DEFERRED, snap)
        assert (mid(deferred) - mid(front)) / TICK == pytest.approx(want["spread_ticks"])
        assert front_age == want["front_quote_age"]
        assert deferred_age == want["deferred_quote_age"]


def test_stale_and_carried_quote_ages(synthetic_expected):
    assert synthetic_expected.loc[synthetic.STALE_DAY, "deferred_quote_age"] == pd.Timedelta(minutes=40)
    assert synthetic_expected.loc[synthetic.CARRIED_DAY, "deferred_quote_age"] == pd.Timedelta(minutes=2)


def test_wrong_minute_gives_a_wrong_spread(synthetic_bbo, synthetic_expected):
    day = date(2026, 10, 26)
    one_late = snapshot_time(day) + pd.Timedelta(minutes=1)
    front, _ = quote_at(synthetic_bbo, FRONT, one_late)
    deferred, _ = quote_at(synthetic_bbo, DEFERRED, one_late)
    spread = (mid(deferred) - mid(front)) / TICK
    expected = synthetic_expected.loc[day, "spread_ticks"]
    assert spread == pytest.approx(expected + synthetic.WRONG_MINUTE_TICKS)


def test_ts_event_is_the_last_trade_not_the_quote_time(synthetic_bbo):
    deferred = synthetic_bbo[synthetic_bbo["symbol"] == DEFERRED]
    lag = deferred.index - deferred["ts_event"]
    assert (lag > pd.Timedelta(hours=2)).all()


def test_daily_volumes_match_expected(synthetic_daily, synthetic_expected):
    volumes = synthetic_daily.pivot_table(
        index=synthetic_daily.index.date, columns="symbol", values="volume"
    )
    want = synthetic_expected.dropna(subset=["front_volume"])
    assert volumes[FRONT].tolist() == want["front_volume"].tolist()
    assert volumes[DEFERRED].tolist() == want["deferred_volume"].tolist()
