"""Which rolls belong to which analysis (Task 6, issue #12).

One place for the split, so no module picks its own date range. A roll is
identified by its front contract's expiry date, as in ``expiries.roll_calendar``.

Decision 10 of ``docs/ANALYSIS_PLAN.md``.
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, List

from euro_roll.expiries import RollPair

# Databento GLBX.MDP3 starts 2010-06-06, so the first full roll is Sep 2010.
FIRST_EXPIRY = date(2010, 7, 1)
LAST_EXPIRY = date(2026, 9, 30)

# The eight recent rolls the idea came from. Exploratory only: they cannot
# also be part of the main test.
EXPLORATORY_FIRST_EXPIRY = date(2024, 12, 1)


def main_test(pairs: Iterable[RollPair]) -> List[RollPair]:
    """Rolls used for the main test: everything before the exploratory rolls."""
    return [p for p in pairs if FIRST_EXPIRY <= p[2] < EXPLORATORY_FIRST_EXPIRY]


def exploratory(pairs: Iterable[RollPair]) -> List[RollPair]:
    """The recent rolls, reported separately."""
    return [p for p in pairs if EXPLORATORY_FIRST_EXPIRY <= p[2] <= LAST_EXPIRY]
