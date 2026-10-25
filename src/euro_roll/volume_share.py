"""Front/deferred volume share per roll: table and chart (Task 4, issue #10).

For each roll, the deferred contract's share of the two contracts' combined
daily volume, by days to the front contract's expiry. The crossover is the
first day the deferred share reaches one half.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Callable, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from euro_roll.expiries import RollPair, roll_calendar

LOOKBACK_DAYS = 60  # calendar days before expiry
# Rolls with Databento data, as in the analysis plan split (config.py in #50).
FIRST_EXPIRY = date(2010, 7, 1)
LAST_EXPIRY = date(2026, 9, 30)


def roll_volume_share(
    daily: pd.DataFrame, roll: RollPair, lookback: int = LOOKBACK_DAYS
) -> pd.DataFrame:
    """One row per trading day up to expiry for one roll.

    ``daily`` has ``symbol`` and ``volume`` columns and a datetime index
    (``fetch_daily_bars`` output). Columns returned: front_volume,
    deferred_volume, deferred_share, days_to_expiry, roll, expiry. Days with no
    volume in either contract have a NaN share.
    """
    front, deferred, expiry = roll
    sub = daily[daily["symbol"].isin([front, deferred])]
    day = pd.to_datetime(sub.index, utc=True).date
    vol = (
        sub.assign(day=day)
        .pivot_table(index="day", columns="symbol", values="volume", aggfunc="sum")
        .reindex(columns=[front, deferred])
        .fillna(0)
    )
    vol.columns = ["front_volume", "deferred_volume"]
    vol = vol[(vol.index <= expiry) & (vol.index >= expiry - timedelta(days=lookback))]
    total = vol["front_volume"] + vol["deferred_volume"]
    vol["deferred_share"] = (vol["deferred_volume"] / total).where(total > 0)
    vol["days_to_expiry"] = [(expiry - d).days for d in vol.index]
    vol["roll"] = front
    vol["expiry"] = expiry  # front symbols repeat every 10 years; expiry is unique
    return vol


def crossover_day(table: pd.DataFrame) -> Optional[int]:
    """Days to expiry on the first day the deferred share is at least 0.5."""
    hit = table[table["deferred_share"] >= 0.5]
    return int(hit["days_to_expiry"].iloc[0]) if len(hit) else None


def build_tables(
    rolls: List[RollPair],
    fetch: Callable[[List[str], date, date], pd.DataFrame],
    lookback: int = LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Daily volume-share rows for every roll, stacked."""
    parts = []
    for roll in rolls:
        front, deferred, expiry = roll
        daily = fetch(
            [front, deferred],
            expiry - timedelta(days=lookback),
            expiry + timedelta(days=1),
        )
        parts.append(roll_volume_share(daily, roll, lookback))
    return pd.concat(parts)


def summary_table(tables: pd.DataFrame, rolls: List[RollPair]) -> pd.DataFrame:
    """One row per roll: expiry and the crossover day."""
    rows = []
    for front, deferred, expiry in rolls:
        t = tables[tables["expiry"] == expiry]
        rows.append(
            {
                "front": front,
                "deferred": deferred,
                "expiry": expiry,
                "crossover_days_to_expiry": crossover_day(t) if len(t) else None,
            }
        )
    return pd.DataFrame(rows)


def plot_volume_share(tables: pd.DataFrame, path) -> Path:
    """Deferred share vs days to expiry: one line per roll plus the median."""
    fig, ax = plt.subplots(figsize=(9, 5))
    for _, t in tables.groupby("expiry", sort=False):
        ax.plot(t["days_to_expiry"], t["deferred_share"], color="grey", alpha=0.3, lw=0.8)
    median = tables.groupby("days_to_expiry")["deferred_share"].median()
    ax.plot(median.index, median.values, color="C0", lw=2, label="median across rolls")
    ax.axhline(0.5, color="k", ls="--", lw=0.8)
    ax.invert_xaxis()
    ax.set_xlabel("calendar days to front expiry")
    ax.set_ylabel("deferred share of front + deferred volume")
    ax.set_title("6E volume share by roll")
    ax.legend()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def main(start_year: int = 2010, end_year: int = 2026, out_dir: str = "outputs") -> None:
    from euro_roll.download import fetch_daily_bars

    rolls = [
        r for r in roll_calendar(start_year, end_year)
        if FIRST_EXPIRY <= r[2] <= LAST_EXPIRY
    ]
    tables = build_tables(rolls, fetch_daily_bars)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_table(tables, rolls).to_csv(out / "volume_share_summary.csv", index=False)
    tables.to_csv(out / "volume_share_daily.csv")
    plot_volume_share(tables, out / "volume_share.png")


if __name__ == "__main__":
    main()