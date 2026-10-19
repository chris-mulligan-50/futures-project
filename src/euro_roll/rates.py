"""Daily USD and EUR short-term rates (Task 42, issue #48).

Used for the carry comparison in ``docs/ANALYSIS_PLAN.md`` (decision 8).
The 6E calendar spread spans three months, so both sides are 3-month
government rates, from free sources that need no API key:

  * USD: 3-month Treasury bill, FRED ``DTB3``. A bank-discount yield
    (360-day year), converted here as a 91-day bill.
  * EUR: euro area AAA government yield curve, 3-month spot rate, ECB Data
    Portal ``YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M``. Already continuously
    compounded.

Both end up continuously compounded, in percent per year. Government rates
sit a little below the rates FX dealers fund at, so the level of the gap
need not match the futures' implied carry; the plan compares weekly changes.

Both are end-of-day values, so a day's value is measured a few hours after
the 10:00 Chicago spread snapshot. On a US or TARGET holiday each leg uses
its latest earlier value, and ``rates_on`` reports which date that was.

The download is cached under the git-ignored ``data/rates/`` folder.
Rebuild it with ``python -m euro_roll.rates``.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Iterable, Optional, Union

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = REPO_ROOT / "data" / "rates" / "rates.csv"

START = "2010-01-01"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3&cosd={start}"
ECB_URL = (
    "https://data-api.ecb.europa.eu/service/data/YC/"
    "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M?format=csvdata&startPeriod={start}"
)

TBILL_DAYS = 91
MAX_AGE_DAYS = 5  # longest gap expected from a holiday weekend

DateLike = Union[str, date, pd.Timestamp]
PathLike = Union[str, Path]


def read_series(source, date_col: str, value_col: str) -> pd.Series:
    """One rate series from a CSV, in percent, with empty or ``.`` values dropped."""
    df = pd.read_csv(source, usecols=[date_col, value_col])
    values = pd.to_numeric(df[value_col], errors="coerce").to_numpy()
    series = pd.Series(values, index=pd.to_datetime(df[date_col]).rename("date"))
    return series.dropna().sort_index()


def discount_to_continuous(discount_pct, days: int = TBILL_DAYS):
    """Bank-discount yield to a continuously compounded rate, both in percent.

    The bill's price per 1 of face value is ``1 - d * days / 360``.
    """
    price = 1 - discount_pct / 100 * days / 360
    return -np.log(price) * 365 / days * 100


def build_rates(usd_discount: pd.Series, eur: pd.Series) -> pd.DataFrame:
    """``usd`` and ``eur`` columns on the union of both calendars.

    A holiday on one side leaves that side NaN instead of dropping the row.
    """
    usd = discount_to_continuous(usd_discount)
    return pd.concat({"usd": usd, "eur": eur}, axis=1, sort=True).rename_axis("date")


def download_rates(start: str = START) -> pd.DataFrame:
    usd = read_series(FRED_URL.format(start=start), "observation_date", "DTB3")
    eur = read_series(ECB_URL.format(start=start), "TIME_PERIOD", "OBS_VALUE")
    return build_rates(usd, eur)


def load_rates(
    path: Optional[PathLike] = None, refresh: bool = False, start: str = START
) -> pd.DataFrame:
    """Cached rates, downloading on the first call or when ``refresh``.

    Written under a temporary name and renamed when complete, as in
    ``euro_roll.cache``, so an interrupted write never looks valid.
    """
    path = Path(path) if path is not None else CACHE_FILE
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col="date", parse_dates=["date"])

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
    """Rates on each of ``days``, with ``gap = usd - eur`` in percent.

    Each leg takes its latest value on or before the day; ``usd_date`` and
    ``eur_date`` say which date that was. A value more than ``max_age_days``
    old counts as missing.
    """
    index = pd.DatetimeIndex(pd.to_datetime(list(days))).normalize().rename("day")
    out = pd.DataFrame(index=index)
    for leg in ("usd", "eur"):
        observed = rates[leg].dropna()
        source = pd.Series(observed.index, index=observed.index).asof(index)
        fresh = (index - pd.DatetimeIndex(source)) <= pd.Timedelta(days=max_age_days)
        out[leg] = observed.asof(index).where(fresh).to_numpy()
        out[f"{leg}_date"] = source.where(fresh).to_numpy()
    out["gap"] = out["usd"] - out["eur"]
    return out[["usd", "eur", "gap", "usd_date", "eur_date"]]


def rate_gap(
    rates: pd.DataFrame, day: DateLike, max_age_days: int = MAX_AGE_DAYS
) -> float:
    """USD minus EUR 3-month rate on ``day``, continuously compounded percent."""
    gap = rates_on(rates, [day], max_age_days)["gap"].iloc[0]
    if pd.isna(gap):
        raise ValueError(f"No rate within {max_age_days} days on or before {day}")
    return float(gap)


if __name__ == "__main__":
    table = load_rates(refresh=True)
    print(f"Saved {len(table)} rows to {CACHE_FILE}")
    print(table.describe().round(3))
