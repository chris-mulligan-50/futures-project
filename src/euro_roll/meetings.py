"""Fed and ECB policy decisions in roll and control windows (decision 7 of
``docs/ANALYSIS_PLAN.md``, issue #16).

A policy decision can move the USD - EUR rate gap, and with it the calendar
spread, in any week. Decision 7 keeps every window in the main test, reports
how often a decision falls in roll and control windows, and repeats the test
without the rolls where either window contains one.

A decision counts for a window if it was announced between the window's two
snapshots, on the days ``changes.py`` used (10:00 Chicago). The ECB
announces at 13:45 or 14:15 Frankfurt time, before that day's snapshot; the
FOMC's statements come out between 12:30 and 14:15 New York time, after it.
So an ECB decision counts from the day after the baseline through the end
day, and an FOMC decision from the baseline day through the day before the
end. The one exception, the FOMC's cut at 10:00 New York time on Tuesday
2020-03-03, cannot be misplaced: baseline and end days are Wednesdays to
Fridays (decision 5's fallback), never Tuesdays.

Dates are announcement days: every scheduled monetary-policy meeting, plus
unscheduled ones that changed a policy rate. Those are the FOMC's cuts of
2020-03-03 and Sunday 2020-03-15, which replaced the cancelled March 17-18
meeting. The ECB's unscheduled actions (2010-05-10, 2011-08-07, 2020-03-18,
2022-06-15) and the FOMC's calls without a rate change are left out.
Sources: federalreserve.gov/monetarypolicy/fomchistorical<year>.htm for
2010-2020 and fomccalendars.htm after; ecb.europa.eu/press/govcdec/mopo,
cross-checked against the ECB's press-conference archive and its key-rate
history.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Tuple

import pandas as pd

from euro_roll.changes import KINDS


def _dates(text: str) -> Tuple[date, ...]:
    return tuple(date.fromisoformat(d) for d in text.split())


FOMC = _dates("""
    2010-01-27 2010-03-16 2010-04-28 2010-06-23 2010-08-10 2010-09-21 2010-11-03 2010-12-14
    2011-01-26 2011-03-15 2011-04-27 2011-06-22 2011-08-09 2011-09-21 2011-11-02 2011-12-13
    2012-01-25 2012-03-13 2012-04-25 2012-06-20 2012-08-01 2012-09-13 2012-10-24 2012-12-12
    2013-01-30 2013-03-20 2013-05-01 2013-06-19 2013-07-31 2013-09-18 2013-10-30 2013-12-18
    2014-01-29 2014-03-19 2014-04-30 2014-06-18 2014-07-30 2014-09-17 2014-10-29 2014-12-17
    2015-01-28 2015-03-18 2015-04-29 2015-06-17 2015-07-29 2015-09-17 2015-10-28 2015-12-16
    2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
    2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
    2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
    2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
    2020-01-29 2020-03-03 2020-03-15 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
    2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
    2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
    2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
    2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
    2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10
    2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16
