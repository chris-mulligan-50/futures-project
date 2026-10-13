"""Verify Databento coverage, cost and 6E expiry dates (Task 2, issue #8).

Only metadata calls and one-day definition pulls (about 65 small requests),
so it is safe to run:

    PYTHONPATH=src python -m euro_roll.coverage
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, List, Tuple

import databento as db

from euro_roll.client import get_client
from euro_roll.download import DATASET, fetch_definitions, request_params
from euro_roll.expiries import RollPair, roll_calendar

RETRIES = 3
SCHEMAS = ["ohlcv-1d", "bbo-1m", "definition"]
FULL_RANGE = ("2010-06-06", "2026-09-30")
SAMPLE_RANGE = ("2025-08-01", "2025-09-20")  # one roll: 6EU5 -> 6EZ5
SAMPLE_SYMBOLS = ["6EU5", "6EZ5"]
EXPIRY_CHECK_YEARS = (2010, 2026)
EXPIRY_CHECK_FIRST = date(2010, 7, 1)  # dataset starts 2010-06-06
EXPIRY_CHECK_LAST = date(2026, 9, 30)


def compare_expiries(
    pairs: Iterable[RollPair], actual: Iterable[date]
) -> List[Tuple[str, date, date, bool]]:
    """(front, formula expiry, Databento expiry, match) for each pair.

    ``actual`` is aligned with ``pairs``. It is a list, not a dict keyed by
    symbol, because raw symbols repeat every ten years (6EU6 is 2016 and 2026).
    """
    return [
        (front, expiry, got, got == expiry)
        for (front, _, expiry), got in zip(pairs, actual)
    ]


def fetch_expirations(client, pairs: Iterable[RollPair]) -> List[date]:
    """Databento expiration date of each pair's front contract, in order.

    Raw symbols repeat every ten years, so each request covers one day
    shortly before that contract's expiry.
    """
    actual = []
    for front, _, expiry in pairs:
        day = expiry - timedelta(days=10)
        for attempt in range(RETRIES):
            try:
                defs = fetch_definitions([front], day, day + timedelta(days=1), client)
                break
            except db.BentoServerError:  # e.g. a transient 504 gateway timeout
                if attempt == RETRIES - 1:
                    raise
        actual.append(defs["expiration"].iloc[-1].date())
    return actual


def main():
    client = get_client()

    print("Dataset range:")
    print(client.metadata.get_dataset_range(dataset=DATASET))

    print("\nSample cost (one roll):")
    for schema in SCHEMAS:
        params = request_params(schema, SAMPLE_SYMBOLS, *SAMPLE_RANGE)
        print(f"  {schema:10s} ${client.metadata.get_cost(**params):.4f}")

    # Raw symbols repeat every decade, so use the parent symbol over the full range.
    print("\nFull-range cost (parent symbol 6E.FUT):")
    for schema in SCHEMAS:
        params = dict(
            request_params(schema, "6E.FUT", *FULL_RANGE), stype_in="parent"
        )
        cost = client.metadata.get_cost(**params)
        size = client.metadata.get_billable_size(**params)
        print(f"  {schema:10s} ${cost:.4f}  {size / 1e9:.2f} GB")

    print("\nFormula expiries vs. Databento definitions:")
    pairs = [
        p for p in roll_calendar(*EXPIRY_CHECK_YEARS)
        if EXPIRY_CHECK_FIRST <= p[2] <= EXPIRY_CHECK_LAST
    ]
    rows = compare_expiries(pairs, fetch_expirations(client, pairs))
    for front, formula, actual, ok in rows:
        if not ok:
            print(f"  {front}  formula {formula}  databento {actual}  MISMATCH")
    matched = sum(ok for *_, ok in rows)
    print(f"  {matched} of {len(rows)} match")


if __name__ == "__main__":
    main()
