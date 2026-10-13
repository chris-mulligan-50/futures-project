"""Roll calendar: 6E expiries and front/deferred pairing (Task 4, issue #10).

Rule: a CME Euro FX (6E) quarterly contract's last trading day is two
business days before the third Wednesday of its contract month (March,
June, September, December).

This is the formula version. It does not read Databento definitions, so
it needs no API key. Check its dates against Databento definition data
when available, and pass known exchange holidays via ``holidays``.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List, Optional, Set, Tuple

QUARTER_MONTHS = (3, 6, 9, 12)
MONTH_CODES = {3: "H", 6: "M", 9: "U", 12: "Z"}
PRODUCT = "6E"

RollPair = Tuple[str, str, date]  # (front, deferred, expiry)


def third_wednesday(year: int, month: int) -> date:
    first = date(year, month, 1)
    first_wed = first + timedelta(days=(2 - first.weekday()) % 7)
    return first_wed + timedelta(days=14)


def business_days_before(
    d: date, n: int, holidays: Optional[Set[date]] = None
) -> date:
    """The date ``n`` business days (Mon-Fri, not a holiday) before ``d``."""
    holidays = holidays or set()
    while n > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            n -= 1
    return d


def expiry_date(
    year: int, month: int, holidays: Optional[Set[date]] = None
) -> date:
    """Last trading day of the 6E contract for ``month`` of ``year``."""
    return business_days_before(third_wednesday(year, month), 2, holidays)


def contract_symbol(year: int, month: int) -> str:
    """e.g. (2026, 3) -> '6EH6'."""
    return f"{PRODUCT}{MONTH_CODES[month]}{year % 10}"


def roll_calendar(
    start_year: int, end_year: int, holidays: Optional[Set[date]] = None
) -> List[RollPair]:
    """(front, deferred, expiry) for each quarter from start_year to end_year.

    The deferred contract is the next quarterly contract, which may fall in
    the following year (December rolls into March).
    """
    pairs: List[RollPair] = []
    for year in range(start_year, end_year + 1):
        for i, month in enumerate(QUARTER_MONTHS):
            nxt_month = QUARTER_MONTHS[(i + 1) % 4]
            nxt_year = year + 1 if month == 12 else year
            pairs.append(
                (
                    contract_symbol(year, month),
                    contract_symbol(nxt_year, nxt_month),
                    expiry_date(year, month, holidays),
                )
            )
    return pairs