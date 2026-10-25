import math
from datetime import date

import pandas as pd
import pytest

from euro_roll.carry import deferred_expiry, excess, implied_gap


def test_deferred_expiry_is_the_next_quarterly_contract():
    assert deferred_expiry(date(2026, 3, 16)) == date(2026, 6, 15)
    assert deferred_expiry(date(2025, 12, 15)) == date(2026, 3, 16)  # December rolls into March
    assert deferred_expiry(date(2023, 6, 16)) == date(2023, 9, 18)  # 6EM3, moved by Juneteenth


def test_implied_gap_inverts_cost_of_carry():
    # A 2% gap over a quarter: F_deferred = F_front * exp(0.02 * 0.25).
    front = 1.1
    deferred = front * math.exp(0.02 * 0.25)
    row = pd.Series({"front_bid": front, "front_ask": front, "deferred_bid": deferred, "deferred_ask": deferred})
    assert implied_gap(row, 0.25) == pytest.approx(2.0)


def test_excess_is_implied_minus_observed_per_window():
    carry = pd.DataFrame({
        "roll_implied": [5.0], "roll_spot": [3.0], "roll_forward": [4.0],
        "control_implied": [1.0], "control_spot": [-1.0], "control_forward": [0.0],
    })
    assert excess(carry, "spot").to_dict("records") == [{"roll": 2.0, "control": 2.0}]
    assert excess(carry, "forward").to_dict("records") == [{"roll": 1.0, "control": 1.0}]
