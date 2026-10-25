"""Net spread change per window (decision 5 of ``docs/ANALYSIS_PLAN.md``).

Each roll gives two numbers in ticks: the net change of the deferred-minus-
front spread over its roll window and over its control window, each from the
baseline Friday's 10:00 snapshot to the ending Friday's. ``change_table``
builds the table ``stats.summarize`` takes.

Decision 5: a day counts only if ``spread.daily_spreads`` kept it. If the
baseline or ending Friday was dropped, the latest valid weekday up to
``FALLBACK_DAYS`` before it stands in. If there is none, the window has no
change and the roll drops out of the tests. The days used are recorded, so
every substitution can be reported.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List, Optional

import pandas as pd

from euro_roll.spread import TICK
from euro_roll.windows import RollWindows, Window

FALLBACK_DAYS = 2  # weekdays before a dropped baseline or ending Friday
KINDS = ("roll", "control")


def candidates(day: date) -> List[date]:
    """``day`` and the ``FALLBACK_DAYS`` weekdays before it, latest first."""
    return list(pd.bdate_range(end=day, periods=FALLBACK_DAYS + 1).date[::-1])


def needed_days(window: Window) -> List[date]:
    """Days to snapshot for ``window``, in date order.

    The baseline Friday and its fallback days, then the five window days.
    Only Wednesday to Friday of the window can stand in for its end; Monday
    and Tuesday are kept so their drops are reported too.
    """
    return sorted(set(candidates(window.baseline)) | set(window.days))


def endpoint(spreads: pd.DataFrame, day: date) -> Optional[date]:
    """The day whose snapshot stands in for ``day``: the latest valid candidate, or None."""
    valid = spreads.loc[candidates(day), "valid"]
    return next((d for d, ok in valid.items() if ok), None)


def window_change(spreads: pd.DataFrame, window: Window) -> Dict[str, object]:
    """Net change in ticks over ``window``, the days it used, and its widest quote.

    ``spreads`` is ``daily_spreads`` output covering ``needed_days(window)``.
    Keys: ``change`` (NaN if either end has no valid day), ``baseline_used``
    and ``end_used`` (None if no valid day), and ``max_width``: the widest
    bid-ask of either leg on those two days, in ticks, for decision 11.
    """
    start = endpoint(spreads, window.baseline)
    end = endpoint(spreads, window.end)
    change = max_width = float("nan")
    if start is not None and end is not None:
        both = spreads.loc[[start, end]]
        change = both.at[end, "spread_ticks"] - both.at[start, "spread_ticks"]
        widths = pd.concat([both[f"{leg}_ask"] - both[f"{leg}_bid"] for leg in ("front", "deferred")])
        max_width = round(widths.max() / TICK, 6)
    return {"change": change, "baseline_used": start, "end_used": end, "max_width": max_width}


def roll_changes(rw: RollWindows, spreads: Dict[str, pd.DataFrame]) -> Dict[str, object]:
    """One row: the roll's contracts, then each window's change, days used and widest quote.

    ``spreads`` maps ``"roll"`` and ``"control"`` to that window's
    ``daily_spreads`` output.
    """
    row: Dict[str, object] = {"expiry": rw.expiry, "front": rw.front, "deferred": rw.deferred}
    for kind in KINDS:
        result = window_change(spreads[kind], getattr(rw, kind))
        row[kind] = result.pop("change")
        row.update({f"{kind}_{key}": value for key, value in result.items()})
    return row


def change_table(rows: Iterable[Dict[str, object]]) -> pd.DataFrame:
    """Rows from ``roll_changes``, indexed by expiry date in date order.

    Front symbols repeat every ten years, so rolls are keyed by expiry. The
    ``roll`` and ``control`` columns are what ``stats.summarize`` reads.
    """
    return pd.DataFrame(list(rows)).set_index("expiry").sort_index()
