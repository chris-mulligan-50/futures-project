from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from euro_roll import analyze, cache, config, meetings
from euro_roll.analyze import quote_range, run
from euro_roll.expiries import roll_calendar
from euro_roll.spread import TICK, session_open, snapshot_time
from euro_roll.windows import roll_window, select_windows

FRONT_BID = 1.1


def fake_fetch(spread_ticks, has_data=lambda day: True, deferred_width=lambda day: 1):
    """A ``fetch`` quoting both legs at 10:00 Chicago each weekday.

    The deferred-minus-front spread on ``day`` is ``spread_ticks(day)``. The
    front is one tick wide and the deferred ``deferred_width(day)`` ticks.
    Days where ``has_data(day)`` is false have no quotes.
    """
    def fetch(symbols, start, end):
        front, deferred = symbols
        rows = []
        for day in pd.bdate_range(start.date(), end.date()).date:
            at = snapshot_time(day)
            if start <= at < end and has_data(day):
                deferred_bid = FRONT_BID + spread_ticks(day) * TICK
                deferred_ask = deferred_bid + deferred_width(day) * TICK
                rows.append({"ts_recv": at, "symbol": front, "bid_px_00": FRONT_BID, "ask_px_00": FRONT_BID + TICK})
                rows.append({"ts_recv": at, "symbol": deferred, "bid_px_00": deferred_bid, "ask_px_00": deferred_ask})
        bbo = pd.DataFrame(rows, columns=["ts_recv", "symbol", "bid_px_00", "ask_px_00"])
        return bbo.set_index(pd.DatetimeIndex(bbo.pop("ts_recv"), tz="UTC"))
    return fetch


def fake_rates(usd=lambda day: 4.0):
    """Daily ``load_rates``-like table with flat curves: USD ``usd(day)``, EUR 2%."""
    days = pd.date_range("2010-01-01", "2026-12-31", name="date")
    usd_rates = [usd(d.date()) for d in days]
    return pd.DataFrame({"usd_3m": usd_rates, "usd_6m": usd_rates, "eur_3m": 2.0, "eur_6m": 2.0}, index=days)


def h1(results, split="exploratory", spec="spread"):
    return results["stats"].loc[(split, spec, "h1")]


def test_quote_range_starts_at_the_first_fallback_session():
    window = roll_window(date(2026, 9, 14))  # baseline Fri Sep 4, fallback from Wed Sep 2
    start, end = quote_range(window)
    assert start == session_open(date(2026, 9, 2))
    assert end == snapshot_time(date(2026, 9, 11)) + pd.Timedelta(minutes=1)


def test_planted_roll_effect_is_found_and_written(tmp_path):
    rolls = select_windows(config.exploratory(roll_calendar(2024, 2026)))
    # The spread is 50 ticks, except 50 + 10 + k in the last three days of
    # roll k's window, so roll k's spread rises 10 + k ticks.
    raised = {r.roll.end - timedelta(days=i): 60 + k for k, r in enumerate(rolls) for i in range(3)}
    results = run(rolls, fake_fetch(lambda day: raised.get(day, 50)), fake_rates(), tmp_path)

    changes = pd.read_csv(tmp_path / "roll_vs_control.csv", index_col="expiry")
    assert changes["roll"].tolist() == [10 + k for k in range(8)]
    assert (changes["control"] == 0).all()

    spread = h1(results)
    assert (spread["n"], spread["n_positive"], spread["mean"]) == (8, 8, 13.5)
    assert spread["sign_p"] < 0.01
    assert h1(results, spec="narrow_quotes")["n"] == 8
    # Rates are flat, so carry explains none of the move.
    assert h1(results, spec="carry_3m")["n_positive"] == 8
    stats = pd.read_csv(tmp_path / "stats.csv", index_col=["split", "spec", "test"])
    assert set(stats.index.get_level_values("split")) == {"exploratory"}
    assert (tmp_path / "figures" / "roll_vs_control.png").exists()

    # Labor Day 2026 falls in the September 2026 roll window.
    dropped = pd.read_csv(tmp_path / "dropped_days.csv")
    assert dropped.to_dict("records") == [
        {"expiry": "2026-09-14", "window": "roll", "day": "2026-09-07", "reason": "holiday"},
    ]


