"""Main test: roll vs. control spread changes and their statistics (#28, #29).

For each roll, download the ``bbo-1m`` quotes its two windows need, take the
10:00 snapshots (``spread.py``, decision 6 of ``docs/ANALYSIS_PLAN.md``),
the net change per window (``changes.py``, decision 5) and run the planned
tests (``stats.py``, decision 9) on the main-test and exploratory rolls
separately (decision 10). Writes to ``outputs/``:

* ``roll_vs_control.csv``: one row per roll, both changes in ticks, the
  days used, the widest quote on them and any Fed or ECB decision between
  them (``meetings.py``, decision 7).
* ``carry.csv``: implied and observed rate-gap changes per window, in
  basis points (``carry.py``, decision 8).
* ``dropped_days.csv``: every dropped snapshot day and its reason (#24).
* ``meetings.csv``: per split, how many roll and control windows contain
  an FOMC or ECB decision (decision 7's overlap table).
* ``stats.csv``: ``stats.summarize`` for each split (``main_test``,
  ``exploratory``) and specification:

  - ``spread``: the main test, changes in ticks.
  - ``narrow_quotes``: without rolls where either leg is quoted wider than
    5 ticks on a day a change uses (decision 11's sensitivity check).
  - ``no_meetings``: without rolls where either window contains an FOMC or
    ECB decision (decision 7's sensitivity check).
  - ``carry_3m``: implied minus observed 3-month gap change, in basis
    points (decision 8, main comparison).
  - ``carry_forward``: the same against the forward gap (sensitivity).
* ``figures/roll_vs_control.png``: both changes per roll over time.

Decision 10: if more than 20% of the snapshot days of the main-test rolls
before 2017-06 are dropped (holidays aside), the main test starts at the
2017-06 roll instead. Only dropped days decide this, not spread changes.

Run on real data (shows the estimated cost and downloads nothing unless
``--download`` is given; cached requests cost nothing). Run ``--all`` only
once the plan is tagged ``plan-v1``:

    PYTHONPATH=src python -m euro_roll.analyze              # 8 exploratory rolls
    PYTHONPATH=src python -m euro_roll.analyze --all        # all 65 rolls
    PYTHONPATH=src python -m euro_roll.analyze --all --download

``--control-offset WEEKS`` moves the control window (default 4, the plan's)
and writes to ``outputs/control_offset_<WEEKS>/`` instead. A robustness
check added after the plan (#30), not part of the main test.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from euro_roll import cache, config
from euro_roll.carry import carry_table, excess
from euro_roll.changes import KINDS, change_table, needed_days, roll_changes
from euro_roll.client import get_client
from euro_roll.download import fetch_bbo_1m, request_params
from euro_roll.expiries import roll_calendar
from euro_roll.meetings import meeting_table, overlap
from euro_roll.rates import load_rates
from euro_roll.spread import daily_spreads, session_open, snapshot_time
from euro_roll.stats import summarize
from euro_roll.windows import CONTROL_OFFSET_WEEKS, RollWindows, Window, select_windows

OUTPUTS = cache.REPO_ROOT / "outputs"
FALLBACK_FIRST_EXPIRY = date(2017, 6, 1)  # decision 10
MAX_DROP_SHARE = 0.20  # decision 10
MAX_WIDTH_TICKS = 5  # decision 11 sensitivity

Fetch = Callable[[List[str], pd.Timestamp, pd.Timestamp], pd.DataFrame]


def quote_range(window: Window) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Start and end of the ``bbo-1m`` request for ``window``.

    From the session open of its first snapshot day to just after the ending
    Friday's snapshot, so every snapshot sees the whole session before it.
    """
    start = session_open(needed_days(window)[0])
    return start, snapshot_time(window.end) + pd.Timedelta(minutes=1)


def roll_spreads(roll: RollWindows, fetch: Fetch) -> Dict[str, pd.DataFrame]:
    """``daily_spreads`` for both windows of ``roll``, keyed by window kind."""
    out = {}
    for kind in KINDS:
        window = getattr(roll, kind)
        bbo = fetch([roll.front, roll.deferred], *quote_range(window))
        out[kind] = daily_spreads(bbo, roll.front, roll.deferred, needed_days(window))
    return out


