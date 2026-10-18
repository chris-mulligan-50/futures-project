"""Shared pytest fixtures. The synthetic 6E data is documented in ``synthetic.py``."""
import pytest

import synthetic


@pytest.fixture
def synthetic_bbo():
    """Synthetic ``bbo-1m`` quotes, shaped like ``fetch_bbo_1m`` output."""
    return synthetic.bbo_1m()


@pytest.fixture
def synthetic_daily():
    """Synthetic ``ohlcv-1d`` bars, shaped like ``fetch_daily_bars`` output."""
    return synthetic.daily_bars()


@pytest.fixture
def synthetic_expected():
    """Per-day answers for the synthetic data: spread, quote ages, volumes, status."""
    return synthetic.EXPECTED.copy()
