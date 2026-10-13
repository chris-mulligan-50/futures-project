"""Fetch 6E data from Databento for named contracts (Task 3, issue #25).

Requests use raw symbols such as ``6EU6`` or the listed spread
``6EZ6-6EU6``, never continuous series. Raw symbols repeat every ten years
(``6EU6`` is both September 2016 and September 2026) and Databento resolves
them for the dates requested, so keep each request inside the contract's
own life. Naive start/end times are read as UTC; end is exclusive.

Caching (#26) and cost previews (#27) are separate.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional, Union

import databento as db
import pandas as pd

from euro_roll.client import get_client

DATASET = "GLBX.MDP3"

DateLike = Union[str, date, pd.Timestamp]


def spread_symbol(front: str, deferred: str) -> str:
    """Raw symbol of the listed calendar spread, e.g. ``6EZ6-6EU6``.

    CME lists the deferred leg first: Databento's definitions include
    ``6EZ6-6EU6``, and ``6EU6-6EZ6`` does not resolve.
    The spread's price sign is not checked yet; read ``leg_side`` in the
    definition data before using spread prices.
    """
    return f"{deferred}-{front}"


def _timestamp(value: DateLike) -> pd.Timestamp:
    """Timestamp, with naive values read as UTC."""
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts


def request_params(
    schema: str,
    symbols: Union[str, Iterable[str]],
    start: DateLike,
    end: DateLike,
) -> dict:
    """Checked arguments for ``timeseries.get_range`` or ``metadata.get_cost``.

    ``end`` is exclusive, as in Databento.
    """
    symbols = [symbols] if isinstance(symbols, str) else list(symbols)
    if not symbols:
        raise ValueError("symbols must not be empty")
    start, end = _timestamp(start), _timestamp(end)
    if start >= end:
        raise ValueError(f"start ({start}) must be before end ({end})")
    return dict(
        dataset=DATASET,
        schema=schema,
        symbols=symbols,
        stype_in="raw_symbol",
        start=start.isoformat(),
        end=end.isoformat(),
    )


def fetch(
    schema: str,
    symbols: Union[str, Iterable[str]],
    start: DateLike,
    end: DateLike,
    client: Optional[db.Historical] = None,
) -> pd.DataFrame:
    """Records for ``symbols`` in ``schema`` from ``start`` to ``end`` (exclusive)."""
    params = request_params(schema, symbols, start, end)
    return (client or get_client()).timeseries.get_range(**params).to_df()


def fetch_daily_bars(
    symbols: Union[str, Iterable[str]],
    start: DateLike,
    end: DateLike,
    client: Optional[db.Historical] = None,
) -> pd.DataFrame:
    """Daily OHLCV bars (UTC days), for volume migration."""
    return fetch("ohlcv-1d", symbols, start, end, client)


def fetch_bbo_1m(
    symbols: Union[str, Iterable[str]],
    start: DateLike,
    end: DateLike,
    client: Optional[db.Historical] = None,
) -> pd.DataFrame:
    """Best bid and offer sampled each minute, for fixed-time snapshots."""
    return fetch("bbo-1m", symbols, start, end, client)


def fetch_definitions(
    symbols: Union[str, Iterable[str]],
    start: DateLike,
    end: DateLike,
    client: Optional[db.Historical] = None,
) -> pd.DataFrame:
    """Instrument definitions, including expiration, for the roll calendar."""
    return fetch("definition", symbols, start, end, client)