def test_wide_quote_on_a_day_used_drops_the_roll_from_the_narrow_stats(tmp_path):
    rolls = select_windows(config.exploratory(roll_calendar(2024, 2026)))
    wide_day = rolls[0].control.end
    fetch = fake_fetch(lambda day: 50 + day.toordinal() % 3, deferred_width=lambda day: 8 if day == wide_day else 1)
    results = run(rolls, fetch, fake_rates(), tmp_path)
    assert results["roll_vs_control"]["control_max_width"].tolist() == [8] + [1] * 7
    assert h1(results)["n"] == 8
    assert h1(results, spec="narrow_quotes")["n"] == 7


def test_roll_with_a_policy_decision_drops_from_the_no_meetings_stats(monkeypatch, tmp_path):
    rolls = select_windows(config.exploratory(roll_calendar(2024, 2026)))
    decision_day = rolls[0].roll.days[3]  # Thursday of the first roll window
    monkeypatch.setitem(meetings.BANKS, "ecb", (decision_day,))
    monkeypatch.setitem(meetings.BANKS, "fomc", ())
    results = run(rolls, fake_fetch(lambda day: 50 + day.toordinal() % 3), fake_rates(), tmp_path)

    assert results["roll_vs_control"]["roll_ecb"].tolist() == [decision_day] + [None] * 7
    assert h1(results)["n"] == 8
    assert h1(results, spec="no_meetings")["n"] == 7
    overlap = pd.read_csv(tmp_path / "meetings.csv", index_col=["split", "bank"])
    assert overlap.loc[("exploratory", "ecb")].to_dict() == {"roll": 1, "control": 0, "rolls": 8}


def test_rate_move_is_taken_out_of_the_carry_comparison(tmp_path):
    rolls = select_windows(config.exploratory(roll_calendar(2024, 2026)))
    # USD rates rise 10 bp on the Wednesday of the first roll window. The
    # ending Friday's snapshot sees it (previous day's rate); the baseline doesn't.
    jump = rolls[0].roll.days[2]
    # The spread is flat in roll windows and ends control windows 1-2 ticks up.
    control_ends = {r.control.end: 51 + k % 2 for k, r in enumerate(rolls)}
    fetch = fake_fetch(lambda day: control_ends.get(day, 50))
    results = run(rolls, fetch, fake_rates(lambda day: 4.1 if day >= jump else 4.0), tmp_path)
    carry = results["carry"]
    assert carry["roll_spot"].tolist() == pytest.approx([10] + [0] * 7)
    assert carry["roll_forward"].tolist() == pytest.approx([10] + [0] * 7)
    assert (carry["roll_implied"] == 0).all() and (carry["control_spot"] == 0).all()
    # The spread did not move in the first roll window, so carry predicted a rise that did not happen.
    roll_excess = results["stats"].loc[("exploratory", "carry_3m", "h2_roll")]
    assert (roll_excess["n_negative"], roll_excess["n_positive"]) == (1, 0)


def test_main_test_falls_back_to_2017_when_early_data_is_poor(tmp_path):
    rolls = select_windows(config.main_test(roll_calendar(2010, 2024)))
    noise = lambda day: 50 + day.toordinal() % 3

    good = run(rolls, fake_fetch(noise), fake_rates(), tmp_path / "good")
    assert good["early_drop_share"] == 0
    assert h1(good, split="main_test")["n"] == 57

    poor = run(rolls, fake_fetch(noise, has_data=lambda day: day >= date(2017, 1, 1)), fake_rates(), tmp_path / "poor")
    assert poor["early_drop_share"] > 0.2
    assert h1(poor, split="main_test")["n"] == 30  # expiries 2017-06 to 2024-09


def test_main_shows_cost_and_downloads_nothing_by_default(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    client = SimpleNamespace(metadata=SimpleNamespace(get_cost=lambda **params: 0.01))
    monkeypatch.setattr(analyze, "get_client", lambda: client)

    def no_download(*args):
        raise AssertionError("downloaded without --download")

    monkeypatch.setattr(analyze, "run", no_download)

    analyze.main([])
    assert "8 rolls, estimated cost of uncached requests: $0.16" in capsys.readouterr().out
    analyze.main(["--all"])
    assert "65 rolls, estimated cost of uncached requests: $1.30" in capsys.readouterr().out
