"""Verify Databento coverage, cost and 6E expiry dates (Task 2, issue #8).

Only metadata calls and one-day definition pulls (a fraction of a cent), so
it is safe to run:

    PYTHONPATH=src python -m euro_roll.coverage
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Iterable, List, Tuple

from euro_roll.client import get_client
from euro_roll.download import DATASET, fetch_definitions, request_params
from euro_roll.expiries import RollPair, roll_calendar

SCHEMAS = ["ohlcv-1d", "bbo-1m", "definition"]
FULL_RANGE = ("2010-06-06", "2026-09-30")
SAMPLE_RANGE = ("2025-08-01", "2025-09-20")  # one roll: 6EU5 -> 6EZ5
SAMPLE_SYMBOLS = ["6EU5", "6EZ5"]
EXPIRY_CHECK_YEARS = (2024, 2026)
EXPIRY_CHECK_FIRST = date(2024, 12, 1)  # the eight recent rolls
EXPIRY_CHECK_LAST = date(2026, 9, 30)


def compare_expiries(
    pairs: Iterable[RollPair], actual: Dict[str, date]
) -> List[Tuple[str, date, date, bool]]:
    """(front, formula expiry, Databento expiry, match) for each pair."""
    return [
        (front, expiry, actual[front], actual[front] == expiry)
        for front, _, expiry in pairs
    ]


def fetch_expirations(client, pairs: Iterable[RollPair]) -> Dict[str, date]:
    """Databento expiration date of each front contract.

    Raw symbols repeat every ten years, so each request covers one day
    shortly before that contract's expiry.
    """
    actual = {}
    for front, _, expiry in pairs:
        day = expiry - timedelta(days=10)
        defs = fetch_definitions([front], day, day + timedelta(days=1), client)
        actual[front] = defs["expiration"].iloc[-1].date()
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
    for front, formula, actual, ok in compare_expiries(
        pairs, fetch_expirations(client, pairs)
    ):
        print(f"  {front}  formula {formula}  databento {actual}  "
              f"{'OK' if ok else 'MISMATCH'}")


if __name__ == "__main__":
    main()
