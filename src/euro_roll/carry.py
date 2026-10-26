"""Carry comparison (decision 8 of ``docs/ANALYSIS_PLAN.md``).

Under cost of carry, F = S exp((r_usd - r_eur) t), so the two contracts of a
roll imply the forward USD - EUR rate gap between their expiries:

    implied gap = ln(F_deferred / F_front) / dt,  dt = years between the expiries

For each window, ``carry_table`` gives the change in the implied gap from
the baseline to the ending snapshot (the days ``changes.py`` used), and the
change in the observed gap known at those snapshots (``rates.py``, previous
day's rates): the 3-month spot gap (main comparison) and the forward gap
between the expiries (sensitivity). Changes are in basis points. Carry
predicts the implied gap tracks the observed one, so the difference is the
move carry does not explain.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Dict, List

import pandas as pd

from euro_roll.changes import KINDS
from euro_roll.expiries import expiry_date
from euro_roll.rates import forward_gap, rate_gap
from euro_roll.windows import RollWindows

GAPS = ("spot", "forward")


def deferred_expiry(front_expiry: date) -> date:
    """Expiry of the next quarterly contract after the one expiring on ``front_expiry``."""
    month = front_expiry.month % 12 + 3  # Mar -> Jun, ..., Dec -> Mar
    return expiry_date(front_expiry.year + (front_expiry.month == 12), month)


def implied_gap(snapshot: pd.Series, years: float) -> float:
    """USD - EUR gap implied by one ``daily_spreads`` row, continuously compounded percent."""
    front = (snapshot["front_bid"] + snapshot["front_ask"]) / 2
    deferred = (snapshot["deferred_bid"] + snapshot["deferred_ask"]) / 2
    return 100 * math.log(deferred / front) / years


def carry_table(
    rolls: List[RollWindows],
    spreads: Dict[date, Dict[str, pd.DataFrame]],
    changes: pd.DataFrame,
    rates: pd.DataFrame,
) -> pd.DataFrame:
    """Per roll and window, the implied, spot and forward gap changes in basis points.

    ``changes`` is ``change_table`` output, for the days each change used.
    Columns are ``<kind>_implied``, ``<kind>_spot`` and ``<kind>_forward``;
    NaN where the window has no change.
    """
    rows = []
    for roll in rolls:
        far = deferred_expiry(roll.expiry)
        years = (far - roll.expiry).days / 365
        row: Dict[str, object] = {"expiry": roll.expiry}
        for kind in KINDS:
            start = changes.at[roll.expiry, f"{kind}_baseline_used"]
            end = changes.at[roll.expiry, f"{kind}_end_used"]
            if pd.isna(start) or pd.isna(end):
                row.update({f"{kind}_{name}": float("nan") for name in ("implied", *GAPS)})
                continue
            s = spreads[roll.expiry][kind]
            row[f"{kind}_implied"] = 100 * (implied_gap(s.loc[end], years) - implied_gap(s.loc[start], years))
            row[f"{kind}_spot"] = 100 * (rate_gap(rates, end) - rate_gap(rates, start))
            row[f"{kind}_forward"] = 100 * (
                forward_gap(rates, end, roll.expiry, far) - forward_gap(rates, start, roll.expiry, far)
            )
        rows.append(row)
    return pd.DataFrame(rows).set_index("expiry").sort_index()


def excess(carry: pd.DataFrame, gap: str) -> pd.DataFrame:
    """Implied minus observed ``gap`` change per window, as ``roll`` and ``control`` columns."""
    return pd.DataFrame({kind: carry[f"{kind}_implied"] - carry[f"{kind}_{gap}"] for kind in KINDS})
