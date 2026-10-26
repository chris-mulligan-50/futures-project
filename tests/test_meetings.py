from datetime import date, timedelta

import pandas as pd
import pytest

from euro_roll.changes import KINDS
from euro_roll.meetings import BANKS, decisions_between, meeting_table, overlap


def changes_row(expiry, roll_days, control_days):
    """A ``change_table``-like row with the days each window used."""
    row = {"roll": 1.0, "control": 1.0}
    for kind, (start, end) in [("roll", roll_days), ("control", control_days)]:
        row.update({f"{kind}_baseline_used": start, f"{kind}_end_used": end})
    return pd.DataFrame([row], index=[expiry])


@pytest.mark.parametrize("bank", sorted(BANKS))
def test_decision_dates_are_sorted_and_far_apart(bank):
    dates = BANKS[bank]
    assert list(dates) == sorted(set(dates))
    # A window's two snapshots are at most nine days apart (a fallback
    # baseline on Wednesday to the ending Friday), so no window can hold two
    # decisions from one bank.
    assert min(b - a for a, b in zip(dates, dates[1:])) > timedelta(days=9)


def test_decisions_fall_on_weekdays_except_the_march_2020_sunday_cut():
    weekend = [d for dates in BANKS.values() for d in dates if d.weekday() >= 5]
    assert weekend == [date(2020, 3, 15)]


def test_sample_is_covered():
    for dates in BANKS.values():
        assert dates[0] <= date(2010, 2, 1) and dates[-1] >= date(2026, 9, 1)


def test_ecb_decision_counts_from_the_day_after_baseline_to_the_end_day(monkeypatch):
    # The ECB announces before the 10:00 Chicago snapshot.
    monkeypatch.setitem(BANKS, "ecb", (date(2026, 9, 4), date(2026, 9, 10), date(2026, 9, 24)))
    assert decisions_between("ecb", date(2026, 9, 4), date(2026, 9, 11)) == [date(2026, 9, 10)]
    assert decisions_between("ecb", date(2026, 9, 4), date(2026, 9, 10)) == [date(2026, 9, 10)]
    assert decisions_between("ecb", date(2026, 9, 10), date(2026, 9, 18)) == []


def test_fomc_decision_counts_from_the_baseline_day_to_the_day_before_the_end(monkeypatch):
    # The FOMC announces after the 10:00 Chicago snapshot.
    monkeypatch.setitem(BANKS, "fomc", (date(2026, 9, 2), date(2026, 9, 16)))
    assert decisions_between("fomc", date(2026, 9, 2), date(2026, 9, 11)) == [date(2026, 9, 2)]
    assert decisions_between("fomc", date(2026, 9, 11), date(2026, 9, 16)) == []
    assert decisions_between("fomc", date(2026, 9, 11), date(2026, 9, 18)) == [date(2026, 9, 16)]


def test_meeting_table_uses_the_days_the_changes_used(monkeypatch):
    monkeypatch.setitem(BANKS, "ecb", (date(2026, 9, 10),))
    monkeypatch.setitem(BANKS, "fomc", (date(2026, 8, 12),))
    changes = changes_row(
        date(2026, 9, 14),
        roll_days=(date(2026, 9, 4), date(2026, 9, 11)),
        # A fallback baseline on Wednesday 2026-08-12 takes in that day's FOMC.
        control_days=(date(2026, 8, 12), date(2026, 8, 14)),
    )
    table = meeting_table(changes)
    assert list(table.columns) == [f"{kind}_{bank}" for kind in KINDS for bank in BANKS]
    assert table.loc[date(2026, 9, 14)].to_dict() == {
        "roll_fomc": None, "roll_ecb": date(2026, 9, 10),
        "control_fomc": date(2026, 8, 12), "control_ecb": None,
    }


def test_window_without_a_change_has_no_decisions(monkeypatch):
    monkeypatch.setitem(BANKS, "ecb", (date(2026, 9, 10),))
    changes = changes_row(date(2026, 9, 14), (None, None), (date(2026, 8, 7), date(2026, 8, 14)))
    assert meeting_table(changes).loc[date(2026, 9, 14), "roll_ecb"] is None


def test_overlap_counts_windows_with_a_decision(monkeypatch):
    monkeypatch.setitem(BANKS, "ecb", (date(2026, 9, 10), date(2026, 6, 4)))
    monkeypatch.setitem(BANKS, "fomc", (date(2026, 6, 3),))
    changes = pd.concat([
        changes_row(date(2026, 9, 14), (date(2026, 9, 4), date(2026, 9, 11)), (date(2026, 8, 7), date(2026, 8, 14))),
        changes_row(date(2026, 6, 15), (date(2026, 6, 5), date(2026, 6, 12)), (date(2026, 5, 29), date(2026, 6, 5))),
    ])
    counts = overlap(meeting_table(changes))
    assert counts.to_dict("index") == {
        "fomc": {"roll": 0, "control": 1, "roll_or_control": 1, "rolls": 2},
        "ecb": {"roll": 1, "control": 1, "roll_or_control": 2, "rolls": 2},
        "fomc_or_ecb": {"roll": 1, "control": 1, "roll_or_control": 2, "rolls": 2},
    }

