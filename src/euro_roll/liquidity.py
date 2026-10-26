"""Control-window liquidity check (Task 41, issue #47).

Is the deferred contract liquid enough in the control week for that week to
be a fair comparison with the roll week? Four weeks before expiry most
trading is still in the front contract, so the deferred may trade little
and its quotes may be stale, which would add noise to the control spread
that the roll spread does not have.

For each roll, and separately for its roll and control windows, this
reports the deferred contract's:

* ``deferred_volume``: median daily volume over the window's five days.
  On a day with a front bar but no deferred bar the deferred did not trade,
  so it counts as zero. A day with no bar for either contract has no data
  and is left out.
* ``deferred_share``: deferred volume as a share of front plus deferred
  volume over the window.
* ``width_ticks`` and ``max_width_ticks``: median and widest bid-ask width
  at the 10:00 snapshot, in ticks, over the days its quote is ``ok``. A
  quote can be fresh but wide; a wide book makes the midpoint, and so the
  spread, less precise. Ticks are ``spread.TICK`` (0.00005). Before 2016
  the exchange tick was 0.0001 (Databento definitions: 6EZ5 0.0001, 6EH6
  0.00005), so then the narrowest possible book is 2.
* ``snapshots``, ``deferred_ok`` and ``valid``: number of snapshot days
  (the baseline Friday and the five window days, the days a window's
  change can use), days the deferred quote is ``ok``, and days both legs
  are ``ok`` and the spread is kept.
* ``dropped``: dropped snapshot days by reason, as in
  ``spread.drop_counts``.

No spread values are reported, so the check can run on any roll without
revealing test results (analysis plan, decision 1 and the professor's
questions table). Daily bars are labelled by UTC day, as Databento
returns them.

Run on real data (shows the estimated cost and downloads nothing unless
``--download`` is given; cached requests cost nothing):

    PYTHONPATH=src python -m euro_roll.liquidity            # 8 recent rolls
    PYTHONPATH=src python -m euro_roll.liquidity --all      # 2010-09 to 2026-09
    PYTHONPATH=src python -m euro_roll.liquidity --download
"""
from __future__ import annotations

import argparse
from datetime import date, time, timedelta
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from euro_roll import cache, config
from euro_roll.changes import KINDS
from euro_roll.client import get_client
from euro_roll.download import fetch, request_params
from euro_roll.expiries import roll_calendar
from euro_roll.spread import (
    MAX_QUOTE_AGE, SNAPSHOT_TIME, TICK, daily_spreads, drop_counts,
    session_open, snapshot_time,
)
from euro_roll.windows import RollWindows, Window, select_windows

MEASURES = [
    "deferred_volume", "deferred_share", "width_ticks", "max_width_ticks",
    "snapshots", "deferred_ok", "valid", "dropped",
]

OUTPUT = cache.REPO_ROOT / "outputs" / "control_liquidity.csv"


def snapshot_days(window: Window) -> List[date]:
    """The baseline Friday and the five window days."""
    return [window.baseline] + window.days


def daily_volumes(daily: pd.DataFrame, front: str, deferred: str, days: Iterable[date]) -> pd.DataFrame:
    """Front and deferred volume on each of ``days`` that has data.

    A missing deferred bar on a day the front traded counts as zero volume.
    Days with no bar for either contract are dropped.
    """
    days = list(days)
    bars = daily[daily["symbol"].isin([front, deferred])]
    table = (
        bars.assign(day=bars.index.date)
        .pivot_table(index="day", columns="symbol", values="volume", aggfunc="sum")
        .reindex(index=days, columns=[front, deferred])
    )
    table = table.dropna(how="all").fillna(0)
    return table.set_axis(["front", "deferred"], axis=1)


def window_liquidity(
    bbo: pd.DataFrame,
    daily: pd.DataFrame,
    front: str,
    deferred: str,
    window: Window,
    at: time = SNAPSHOT_TIME,
    max_age: pd.Timedelta = MAX_QUOTE_AGE,
) -> Dict[str, object]:
    """The measures in ``MEASURES`` for one window. See the module docstring."""
    volumes = daily_volumes(daily, front, deferred, window.days)
    total = volumes.to_numpy().sum()

    spreads = daily_spreads(bbo, front, deferred, snapshot_days(window), at, max_age)
    ok = spreads["deferred_status"] == "ok"
    width = ((spreads.loc[ok, "deferred_ask"] - spreads.loc[ok, "deferred_bid"]) / TICK).round(6)

    return {
        "deferred_volume": volumes["deferred"].median() if len(volumes) else float("nan"),
        "deferred_share": volumes["deferred"].sum() / total if total else float("nan"),
        "width_ticks": width.median() if ok.any() else float("nan"),
        "max_width_ticks": width.max() if ok.any() else float("nan"),
        "snapshots": len(spreads),
        "deferred_ok": int(ok.sum()),
        "valid": int(spreads["valid"].sum()),
        "dropped": drop_counts(spreads).to_dict(),
    }


