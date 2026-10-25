from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd

from euro_roll import analyze, cache, config
from euro_roll.analyze import quote_range, run
from euro_roll.expiries import roll_calendar
from euro_roll.spread import TICK, session_open, snapshot_time
from euro_roll.windows import roll_window, select_windows

FRONT_BID = 1.1


def fake_fetch(spread_ticks, has_data=lambda day: True):
    """A ``fetch`` quoting both legs one tick wide at 10:00 Chicago each weekday.

    The deferred-minus-front spread on ``day`` is ``spread_ticks(day)``. Days
    where ``has_data(day)`` is false have no quotes.
    """
    def fetch(symbols, start, end):
        front, deferred = symbols
        rows = []
        for day in pd.bdate_range(start.date(), end.date()).date:
            at = snapshot_time(day)
            if start <= at < end and has_data(day):
                deferred_bid = FRONT_BID + spread_ticks(day) * TICK
                rows.append({"ts_recv": at, "symbol": front, "bid_px_00": FRONT_BID, "ask_px_00": FRONT_BID + TICK})
                rows.append({"ts_recv": at, "symbol": deferred, "bid_px_00": deferred_bid, "ask_px_00": deferred_bid + TICK})
        bbo = pd.DataFrame(rows, columns=["ts_recv", "symbol", "bid_px_00", "ask_px_00"])
        return bbo.set_index(pd.DatetimeIndex(bbo.pop("ts_recv"), tz="UTC"))
    return fetch


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
    results = run(rolls, fake_fetch(lambda day: raised.get(day, 50)), tmp_path)

    changes = pd.read_csv(tmp_path / "roll_vs_control.csv", index_col="expiry")
    assert changes["roll"].tolist() == [10 + k for k in range(8)]
    assert (changes["control"] == 0).all()

    h1 = results["stats_exploratory"].loc["h1"]
    assert (h1["n"], h1["n_positive"], h1["mean"]) == (8, 8, 13.5)
    assert h1["sign_p"] < 0.01
    assert "stats_main" not in results and not (tmp_path / "stats_main.csv").exists()

    # Labor Day 2026 falls in the September 2026 roll window.
    dropped = pd.read_csv(tmp_path / "dropped_days.csv")
    assert dropped.to_dict("records") == [
        {"expiry": "2026-09-14", "window": "roll", "day": "2026-09-07", "reason": "holiday"},
    ]


def test_main_test_falls_back_to_2017_when_early_data_is_poor(tmp_path):
    rolls = select_windows(config.main_test(roll_calendar(2010, 2024)))
    noise = lambda day: 50 + day.toordinal() % 3

    good = run(rolls, fake_fetch(noise), tmp_path / "good")
    assert good["early_drop_share"] == 0
    assert good["stats_main"].loc["h1", "n"] == 57

    poor = run(rolls, fake_fetch(noise, has_data=lambda day: day >= date(2017, 1, 1)), tmp_path / "poor")
    assert poor["early_drop_share"] > 0.2
    assert poor["stats_main"].loc["h1", "n"] == 30  # expiries 2017-06 to 2024-09


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
