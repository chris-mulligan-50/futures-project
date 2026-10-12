"""Roll and control window selection (Task 7, issue #13).

Rule (README, "Select windows"):
  * Roll window: the last full Monday-Friday week before the front
    contract's expiry.
  * Control window: the same weekday pattern, four weeks earlier, for the
    same contract pair.
  * Changes are measured from the preceding Friday's snapshot (the
    baseline) to each window's ending Friday, giving five daily changes.

Inputs are (front, deferred, expiry) tuples, the interface the roll
calendar (Task 4) will produce. No Databento access is needed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Tuple

CONTROL_OFFSET_WEEKS = 4

RollPair = Tuple[str, str, date]  # (front, deferred, expiry)


@dataclass(frozen=True)
class Window:
    baseline: date  # Friday before the window; snapshot used as the start level
    start: date     # Monday
    end: date       # Friday

    @property
    def days(self) -> List[date]:
        """The five weekdays (Mon-Fri) whose snapshots give daily changes."""
        return [self.start + timedelta(days=i) for i in range(5)]

    def shifted(self, weeks: int) -> "Window":
        d = timedelta(weeks=weeks)
        return Window(self.baseline + d, self.start + d, self.end + d)


@dataclass(frozen=True)
class RollWindows:
    front: str
    deferred: str
    expiry: date
    roll: Window
    control: Window


def roll_window(expiry: date) -> Window:
    """Last full Mon-Fri week that ends before ``expiry``.

    A week containing the expiry is never "full and before" it, so we step
    back to the Friday before that week's Monday. This also handles expiries
    moved by holidays (e.g. a Wednesday or Friday expiry).
    """
    monday_of_expiry_week = expiry - timedelta(days=expiry.weekday())
    end = monday_of_expiry_week - timedelta(days=3)  # previous Friday
    start = end - timedelta(days=4)                  # that week's Monday
    baseline = end - timedelta(days=7)               # Friday before it
    return Window(baseline=baseline, start=start, end=end)


def control_window(expiry: date, offset_weeks: int = CONTROL_OFFSET_WEEKS) -> Window:
    """Same weekday pattern as the roll window, ``offset_weeks`` earlier."""
    if offset_weeks < 1:
        raise ValueError("offset_weeks must be at least 1")
    return roll_window(expiry).shifted(-offset_weeks)


def select_windows(
    pairs: Iterable[RollPair], offset_weeks: int = CONTROL_OFFSET_WEEKS
) -> List[RollWindows]:
    """Roll and control windows for each (front, deferred, expiry) pair."""
    return [
        RollWindows(
            front=front,
            deferred=deferred,
            expiry=expiry,
            roll=roll_window(expiry),
            control=control_window(expiry, offset_weeks),
        )
        for front, deferred, expiry in pairs
    ]
    