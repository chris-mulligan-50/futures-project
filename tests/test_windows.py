import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from euro_roll.windows import (  # noqa: E402
    control_window,
    roll_window,
    select_windows,
)

# Hardcoded fake roll calendar until Task 4 lands.
# 6E expiry = two business days before the third Wednesday (a Monday).
FAKE_PAIRS = [
    ("6EH6", "6EM6", date(2026, 3, 16)),
    ("6EM6", "6EU6", date(2026, 6, 15)),
]


def test_roll_window_monday_expiry():
    w = roll_window(date(2026, 3, 16))
    assert w.baseline == date(2026, 3, 6)
    assert w.start == date(2026, 3, 9)
    assert w.end == date(2026, 3, 13)


def test_weekday_shape():
    w = roll_window(date(2026, 3, 16))
    assert w.baseline.weekday() == 4  # Friday
    assert w.start.weekday() == 0     # Monday
    assert w.end.weekday() == 4       # Friday
    assert [d.weekday() for d in w.days] == [0, 1, 2, 3, 4]


@pytest.mark.parametrize(
    "expiry", [date(2026, 3, 11), date(2026, 3, 13)]  # Wed / Fri (holiday-shifted)
)
def test_mid_week_expiry_uses_previous_full_week(expiry):
    w = roll_window(expiry)
    assert w.end == date(2026, 3, 6)
    assert w.end < expiry


def test_window_ends_before_expiry_always():
    for day in range(1, 29):
        e = date(2026, 6, day)
        if e.weekday() < 5:
            assert roll_window(e).end < e


def test_control_is_four_weeks_earlier():
    c = control_window(date(2026, 3, 16))
    assert c.baseline == date(2026, 2, 6)
    assert c.start == date(2026, 2, 9)
    assert c.end == date(2026, 2, 13)


def test_control_offset_parameter():
    assert control_window(date(2026, 3, 16), offset_weeks=6).start == date(2026, 1, 26)
    with pytest.raises(ValueError):
        control_window(date(2026, 3, 16), offset_weeks=0)


def test_windows_do_not_overlap():
    r, c = roll_window(date(2026, 3, 16)), control_window(date(2026, 3, 16))
    assert c.end < r.baseline


def test_select_windows_keeps_pair_and_order():
    out = select_windows(FAKE_PAIRS)
    assert [o.front for o in out] == ["6EH6", "6EM6"]
    assert out[1].deferred == "6EU6"
    assert out[1].roll.end == date(2026, 6, 12)
    assert out[1].control.end == date(2026, 5, 15)


def test_year_boundary():
    w = roll_window(date(2026, 1, 5))  # Monday just after New Year
    assert w.end == date(2026, 1, 2)
    assert w.baseline == date(2025, 12, 26)