"""Daily USD and EUR short-term rates (Task 42, issue #48).

Used for the carry comparison in ``docs/ANALYSIS_PLAN.md`` (decision 8):
the 6E calendar spread spans three months, so both sides are 3-month
government rates.

Sources (free, no API key):
  * USD: 3-month Treasury bill, secondary market, FRED ``DTB3``. Quoted as a
    bank-discount yield (360-day year), in percent.
  * EUR: euro area AAA government yield curve, 3-month spot rate, ECB Data
    Portal ``YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M``. Svensson model,
    continuously compounded, percent per year.

Both are converted to the same basis: continuously compounded, percent per
year. The T-bill is treated as a 91-day bill. Government rates sit a little
below the rates FX dealers fund at, so the level of the gap need not match
the futures' implied carry; weekly changes are what the plan compares.

Timing: both are end-of-day values, so the value for a day is measured a few
hours after the 10:00 Chicago spread snapshot. Days without a value (US or
TARGET holidays, e.g. FRED leaves 2010-12-24 empty) use each leg's latest
earlier value, and ``rates_on`` reports which date was used.

The download is cached under the git-ignored ``data/rates/`` folder. Delete
the file, or pass ``refresh=True``, to rebuild it. From the command line:
``python -m euro_roll.rates``.
"""
from __future__ import annotations

import math
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


def parse_fred(source) -> pd.Series:
    """FRED CSV (``observation_date,DTB3``) as a Series in percent, holidays dropped."""
    df = pd.read_csv(source)
    values = pd.to_numeric(df["DTB3"], errors="coerce")  # holidays are empty or "."
    s = pd.Series(values.to_numpy(), index=pd.to_datetime(df["observation_date"]))
    return s.dropna().rename("usd_discount").rename_axis("date")


def parse_ecb(source) -> pd.Series:
    """ECB Data Portal CSV (``format=csvdata``) as a Series in percent."""
    df = pd.read_csv(source, usecols=["TIME_PERIOD", "OBS_VALUE"])
    s = pd.Series(
        pd.to_numeric(df["OBS_VALUE"], errors="coerce").to_numpy(),
        index=pd.to_datetime(df["TIME_PERIOD"]),
    )
    return s.dropna().sort_index().rename("eur").rename_axis("date")


def discount_to_continuous(discount_pct, days: int = TBILL_DAYS):
    """Bank-discount yield (percent, 360-day) to a continuously compounded rate (percent, 365-day).

    Price per 1 of face value is ``1 - d * days / 360``; the continuous rate
    is ``-ln(price) * 365 / days``.
    """
    price = 1 - np.asarray(discount_pct, dtype=float) / 100 * days / 360
    rate = -np.log(price) * 365 / days * 100
    if isinstance(discount_pct, pd.Series):
        return pd.Series(rate, index=discount_pct.index, name=discount_pct.name)
    return float(rate) if np.ndim(rate) == 0 else rate


def build_rates(usd_discount: pd.Series, eur: pd.Series) -> pd.DataFrame:
    """One table of ``usd`` and ``eur``, continuously compounded percent.

    Rows are the union of both calendars, so a holiday on one side leaves
    that side NaN rather than dropping the other side's value.
    """
    usd = discount_to_continuous(usd_discount).rename("usd")
    return pd.concat([usd, eur.rename("eur")], axis=1, sort=True).rename_axis("date")


def download_rates(start: str = START) -> pd.DataFrame:
    """Fetch both series from FRED and the ECB (no API key needed)."""
    usd = parse_fred(FRED_URL.format(start=start))
    eur = parse_ecb(ECB_URL.format(start=start))
    return build_rates(usd, eur)


def load_rates(
    path: Optional[PathLike] = None, refresh: bool = False, start: str = START
) -> pd.DataFrame:
    """Cached rates table, downloading it on the first call or when ``refresh``.

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


def _as_of(series: pd.Series, days: pd.DatetimeIndex, max_age_days: int):
    """Latest value on or before each day, and the date it came from."""
    s = series.dropna().sort_index()
    pos = s.index.searchsorted(days, side="right") - 1
    found = pos >= 0
    values = np.full(len(days), np.nan)
    source = pd.Series(pd.NaT, index=days, dtype="datetime64[ns]")
    values[found] = s.to_numpy()[pos[found]]
    source[found] = s.index[pos[found]]
    too_old = (days - pd.DatetimeIndex(source)).days > max_age_days
    values[too_old] = np.nan
    source[too_old] = pd.NaT
    return values, source.to_numpy()


def rates_on(
    rates: pd.DataFrame, days: Iterable[DateLike], max_age_days: int = MAX_AGE_DAYS
) -> pd.DataFrame:
    """Rates aligned to ``days``, with ``gap = usd - eur`` in percent.

    Each leg uses its latest value on or before the day; ``usd_date`` and
    ``eur_date`` say which date that was. A leg whose latest value is more
    than ``max_age_days`` old is NaN, and so is the gap.
    """
    index = pd.DatetimeIndex(pd.to_datetime(list(days))).normalize()
    out = pd.DataFrame(index=index.rename("day"))
    for leg in ("usd", "eur"):
        out[leg], out[f"{leg}_date"] = _as_of(rates[leg], index, max_age_days)
    out["gap"] = out["usd"] - out["eur"]
    return out[["usd", "eur", "gap", "usd_date", "eur_date"]]


def rate_gap(
    rates: pd.DataFrame, day: DateLike, max_age_days: int = MAX_AGE_DAYS
) -> float:
    """USD minus EUR 3-month rate on ``day``, continuously compounded percent."""
    gap = rates_on(rates, [day], max_age_days)["gap"].iloc[0]
    if math.isnan(gap):
        raise ValueError(f"No rate within {max_age_days} days on or before {day}")
    return float(gap)


if __name__ == "__main__":
    table = load_rates(refresh=True)
    print(f"Saved {len(table)} rows to {CACHE_FILE}")
    print(table.describe().round(3))
