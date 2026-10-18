"""Calendar spread at a fixed daily time (Task 5, issue #11).

For each requested day, take each contract's best bid and ask in force at
10:00 America/Chicago, compute midpoints, and report the deferred midpoint
minus the front midpoint in ticks (one 6E tick is 0.00005 USD per EUR).

Input is ``bbo-1m`` data as returned by ``fetch_bbo_1m``. In that schema a
row is published only for minutes in which the book changed, and
``ts_recv`` is the end of the minute. So the quote in force at 10:00 is the
latest row at or before 10:00, and its age is the time since that row.
``ts_event`` is the time of the last trade, not of the last quote, so it is
not used for quote age.

Each contract's quote at the snapshot gets a status:

* ``missing``: no quote since the session opened (17:00 Chicago the day
  before), so nothing was quoted that day.
* ``stale``: the latest quote is older than ``max_age``.
* ``one-sided``: the bid or the ask is absent.
* ``crossed``: the bid is above the ask.
* ``ok``: otherwise.

A day is kept only if both contracts are ``ok``. Dropped days stay in the
output with their reason, for the data-quality log (Task 18, issue #24).

``SNAPSHOT_TIME`` and ``MAX_QUOTE_AGE`` are provisional until the method
decision (Task 6, issue #12) settles them; both can be passed explicitly.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable

import pandas as pd

TICK = 0.00005
TIMEZONE = "America/Chicago"
SNAPSHOT_TIME = time(10, 0)  # provisional (Task 6)
MAX_QUOTE_AGE = pd.Timedelta(minutes=5)  # provisional (Task 6)
SESSION_OPEN = time(17, 0)  # CME Globex opens 17:00 Chicago the day before

LEG_COLUMNS = ["bid", "ask", "age", "status"]


def _utc(day: date, at: time) -> pd.Timestamp:
    local = pd.Timestamp(datetime.combine(day, at), tz=TIMEZONE)
    return local.tz_convert("UTC").as_unit("ns")


def snapshot_time(day: date, at: time = SNAPSHOT_TIME) -> pd.Timestamp:
    """``at`` Chicago time on ``day``, in UTC; follows daylight saving."""
    return _utc(day, at)


def session_open(day: date) -> pd.Timestamp:
    """Start of the CME session that trades on ``day``, in UTC."""
    return _utc(day - timedelta(days=1), SESSION_OPEN)


def quotes_at(
    bbo: pd.DataFrame,
    symbol: str,
    days: Iterable[date],
    at: time = SNAPSHOT_TIME,
    max_age: pd.Timedelta = MAX_QUOTE_AGE,
) -> pd.DataFrame:
    """Quote in force for ``symbol`` at ``at`` on each day, with its status.

    Indexed by day, with columns ``bid``, ``ask``, ``age`` and ``status``.
    """
    days = list(days)
    snaps = pd.DataFrame({
        "day": days,
        "snapshot": pd.DatetimeIndex([snapshot_time(d, at) for d in days]),
        "session_open": pd.DatetimeIndex([session_open(d) for d in days]),
    }).sort_values("snapshot")

    rows = bbo[bbo["symbol"] == symbol]
    quotes = pd.DataFrame({
        "quote_time": rows.index.as_unit("ns"),
        "bid": rows["bid_px_00"].to_numpy(),
        "ask": rows["ask_px_00"].to_numpy(),
    }).sort_values("quote_time")

    out = pd.merge_asof(
        snaps, quotes, left_on="snapshot", right_on="quote_time",
        allow_exact_matches=True,
    ).set_index("day")

    out["age"] = out["snapshot"] - out["quote_time"]
    missing = out["quote_time"].isna() | (out["quote_time"] < out["session_open"])
    out.loc[missing, ["bid", "ask", "age"]] = None

    status = pd.Series("ok", index=out.index)
    status[out["bid"] > out["ask"]] = "crossed"
    status[out["bid"].isna() | out["ask"].isna()] = "one-sided"
    status[out["age"] > max_age] = "stale"
    status[missing] = "missing"
    out["status"] = status
    return out.loc[days, LEG_COLUMNS]


def daily_spreads(
    bbo: pd.DataFrame,
    front: str,
    deferred: str,
    days: Iterable[date],
    at: time = SNAPSHOT_TIME,
    max_age: pd.Timedelta = MAX_QUOTE_AGE,
) -> pd.DataFrame:
    """Deferred-minus-front spread in ticks at ``at`` Chicago on each day.

    Pass every day you need, including ones you expect to be empty: a day
    with no data is reported as dropped rather than silently left out.

    Indexed by day. Columns: ``snapshot`` (UTC); ``front_bid``, ``front_ask``,
    ``front_age``, ``front_status`` and the same for ``deferred_``;
    ``spread_ticks`` (NaN when dropped); ``valid``; and ``reason``, e.g.
    ``"deferred stale"`` (empty when valid).
    """
    days = list(days)
    legs = {
        name: quotes_at(bbo, symbol, days, at, max_age).add_prefix(f"{name}_")
        for name, symbol in [("front", front), ("deferred", deferred)]
    }
    out = pd.concat(legs.values(), axis=1)
    out.insert(0, "snapshot", [snapshot_time(d, at) for d in days])

    front_mid = (out["front_bid"] + out["front_ask"]) / 2
    deferred_mid = (out["deferred_bid"] + out["deferred_ask"]) / 2
    valid = (out["front_status"] == "ok") & (out["deferred_status"] == "ok")
    # Rounded to remove float noise; quotes sit on a half-tick grid of mids.
    spread = ((deferred_mid - front_mid) / TICK).round(6)
    out["spread_ticks"] = spread.where(valid)
    out["valid"] = valid
    out["reason"] = [
        ", ".join(
            f"{leg} {status}"
            for leg, status in [("front", f), ("deferred", d)]
            if status != "ok"
        )
        for f, d in zip(out["front_status"], out["deferred_status"])
    ]
    return out


def dropped_days(spreads: pd.DataFrame) -> pd.DataFrame:
    """The days ``daily_spreads`` rejected, with their reason and quote ages."""
    cols = ["reason", "front_status", "front_age", "deferred_status", "deferred_age"]
    return spreads.loc[~spreads["valid"], cols]


def drop_counts(spreads: pd.DataFrame) -> pd.Series:
    """Number of rejected days per reason."""
    return dropped_days(spreads)["reason"].value_counts().rename("days")
