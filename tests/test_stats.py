import itertools

import numpy as np
import pandas as pd
import pytest
from scipy import stats as scipy_stats

from euro_roll.stats import (
    COLUMNS,
    bootstrap_ci,
    sign_test,
    summarize,
    wilcoxon_test,
)

N_ROLLS = 57  # main-test rolls (docs/ANALYSIS_PLAN.md, decision 10)


def ticks(x):
    """Round to the half-tick grid that spread mids sit on."""
    return np.round(np.asarray(x) * 2) / 2


def changes(roll, control):
    """A ``summarize`` input with one row per roll, indexed by fake expiries."""
    expiries = pd.date_range("2010-09-13", periods=len(roll), freq="91D")
    return pd.DataFrame({"roll": roll, "control": control}, index=expiries)


def ar1(phi, n, rng, burn=50):
    """Autocorrelated series: each value is ``phi`` times the last plus noise."""
    e = rng.normal(size=n + burn)
    x = np.zeros(n + burn)
    for i in range(1, n + burn):
        x[i] = phi * x[i - 1] + e[i]
    return x[burn:]


# Sign and Wilcoxon tests

def test_sign_test_exact_value():
    # 9 of 10 positive: p = 2 * (C(10,0) + C(10,1)) / 2**10
    assert sign_test([1] * 9 + [-1]) == pytest.approx(22 / 1024)


def test_sign_test_drops_zeros():
    x = [1] * 9 + [-1]
    assert sign_test(x + [0, 0, 0]) == sign_test(x)


@pytest.mark.parametrize("x", [
    [3.5, -1.0, 2.0, 0.5, 4.0, -0.5, 1.5],  # ties
    # 12 values: all 2**12 sign patterns are used. Two zeros passed to scipy
    # would make it 2**14, more than n_resamples, and switch to random
    # patterns, so they must be dropped first.
    [0.5, -1.0, 1.5, 2.0, -2.5, 3.0, 3.5, 4.0, -4.5, 5.0, 5.5, 6.0],
])
def test_wilcoxon_drops_zeros(x):
    assert wilcoxon_test(x + [0.0, 0.0]) == wilcoxon_test(x)


def exact_signed_rank_p(x):
    """Two-sided signed-rank p-value from all 2**n sign patterns, ties averaged."""
    x = np.asarray(x, dtype=float)
    ranks = scipy_stats.rankdata(np.abs(x))
    observed = ranks[x > 0].sum()
    signs = np.array(list(itertools.product([0, 1], repeat=len(x))))
    null = signs @ ranks
    return min(1.0, 2 * min((null <= observed).mean(), (null >= observed).mean()))


def test_wilcoxon_is_exact_with_ties_above_13_values():
    # 14 tied values, where scipy's default uses the normal approximation
    # (p = 0.084 against an exact 0.106). With enough resamples to enumerate
    # every sign pattern, the test must match the exact p-value.
    x = [-1.0] * 4 + [-0.5, 0.5] + [1.0] * 3 + [1.5] * 5
    assert wilcoxon_test(x, n_resamples=2 ** len(x)) == pytest.approx(
        exact_signed_rank_p(x)
    )


def test_missing_values_are_rejected():
    for f in (sign_test, wilcoxon_test, bootstrap_ci):
        with pytest.raises(ValueError):
            f([1.0, 2.0, np.nan, -1.0])


def test_symmetric_data_gives_p_one():
    x = [-2.0, -1.0, 1.0, 2.0]
    assert sign_test(x) == pytest.approx(1.0)
    assert wilcoxon_test(x) == pytest.approx(1.0)


def test_all_zero_gives_nan():
    assert np.isnan(sign_test([0, 0, 0]))
    assert np.isnan(wilcoxon_test([0.0, 0.0, 0.0]))


def test_one_nonzero_value_gives_p_one():
    # One value has two sign patterns, equally extreme, as in the sign test.
    assert wilcoxon_test([0.0, 1.5, 0.0]) == sign_test([0.0, 1.5, 0.0]) == 1.0


def test_tests_hold_size_under_the_null():
    # Roll and control changes from the same distribution, on the tick grid
    # so ties and zeros occur as in real data. About 5% of nominal 5% tests
    # should reject; the sign test is discrete, so it rejects less often.
    # Fewer Wilcoxon resamples keep this fast; the p-value stays valid, on a
    # coarser grid.
    rng = np.random.default_rng(1)
    sims = 1000
    sign_rej = wilcoxon_rej = 0
    for _ in range(sims):
        d = np.abs(ticks(rng.normal(0, 3, N_ROLLS))) - np.abs(ticks(rng.normal(0, 3, N_ROLLS)))
        sign_rej += sign_test(d) < 0.05
        wilcoxon_rej += wilcoxon_test(d, n_resamples=199) < 0.05
    assert 0.015 <= sign_rej / sims <= 0.06
    assert 0.03 <= wilcoxon_rej / sims <= 0.07


