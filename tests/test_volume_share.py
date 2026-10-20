from datetime import date

import pandas as pd

from euro_roll.volume_share import (
    build_tables,
    crossover_day,
    plot_volume_share,
    roll_volume_share,
    summary_table,
)

ROLL = ("6EU6", "6EZ6", date(2026, 9, 14))


def _daily():
    # Business days Sep 8, 9, 10, 11, 14. Front volume falls, deferred rises.
    days = pd.date_range("2026-09-08", "2026-09-14", freq="B", tz="UTC")
    rows = []
    for i, d in enumerate(days):
        rows.append({"ts_event": d, "symbol": "6EU6", "volume": 100 - 20 * i})
        rows.append({"ts_event": d, "symbol": "6EZ6", "volume": 10 + 20 * i})
    return pd.DataFrame(rows).set_index("ts_event")


def test_share_and_days_to_expiry():
    t = roll_volume_share(_daily(), ROLL)
    assert t["deferred_share"].iloc[0] == 10 / 110
    assert t["days_to_expiry"].iloc[-1] == 0


def test_crossover_is_first_day_at_or_above_half():
    # Sep 10: 60 vs 50 -> share 0.4545. Sep 11: 40 vs 70 -> share 0.636.
    t = roll_volume_share(_daily(), ROLL)
    assert crossover_day(t) == 3  # Sep 11 is 3 days before Sep 14


def test_no_volume_day_has_nan_share():
    daily = _daily().assign(volume=0)
    assert roll_volume_share(daily, ROLL)["deferred_share"].isna().all()


def test_other_contracts_are_ignored():
    extra = _daily().copy()
    extra.loc[extra.index[0], "symbol"] = "6EH7"
    t = roll_volume_share(extra, ROLL)
    assert set(t["roll"]) == {"6EU6"}


def test_every_roll_gets_a_summary_row_and_chart(tmp_path):
    tables = build_tables([ROLL], lambda syms, s, e: _daily())
    summary = summary_table(tables, [ROLL])
    assert list(summary["front"]) == ["6EU6"]
    assert summary["crossover_days_to_expiry"].iloc[0] == 3
    assert plot_volume_share(tables, tmp_path / "chart.png").exists()


def test_repeated_front_symbols_are_kept_separate():
    # 6EU6 is both the 2016 and the 2026 contract.
    roll_2016 = ("6EU6", "6EZ6", date(2016, 9, 19))
    days = pd.date_range(end="2016-09-19", periods=5, freq="B", tz="UTC")
    rows = []
    for d in days:
        rows.append({"ts_event": d, "symbol": "6EU6", "volume": 10})
        rows.append({"ts_event": d, "symbol": "6EZ6", "volume": 90})
    both = pd.concat([pd.DataFrame(rows).set_index("ts_event"), _daily()]).sort_index()
    rolls = [roll_2016, ROLL]
    tables = build_tables(rolls, lambda syms, s, e: both)
    summary = summary_table(tables, rolls)
    assert list(summary["crossover_days_to_expiry"]) == [6, 3]