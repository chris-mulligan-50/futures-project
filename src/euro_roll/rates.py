"""Daily USD and EUR short-term rates (Task 42, issue #48).

Used for the carry comparison in ``docs/ANALYSIS_PLAN.md`` (decision 8).
Government rates at 3 and 6 months, from free sources that need no API key:

  * USD: Treasury bills, FRED ``DTB3`` and ``DTB6``. Bank-discount yields
    (360-day year), converted here as 91- and 182-day bills.
  * EUR: euro area AAA government yield curve, spot rates
    ``YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M`` and ``SR_6M`` from the ECB Data
    Portal. Already continuously compounded.

All end up continuously compounded, in percent per year. Government rates
sit a little below the rates FX dealers fund at, so the level of the gap
need not match the futures' implied carry; the plan compares weekly changes.

All are end-of-day values, measured a few hours after the 10:00 Chicago
spread snapshot, so ``rates_on`` uses each currency's latest values dated
before the snapshot day and reports which date that was.

``rate_gap`` is the 3-month spot gap. ``forward_gap`` is the gap between
the two expiries, the period the calendar spread prices.

The download is cached under the git-ignored ``data/rates/`` folder.
Rebuild it with ``python -m euro_roll.rates``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, Optional, Union

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = REPO_ROOT / "data" / "rates" / "rates.csv"

START = "2010-01-01"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}"
ECB_URL = (
    "https://data-api.ecb.europa.eu/service/data/YC/"
    "B.U2.EUR.4F.G_N_A.SV_C_YM.{series}?format=csvdata&startPeriod={start}"
)


@dataclass(frozen=True)
class Tenor:
    years: float
    fred: str       # FRED T-bill series
    bill_days: int  # bill maturity, for the discount conversion
    ecb: str        # ECB AAA curve spot-rate series


TENORS = {
    "3m": Tenor(0.25, "DTB3", 91, "SR_3M"),
    "6m": Tenor(0.5, "DTB6", 182, "SR_6M"),
}
COLUMNS = [f"{cur}_{t}" for cur in ("usd", "eur") for t in TENORS]

MAX_AGE_DAYS = 5  # longest gap expected from a holiday weekend

DateLike = Union[str, date, pd.Timestamp]
PathLike = Union[str, Path]


def read_series(source, date_col: str, value_col: str) -> pd.Series:
    """One rate series from a CSV, in percent, with empty or ``.`` values dropped."""
    df = pd.read_csv(source, usecols=[date_col, value_col])
    values = pd.to_numeric(df[value_col], errors="coerce").to_numpy()
    series = pd.Series(values, index=pd.to_datetime(df[date_col]).rename("date"))
    return series.dropna().sort_index()


def discount_to_continuous(discount_pct, days: int):
    """Bank-discount yield to a continuously compounded rate, both in percent.

    The bill's price per 1 of face value is ``1 - d * days / 360``.
    """
    price = 1 - discount_pct / 100 * days / 360
    return -np.log(price) * 365 / days * 100


def build_rates(
    usd_discount: Dict[str, pd.Series], eur: Dict[str, pd.Series]
) -> pd.DataFrame:
    """One column per currency and tenor (``usd_3m``, ...) on the union of calendars.

    Both arguments map a tenor in ``TENORS`` to its series. A holiday on one
    side leaves that side NaN instead of dropping the row.
    """
    columns = {}
    for t, tenor in TENORS.items():
        columns[f"usd_{t}"] = discount_to_continuous(usd_discount[t], tenor.bill_days)
        columns[f"eur_{t}"] = eur[t]
    return pd.concat(columns, axis=1, sort=True).rename_axis("date")[COLUMNS]


def download_rates(start: str = START) -> pd.DataFrame:
    usd, eur = {}, {}
    for t, tenor in TENORS.items():
        usd[t] = read_series(
            FRED_URL.format(series=tenor.fred, start=start), "observation_date", tenor.fred
        )
        eur[t] = read_series(
            ECB_URL.format(series=tenor.ecb, start=start), "TIME_PERIOD", "OBS_VALUE"
        )
    return build_rates(usd, eur)


def load_rates(
    path: Optional[PathLike] = None, refresh: bool = False, start: str = START
) -> pd.DataFrame:
    """Cached rates, downloading on the first call, when ``refresh``, or when
    the cache was written with other columns.

    Written under a temporary name and renamed when complete, as in
    ``euro_roll.cache``, so an interrupted write never looks valid.
    """
    path = Path(path) if path is not None else CACHE_FILE
    if path.exists() and not refresh:
        cached = pd.read_csv(path, index_col="date", parse_dates=["date"])
        if list(cached.columns) == COLUMNS:
            return cached

    rates = download_rates(start)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    try:
        rates.to_csv(partial)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
    return rates


def rates_on(
    rates: pd.DataFrame, days: Iterable[DateLike], max_age_days: int = MAX_AGE_DAYS
) -> pd.DataFrame:
    """Rates known at the snapshot on each of ``days``, with the 3-month
    ``gap_3m = usd_3m - eur_3m`` in percent.

    Each currency takes its latest values dated before the day, never the
    day itself (decision 8); ``usd_date`` and ``eur_date`` say which date
    that was. Both of a currency's tenors come from the same date. A value
    more than ``max_age_days`` older than the day counts as missing.
    """
    index = pd.DatetimeIndex(pd.to_datetime(list(days))).normalize().rename("day")
    before = index - pd.Timedelta(days=1)
    out = pd.DataFrame(index=index)
    for cur in ("usd", "eur"):
        columns = [f"{cur}_{t}" for t in TENORS]
        observed = rates[columns].dropna()
        source = pd.Series(observed.index, index=observed.index).asof(before)
        fresh = (index - pd.DatetimeIndex(source)) <= pd.Timedelta(days=max_age_days)
        for col in columns:
            out[col] = observed[col].asof(before).where(fresh).to_numpy()
        out[f"{cur}_date"] = source.where(fresh).to_numpy()
    out["gap_3m"] = out["usd_3m"] - out["eur_3m"]
    return out[[*COLUMNS, "gap_3m", "usd_date", "eur_date"]]


def _known_on(rates: pd.DataFrame, day: DateLike, max_age_days: int) -> pd.Series:
    row = rates_on(rates, [day], max_age_days).iloc[0]
    if row[COLUMNS].isna().any():
        raise ValueError(f"No rate within {max_age_days} days before {day}")
    return row


def rate_gap(
    rates: pd.DataFrame, day: DateLike, max_age_days: int = MAX_AGE_DAYS
) -> float:
    """USD minus EUR 3-month rate known on ``day``, continuously compounded percent."""
    return float(_known_on(rates, day, max_age_days)["gap_3m"])


def forward_gap(
    rates: pd.DataFrame,
    day: DateLike,
    start: DateLike,
    end: DateLike,
    max_age_days: int = MAX_AGE_DAYS,
) -> float:
    """USD minus EUR forward rate from ``start`` to ``end``, known on ``day``.

    With ``start`` and ``end`` the two expiries, this is the period the
    calendar spread prices. For each currency, f = (r2 t2 - r1 t1) / (t2 - t1),
    where t1 and t2 are years from ``day`` to ``start`` and ``end``, and the
    spot rates r1 and r2 are interpolated linearly between 3 and 6 months
    and held flat outside. The ECB curve is not fitted below 3 months, so a
    ``start`` sooner than that, as in every roll and control window, uses
    the 3-month rate.
    """
    row = _known_on(rates, day, max_age_days)
    t1 = (pd.Timestamp(start) - row.name).days / 365
    t2 = (pd.Timestamp(end) - row.name).days / 365
    if not 0 <= t1 < t2:
        raise ValueError(f"need day <= start < end, got {day}, {start}, {end}")
    years = [tenor.years for tenor in TENORS.values()]
    gap = 0.0
    for cur, sign in (("usd", 1), ("eur", -1)):
        r1, r2 = np.interp([t1, t2], years, [row[f"{cur}_{t}"] for t in TENORS])
        gap += sign * (r2 * t2 - r1 * t1) / (t2 - t1)
    return float(gap)


if __name__ == "__main__":
    table = load_rates(refresh=True)
    print(f"Saved {len(table)} rows to {CACHE_FILE}")
    print(table.describe().round(3))
