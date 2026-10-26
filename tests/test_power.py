from datetime import date

import numpy as np
import pandas as pd
import pytest

from euro_roll.power import TESTS, power, power_table

N_ROLLS = 57
N_SIMULATIONS = 400  # enough to tell 5% from 100%, and fast


def ticks(x):
    """Round to the half-tick grid, as real changes are."""
    return np.round(np.asarray(x) * 2) / 2


@pytest.fixture
def changes():
    rng = np.random.default_rng(3)
    return ticks(rng.normal(0, 3, N_ROLLS)), ticks(rng.normal(0, 3, N_ROLLS))


def test_no_effect_rejects_about_five_percent(changes):
    rates = power(*changes, "shift", 0, n_simulations=N_SIMULATIONS)
    assert all(rate < 0.12 for rate in rates.values())


def test_a_large_push_is_found(changes):
    rates = power(*changes, "shift", 6, n_simulations=N_SIMULATIONS)
    assert rates["h1_wilcoxon"] > 0.9 and rates["h2_mean"] > 0.9


def test_power_grows_with_the_push(changes):
    small = power(*changes, "shift", 1, n_simulations=N_SIMULATIONS)
    large = power(*changes, "shift", 3, n_simulations=N_SIMULATIONS)
    assert all(large[t] >= small[t] for t in TESTS)


def test_scaling_does_not_move_the_direction_tests(changes):
    # Larger roll-week moves in both directions say nothing about direction.
    rates = power(*changes, "scale", 2, n_simulations=N_SIMULATIONS)
    assert rates["h1_wilcoxon"] > 0.5
    assert rates["h2_sign"] < 0.12


def test_seed_makes_it_reproducible(changes):
    assert power(*changes, "shift", 2, n_simulations=50) == power(*changes, "shift", 2, n_simulations=50)


def test_unknown_effect_is_rejected(changes):
    with pytest.raises(ValueError):
        power(*changes, "drift", 1)


def test_table_uses_rolls_with_both_changes(changes):
    roll, control = changes
    frame = pd.DataFrame(
        {"roll": np.append(roll, np.nan), "control": np.append(control, 1.0)},
        index=[date(2010, 9, 13)] * (N_ROLLS + 1),
    )
    table = power_table(frame, effects=[("shift", 0), ("scale", 2)], n_simulations=50)
    assert list(table.index) == [("shift", 0), ("scale", 2)]
    assert list(table.columns) == TESTS
    expected = power(roll, control, "shift", 0, n_simulations=50)
    assert table.loc[("shift", 0)].to_dict() == expected