# Bootstrap intervals

def test_constant_series_gives_point_interval():
    assert bootstrap_ci([2.5] * 10) == pytest.approx((2.5, 2.5))
    assert bootstrap_ci([2.5] * 10, block=4) == pytest.approx((2.5, 2.5))


def test_one_block_of_full_length_resamples_the_series_itself():
    # With block = n each resample is the series rotated, so every resample
    # mean equals the sample mean and the interval collapses to it.
    x = np.arange(8.0)
    assert bootstrap_ci(x, block=8) == pytest.approx((x.mean(), x.mean()))


def test_block_bootstrap_weights_every_roll_equally():
    # One large roll, placed first, in the middle or last. A plain
    # moving-block bootstrap draws the first and last rolls about a quarter
    # as often as the rest, so its interval would depend on where the large
    # roll sits; the circular version gives the same interval.
    def one_large_roll(i):
        x = np.zeros(N_ROLLS)
        x[i] = N_ROLLS
        return x

    intervals = {bootstrap_ci(one_large_roll(i), block=4) for i in (0, 28, N_ROLLS - 1)}
    assert len(intervals) == 1


@pytest.mark.parametrize("block", [0, 11])
def test_block_out_of_range(block):
    with pytest.raises(ValueError):
        bootstrap_ci(np.arange(10.0), block=block)


def test_bootstrap_is_reproducible():
    x = np.random.default_rng(2).normal(size=N_ROLLS)
    assert bootstrap_ci(x) == bootstrap_ci(x)
    assert bootstrap_ci(x, block=4) == bootstrap_ci(x, block=4)
    assert bootstrap_ci(x, seed=1) != bootstrap_ci(x, seed=2)


def test_bootstrap_width_matches_t_interval():
    # For n = 57 the percentile interval is about 3% narrower than the
    # t-interval (normal quantile, 1/n variance); a scaling bug would not be.
    x = np.random.default_rng(3).normal(1, 3, N_ROLLS)
    low, high = bootstrap_ci(x)
    half_t = scipy_stats.t.ppf(0.975, N_ROLLS - 1) * x.std(ddof=1) / np.sqrt(N_ROLLS)
    assert (high - low) / (2 * half_t) == pytest.approx(0.97, abs=0.04)
    assert low < x.mean() < high


def test_bootstrap_coverage_on_iid_data():
    rng = np.random.default_rng(4)
    sims, covered = 500, 0
    for i in range(sims):
        low, high = bootstrap_ci(rng.normal(1, 3, N_ROLLS), n_resamples=2000, seed=i)
        covered += low <= 1 <= high
    assert 0.90 <= covered / sims <= 0.98


def test_block_interval_is_wider_when_rolls_are_dependent():
    # Nearby rolls sharing a rate regime act like positive autocorrelation.
    # The ordinary bootstrap ignores it; the block bootstrap keeps it within
    # each run of four rolls, so its interval is wider.
    x = ar1(0.8, N_ROLLS, np.random.default_rng(5))
    low, high = bootstrap_ci(x)
    block_low, block_high = bootstrap_ci(x, block=4)
    assert block_high - block_low > 1.2 * (high - low)


# summarize

def test_summarize_layout():
    rng = np.random.default_rng(7)
    out = summarize(changes(ticks(rng.normal(0, 3, N_ROLLS)), ticks(rng.normal(0, 3, N_ROLLS))))
    assert list(out.index) == ["h1", "h2_roll", "h2_roll_minus_control"]
    assert list(out.columns) == COLUMNS
    assert (out["n"] == N_ROLLS).all()
    # Only the statistics in the plan are filled in.
    assert out.loc["h2_roll", ["wilcoxon_p", "mean", "ci_low", "block_ci_low"]].isna().all()
    assert out.loc["h2_roll_minus_control", ["sign_p", "wilcoxon_p"]].isna().all()


def test_summarize_reports_both_planned_intervals():
    # Decision 9: percentile bootstrap (main) and blocks of four rolls
    # (sensitivity), plus the lag-1 autocorrelation as the #29 diagnostic.
    rng = np.random.default_rng(12)
    roll, control = ticks(3 * ar1(0.8, N_ROLLS, rng)), ticks(3 * ar1(0.8, N_ROLLS, rng))
    out = summarize(changes(roll, control))
    for row, x in [("h1", np.abs(roll) - np.abs(control)), ("h2_roll_minus_control", roll - control)]:
        assert tuple(out.loc[row, ["ci_low", "ci_high"]]) == bootstrap_ci(x)
        assert tuple(out.loc[row, ["block_ci_low", "block_ci_high"]]) == bootstrap_ci(x, block=4)
        assert out.loc[row, "lag1_autocorr"] == pytest.approx(np.corrcoef(x[:-1], x[1:])[0, 1])


