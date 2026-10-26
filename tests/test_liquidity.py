from datetime import date

import pandas as pd
import pytest

import synthetic
from euro_roll import liquidity
from euro_roll.liquidity import (
    compare_windows, daily_volumes, drop_reasons, liquidity_table,
    roll_liquidity, window_liquidity, window_requests,
)
from euro_roll.windows import RollWindows, Window
from synthetic import DEFERRED, FRONT

# Two windows inside the synthetic data (see synthetic.py).
# Week 2 has the stale deferred quote on Thu 2026-11-05.
WEEK2 = Window(baseline=date(2026, 10, 30), start=date(2026, 11, 2), end=date(2026, 11, 6))
# Week 1 has the missing day, Wed 2026-10-28, and its baseline (Fri 2026-10-23)
# is before the data starts, so it is missing too.
WEEK1 = Window(baseline=date(2026, 10, 23), start=date(2026, 10, 26), end=date(2026, 10, 30))
ROLL = RollWindows(FRONT, DEFERRED, date(2026, 12, 14), roll=WEEK2, control=WEEK1)
BOTH_MISSING = "front missing, deferred missing"


def measures(bbo, daily, window, **kwargs):
    return window_liquidity(bbo, daily, FRONT, DEFERRED, window, **kwargs)


def volumes(expected, days, leg):
    return expected.loc[days, f"{leg}_volume"].dropna().astype(int)


def test_week_with_a_stale_quote(synthetic_bbo, synthetic_daily, synthetic_expected):
    out = measures(synthetic_bbo, synthetic_daily, WEEK2)
    deferred = volumes(synthetic_expected, WEEK2.days, "deferred")
    front = volumes(synthetic_expected, WEEK2.days, "front")
    assert out["deferred_volume"] == deferred.median() == 8_500
    assert out["deferred_share"] == pytest.approx(deferred.sum() / (deferred.sum() + front.sum()))
    assert out["width_ticks"] == out["max_width_ticks"] == 2  # synthetic quotes are two ticks wide
    assert (out["snapshots"], out["deferred_ok"], out["valid"]) == (6, 5, 5)
    assert out["dropped"] == {"deferred stale": 1}


def test_day_without_data_is_left_out_of_volume(synthetic_bbo, synthetic_daily, synthetic_expected):
    out = measures(synthetic_bbo, synthetic_daily, WEEK1)
    deferred = volumes(synthetic_expected, WEEK1.days, "deferred")
    assert len(deferred) == 4  # the missing day has no bars
    assert out["deferred_volume"] == deferred.median() == 6_000
    assert (out["snapshots"], out["deferred_ok"], out["valid"]) == (6, 4, 4)
    assert out["dropped"] == {BOTH_MISSING: 2}


def test_deferred_without_a_bar_counts_as_zero(synthetic_daily):
    day = date(2026, 11, 4)
    no_trade = (synthetic_daily.index.date == day) & (synthetic_daily["symbol"] == DEFERRED)
    out = daily_volumes(synthetic_daily[~no_trade], FRONT, DEFERRED, WEEK2.days)
    assert out.loc[day].tolist() == [143_000, 0]
    assert out["deferred"].median() == 8_000


def test_widest_quote_is_reported(synthetic_bbo, synthetic_daily):
    bbo = synthetic_bbo.copy()
    at_10 = (bbo["symbol"] == DEFERRED) & (bbo.index == synthetic.snapshot_time(date(2026, 11, 4)))
    bbo.loc[at_10, "ask_px_00"] += 18 * synthetic.TICK  # 2 -> 20 ticks wide
    out = measures(bbo, synthetic_daily, WEEK2)
    assert (out["width_ticks"], out["max_width_ticks"]) == (2, 20)
    assert out["valid"] == 5  # wide is not a rejection


def test_quote_settings_take_effect(synthetic_bbo, synthetic_daily):
    lenient = measures(synthetic_bbo, synthetic_daily, WEEK2, max_age=pd.Timedelta(minutes=45))
    assert (lenient["valid"], lenient["dropped"]) == (6, {})


def test_roll_row_has_both_windows(synthetic_bbo, synthetic_daily):
    row = roll_liquidity(ROLL, synthetic_bbo, synthetic_daily)
    assert (row["expiry"], row["front"], row["deferred"]) == (ROLL.expiry, FRONT, DEFERRED)
    for kind in liquidity.KINDS:
        assert {f"{kind}_{m}" for m in liquidity.MEASURES} <= row.keys()
    assert (row["roll_valid"], row["control_valid"]) == (5, 4)


def test_no_spread_values_are_reported(synthetic_bbo, synthetic_daily):
    # The check may run on held-out rolls, so it must not reveal spread levels or changes.
    row = roll_liquidity(ROLL, synthetic_bbo, synthetic_daily)
    assert not [name for name in row if "spread" in name]


@pytest.fixture
def table(synthetic_bbo, synthetic_daily):
    later = RollWindows(FRONT, DEFERRED, date(2027, 3, 15), roll=WEEK2, control=WEEK1)
    rows = [roll_liquidity(r, synthetic_bbo, synthetic_daily) for r in [later, ROLL]]
    return liquidity_table(rows)


def test_table_is_indexed_by_expiry(table):
    assert table.index.tolist() == [date(2026, 12, 14), date(2027, 3, 15)]


def test_compare_windows_pools_snapshots(table):
    out = compare_windows(table)
    assert out.loc["rolls"].tolist() == [2, 2]
    assert out.loc["valid snapshots", "roll"] == pytest.approx(10 / 12)
    assert out.loc["valid snapshots", "control"] == pytest.approx(8 / 12)
    assert out.loc["median deferred volume"].tolist() == [8_500, 6_000]
    assert out.loc["rolls with a dropped day"].tolist() == [2, 2]


def test_drop_reasons_sum_over_rolls(table):
    out = drop_reasons(table)
    assert out.loc["deferred stale"].tolist() == [2, 0]
    assert out.loc[BOTH_MISSING].tolist() == [0, 4]


def test_requests_cover_each_snapshots_session():
    (bbo_schema, _, bbo_start, bbo_end), (daily_schema, _, day_start, day_end) = window_requests(WEEK2)
    assert (bbo_schema, daily_schema) == ("bbo-1m", "ohlcv-1d")
    # Session for the baseline opens Thu 17:00 Chicago (daylight time, UTC-5).
    assert bbo_start == pd.Timestamp("2026-10-29 22:00", tz="UTC")
    # Just after the ending Friday's 10:00 snapshot (standard time, UTC-6).
    assert bbo_end == pd.Timestamp("2026-11-06 16:01", tz="UTC")
    assert (day_start, day_end) == (pd.Timestamp("2026-11-02", tz="UTC"), pd.Timestamp("2026-11-07", tz="UTC"))


class CostOnlyClient:
    """Quotes a cost for every request and fails if anything is downloaded."""

    def __init__(self):
        self.metadata = self
        self.timeseries = self
        self.quoted = []

    def get_cost(self, **params):
        self.quoted.append(params)
        return 0.01

    def get_range(self, **params):
        raise AssertionError("downloaded without --download")


def test_script_shows_cost_without_downloading(monkeypatch, tmp_path, capsys):
    client = CostOnlyClient()
    monkeypatch.setattr(liquidity, "get_client", lambda: client)
    monkeypatch.setattr(liquidity.cache, "CACHE_DIR", tmp_path)  # nothing cached
    liquidity.main([])
    assert len(client.quoted) == 8 * 2 * 2  # 8 rolls, 2 windows, 2 schemas
    assert "8 rolls, estimated cost of uncached requests: $0.32" in capsys.readouterr().out
