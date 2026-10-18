"""Synthetic 6E quotes and daily bars for tests (Task 14, issue #20).

Built as real DBN records, so ``to_df()`` gives the same columns and types
as ``fetch_bbo_1m`` and ``fetch_daily_bars``. No network or API key needed.
Use the pytest fixtures in ``conftest.py`` or import this module directly.

Contents
--------
Front ``6EZ6`` and deferred ``6EH7``, the ten weekdays from Mon 2026-10-26 to
Fri 2026-11-06. US daylight saving time ends on Sun 2026-11-01, so the 10:00
America/Chicago snapshot is 15:00 UTC in the first week and 16:00 UTC in
the second.

Quotes (``bbo-1m``) cover 09:55-10:05 Chicago and follow what real
``bbo-1m`` data does:

* ``ts_recv`` is the end of each minute, so the row at 10:00:00 is the book
  as of 10:00:00.
* A row appears only for minutes in which the book changed. With no row
  at 10:00, the quote at 10:00 is the latest earlier row.
* ``ts_event``, ``price``, ``size`` and ``side`` describe the last *trade*,
  not the last quote. For the deferred contract that trade is hours old
  even when its quotes are current, so do not measure quote age from
  ``ts_event``.

The quotes in force at 10:00 give a deferred-minus-front spread of
``60.5 + i`` ticks on day ``i`` (0-9). Every other deferred row is 5 ticks
wider, so a snapshot taken at the wrong minute gives the wrong answer.

Special days (see ``EXPECTED``):

=================  =======  ================================================
Day                Status   What is in the data
=================  =======  ================================================
Wed 2026-10-28     missing  No quotes or daily bars for either contract.
Tue 2026-11-03     carried  The deferred book did not change from 09:58 to
                            10:00, so its 10:00 quote is the 09:58 row
                            (2 minutes old). Meant to pass a quote-age limit.
Thu 2026-11-05     stale    The deferred's latest quote is at 09:20
                            (40 minutes old). Meant to fail a quote-age limit.
=================  =======  ================================================

Daily bars (``ohlcv-1d``) have one bar per contract per day except the
missing day, labelled midnight UTC, with volumes given in ``EXPECTED``.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from typing import Dict, List, Tuple

import databento as db
import databento_dbn as dbn
import pandas as pd

FRONT, DEFERRED = "6EZ6", "6EH7"
TICK = 0.00005
CHICAGO = "America/Chicago"
SNAPSHOT = time(10, 0)
WRONG_MINUTE_TICKS = 5

DAYS: List[date] = list(pd.bdate_range("2026-10-26", "2026-11-06").date)
MISSING_DAY = date(2026, 10, 28)
CARRIED_DAY = date(2026, 11, 3)
STALE_DAY = date(2026, 11, 5)

_IDS = {FRONT: 1001, DEFERRED: 1002}
_TICK = 50_000  # one tick in DBN price units (1e-9)

# Deferred rows per day as (minutes from 10:00, minute of the quote in force at 10:00).
_DEFAULT_MINUTES = (list(range(-5, 6)), 0)
_DEFERRED_MINUTES: Dict[date, Tuple[List[int], int]] = {
    CARRIED_DAY: ([-5, -4, -3, -2, 1, 2, 3, 4, 5], -2),
    STALE_DAY: ([-40], -40),
}
_STATUS = {MISSING_DAY: "missing", CARRIED_DAY: "carried", STALE_DAY: "stale"}


def snapshot_time(day: date) -> pd.Timestamp:
    """10:00 America/Chicago on ``day``, in UTC."""
    local = pd.Timestamp(datetime.combine(day, SNAPSHOT), tz=CHICAGO)
    return local.tz_convert("UTC")


def _front_volume(i: int) -> int:
    return 150_000 - 1_000 * i


def _deferred_volume(i: int) -> int:
    return 5_000 + 500 * i


def _expected() -> pd.DataFrame:
    rows = []
    for i, day in enumerate(DAYS):
        missing = day == MISSING_DAY
        quote_minute = _DEFERRED_MINUTES.get(day, _DEFAULT_MINUTES)[1]
        rows.append({
            "day": day,
            "status": _STATUS.get(day, "ok"),
            "spread_ticks": None if missing else 60.5 + i,
            "front_quote_age": None if missing else pd.Timedelta(0),
            "deferred_quote_age": (
                None if missing else pd.Timedelta(minutes=-quote_minute)
            ),
            "front_volume": None if missing else _front_volume(i),
            "deferred_volume": None if missing else _deferred_volume(i),
        })
    volumes = {"front_volume": "Int64", "deferred_volume": "Int64"}
    return pd.DataFrame(rows).set_index("day").astype(volumes)


EXPECTED = _expected()


def _ns(ts: pd.Timestamp) -> int:
    return pd.Timestamp(ts).value


def _metadata(schema: dbn.Schema) -> dbn.Metadata:
    first, last = DAYS[0], DAYS[-1] + timedelta(days=1)
    mappings = [
        SimpleNamespace(
            raw_symbol=symbol,
            intervals=[SimpleNamespace(start_date=first, end_date=last, symbol=str(iid))],
        )
        for symbol, iid in _IDS.items()
    ]
    return dbn.Metadata(
        dataset="GLBX.MDP3",
        schema=schema,
        stype_in=dbn.SType.RAW_SYMBOL,
        stype_out=dbn.SType.INSTRUMENT_ID,
        start=_ns(pd.Timestamp(first, tz="UTC")),
        end=_ns(pd.Timestamp(last, tz="UTC")),
        symbols=list(_IDS),
        partial=[],
        not_found=[],
        mappings=mappings,
    )


def _quote(symbol, ts_recv, bid, ask, size, ts_event, trade_price, side, sequence):
    return dbn.BBOMsg(
        rtype=dbn.RType.BBO_1M,
        publisher_id=1,
        instrument_id=_IDS[symbol],
        ts_event=_ns(ts_event),
        price=trade_price,
        size=1,
        side=side,
        flags=128,
        ts_recv=_ns(ts_recv),
        sequence=sequence,
        levels=dbn.BidAskPair(
            bid_px=bid, ask_px=ask, bid_sz=size, ask_sz=size + 1, bid_ct=1, ask_ct=1
        ),
    )


def bbo_1m_store() -> db.DBNStore:
    """The synthetic ``bbo-1m`` quotes as a DBN store."""
    records = []
    for i, day in enumerate(DAYS):
        if day == MISSING_DAY:
            continue
        snap = snapshot_time(day)
        front_bid = 1_160_000_000 + 2 * i * _TICK
        deferred_bid = front_bid + (60 + i) * _TICK
        deferred_trade = snap - pd.Timedelta(hours=2, minutes=48)

        for m in range(-5, 6):
            ts = snap + pd.Timedelta(minutes=m)
            # Prices stay put; changing sizes are the book updates that publish a row.
            records.append((ts, FRONT, front_bid, front_bid + _TICK, 10 + m + 5,
                            ts - pd.Timedelta(seconds=3), front_bid, dbn.Side.BID))

        minutes, quote_minute = _DEFERRED_MINUTES.get(day, _DEFAULT_MINUTES)
        for m in minutes:
            ts = snap + pd.Timedelta(minutes=m)
            bid = deferred_bid if m == quote_minute else deferred_bid + WRONG_MINUTE_TICKS * _TICK
            records.append((ts, DEFERRED, bid, bid + 2 * _TICK, 3,
                            deferred_trade, deferred_bid + _TICK, dbn.Side.ASK))

    records.sort(key=lambda r: (r[0], _IDS[r[1]]))
    body = b"".join(
        bytes(_quote(symbol, ts, bid, ask, size, ts_event, price, side, seq))
        for seq, (ts, symbol, bid, ask, size, ts_event, price, side) in enumerate(records, 1)
    )
    return db.DBNStore.from_bytes(bytes(_metadata(dbn.Schema.BBO_1M).encode()) + body)


def daily_bars_store() -> db.DBNStore:
    """The synthetic ``ohlcv-1d`` bars as a DBN store."""
    bars = []
    for i, day in enumerate(DAYS):
        if day == MISSING_DAY:
            continue
        front_close = 1_160_000_000 + 2 * i * _TICK
        for symbol, close, volume in [
            (FRONT, front_close, _front_volume(i)),
            (DEFERRED, front_close + (60 + i) * _TICK, _deferred_volume(i)),
        ]:
            bars.append(dbn.OHLCVMsg(
                rtype=dbn.RType.OHLCV_1D,
                publisher_id=1,
                instrument_id=_IDS[symbol],
                ts_event=_ns(pd.Timestamp(day, tz="UTC")),
                open=close - _TICK,
                high=close + 4 * _TICK,
                low=close - 4 * _TICK,
                close=close,
                volume=volume,
            ))
    body = b"".join(bytes(bar) for bar in bars)
    return db.DBNStore.from_bytes(bytes(_metadata(dbn.Schema.OHLCV_1D).encode()) + body)


def bbo_1m() -> pd.DataFrame:
    """The quotes as ``fetch_bbo_1m`` would return them."""
    return bbo_1m_store().to_df()


def daily_bars() -> pd.DataFrame:
    """The daily bars as ``fetch_daily_bars`` would return them."""
    return daily_bars_store().to_df()