""")

ECB = _dates("""
    2010-01-14 2010-02-04 2010-03-04 2010-04-08 2010-05-06 2010-06-10
    2010-07-08 2010-08-05 2010-09-02 2010-10-07 2010-11-04 2010-12-02
    2011-01-13 2011-02-03 2011-03-03 2011-04-07 2011-05-05 2011-06-09
    2011-07-07 2011-08-04 2011-09-08 2011-10-06 2011-11-03 2011-12-08
    2012-01-12 2012-02-09 2012-03-08 2012-04-04 2012-05-03 2012-06-06
    2012-07-05 2012-08-02 2012-09-06 2012-10-04 2012-11-08 2012-12-06
    2013-01-10 2013-02-07 2013-03-07 2013-04-04 2013-05-02 2013-06-06
    2013-07-04 2013-08-01 2013-09-05 2013-10-02 2013-11-07 2013-12-05
    2014-01-09 2014-02-06 2014-03-06 2014-04-03 2014-05-08 2014-06-05
    2014-07-03 2014-08-07 2014-09-04 2014-10-02 2014-11-06 2014-12-04
    2015-01-22 2015-03-05 2015-04-15 2015-06-03 2015-07-16 2015-09-03 2015-10-22 2015-12-03
    2016-01-21 2016-03-10 2016-04-21 2016-06-02 2016-07-21 2016-09-08 2016-10-20 2016-12-08
    2017-01-19 2017-03-09 2017-04-27 2017-06-08 2017-07-20 2017-09-07 2017-10-26 2017-12-14
    2018-01-25 2018-03-08 2018-04-26 2018-06-14 2018-07-26 2018-09-13 2018-10-25 2018-12-13
    2019-01-24 2019-03-07 2019-04-10 2019-06-06 2019-07-25 2019-09-12 2019-10-24 2019-12-12
    2020-01-23 2020-03-12 2020-04-30 2020-06-04 2020-07-16 2020-09-10 2020-10-29 2020-12-10
    2021-01-21 2021-03-11 2021-04-22 2021-06-10 2021-07-22 2021-09-09 2021-10-28 2021-12-16
    2022-02-03 2022-03-10 2022-04-14 2022-06-09 2022-07-21 2022-09-08 2022-10-27 2022-12-15
    2023-02-02 2023-03-16 2023-05-04 2023-06-15 2023-07-27 2023-09-14 2023-10-26 2023-12-14
    2024-01-25 2024-03-07 2024-04-11 2024-06-06 2024-07-18 2024-09-12 2024-10-17 2024-12-12
    2025-01-30 2025-03-06 2025-04-17 2025-06-05 2025-07-24 2025-09-11 2025-10-30 2025-12-18
    2026-02-05 2026-03-19 2026-04-30 2026-06-11 2026-07-23 2026-09-10
""")

BANKS: Dict[str, Tuple[date, ...]] = {"fomc": FOMC, "ecb": ECB}
# Whether the bank announces before the 10:00 Chicago snapshot on its day.
BEFORE_SNAPSHOT = {"fomc": False, "ecb": True}


def decisions_between(bank: str, start: date, end: date) -> List[date]:
    """``bank``'s decisions announced after the snapshot on ``start`` and by the one on ``end``."""
    if BEFORE_SNAPSHOT[bank]:
        return [d for d in BANKS[bank] if start < d <= end]
    return [d for d in BANKS[bank] if start <= d < end]


def meeting_table(changes: pd.DataFrame) -> pd.DataFrame:
    """The decision in each window, per bank, or None.

    ``changes`` is ``changes.change_table`` output. Columns are
    ``<kind>_<bank>``, e.g. ``roll_ecb``. A window's two snapshots are at
    most nine days apart and no bank decided twice within nine days, so a
    window holds at most one decision per bank. A window with no change
    (decision 5) has no snapshots, so None.
    """
    rows = {}
    for expiry, row in changes.iterrows():
        rows[expiry] = {}
        for kind in KINDS:
            start, end = row[f"{kind}_baseline_used"], row[f"{kind}_end_used"]
            used = pd.notna(start) and pd.notna(end)
            for bank in BANKS:
                found = decisions_between(bank, start, end) if used else []
                rows[expiry][f"{kind}_{bank}"] = found[0] if found else None
    columns = [f"{kind}_{bank}" for kind in KINDS for bank in BANKS]
    return pd.DataFrame.from_dict(rows, orient="index", columns=columns).rename_axis(changes.index.name)


def overlap(table: pd.DataFrame) -> pd.DataFrame:
    """Rolls with an FOMC, ECB or any decision, by window.

    ``table`` is ``meeting_table`` output for the rolls to count. Rows are
    ``fomc``, ``ecb`` and ``fomc_or_ecb``; columns count the rolls with
    such a decision in the ``roll`` window, the ``control`` window, and
    either (``roll_or_control``), out of ``rolls``. ``rolls`` minus the
    ``fomc_or_ecb`` / ``roll_or_control`` cell is the ``no_meetings`` sample.
    """
    has = {}
    for kind in KINDS:
        has[kind] = {bank: table[f"{kind}_{bank}"].notna() for bank in BANKS}
        has[kind]["fomc_or_ecb"] = pd.concat(has[kind].values(), axis=1).any(axis=1)
    rows = has["roll"].keys()
    out = pd.DataFrame({kind: [int(has[kind][r].sum()) for r in rows] for kind in KINDS}, index=list(rows))
    out["roll_or_control"] = [int((has["roll"][r] | has["control"][r]).sum()) for r in rows]
    out["rolls"] = len(table)
    return out.rename_axis("bank")