def dropped_log(spreads: Dict[date, Dict[str, pd.DataFrame]]) -> pd.DataFrame:
    """Every dropped snapshot day: expiry, window kind, day and reason."""
    rows = [
        {"expiry": expiry, "window": kind, "day": day, "reason": reason}
        for expiry, by_kind in spreads.items()
        for kind, s in by_kind.items()
        for day, reason in s.loc[~s["valid"], "reason"].items()
    ]
    return pd.DataFrame(rows, columns=["expiry", "window", "day", "reason"])


def early_drop_share(rolls: List[RollWindows], spreads: Dict[date, Dict[str, pd.DataFrame]]) -> float:
    """Decision 10's measure: share of snapshot days dropped, pooled over the
    main-test rolls before 2017-06.

    Snapshot days are each window's baseline Friday and five days. Holidays
    are left out of both counts, since decision 6 drops them by design.
    """
    dropped = total = 0
    for roll in rolls:
        if not config.FIRST_EXPIRY <= roll.expiry < FALLBACK_FIRST_EXPIRY:
            continue
        for kind in KINDS:
            window = getattr(roll, kind)
            s = spreads[roll.expiry][kind].loc[[window.baseline] + window.days]
            s = s[s["reason"] != "holiday"]
            dropped += int((~s["valid"]).sum())
            total += len(s)
    return dropped / total if total else float("nan")


def plot_roll_vs_control(changes: pd.DataFrame, path) -> Path:
    """Roll- and control-window change per roll by expiry, exploratory rolls shaded."""
    roll_color, control_color, ink, muted = "#2a78d6", "#898781", "#0b0b0b", "#52514e"
    expiry = pd.to_datetime(pd.Series(changes.index, index=changes.index))

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.axhline(0, color="#c3c2b7", lw=1, zorder=1)
    exploratory = expiry >= pd.Timestamp(config.EXPLORATORY_FIRST_EXPIRY)
    if exploratory.any():
        start = expiry[exploratory].min() - pd.Timedelta(days=45)
        ax.axvspan(start, expiry.max() + pd.Timedelta(days=45), color="#f0efec", zorder=0)
        ax.text(start + pd.Timedelta(days=20), 1, "exploratory rolls", transform=ax.get_xaxis_transform(),
                va="top", fontsize=9, color=muted)
    for column, color, label, size in [
        ("control", control_color, "Control week", 30),
        ("roll", roll_color, "Roll week", 40),
    ]:
        ax.scatter(expiry, changes[column], s=size, color=color, label=label,
                   edgecolors="#fcfcfb", linewidths=1, zorder=3)

    ax.set_ylabel("Net spread change (ticks)", color=ink)
    ax.set_title("Spread change per roll, baseline Friday to ending Friday",
                 loc="left", fontsize=11, color=ink, pad=24)
    ax.grid(axis="y", color="#e1e0d9", lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=muted)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1), ncol=2, frameon=False, labelcolor=ink)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)
    return path


