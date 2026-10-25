"""Main test: roll vs. control spread changes and their statistics (#28, #29).

For each roll, download the ``bbo-1m`` quotes its two windows need, take the
10:00 snapshots (``spread.py``, decision 6 of ``docs/ANALYSIS_PLAN.md``),
the net change per window (``changes.py``, decision 5) and run the planned
tests (``stats.py``, decision 9) on the main-test and exploratory rolls
separately (decision 10). Writes to ``outputs/``:

* ``roll_vs_control.csv``: one row per roll, both changes in ticks and the
  days used.
* ``dropped_days.csv``: every dropped snapshot day and its reason (#24).
* ``stats_main.csv`` and ``stats_exploratory.csv``: ``stats.summarize``.

Decision 10: if more than 20% of the snapshot days of the main-test rolls
before 2017-06 are dropped (holidays aside), the main test starts at the
2017-06 roll instead. Only dropped days decide this, not spread changes.

Run on real data (shows the estimated cost and downloads nothing unless
``--download`` is given; cached requests cost nothing). Run ``--all`` only
once the plan is tagged ``plan-v1``:

    PYTHONPATH=src python -m euro_roll.analyze              # 8 exploratory rolls
    PYTHONPATH=src python -m euro_roll.analyze --all        # all 65 rolls
    PYTHONPATH=src python -m euro_roll.analyze --all --download
"""
from __future__ import annotations

import argparse
from datetime import date
from typing import Callable, Dict, List, Tuple

import pandas as pd

from euro_roll import cache, config
from euro_roll.changes import KINDS, change_table, needed_days, roll_changes
from euro_roll.client import get_client
from euro_roll.download import fetch_bbo_1m, request_params
from euro_roll.expiries import roll_calendar
from euro_roll.spread import daily_spreads, session_open, snapshot_time
from euro_roll.stats import summarize
from euro_roll.windows import RollWindows, Window, select_windows

OUTPUTS = cache.REPO_ROOT / "outputs"
FALLBACK_FIRST_EXPIRY = date(2017, 6, 1)  # decision 10
MAX_DROP_SHARE = 0.20  # decision 10

Fetch = Callable[[List[str], pd.Timestamp, pd.Timestamp], pd.DataFrame]


def quote_range(window: Window) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Start and end of the ``bbo-1m`` request for ``window``.

    From the session open of its first snapshot day to just after the ending
    Friday's snapshot, so every snapshot sees the whole session before it.
    """
    start = session_open(needed_days(window)[0])
    return start, snapshot_time(window.end) + pd.Timedelta(minutes=1)


def roll_spreads(roll: RollWindows, fetch: Fetch) -> Dict[str, pd.DataFrame]:
    """``daily_spreads`` for both windows of ``roll``, keyed by window kind."""
    out = {}
    for kind in KINDS:
        window = getattr(roll, kind)
        bbo = fetch([roll.front, roll.deferred], *quote_range(window))
        out[kind] = daily_spreads(bbo, roll.front, roll.deferred, needed_days(window))
    return out


def dropped_log(spreads: Dict[date, Dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """Every dropped snapshot day: expiry, window kind, day and reason."""
    rows = [
        {"expiry": expiry, "window": kind, "day": day, "reason": reason}
        for expiry, by_kind in spreads.items()
        for kind, s in by_kind.items()
        for day, reason in s.loc[~s["valid"], "reason"].items()
    ]
    return pd.DataFrame(rows, columns=["expiry", "window", "day", "reason"])


def early_drop_share(rolls: List[RollWindows], spreads: Dict[date, Dict[str, pd.DataFrame]]) -> float:
    """Decision 10's measure: share of snapshot days dropped, pooled over the
    main-test rolls before 2017-06.

    Snapshot days are each window's baseline Friday and five days. Holidays
    are left out of both counts, since decision 6 drops them by design.
    """
    dropped = total = 0
    for roll in rolls:
        if not config.FIRST_EXPIRY <= roll.expiry < FALLBACK_FIRST_EXPIRY:
            continue
        for kind in KINDS:
            window = getattr(roll, kind)
            s = spreads[roll.expiry][kind].loc[[window.baseline] + window.days]
            s = s[s["reason"] != "holiday"]
            dropped += int((~s["valid"]).sum())
            total += len(s)
    return dropped / total if total else float("nan")


def run(rolls: List[RollWindows], fetch: Fetch, out_dir=OUTPUTS) -> Dict[str, object]:
    """Compute everything for ``rolls`` and write it to ``out_dir``.

    Returns the tables written and decision 10's drop share.
    """
    spreads = {roll.expiry: roll_spreads(roll, fetch) for roll in rolls}
    share = early_drop_share(rolls, spreads)
    changes = change_table(roll_changes(roll, spreads[roll.expiry]) for roll in rolls)
    dropped = dropped_log(spreads)

    out_dir.mkdir(parents=True, exist_ok=True)
    changes.to_csv(out_dir / "roll_vs_control.csv")
    dropped.to_csv(out_dir / "dropped_days.csv", index=False)
    results: Dict[str, object] = {
        "roll_vs_control": changes, "dropped_days": dropped, "early_drop_share": share,
    }

    pairs = [(r.front, r.deferred, r.expiry) for r in rolls]
    first = FALLBACK_FIRST_EXPIRY if share > MAX_DROP_SHARE else config.FIRST_EXPIRY
    groups = {
        "main": [p[2] for p in config.main_test(pairs) if p[2] >= first],
        "exploratory": [p[2] for p in config.exploratory(pairs)],
    }
    for name, expiries in groups.items():
        if expiries:
            stats = summarize(changes.loc[expiries])
            stats.to_csv(out_dir / f"stats_{name}.csv")
            results[f"stats_{name}"] = stats
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--all", action="store_true",
                        help="all 65 rolls, not only the 8 exploratory ones")
    parser.add_argument("--download", action="store_true",
                        help="download after showing the cost (default: cost only)")
    args = parser.parse_args(argv)

    calendar = roll_calendar(2010, 2026)
    pairs = config.exploratory(calendar)
    if args.all:
        pairs = config.main_test(calendar) + pairs
    rolls = select_windows(pairs)

    client = get_client()
    cost = 0.0
    for roll in rolls:
        for kind in KINDS:
            params = request_params("bbo-1m", [roll.front, roll.deferred], *quote_range(getattr(roll, kind)))
            if not cache.cache_path(params).exists():
                cost += client.metadata.get_cost(**params)
    print(f"{len(rolls)} rolls, estimated cost of uncached requests: ${cost:.2f}")
    if not args.download:
        print("Nothing downloaded. Re-run with --download to fetch.")
        return

    results = run(rolls, lambda symbols, start, end: fetch_bbo_1m(symbols, start, end, client))
    print(f"\nWrote {OUTPUTS}")
    print(f"Pre-2017-06 drop share (decision 10): {results['early_drop_share']:.1%}")
    with pd.option_context("display.width", 120, "display.float_format", "{:.3f}".format):
        for name in ("stats_main", "stats_exploratory"):
            if name in results:
                print(f"\n{name}:\n{results[name]}")


if __name__ == "__main__":
    main()
