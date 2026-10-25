from datetime import date

import pandas as pd
import pytest

from euro_roll.changes import (
    candidates,
    change_table,
    needed_days,
    roll_changes,
    window_change,
)
from euro_roll.spread import daily_spreads
from euro_roll.windows import Window, roll_window, select_windows
from synthetic import DEFERRED, FRONT

# Sep 2026 roll: baseline Fri Sep 4, window Mon Sep 7 - Fri Sep 11.
WINDOW = roll_window(date(2026, 9, 14))


def fake_spreads(window=WINDOW, dropped=()):
    """``daily_spreads``-like rows over ``needed_days(window)``: 100, 101, ... ticks."""
    days = needed_days(window)
    valid = pd.Series([d not in dropped for d in days], index=days)
    ticks = pd.Series([100.0 + i for i in range(len(days))], index=days)
    return pd.DataFrame({"spread_ticks": ticks.where(valid), "valid": valid})


def test_needed_days_add_two_fallback_days_before_the_baseline():
    assert needed_days(WINDOW) == [date(2026, 9, d) for d in (2, 3, 4, 7, 8, 9, 10, 11)]


def test_change_is_ending_friday_minus_baseline_friday():
    # Sep 4 is 102 ticks, Sep 11 is 107.
    assert window_change(fake_spreads(), WINDOW) == {
        "change": 5.0, "baseline_used": date(2026, 9, 4), "end_used": date(2026, 9, 11),
    }


def test_dropped_baseline_uses_latest_valid_day_before_it():
    one = window_change(fake_spreads(dropped={date(2026, 9, 4)}), WINDOW)
    assert (one["baseline_used"], one["change"]) == (date(2026, 9, 3), 6.0)
    two = window_change(fake_spreads(dropped={date(2026, 9, 4), date(2026, 9, 3)}), WINDOW)
    assert (two["baseline_used"], two["change"]) == (date(2026, 9, 2), 7.0)


def test_dropped_ending_friday_uses_thursday():
    out = window_change(fake_spreads(dropped={date(2026, 9, 11)}), WINDOW)
    assert (out["end_used"], out["change"]) == (date(2026, 9, 10), 4.0)


def test_fallback_stops_after_two_days():
    # Tuesday Sep 8 is valid but three weekdays before the ending Friday.
    dropped = {date(2026, 9, 11), date(2026, 9, 10), date(2026, 9, 9)}
    out = window_change(fake_spreads(dropped=dropped), WINDOW)
    assert out["end_used"] is None and pd.isna(out["change"])


def test_missing_snapshot_rows_raise():
    with pytest.raises(KeyError):
        window_change(fake_spreads().drop(date(2026, 9, 4)), WINDOW)


def test_table_is_keyed_by_expiry_and_keeps_excluded_rolls():
    # 6EU6 is both the 2016 and the 2026 contract; rolls given out of order.
    new, old = select_windows([("6EU6", "6EZ6", date(2026, 9, 14)), ("6EU6", "6EZ6", date(2016, 9, 19))])
    no_baseline = set(candidates(old.roll.baseline))
    rows = [
        roll_changes(new, {"roll": fake_spreads(new.roll), "control": fake_spreads(new.control)}),
        roll_changes(old, {"roll": fake_spreads(old.roll, no_baseline), "control": fake_spreads(old.control)}),
    ]
    table = change_table(rows)
    assert table.index.tolist() == [date(2016, 9, 19), date(2026, 9, 14)]
    assert pd.isna(table.loc[date(2016, 9, 19), "roll"])
    assert table.loc[date(2026, 9, 14), ["roll", "control"]].tolist() == [5.0, 5.0]
    assert table.loc[date(2026, 9, 14), "control_end_used"] == date(2026, 8, 14)


def test_synthetic_quotes_end_to_end(synthetic_bbo, synthetic_expected):
    # Baseline Fri Oct 30; fallback days Thu Oct 29 and Wed Oct 28 (no data).
    window = Window(baseline=date(2026, 10, 30), start=date(2026, 11, 2), end=date(2026, 11, 6))
    want = synthetic_expected["spread_ticks"]

    def change(holidays):
        spreads = daily_spreads(synthetic_bbo, FRONT, DEFERRED, needed_days(window), holidays=holidays)
        return window_change(spreads, window)

    assert change(set())["change"] == want[date(2026, 11, 6)] - want[date(2026, 10, 30)]
    # Friday Nov 6 dropped and Thursday Nov 5 stale, so Wednesday Nov 4 stands in.
    assert change({date(2026, 11, 6)})["end_used"] == date(2026, 11, 4)
    # Baseline and Thursday dropped; Wednesday Oct 28 has no data, so no change.
    assert pd.isna(change({date(2026, 10, 30), date(2026, 10, 29)})["change"])
