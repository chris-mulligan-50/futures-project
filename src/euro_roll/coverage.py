"""Task 2: verify Databento coverage and cost for 6E quarterly contracts.

Read-only: only calls metadata endpoints, which do not bill for data.

    python -m euro_roll.coverage
"""
import os

import databento as db

DATASET = "GLBX.MDP3"
SCHEMAS = ["ohlcv-1d", "bbo-1m", "definition"]
FULL_RANGE = ("2010-06-06", "2026-09-30")
SAMPLE_RANGE = ("2025-08-01", "2025-09-20")  # one roll: 6EU5 -> 6EZ5
SAMPLE_SYMBOLS = ["6EU5", "6EZ5"]
QUARTER_CODES = "HMUZ"


def quarterly_symbols(first_year, last_year):
    """Raw symbols like 6EH0 (single-digit year, as in the notebook)."""
    return [
        f"6E{code}{year % 10}"
        for year in range(first_year, last_year + 1)
        for code in QUARTER_CODES
    ]


def main():
    client = db.Historical(key=os.environ["DATABENTO_API_KEY"])

    print("Dataset range:")
    print(client.metadata.get_dataset_range(dataset=DATASET))

    print("\nSample cost (one roll):")
    for schema in SCHEMAS:
        cost = client.metadata.get_cost(
            dataset=DATASET, schema=schema, symbols=SAMPLE_SYMBOLS,
            stype_in="raw_symbol", start=SAMPLE_RANGE[0], end=SAMPLE_RANGE[1],
        )
        print(f"  {schema:10s} ${cost:.4f}")

    # Single-digit years repeat every decade, so a raw-symbol query over the
    # full range is ambiguous; use the parent symbol for cost and size only.
    print("\nFull-range cost (parent symbol 6E.FUT):")
    for schema in SCHEMAS:
        params = dict(
            dataset=DATASET, schema=schema, symbols=["6E.FUT"],
            stype_in="parent", start=FULL_RANGE[0], end=FULL_RANGE[1],
        )
        cost = client.metadata.get_cost(**params)
        size = client.metadata.get_billable_size(**params)
        print(f"  {schema:10s} ${cost:.4f}  {size / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