def roll_liquidity(
    roll: RollWindows,
    bbo: pd.DataFrame,
    daily: pd.DataFrame,
    at: time = SNAPSHOT_TIME,
    max_age: pd.Timedelta = MAX_QUOTE_AGE,
) -> Dict[str, object]:
    """One row: the roll's contracts, then each measure for both windows.

    Columns are ``roll_<measure>`` and ``control_<measure>``.
    """
    row: Dict[str, object] = {
        "expiry": roll.expiry, "front": roll.front, "deferred": roll.deferred,
    }
    for kind in KINDS:
        measures = window_liquidity(
            bbo, daily, roll.front, roll.deferred, getattr(roll, kind), at, max_age
        )
        row.update({f"{kind}_{name}": value for name, value in measures.items()})
    return row


def liquidity_table(rows: Iterable[Dict[str, object]]) -> pd.DataFrame:
    """Rows from ``roll_liquidity`` as a table indexed by expiry date.

    Indexed by expiry, not symbol, because symbols repeat every ten years.
    """
    return pd.DataFrame(list(rows)).set_index("expiry").sort_index()


def compare_windows(table: pd.DataFrame) -> pd.DataFrame:
    """Roll vs. control across all rolls, one column per window kind.

    Volume, share and widths are medians across rolls; the snapshot shares
    are pooled over every snapshot day.
    """
    out = {}
    for kind in KINDS:
        t = {name: table[f"{kind}_{name}"] for name in MEASURES}
        snapshots = t["snapshots"].sum()
        out[kind] = {
            "rolls": len(table),
            "median deferred volume": t["deferred_volume"].median(),
            "median deferred share": t["deferred_share"].median(),
            "median deferred width (ticks)": t["width_ticks"].median(),
            "median widest deferred width (ticks)": t["max_width_ticks"].median(),
            "deferred quote ok": t["deferred_ok"].sum() / snapshots,
            "valid snapshots": t["valid"].sum() / snapshots,
            "rolls with a dropped day": int((t["valid"] < t["snapshots"]).sum()),
        }
    return pd.DataFrame(out)


def drop_reasons(table: pd.DataFrame) -> pd.DataFrame:
    """Dropped snapshot days by reason, summed over rolls, per window kind."""
    counts = {
        kind: pd.DataFrame(table[f"{kind}_dropped"].tolist()).sum()
        for kind in KINDS
    }
    return pd.DataFrame(counts).fillna(0).astype(int).rename_axis("reason")


def _format_dropped(dropped: Dict[str, int]) -> str:
    return "; ".join(f"{reason}: {n}" for reason, n in dropped.items())


# --- Real data -------------------------------------------------------------

def window_requests(window: Window) -> List[Tuple[str, str, pd.Timestamp, pd.Timestamp]]:
    """(schema, kind, start, end) of the two requests one window needs.

    Quotes run from the baseline's session open to just after the ending
    Friday's snapshot, so every snapshot can see the whole session before it.
    """
    return [
        ("bbo-1m", "bbo", session_open(window.baseline),
         snapshot_time(window.end) + pd.Timedelta(minutes=1)),
        ("ohlcv-1d", "daily", pd.Timestamp(window.start, tz="UTC"),
         pd.Timestamp(window.end + timedelta(days=1), tz="UTC")),
    ]


def _summary(table: pd.DataFrame) -> str:
    reasons = drop_reasons(table)
    dropped = reasons.to_string() if len(reasons) else "No dropped snapshot days."
    return f"{compare_windows(table)}\n\n{dropped}"


def _rolls(all_rolls: bool) -> List[RollWindows]:
    calendar = roll_calendar(2010, 2026)
    pairs = config.exploratory(calendar)
    if all_rolls:
        pairs = config.main_test(calendar) + pairs
    return select_windows(pairs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--all", action="store_true",
                        help="all rolls from 2010-09, not only the 8 recent ones")
    parser.add_argument("--download", action="store_true",
                        help="download after showing the cost (default: cost only)")
    args = parser.parse_args(argv)

    rolls = _rolls(args.all)
    client = get_client()
    cost = 0.0
    for roll in rolls:
        for kind in KINDS:
            for schema, _, start, end in window_requests(getattr(roll, kind)):
                params = request_params(schema, [roll.front, roll.deferred], start, end)
                if not cache.cache_path(params).exists():
                    cost += client.metadata.get_cost(**params)
    print(f"{len(rolls)} rolls, estimated cost of uncached requests: ${cost:.2f}")
    if not args.download:
        print("Nothing downloaded. Re-run with --download to fetch.")
        return

    rows = []
    for roll in rolls:
        data = {"bbo": [], "daily": []}
        for kind in KINDS:
            for schema, name, start, end in window_requests(getattr(roll, kind)):
                data[name].append(fetch(schema, [roll.front, roll.deferred], start, end, client))
        rows.append(roll_liquidity(roll, pd.concat(data["bbo"]), pd.concat(data["daily"])))
    table = liquidity_table(rows)

    csv = table.copy()
    for kind in KINDS:
        csv[f"{kind}_dropped"] = csv[f"{kind}_dropped"].map(_format_dropped)
    OUTPUT.parent.mkdir(exist_ok=True)
    csv.to_csv(OUTPUT)

    with pd.option_context("display.width", 120, "display.float_format", "{:.3f}".format):
        print(f"\nWrote {OUTPUT}")
        main_test = table.index < config.EXPLORATORY_FIRST_EXPIRY
        for name, rows in [("Main-test rolls", main_test), ("Exploratory rolls", ~main_test)]:
            if rows.any():
                print(f"\n{name}:\n{_summary(table[rows])}")


if __name__ == "__main__":
    main()
