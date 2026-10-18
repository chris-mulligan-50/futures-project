# Analysis Plan (Task 6, issue #12)

**Status: PROPOSED.** Nothing here is final until every member signs off in
#12. Once signed off, this file is committed and tagged `plan-v1` before the
main test runs on the held-out rolls. After that, any change goes in the
deviation log below with a reason.

The proposals use only design reasoning and data-quality evidence (volume,
quote availability, daylight saving). None looks at spread changes in the
main sample, so nothing here depends on test results.

## Hypotheses (from the README)

- **H1 (magnitude):** the absolute change in the calendar spread is larger in
  roll windows than in matched control windows.
- **H2 (direction):** whether the spread systematically rises or falls in
  roll windows. Not interpreted as a cost to funds collectively unless we can
  tell which side dominates rolling.
- **H3 (cost, only if H1 and H2 hold):** the average excess move in dollars per
  contract rolled (one tick is USD 6.25 per contract).

## Decisions

| # | Decision | Proposal | Why |
|---|---|---|---|
| 1 | Roll and control windows | Roll window: last full Mon-Fri week before expiry. Control: same pattern 4 weeks earlier, same pair. As implemented in `windows.py`. | Fixed rule known in advance. Listed-spread volume peaks on the roll week's Wednesday and 80-87% of it trades in that week, only 0-1% in the control week (#42, exploratory rolls, volume only). |
| 2 | Number of control windows | One per roll for the main test. | Matches the README and keeps the comparison one paired difference per roll. Several control weeks only if #47 shows a single week is too noisy; the multiple-windows issue was closed (#33). |
| 3 | Snapshot time | 10:00 America/Chicago, each weekday. | A fixed local time keeps snapshots comparable across days. Quotes were fresh for both legs on every day of the Sep 2026 roll and control windows (#45, quality only). Follows daylight saving. Not yet tested against intraday volume, so alternatives can be compared on drop rate only. |
| 4 | Quote-age limit | 5 minutes, measured from the last `bbo-1m` row, not `ts_event`. | `ts_event` is the last trade and can be hours old while quotes are live (#44). Confirm the drop rate with the data-quality log (#24) on the exploratory rolls before the main test. |
| 5 | Missing-data policy | A day is kept only if both legs have an ok quote (not missing, stale, one-sided or crossed). If a window's starting or ending Friday is dropped, use the previous valid business day within 2 days; otherwise exclude that roll. Report every dropped day and reason. | One consistent rule, applied before looking at results, with the cost of dropping visible in the log. |
| 6 | Exchange holidays | Treat CME holiday sessions as missing, even if quotes exist. | On a holiday such as Labor Day trades are booked to the next day, so the day is not comparable. The team should confirm (open question in #45). |
| 7 | Fed/ECB meetings | First tabulate how often a meeting falls in roll and control windows (#16). Main test includes all windows; exclude windows containing a decision as a sensitivity check. | Excluding up front could remove a large share of rolls if meetings cluster near expiry. Decide after seeing the overlap table, which does not use spread data. |
| 8 | Carry and rates | Compare the spread with the simple carry-implied level using observed USD and EUR short rates (#48), as a secondary result. No detailed rate model. | The professor asked for rates directly rather than assuming shared regimes. |
| 9 | Confidence interval | Percentile bootstrap of the mean paired difference across rolls. Use a block bootstrap if the differences are autocorrelated across consecutive rolls (check lag 1). Also report sign and Wilcoxon tests. | Minute rows are not independent tests; the unit is the roll. |
| 10 | Held-out vs. exploratory split | Main test: 57 rolls, expiries 2010-09 to 2024-09. Exploratory: the 8 recent rolls, 2024-12 to 2026-09. In `euro_roll/config.py`. | The recent eight gave rise to the idea, so they cannot also be the test. If data quality before 2017-05-21 is poor (older feed, no capture timestamps), fall back to expiries from 2017-06 on, which gives about 30 rolls. |

## Sign-off

Comment in #12 to sign off; tick here once done.

- [ ] Chris Mulligan
- [ ] Sidharth Saha
- [ ] Shreya Enaganti
- [ ] Gonzalo Romero

## Deviation log

Changes after this plan is frozen. Date, what changed, why.

(none yet)
