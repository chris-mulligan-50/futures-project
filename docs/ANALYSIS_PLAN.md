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

## Test statistics

For roll *i*, let S be the spread in ticks at the 10:00 snapshot.
ΔR<sub>i</sub> = S(roll window's ending Friday) − S(its baseline Friday), and
ΔC<sub>i</sub> is the same for the control window.

- **H1:** d<sub>i</sub> = |ΔR<sub>i</sub>| − |ΔC<sub>i</sub>|, one value per
  roll. Report the mean of d with its confidence interval (decision 9), plus
  sign and Wilcoxon signed-rank tests on d. Two-sided p-values.
- **H2:** sign test on ΔR<sub>i</sub> (share of rolls where the spread rose).
  Also report the mean of ΔR<sub>i</sub> − ΔC<sub>i</sub> with the same
  confidence-interval procedure.

The net move from baseline to end is used, not the sum of daily moves,
because the hypothesis is that rolling shifts the spread's level. A
volatility measure would test a different question. With the net move, only
the two Fridays enter the statistic, which is what decision 5's rule covers.

## Decisions

| # | Decision | Proposal | Why |
|---|---|---|---|
| 1 | Roll and control windows | Roll window: last full Mon-Fri week before expiry. Control: same pattern 4 weeks earlier, same pair. As implemented in `windows.py`. | Fixed rule known in advance. Listed-spread volume peaks on the roll week's Wednesday and 80-87% of it trades in that week, only 0-1% in the control week (#42, exploratory rolls, volume only). Listed-spread volume is the right measure because spread trades do not appear as a separate cleared volume (Class 2, `calendars.ipynb`). Known bias: 7-17% of spread volume trades in the week before, mostly before the baseline snapshot, so part of any roll effect may already be in the baseline. This biases H1 toward finding no effect; we accept that rather than widen the window after seeing data. Edge case: 6EM3 expired on Friday 2023-06-16 (Juneteenth, #54), so its roll window is June 5-9, a week before its volume crossover. We keep the rule for it, which also biases H1 toward no effect. |
| 2 | Number of control windows | One per roll for the main test. | Matches the README and keeps the comparison one paired difference per roll; the multiple-windows issue was closed (#33). #47 found the control-week deferred is quoted wider (decision 11), but earlier control weeks would be thinner still, so adding them would not help. |
| 3 | Snapshot time | 10:00 America/Chicago, each weekday. | A fixed local time keeps snapshots comparable across days. Quotes were fresh for both legs on every day of the Sep 2026 roll and control windows (#45, quality only). Follows daylight saving. Not yet tested against intraday volume, so alternatives can be compared on drop rate only. |
| 4 | Quote-age limit | 5 minutes, measured from the last `bbo-1m` row, not `ts_event`. | `ts_event` is the last trade and can be hours old while quotes are live (#44). Confirm the drop rate with the data-quality log (#24) on the exploratory rolls before the main test. |
| 5 | Missing-data policy | A day is kept only if both legs have an ok quote (not missing, stale, one-sided or crossed). If a window's baseline or ending Friday is dropped, use the previous valid business day within 2 days; otherwise exclude that roll. Report every dropped day and reason. | One consistent rule, applied before looking at results, with the cost of dropping visible in the log. |
| 6 | Exchange holidays | Treat CME holiday sessions as missing, even if quotes exist. Applied where snapshots are taken (`spread.py`), as a dropped day with reason `holiday`, from a full list of CME holiday sessions. That list is separate from the one in `expiries.py` (#54), which only needs holidays that can move an expiry. | On a holiday such as Labor Day trades are booked to the next day, so the day is not comparable. Labor Day 2026-09-07 falls in the September 2026 roll window. |
| 7 | Fed/ECB meetings | First tabulate how often a meeting falls in roll and control windows (#16). Main test includes all windows; exclude windows containing a decision as a sensitivity check. | Excluding up front could remove a large share of rolls if meetings cluster near expiry. Decide after seeing the overlap table, which does not use spread data. |
| 8 | Carry and rates | Secondary result. Convert the spread to an implied rate gap, ln(F<sub>deferred</sub> / F<sub>front</sub>) / Δt, with Δt the time between the two expiries in years. Under cost of carry this is the forward USD − EUR rate gap between the two expiries. Compare its weekly change with the change in the observed gap (#51), in roll vs. control weeks: the 3-month spot gap as the main comparison, and the forward gap between the expiries (from 3- and 6-month rates) as a sensitivity check. Rates are taken from the day before each snapshot. No detailed rate model. | The professor asked for rates directly rather than assuming shared regimes. Implying carry from two expiries without a spot price follows Class 3 (`cost_of_carry.ipynb`). Carry predicts the implied gap tracks the observed gap with no roll-week bump, so a roll-week move beyond the rate change is the effect we are testing. Rates are end-of-day, so same-day values would come after the snapshot. Limitation: in control weeks the spread's period starts about 5 weeks out, so the spot gap fits control weeks worse than roll weeks (on the 65 rolls, a median 0.9 vs. 0.5 bp gap between the two measures' weekly changes, rates only). The forward gap narrows this, but the ECB curve starts at 3 months, so the first weeks of the period still use the 3-month rate. |
| 9 | Confidence interval | Main: percentile bootstrap of the mean across rolls (10,000 resamples, fixed seed). Sensitivity: circular block bootstrap with blocks of 4 consecutive rolls (one year), wrapping from the last roll to the first; a block can span a roll dropped under decision 5. 95% two-sided intervals, both always reported, alongside the sign and Wilcoxon tests. Those two tests drop changes of exactly zero; the mean keeps them. Wilcoxon p-values use sign-flip permutations (10,000, fixed seed). | Minute rows are not independent tests; the unit is the roll. Fixing both procedures now avoids choosing one after checking dependence in the results. Blocks of a year allow for shared rate regimes across nearby rolls. Circular rather than plain moving-block, because the plain version draws the first and last rolls about a quarter as often as the rest (Politis and Romano, 1992). Permutation p-values stay exact with ties and give the 8 and 57 rolls the same method (#52). |
| 10 | Held-out vs. exploratory split | Main test: 57 rolls, expiries 2010-09 to 2024-09. Exploratory: the 8 recent rolls, 2024-12 to 2026-09. In `euro_roll/config.py`. | The recent eight gave rise to the idea, so they cannot also be the test. If data quality before 2017-05-21 is poor (older feed, no capture timestamps), fall back to expiries from 2017-06 on, which gives about 30 rolls. "Poor" means more than 20% of all window days of the pre-2017-06 rolls, pooled across those rolls, are dropped under decision 5, judged from the data-quality log (#24) alone, before any spread change is computed. |
| 11 | Wide quotes | Main test keeps every day that passes decision 5. Sensitivity: drop rolls where either leg is wider than 5 ticks on the baseline or ending Friday used. The data-quality log (#24) reports the width of both legs at every snapshot. | The control-week deferred is often quoted wide (#55, quality only): before mid-2017, 74% of control weeks have a snapshot wider than 5 ticks, against 4% of roll weeks. A cap in the main test would mostly drop old control weeks and could trip decision 10's fallback. A cap also does not fix the real issue: the control-week deferred is less liquid by design, so its midpoint is noisier, which makes control changes look larger and biases H1 toward no effect. A null H1 result has to be read with that in mind. |

## Questions from the professor's check-in

| Question | Where it is handled |
|---|---|
| Does the meeting schedule line up with the roll schedule? Can it be ignored at first? | Decision 7: overlap table first (#16), all windows in the main test, meeting exclusion as a sensitivity check. |
| Is the second contract month liquid enough for the control week? | #47 compares deferred volume, valid-snapshot share and bid-ask width in roll vs. control weeks. Wide control-week quotes: decision 11. |
| What does cost of carry imply? | Decision 8: the implied rate gap should track the observed rate gap, with no roll-week bump. |
| Can rates be included directly? | Decision 8, using observed USD and EUR rates (#48). |
| What would an interest-rate model add? | Out of scope; only the simple carry relation above (README). |
| Multiple currencies? | Out of scope for this project; noted as an extension. |

## Sign-off

Comment in #12 to sign off; tick here once done.

- [ ] Chris Mulligan
- [x] Sidharth Saha
- [x] Shreya Enaganti
- [x] Gonzalo Romero

## Deviation log

Changes after this plan is frozen. Date, what changed, why.

- **2026-10-25, timing.** The main test ran before Chris's sign-off and
  before the `plan-v1` tag, to meet the 2026-10-27 deadline. The decisions
  above are as three of four members signed them; the items below were
  settled before the main-test results were seen.
- **2026-10-25, decision 7.** In the paired test a window cannot be dropped
  alone, so `no_meetings` drops a roll if either of its windows contains a
  decision. A decision counts if it was announced between the window's two
  snapshots. Decisions are every scheduled FOMC and ECB monetary-policy
  meeting plus unscheduled ones that changed a policy rate
  (`euro_roll/meetings.py`).
- **2026-10-25, decision 9.** The block interval is left empty for a subset
  of fewer than eight rolls (two blocks): with one block every resample is
  a rotation of the same rolls, and with under two the interval is too
  narrow. Only exploratory subsets can be that small.
- **2026-10-25, added check.** Control windows two and three weeks before
  the roll window instead of four (`--control-offset`, #30), because
  decision 11 expects the thin four-week control to bias H1 toward no
  effect. Reported as a robustness check, not as the main test. One week
  is not used: 7-17% of spread volume already trades then (decision 1).
  Decision 10's fallback is judged on the plan's windows in these runs too,
  so they keep the main test's sample.