@pytest.mark.parametrize("n", [3, 4, 7])
def test_summarize_leaves_the_block_interval_empty_below_two_blocks(n):
    # A subset can be small, e.g. the exploratory rolls without a Fed or ECB
    # decision (decision 7). With n = 4 every resample would be a rotation
    # of the same four rolls, giving a zero-width interval.
    rng = np.random.default_rng(n)
    out = summarize(changes(ticks(rng.normal(0, 3, n)), ticks(rng.normal(0, 3, n))))
    assert out.loc["h1", "n"] == n
    assert out.loc["h1", ["ci_low", "ci_high"]].notna().all()
    assert out.loc["h1", ["block_ci_low", "block_ci_high"]].isna().all()


def test_summarize_reports_the_block_interval_from_two_blocks():
    # The 8 exploratory rolls are exactly two blocks.
    rng = np.random.default_rng(8)
    out = summarize(changes(ticks(rng.normal(0, 3, 8)), ticks(rng.normal(0, 3, 8))))
    low, high = out.loc["h1", ["block_ci_low", "block_ci_high"]]
    assert low < high


def test_summarize_counts_rises_falls_and_zeros():
    # 30 rolls where the spread rose, 17 where it fell, 10 unchanged.
    roll = [1.0] * 30 + [-0.5] * 17 + [0.0] * 10
    h2 = summarize(changes(roll, [0.0] * 57)).loc["h2_roll"]
    assert (h2["n"], h2["n_positive"], h2["n_negative"], h2["n_zero"]) == (57, 30, 17, 10)
    assert h2["sign_p"] == pytest.approx(scipy_stats.binomtest(30, 47).pvalue)


def test_summarize_h1_detects_a_planted_magnitude_effect():
    # Roll-week moves three times as large as control-week moves.
    rng = np.random.default_rng(8)
    out = summarize(changes(ticks(rng.normal(0, 9, N_ROLLS)), ticks(rng.normal(0, 3, N_ROLLS))))
    h1 = out.loc["h1"]
    assert h1["sign_p"] < 0.01
    assert h1["wilcoxon_p"] < 0.01
    assert h1["ci_low"] > 0
    assert h1["block_ci_low"] > 0
    assert h1["n_positive"] > h1["n_negative"]


def test_summarize_h2_detects_a_planted_rise():
    # The spread rises by 2 ticks on average in roll weeks only.
    rng = np.random.default_rng(9)
    out = summarize(changes(ticks(rng.normal(2, 3, N_ROLLS)), ticks(rng.normal(0, 3, N_ROLLS))))
    assert out.loc["h2_roll", "sign_p"] < 0.01
    assert out.loc["h2_roll", "n_positive"] > out.loc["h2_roll", "n_negative"]
    assert out.loc["h2_roll_minus_control", "ci_low"] > 0
    assert out.loc["h2_roll_minus_control", "block_ci_low"] > 0


def test_summarize_drops_rolls_missing_either_change():
    rng = np.random.default_rng(10)
    df = changes(ticks(rng.normal(0, 3, 12)), ticks(rng.normal(0, 3, 12)))
    df.iloc[3, 0] = np.nan  # roll window excluded under decision 5
    df.iloc[7, 1] = np.nan  # control window excluded
    out = summarize(df)
    assert (out["n"] == 10).all()
    assert out.loc["h1", "mean"] == pytest.approx(
        (df["roll"].abs() - df["control"].abs()).dropna().mean()
    )


def test_summarize_sorts_rolls_before_the_block_bootstrap():
    rng = np.random.default_rng(11)
    df = changes(ticks(rng.normal(0, 3, 16)), ticks(rng.normal(0, 3, 16)))
    shuffled = df.sample(frac=1, random_state=0)
    pd.testing.assert_frame_equal(summarize(shuffled), summarize(df))


def test_summarize_accepts_plain_dates():
    df = changes(ticks(np.random.default_rng(13).normal(0, 3, 16)), [0.5] * 16)
    as_dates = df.set_axis([t.date() for t in df.index]).iloc[::-1]
    pd.testing.assert_frame_equal(summarize(as_dates), summarize(df))


def test_summarize_rejects_symbol_index():
    # 6EU0 is both the 2010 and the 2020 contract, and sorting symbols
    # would put 6EH0 next to 6EH1, so rolls must be indexed by date.
    df = pd.DataFrame({"roll": [1.0] * 4, "control": [0.5] * 4},
                      index=["6EU0", "6EZ0", "6EH1", "6EM1"])
    with pytest.raises(ValueError, match="expiry date"):
        summarize(df)


def test_summarize_rejects_duplicate_rolls():
    df = changes([1.0, 2.0, 3.0, 4.0], [0.5] * 4)
    df.index = df.index[[0, 1, 1, 2]]
    with pytest.raises(ValueError, match="once"):
        summarize(df)


def test_summarize_with_no_usable_roll():
    df = changes([np.nan, 1.0], [0.5, np.nan])
    with pytest.raises(ValueError):
        summarize(df)
