"""Power of the main test: how large an effect would it have found?

Added after the main-test results (deviation log of ``docs/ANALYSIS_PLAN.md``),
so it describes the design, not the evidence.

Null data come from the observed changes: resample the main-test rolls with
replacement and, within each, swap the roll and control change at random, so
the two are exchangeable. An effect is then added to the roll change:

* ``shift``: the roll moves the spread by ``size`` ticks every roll (up if
  positive, down if negative).
* ``scale``: roll-week changes are ``size`` times as large (more volatile).

Power is the share of simulations in which a test rejects at 5%, two-sided.
The tests are the plan's sign tests (``stats.sign_test``) and the Wilcoxon
test on d, with scipy's default p-value since a permutation p-value in every
simulation would be slow, and t-tests standing in for the bootstrap intervals
of the two means. Reads ``outputs/roll_vs_control.csv`` from the main test
and writes ``outputs/power.csv``; downloads nothing:

    PYTHONPATH=src python -m euro_roll.power
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp, wilcoxon

from euro_roll import cache, config
from euro_roll.stats import sign_test

N_SIMULATIONS = 2_000
SEED = 37000
LEVEL = 0.05
EFFECTS: Tuple[Tuple[str, float], ...] = (
    ("shift", -3), ("shift", -2), ("shift", -1), ("shift", 0),
    ("shift", 1), ("shift", 2), ("shift", 3), ("shift", 4),
    ("scale", 1.5), ("scale", 2),
)
TESTS = ["h1_mean", "h1_sign", "h1_wilcoxon", "h2_sign", "h2_mean"]
OUTPUTS = cache.REPO_ROOT / "outputs"


def p_values(roll: np.ndarray, control: np.ndarray) -> Dict[str, float]:
    """Two-sided p-value of each test in ``TESTS``."""
    d = np.abs(roll) - np.abs(control)
    nonzero = d[d != 0]
    return {
        "h1_mean": ttest_1samp(d, 0).pvalue,
        "h1_sign": sign_test(d),
        "h1_wilcoxon": wilcoxon(nonzero).pvalue if len(nonzero) else np.nan,
        "h2_sign": sign_test(roll),
        "h2_mean": ttest_1samp(roll - control, 0).pvalue,
    }


def power(
    roll, control, effect: str, size: float,
    n_simulations: int = N_SIMULATIONS, seed: int = SEED,
) -> Dict[str, float]:
    """Share of simulations in which each test rejects at ``LEVEL``."""
    if effect not in ("shift", "scale"):
        raise ValueError(f"effect must be 'shift' or 'scale', got {effect!r}")
    roll, control = np.asarray(roll, dtype=float), np.asarray(control, dtype=float)
    n = len(roll)
    rng = np.random.default_rng(seed)
    rejections = dict.fromkeys(TESTS, 0)
    for _ in range(n_simulations):
        rows = rng.integers(0, n, n)
        swap = rng.random(n) < 0.5
        r = np.where(swap, control[rows], roll[rows])
        c = np.where(swap, roll[rows], control[rows])
        r = r + size if effect == "shift" else r * size
        for test, p in p_values(r, c).items():
            rejections[test] += bool(p < LEVEL)  # a NaN p-value never rejects
    return {test: k / n_simulations for test, k in rejections.items()}


def power_table(
    changes: pd.DataFrame,
    effects: Iterable[Tuple[str, float]] = EFFECTS,
    n_simulations: int = N_SIMULATIONS,
) -> pd.DataFrame:
    """``power`` for each effect, on the rolls of ``changes`` with both changes."""
    kept = changes[["roll", "control"]].dropna()
    rows = {
        (effect, size): power(kept["roll"], kept["control"], effect, size, n_simulations)
        for effect, size in effects
    }
    table = pd.DataFrame.from_dict(rows, orient="index", columns=TESTS)
    table.index.names = ["effect", "size"]
    return table


def main() -> None:
    changes = pd.read_csv(OUTPUTS / "roll_vs_control.csv", index_col="expiry", parse_dates=["expiry"])
    expiry = changes.index.date
    main_test = changes[(expiry >= config.FIRST_EXPIRY) & (expiry < config.EXPLORATORY_FIRST_EXPIRY)]
    table = power_table(main_test)
    table.to_csv(OUTPUTS / "power.csv")
    print(f"{len(main_test)} main-test rolls, {N_SIMULATIONS} simulations per effect")
    print(table.round(2))


if __name__ == "__main__":
    main()