def run(
    rolls: List[RollWindows],
    fetch: Fetch,
    rates: pd.DataFrame,
    out_dir=OUTPUTS,
    early_share: Optional[float] = None,
) -> Dict[str, object]:
    """Compute everything for ``rolls`` and write it to ``out_dir``.

    ``rates`` is ``rates.load_rates()`` output. ``early_share`` replaces
    decision 10's drop share from ``rolls``, so a run with other control
    windows keeps the main test's sample. Returns the tables written and
    the drop share used.
    """
    spreads = {roll.expiry: roll_spreads(roll, fetch) for roll in rolls}
    share = early_drop_share(rolls, spreads) if early_share is None else early_share
    changes = change_table(roll_changes(roll, spreads[roll.expiry]) for roll in rolls)
    decisions = meeting_table(changes)
    changes = changes.join(decisions)
    carry = carry_table(rolls, spreads, changes, rates)
    dropped = dropped_log(spreads)

    narrow = (changes[[f"{kind}_max_width" for kind in KINDS]] <= MAX_WIDTH_TICKS).all(axis=1)
    calm = decisions.isna().all(axis=1)
    specs = {
        "spread": changes,
        "narrow_quotes": changes[narrow],
        "no_meetings": changes[calm],
        "carry_3m": excess(carry, "spot"),
        "carry_forward": excess(carry, "forward"),
    }
    pairs = [(r.front, r.deferred, r.expiry) for r in rolls]
    first = FALLBACK_FIRST_EXPIRY if share > MAX_DROP_SHARE else config.FIRST_EXPIRY
    splits = {
        "main_test": [p[2] for p in config.main_test(pairs) if p[2] >= first],
        "exploratory": [p[2] for p in config.exploratory(pairs)],
    }
    stats = {}
    for split, expiries in splits.items():
        for spec, table in specs.items():
            subset = table[table.index.isin(expiries)]
            if subset[["roll", "control"]].notna().all(axis=1).any():
                stats[(split, spec)] = summarize(subset)
    stats = pd.concat(stats, names=["split", "spec", "test"])
    # Over the rolls the tests use: both changes present.
    tested = changes[["roll", "control"]].notna().all(axis=1)
    overlaps = pd.concat(
        {split: overlap(decisions[tested & decisions.index.isin(expiries)]) for split, expiries in splits.items()},
        names=["split", "bank"],
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    changes.to_csv(out_dir / "roll_vs_control.csv")
    carry.to_csv(out_dir / "carry.csv")
    dropped.to_csv(out_dir / "dropped_days.csv", index=False)
    overlaps.to_csv(out_dir / "meetings.csv")
    stats.to_csv(out_dir / "stats.csv")
    plot_roll_vs_control(changes, out_dir / "figures" / "roll_vs_control.png")
    return {
        "roll_vs_control": changes, "carry": carry, "dropped_days": dropped,
        "meetings": overlaps, "stats": stats, "early_drop_share": share,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--all", action="store_true",
                        help="all 65 rolls, not only the 8 exploratory ones")
    parser.add_argument("--download", action="store_true",
                        help="download after showing the cost (default: cost only)")
    parser.add_argument("--control-offset", type=int, default=CONTROL_OFFSET_WEEKS, metavar="WEEKS",
                        help="weeks from the control to the roll window (default: %(default)s)")
    args = parser.parse_args(argv)

    calendar = roll_calendar(2010, 2026)
    pairs = config.exploratory(calendar)
    if args.all:
        pairs = config.main_test(calendar) + pairs
    rolls = select_windows(pairs, args.control_offset)
    plan = select_windows(pairs)  # decision 10 is judged on the plan's windows

    client = get_client()
    requests = {}
    for roll in rolls + plan:
        for kind in KINDS:
            params = request_params("bbo-1m", [roll.front, roll.deferred], *quote_range(getattr(roll, kind)))
            requests[cache.cache_path(params)] = params
    cost = sum(client.metadata.get_cost(**p) for path, p in requests.items() if not path.exists())
    print(f"{len(rolls)} rolls, estimated cost of uncached requests: ${cost:.2f}")
    if not args.download:
        print("Nothing downloaded. Re-run with --download to fetch.")
        return

    fetch = lambda symbols, start, end: fetch_bbo_1m(symbols, start, end, client)
    out_dir, early_share = OUTPUTS, None
    if args.control_offset != CONTROL_OFFSET_WEEKS:
        out_dir = OUTPUTS / f"control_offset_{args.control_offset}"
        early_share = early_drop_share(plan, {r.expiry: roll_spreads(r, fetch) for r in plan})
    results = run(rolls, fetch, load_rates(), out_dir, early_share)
    print(f"\nWrote {out_dir}")
    print(f"Pre-2017-06 drop share (decision 10): {results['early_drop_share']:.1%}")
    print(f"\nWindows with an FOMC or ECB decision (decision 7):\n{results['meetings']}")
    h1 = results["stats"].xs("h1", level="test")
    columns = ["n", "n_positive", "mean", "ci_low", "ci_high", "sign_p", "wilcoxon_p"]
    with pd.option_context("display.width", 120, "display.float_format", "{:.3f}".format):
        print(f"\nH1, |roll| - |control|:\n{h1[columns]}")


if __name__ == "__main__":
    main()
