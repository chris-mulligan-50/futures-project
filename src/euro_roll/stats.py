"""Paired roll-vs-control statistics (Tasks 22 and 23, issues #28 and #29).

Implements the test statistics and decision 9 of ``docs/ANALYSIS_PLAN.md``.
The unit is the roll: each roll gives one net spread change in its roll
window and one in its control window, in ticks, from the baseline Friday to
the ending Friday.

* H1 (magnitude): d = |roll change| - |control change|.
* H2 (direction): the roll change, and roll change minus control change.

Intervals for a mean (decision 9): a percentile bootstrap (main) and a
circular block bootstrap over runs of four consecutive rolls, one year
(sensitivity, for rate regimes shared by nearby rolls). All p-values are
two-sided.

A change of exactly zero has no sign, and the half-tick grid makes zeros
common. The sign and Wilcoxon tests drop them, the standard convention, and
``n_zero`` counts them. They stay in the mean.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from scipy.stats import PermutationMethod, binomtest, wilcoxon

N_RESAMPLES = 10_000
SEED = 37000
LEVEL = 0.95
BLOCK_ROLLS = 4  # one year of quarterly rolls

COLUMNS = [
    "n", "n_positive", "n_negative", "n_zero", "sign_p", "wilcoxon_p",
    "mean", "ci_low", "ci_high", "block_ci_low", "block_ci_high",
    "lag1_autocorr",
]


def _as_array(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if np.isnan(x).any():
        raise ValueError("drop missing rolls before testing")
    return x


def sign_test(x) -> float:
    """Two-sided exact sign test: are positive and negative values equally likely?"""
    x = _as_array(x)
    nonzero = x[x != 0]
    if len(nonzero) == 0:
        return np.nan
    return float(binomtest(int((nonzero > 0).sum()), len(nonzero)).pvalue)


def wilcoxon_test(x, n_resamples: int = N_RESAMPLES, seed: int = SEED) -> float:
    """Two-sided Wilcoxon signed-rank test: is ``x`` symmetric about zero?

    Zeros are dropped first. The p-value comes from flipping the signs of
    the ranked values, which stays exact when values tie, as they do on the
    tick grid. All 2**n sign patterns are used when there are at most
    ``n_resamples`` of them (n <= 13 by default); otherwise ``n_resamples``
    random ones with a fixed seed. Scipy's default would switch to the
    normal approximation above 13 tied values, so the 8 exploratory and 57
    main rolls would get different methods.
    """
    x = _as_array(x)
    nonzero = x[x != 0]
    if len(nonzero) == 0:
        return np.nan
    method = PermutationMethod(n_resamples=n_resamples, rng=seed)
    return float(wilcoxon(nonzero, method=method).pvalue)


def bootstrap_ci(
    x,
    block: int = 1,
    n_resamples: int = N_RESAMPLES,
    level: float = LEVEL,
    seed: int = SEED,
) -> Tuple[float, float]:
    """Percentile interval for the mean of ``x``, which must be in roll order.

    ``block=1`` is the ordinary bootstrap. With ``block > 1`` each resample
    joins runs of ``block`` consecutive rolls, so dependence between nearby
    rolls is kept. Runs may wrap from the last roll to the first (circular
    block bootstrap); without that, the first and last rolls would be drawn
    about a quarter as often as the rest.
    """
    x = _as_array(x)
    n = len(x)
    if not 1 <= block <= n:
        raise ValueError(f"block must be between 1 and len(x) = {n}, got {block}")
    rng = np.random.default_rng(seed)
    n_runs = -(-n // block)  # ceil(n / block)
    starts = rng.integers(0, n, size=(n_resamples, n_runs))
    idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(n_resamples, -1)[:, :n]
    means = x[idx].mean(axis=1)
    tail = (1 - level) / 2
    low, high = np.quantile(means, [tail, 1 - tail])
    return float(low), float(high)


def _counts_and_sign_test(x: np.ndarray) -> Dict[str, float]:
    return {
        "n_positive": int((x > 0).sum()),
        "n_negative": int((x < 0).sum()),
        "n_zero": int((x == 0).sum()),
        "sign_p": sign_test(x),
    }


def _mean_and_intervals(x: np.ndarray) -> Dict[str, float]:
    low, high = bootstrap_ci(x)
    block_low, block_high = bootstrap_ci(x, block=BLOCK_ROLLS)
    return {
        "mean": float(x.mean()),
        "ci_low": low,
        "ci_high": high,
        "block_ci_low": block_low,
        "block_ci_high": block_high,
        # Dependence diagnostic for #29. Reported only; decision 9 fixes both
        # intervals in advance, so it does not choose between them.
        "lag1_autocorr": float(pd.Series(x).autocorr()),
    }


def summarize(changes: pd.DataFrame) -> pd.DataFrame:
    """The planned H1 and H2 statistics, one row each.

    ``changes`` has one row per roll, indexed by expiry date, with columns
    ``roll`` and ``control``: the net spread change in ticks in each window.
    A roll missing either change (excluded under decision 5) is dropped, so
    ``n`` is the number of rolls the result rests on. The block bootstrap
    treats the remaining rolls as consecutive, so a block can span a
    dropped roll.

    Rows:

    * ``h1``: d = |roll| - |control|; sign and Wilcoxon tests, mean and intervals.
    * ``h2_roll``: sign test on the roll change; ``n_positive`` counts the
      rolls where the spread rose.
    * ``h2_roll_minus_control``: mean of roll - control and its intervals.

    Cells the plan does not call for are NaN, so no extra test is reported.
    """
    # The block bootstrap needs rolls in date order. Front symbols would not
    # do: 6EU0 is both the 2010 and the 2020 contract.
    if not all(isinstance(v, date) for v in changes.index):
        raise ValueError("index rolls by expiry date, not by symbol")
    if not changes.index.is_unique:
        raise ValueError("each roll must appear once")
    kept = changes[["roll", "control"]].sort_index().dropna()
    if kept.empty:
        raise ValueError("no roll has both a roll and a control change")

    # Changes in spread_ticks are multiples of half a tick, which floats hold
    # exactly, so equal moves give an exact zero below.
    roll = kept["roll"].to_numpy(dtype=float)
    control = kept["control"].to_numpy(dtype=float)
    d = np.abs(roll) - np.abs(control)
    n = len(kept)
    rows = {
        "h1": {
            "n": n, **_counts_and_sign_test(d),
            "wilcoxon_p": wilcoxon_test(d), **_mean_and_intervals(d),
        },
        "h2_roll": {"n": n, **_counts_and_sign_test(roll)},
        "h2_roll_minus_control": {"n": n, **_mean_and_intervals(roll - control)},
    }
    return pd.DataFrame.from_dict(rows, orient="index").reindex(columns=COLUMNS)
