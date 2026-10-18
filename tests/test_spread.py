from datetime import date, time

import pandas as pd
import pytest

import synthetic
from euro_roll.spread import daily_spreads, drop_counts, dropped_days, quotes_at
from synthetic import DAYS, DEFERRED, FRONT


def spreads(bbo, **kwargs):
    return daily_spreads(bbo, FRONT, DEFERRED, DAYS, **kwargs)


def at_10am(bbo, symbol, day):
    """Mask selecting ``symbol``'s 10:00 Chicago row on ``day``."""
    return (bbo["symbol"] == symbol) & (bbo.index == synthetic.snapshot_time(day))


def test_matches_the_synthetic_answers(synthetic_bbo, synthetic_expected):
    out = spreads(synthetic_bbo)
    ok = synthetic_expected["status"].isin(["ok", "carried"])
    assert out["valid"].tolist() == ok.tolist()
    assert out.loc[ok, "spread_ticks"].tolist() == synthetic_expected.loc[ok, "spread_ticks"].tolist()
    assert out.loc[ok, "front_age"].tolist() == synthetic_expected.loc[ok, "front_quote_age"].tolist()
    assert out.loc[ok, "deferred_age"].tolist() == synthetic_expected.loc[ok, "deferred_quote_age"].tolist()


def test_sign_is_deferred_minus_front(synthetic_bbo):
    normal = spreads(synthetic_bbo)
    swapped = daily_spreads(synthetic_bbo, DEFERRED, FRONT, DAYS)
    assert (normal["spread_ticks"].dropna() > 0).all()
    assert swapped["spread_ticks"].dropna().tolist() == (-normal["spread_ticks"].dropna()).tolist()


def test_snapshot_follows_daylight_saving(synthetic_bbo):
    out = spreads(synthetic_bbo)
    assert out.loc[date(2026, 10, 30), "snapshot"] == pd.Timestamp("2026-10-30 15:00", tz="UTC")
    assert out.loc[date(2026, 11, 2), "snapshot"] == pd.Timestamp("2026-11-02 16:00", tz="UTC")


def test_day_without_data_is_missing_not_stale(synthetic_bbo):
    # The previous day's 10:05 quote exists but belongs to an earlier session.
    row = spreads(synthetic_bbo).loc[synthetic.MISSING_DAY]
    assert (row["front_status"], row["deferred_status"]) == ("missing", "missing")
    assert pd.isna(row["front_age"]) and pd.isna(row["spread_ticks"])
    assert row["reason"] == "front missing, deferred missing"


def test_stale_quote_is_rejected(synthetic_bbo):
    row = spreads(synthetic_bbo).loc[synthetic.STALE_DAY]
    assert row["deferred_status"] == "stale"
    assert row["deferred_age"] == pd.Timedelta(minutes=40)
    assert not row["valid"] and row["reason"] == "deferred stale"


def test_quote_age_limit_is_a_parameter(synthetic_bbo, synthetic_expected):
    lenient = spreads(synthetic_bbo, max_age=pd.Timedelta(minutes=45))
    strict = spreads(synthetic_bbo, max_age=pd.Timedelta(minutes=1))
    assert lenient.loc[synthetic.STALE_DAY, "spread_ticks"] == synthetic_expected.loc[synthetic.STALE_DAY, "spread_ticks"]
    assert strict.loc[synthetic.CARRIED_DAY, "deferred_status"] == "stale"


def test_carried_quote_is_used_when_no_row_at_10am(synthetic_bbo):
    row = spreads(synthetic_bbo).loc[synthetic.CARRIED_DAY]
    assert row["valid"] and row["deferred_age"] == pd.Timedelta(minutes=2)


def test_snapshot_time_is_a_parameter(synthetic_bbo, synthetic_expected):
    day = date(2026, 10, 26)
    late = spreads(synthetic_bbo, at=time(10, 1))
    want = synthetic_expected.loc[day, "spread_ticks"] + synthetic.WRONG_MINUTE_TICKS
    assert late.loc[day, "spread_ticks"] == pytest.approx(want)


def test_ts_event_is_not_used_for_quote_age(synthetic_bbo):
    old_trades = synthetic_bbo.assign(ts_event=pd.Timestamp("2026-01-01", tz="UTC"))
    pd.testing.assert_frame_equal(spreads(old_trades), spreads(synthetic_bbo))


def test_one_sided_quote_is_rejected(synthetic_bbo):
    day = date(2026, 10, 27)
    bbo = synthetic_bbo.copy()
    bbo.loc[at_10am(bbo, DEFERRED, day), "ask_px_00"] = float("nan")
    row = spreads(bbo).loc[day]
    assert row["deferred_status"] == "one-sided" and row["reason"] == "deferred one-sided"


def test_crossed_quote_is_rejected(synthetic_bbo):
    day = date(2026, 10, 27)
    bbo = synthetic_bbo.copy()
    mask = at_10am(bbo, FRONT, day)
    bbo.loc[mask, "bid_px_00"] = bbo.loc[mask, "ask_px_00"] + synthetic.TICK
    assert spreads(bbo).loc[day, "front_status"] == "crossed"


def test_unknown_symbol_is_missing_every_day(synthetic_bbo):
    out = quotes_at(synthetic_bbo, "6EM7", DAYS)
    assert (out["status"] == "missing").all()


def test_every_requested_day_is_reported_in_order(synthetic_bbo):
    days = [date(2026, 11, 6), synthetic.MISSING_DAY, date(2026, 10, 26)]
    out = daily_spreads(synthetic_bbo, FRONT, DEFERRED, days)
    assert out.index.tolist() == days


def test_drop_report(synthetic_bbo):
    out = spreads(synthetic_bbo)
    assert dropped_days(out).index.tolist() == [synthetic.MISSING_DAY, synthetic.STALE_DAY]
    assert drop_counts(out).to_dict() == {
        "front missing, deferred missing": 1,
        "deferred stale": 1,
    }
