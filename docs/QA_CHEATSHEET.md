# Q&A Cheat Sheet

For the four presenters. Short spoken answers first, detail after "If pressed". Every number comes from `outputs/` on `main` or the file named next to it. If a question goes beyond this sheet, say what we measured and what we didn't. Don't guess.

## 30-second version

We asked whether Euro FX (6E) calendar spreads move more in quarterly roll weeks than in a control week four weeks earlier. Using Databento CME quotes for 57 held-out rolls from 2010 to 2024, we found no evidence of a roll-week effect: +0.52 ticks, 95% interval −0.96 to +2.19, and every planned check agrees. That is weaker than "no effect". The control week is thinly traded and quoted about twice as wide, which biases the test toward finding nothing, and a simulation shows we would miss a moderate effect more than half the time.

## Numbers to know

| What | Number | Source |
|---|---|---|
| Rolls | 65 total: 57 main test (2010-09 to 2024-09) + 8 exploratory (2024-12 to 2026-09) | `config.py` |
| H1: mean of \|roll\| − \|control\| | +0.52 ticks, 95% CI −0.96 to +2.19 (block CI −0.74 to +1.99) | `stats.csv` |
| H1 tests | sign p = 0.89, Wilcoxon p = 0.37; 24 up / 26 down / 7 zero | `stats.csv` |
| H2: roll weeks where the spread rose | 24 of 50 nonzero, p = 0.89 | `stats.csv` |
| H2: mean of roll − control | −0.45 ticks, CI −2.30 to +1.64 | `stats.csv` |
| Mean absolute net move | 3.22 ticks in roll weeks vs. 2.70 in control weeks | `roll_vs_control.csv` |
| One tick | 0.00005 USD per EUR = USD 6.25 per 125,000 EUR contract (0.0001 = USD 12.50 before 2016) | contract spec, Databento definitions |
| +0.52 ticks in dollars | about USD 3.25 per contract, under one tick | — |
| Narrow quotes check | 34 rolls, +0.40 (−0.96 to +2.10) | `stats.csv` |
| No Fed/ECB weeks check | 27 rolls, +0.52 (−1.09 to +2.65) | `stats.csv` |
| Carry-adjusted, in bp | 3-month gap +1.94 (−0.76 to +4.93); forward gap +2.39 (−0.31 to +5.35) | `stats.csv` |
| Control 2 / 3 weeks out (added after the plan) | +0.12 (−1.31 to +1.68) / +1.17 (−0.21 to +2.78; block CI +0.04 to +2.46) | `control_offset_*/stats.csv` |
| Exploratory 8 rolls | −0.88 (−2.44 to +0.38); spread rose in 4 of 8 | `stats.csv` |
| Power with 57 rolls | 29–43% to detect a roll move 1.5× the control's; 68–85% for 2× | `power.csv` |
| Fed/ECB decision inside the window | 29 of 57 roll windows vs. 1 control window | `meetings.csv` |
| Dropped snapshot days | 7 in total: 5 CME holidays + 2 days in June 2014 with no quotes; 0.6% of pre-2017 days | `dropped_days.csv` |
| Listed-spread volume (8 recent rolls) | 80–87% in the roll week, 7–17% the week before, 0–1% in the control week; peaks Wednesday | `notebooks/roll_spread_volume.ipynb` |
| Outright volume crossover | 3 calendar days before expiry (the Friday) in 63 of 65 rolls | `volume_share_summary.csv` |
| Control-week deferred liquidity (all 65) | median 751 contracts/day vs. 48,999 in roll weeks (~1.3%); median width 3.5 vs. 2.0 ticks | `control_liquidity.csv` |
| Expiry formula | matches Databento definitions for 64 of 65 contracts (6EM3 is the miss) | `coverage.py` |
| Tests | 191, run by GitHub Actions on Linux and Windows | `tests/` |

## Who knows what

Send the question to whoever built that part.

| Area | Owner | Files |
|---|---|---|
| Spread construction, quote checks, cache, test data and CI, liquidity check | Chris | `spread.py`, `cache.py`, `tests/synthetic.py`, `liquidity.py` |
| Statistics, runner, carry, rates, meetings, power simulation, downloader | Gonzalo | `stats.py`, `analyze.py`, `changes.py`, `carry.py`, `rates.py`, `meetings.py`, `power.py`, `download.py` |
| Roll calendar, windows, volume share | Sid | `expiries.py`, `windows.py`, `volume_share.py` |
| Coverage and cost check, analysis plan, README, slides | Shreya | `coverage.py`, `config.py`, `docs/ANALYSIS_PLAN.md`, `README.md` |

---

## 1. The question and why it matters

**What is a roll, and why would it cost anything?**
6E contracts expire quarterly. A fund that hedges euro exposure has to close the expiring contract and open the next one. The calendar fixes the timing, so much of that volume lands in the same few days each quarter and others can anticipate it. If that crowding moves the spread against rollers, they pay a cost that appears on no fee schedule.

**Why the calendar spread and not the futures price?**
The roller trades the spread: sell front, buy deferred (or the reverse). The spread is the price of switching. Outright price moves are mostly the exchange rate, which rolling shouldn't move.

**Why 6E?**
It is the most liquid CME FX future, with a clean quarterly cycle and Databento history back to 2010. We kept to one market so the pipeline could be finished. The professor agreed that adding currencies is beyond the course's scope.

**What's the prior evidence?**
Mou (2010) found price pressure around the predictable Goldman commodity-index roll. Irwin, Sanders and Yan (2023) found that roll effect disappeared in 2012–2019. CME's 2022 note says FX roll activity concentrates in the week before expiry alongside deep liquidity. So we tested for an effect without assuming one.

**Where did the idea come from?**
A quick look at the 8 most recent rolls suggested the spread rose in every roll week. Under the final definitions it rose in 4 of 8. Because those rolls gave us the idea, they can't also be the test, so they are reported as exploratory only.

**What are H1, H2 and H3?**
- H1 (magnitude): the spread moves more, in absolute terms, in roll weeks than in control weeks.
- H2 (direction): the spread systematically rises or falls in roll weeks.
- H3 (cost): a dollar cost per contract, computed only if H1 and H2 hold. Neither held, so H3 isn't computed.

**Why can't a directional move be called a cost to funds?**
Rolling a long hedge means selling front and buying deferred; rolling a short does the opposite. A rise in the spread hurts one side and helps the other. Without knowing which side dominates, a direction isn't a cost to "funds" as a group. CFTC positioning data could tell us, but we cut it.

## 2. Data (Databento, CME)

**Which data did you use?**
Databento `GLBX.MDP3`, which is CME Globex captured directly, with three schemas:
- `bbo-1m` (best bid and offer each minute) for the 10:00 snapshots;
- `ohlcv-1d` (daily bars) for volumes;
- `definition` for expiry dates and tick size.

**How much did it cost?**
USD 0.00 on our team account. Prices differ by account, so every script prints an estimated cost and downloads nothing unless `--download` is given.

**Why named contracts and not a continuous series?**
A continuous series splices contracts together, so a "return" across a switch mixes two instruments. We request each contract by its own symbol, such as `6EU6`, inside its own life.

**What's the catch with symbols?**
They repeat every ten years: `6EU6` is both September 2016 and September 2026. Every table is keyed by expiry date, not symbol. A review caught one module that grouped by symbol and merged 2016 with 2026; it was fixed before merging.

**Why not use the listed calendar spread's own quotes?**
We measure the spread by legging the two outrights, which works the same way in every window. The listed spread barely trades in the control week (0–1% of its volume). Its price sign and leg order also need the definition data to interpret. A comparison with the listed spread was planned and cut for time.

**Why not settlement prices?**
CME settles deferred FX months partly from the calendar-spread market, so a settlement-based spread would be partly CME's own estimate. Midquotes at a fixed time are observed directly.

**Was data quality a problem?**
Very little: 7 dropped snapshot days in 65 rolls. Five are CME holidays, dropped by rule, and two are June 2014 days when neither contract had quotes for 15 hours, which looks like a feed gap. The plan's fallback to a post-2017 sample would have triggered at 20% of pre-2017 days dropped; the actual figure was 0.6%.

**Did anything change in the data over time?**
Yes. The tick halved from 0.0001 to 0.00005 around the turn of 2016: Databento's definitions show 0.0001 for 6EZ5 (November 2015) and 0.00005 for 6EH6 (February 2016). We measure everything in 0.00005 units, so before 2016 the narrowest possible book is 2 ticks and spread changes sit on a coarser grid, with more exact zeros.

**How long does it take to reproduce?**
About 45 minutes for the first download. Everything is cached under `data/databento/` (git-ignored), so reruns are fast and free. Databento's gateway sometimes returns 504 errors; rerunning resumes from the cache.

## 3. Method

**How is the spread measured?**
Deferred midpoint minus front midpoint, in ticks, from each contract's best bid and offer in force at 10:00 America/Chicago each weekday. The 10:00 follows daylight saving, which the tests check.

**Why 10:00 Chicago?**
It's a fixed local time inside the liquid US/Europe overlap. It also places ECB announcements (13:45 or 14:15 Frankfurt) before the snapshot and FOMC statements (12:30–14:15 New York) after it, which `meetings.py` accounts for. No alternative time was tested on results.

**What makes a quote usable?**
Both legs must have a bid and an ask, not crossed, quoted since that session opened (17:00 Chicago the day before), and no more than 5 minutes old. CME holiday sessions are dropped even when quotes exist, because their trades are booked to the next day.

**How do you measure quote age?**
From the last `bbo-1m` row, not from `ts_event`. `ts_event` is the time of the last trade, which can be hours old while quotes are live. A test fails if `ts_event` is used.

**What's the roll window? The control window?**
The roll window is the last full Monday–Friday week before the front contract expires. The control window is the same weekday pattern four weeks earlier, for the same two contracts. Both rules are fixed in advance, so nothing is chosen after seeing data.

**Why one week? Why four weeks back?**
Listed-spread volume shows rolling is concentrated in that week (80–87%). The control has to be close enough to share the same contract pair and rate environment, but before rolling starts. One week back is contaminated, since 7–17% of spread volume trades then. We added 2- and 3-week controls as robustness checks after the plan.

**Why not several control weeks?**
Earlier weeks are even thinner and wider-quoted, so they would add noise, not information. One control per roll keeps one paired number per roll.

**What exactly is the statistic?**
For each roll, d = |ΔR| − |ΔC|. ΔR is the net change from the baseline Friday's 10:00 snapshot to the roll window's ending Friday, and ΔC is the same for the control window. That gives one number per roll, so the unit of analysis is the roll, not the minute.

**Why the net move and not the sum of daily moves, or volatility?**
The hypothesis is that rolling shifts the spread's level. A volatility measure would test a different question. With the net move, only two snapshots per window enter the statistic.

**What if a Friday snapshot is missing?**
Use the latest valid weekday up to 2 days before it; otherwise the roll drops out. This happened once: the June 2014 roll week ended on Wednesday the 11th, because the 12th and 13th had no quotes. No roll was lost; all 65 have both changes.

**How is the expiry date set?**
The rule is two business days before the third Wednesday, with CME holidays skipped; trading ends 9:16 Chicago that day. It matches Databento for 64 of 65 contracts. The miss is June 2023, which expired Friday the 16th because Juneteenth fell on Monday the 19th. The calendar now handles that.

**Did the Juneteenth case cause a problem?**
Before the fix, June 2023's roll window contained the real expiry day, and the front stopped quoting at 9:17. With the fix, its roll window is June 5–9, a week before its volume crossover. We kept the rule, and that biases H1 toward no effect.

## 4. Statistics

**Why these tests?**
With 57 rolls and fat-tailed moves, we wanted tests that don't assume normality:
- a sign test (just direction);
- a Wilcoxon signed-rank test (direction and size ranks);
- a bootstrap interval for the mean.

All were chosen before the results.

**What about zeros?**
Changes sit on a half-tick grid, so exact zeros are common: 7 of 57 for d. The sign and Wilcoxon tests drop them, which is the standard convention; the mean keeps them.

**Why permutation p-values for Wilcoxon?**
Tied values break scipy's default method, which also switches from exact to approximate above 13 values. Sign-flip permutations stay exact with ties and give the 8-roll and 57-roll samples the same method.

**Why two bootstrap intervals?**
- **Percentile bootstrap:** the main interval, from 10,000 resamples with a fixed seed.
- **Circular block bootstrap:** a sensitivity interval, using blocks of 4 consecutive rolls (one year), in case nearby rolls share a rate regime.

Both were fixed in advance and are always reported. Circular, because the plain moving-block version draws the first and last rolls about a quarter as often as the rest.

**Is there dependence across rolls?**
The lag-1 autocorrelation of d is −0.25, so there's no sign of positive dependence. The block interval (−0.74 to +1.99) is close to the percentile one.

**You ran many specifications. Multiple testing?**
The main test is one pre-specified statistic. The others are sensitivity checks that ask whether the null survives, and none of the planned ones has an interval excluding zero. We didn't adjust p-values. A few post-hoc carry results in the offset runs dip below 5%, which is what you'd expect by chance across that many extra statistics.

**How was power estimated?**
Null data come from the observed changes: resample rolls, randomly swap each roll's roll and control change, then add an effect. With a move 1.5× the control's, the tests catch it 29–43% of the time; at 2×, 68–85%. A consistent upward push of 1 tick per roll week would be caught by H2's sign test about 90% of the time, but a downward one only 37%, probably because the spread drifts up slightly in this sample (mean change +0.55 ticks in roll weeks, +1.0 in control weeks). This simulation was added after the results, and the plan's log says so.

## 5. Results

**What did you find?**
No evidence of a roll-week effect. Roll weeks moved slightly more on average (3.22 vs. 2.70 ticks), but the difference of +0.52 ticks is well inside the noise (−0.96 to +2.19, p = 0.89 and 0.37). There's no consistent direction either: the spread rose in 24 of 50 roll weeks.

**Is +0.52 ticks economically meaningful?**
No. It's about USD 3.25 per contract, less than one tick, and smaller than the bid-ask spread a roller crosses anyway.

**What drives the positive mean?**
Mostly four large roll weeks:
- December 2017: +27.5 ticks (FOMC hike and ECB meeting in the window);
- March 2023: +19.5 (the SVB week);
- September 2011: −18.0 in signed terms (euro-crisis dollar-funding stress);
- March 2020: +17.5 (COVID, ECB on March 12).

Without the largest one, the mean of d is +0.05. The event labels are context we know, not something we tested.

**Roll-week changes look more volatile (SD 6.2 vs. 3.8 ticks). Isn't that an effect?**
It comes from those few event weeks. The median d is exactly 0, and the sign test (which ignores size) shows nothing. A variance comparison wasn't the planned test, so we don't claim it either way.

**Why are the H1 and H2 counts identical (24 / 26 / 7)?**
Coincidence. They're different rolls: only 10 rolls are positive on both.

**The exploratory rolls go negative, and their block interval excludes zero. Does that matter?**
That's 8 rolls in two blocks, reported separately on purpose. It shows the motivating pattern (the spread rising every roll week) didn't hold under our definitions. It's not evidence for or against H1.

**At 3 weeks the block interval excludes zero. Is there an effect after all?**
It's a check we added after seeing results, the percentile interval includes zero, and the result comes from the few largest roll weeks. We call it inconclusive.

## 6. The professor's questions

**Do Fed/ECB meetings line up with rolls? Can they be ignored?**
They line up, so they can't be ignored. A decision falls inside 29 of 57 roll windows but only 1 control window. The Fed's and ECB's quarterly meetings fall mid-month, like the expiries, while the control week usually sits between meetings. We keep all rolls in the main test, and repeating it without any roll that has a meeting in either window (27 rolls) gives the same answer.

**Is the second contract month liquid enough for a good control?**
Usable but noisy. In the control week the deferred contract trades about 1.3% of its roll-week volume, yet its 10:00 quote was fresh on every control day in 16 years, so no roll lost its control. Its book is about twice as wide (median 3.5 vs. 2.0 ticks). A wider book makes the control midpoint noisier, which inflates |ΔC| and biases H1 toward no effect. Dropping rolls with wide quotes (34 left) doesn't change the result.

**Why were control books so wide in 2017–2019?**
Seven rolls from December 2017 to June 2019 had control-week deferred books of 14–45 ticks (median 22) while roll weeks stayed at 1–2. We don't know why. One possibility, from Databento's documentation: its CME book shows direct orders only, without implied prices, so when liquidity sits in the spread instrument the outright book looks wider than it really is. We didn't verify this.

**What does cost of carry imply?**
F = S·e^((r_USD − r_EUR)t), so two contracts imply the forward USD − EUR rate gap between their expiries: ln(F_deferred / F_front) / Δt. Carry predicts that this implied gap tracks the observed rate gap, with no roll-week bump. One tick is about 1.8 bp of implied gap.

**Did you include rates directly?**
Yes:
- USD: 3-month and 6-month T-bills (FRED `DTB3`, `DTB6`);
- EUR: the euro-area AAA curve (ECB `SR_3M`, `SR_6M`).

We use the previous day's values, because they're end-of-day and the snapshot is at 10:00. Subtracting the observed gap change (spot, or the forward between the expiries) still shows no effect.

**Does carry explain the weekly moves?**
Not week to week. Implied and observed gap changes are essentially uncorrelated (about 0.0 in both windows), which is why the carry-adjusted intervals are wider. Plausible reasons:
- government rates aren't dealer funding rates;
- FX-implied rates also carry the cross-currency basis;
- a 1-tick quote change is already 1.8 bp.

We didn't test which one it is.

**Spot or forward gap?**
The spread prices a forward period starting at the front contract's expiry. That's about a week out in the roll week but about five weeks out in the control week, so the spot 3-month gap fits control weeks worse. That asymmetry is why we added the forward gap built from 3- and 6-month rates. The ECB curve starts at 3 months, so the forward gap is still approximate.

**What would an interest-rate model add?**
Nothing we needed. The question is whether the spread moves beyond carry in roll weeks, and the simple carry relation with observed rates answers that. We kept it out of scope, as the professor suggested.

**Multiple currencies?**
6J and 6B would add rolls, and power, given the limited history. It's out of scope for the course, but it's the first extension we would do.

## 7. Limits and hard questions

**So rolling is free?**
No. We found no detectable effect in a test that has limited power and leans toward finding nothing. A moderate effect could exist and be missed.

**Could part of the effect be in your baseline already?**
Yes. 7–17% of spread volume trades the week before the roll week, mostly before the baseline Friday snapshot. That also biases H1 toward no effect. We accepted it rather than widen the window after seeing data.

**Doesn't the spread just reflect interest rates?**
Mostly, yes, which is why we used a paired design with the same contract pair and checked carry and central-bank meetings. We can't show who pays, or that rolling caused any move.

**Did you look at the held-out data before fixing the method?**
The decisions use only design reasoning and data-quality evidence: volume, quote freshness and quote width, with no spread changes. The liquidity check never outputs a spread value, and a test enforces that. Every later change is in the plan's deviation log.

**Was the plan frozen?**
Not fully. Three of four members signed off, and the main test ran on October 25, before Chris's sign-off and before the planned `plan-v1` tag, to meet the deadline. The open item had been the quote-width rule, which became decision 11 before the test ran. The deviation log records all of this.

**What was decided after the results?**
The 2- and 3-week controls and the power simulation. Both are labelled as post-hoc everywhere, and neither changes the main test.

**Why a 5-tick limit for "narrow quotes"?**
It was set before the results, from the liquidity data. Before mid-2017, 74% of control weeks had a snapshot wider than 5 ticks, against 4% of roll weeks. It's a sensitivity check, not a filter in the main test, because a cap would mostly remove old control weeks without fixing the underlying thinness.

**Is the 5-minute quote-age limit meaningful if quotes are always fresh?**
In this data a `bbo-1m` row appears in almost every minute, so the limit catches feed gaps (such as June 2014), not quiet markets. At every snapshot the main test uses, the bid or ask had changed within the previous 3 minutes.

## 8. What we didn't do (and would next)

- **Reversal check before expiry:** does a roll-week move unwind? Cut for time.
- **CFTC Traders in Financial Futures positioning:** would tell us which side dominates rolling, so a direction could be read as a cost. Cut for time.
- **Other currencies (6J, 6B):** more rolls, more power. Out of scope.
- **Front-running strategy:** with no detectable effect, and an estimate below one tick when the bid-ask is 1–2 ticks, there's nothing to trade.
- **Intraday timing:** spread volume peaks on the roll week's Wednesday; a finer test around that peak could have more power.
- **Listed spread quotes:** measuring the spread directly from the spread instrument.
- **Implied prices:** a book that includes implied liquidity might show the control week as less wide.

## 9. Code and reproduction

**How do I run it?**
Install the requirements and set `DATABENTO_API_KEY`. `python -m euro_roll.analyze --all` previews the cost; adding `--download` runs the test and writes `outputs/`. `python -m pytest` needs no key or network. See the README for the commands. On Windows PowerShell, set `$env:PYTHONPATH="src"` instead of the `PYTHONPATH=src` prefix.

**What's the pipeline?**
`download` + `cache` → `expiries` → `windows` → `spread` (10:00 snapshots and quote checks) → `changes` (net change per window) → `stats`, `meetings`, `carry`, `rates` → `analyze` (writes everything). `power`, `liquidity` and `volume_share` are separate scripts.

**How does the cache work?**
Each request is saved once as the DBN file Databento sent, keyed by a hash of the whole request. Files are written under a temporary name and renamed when complete, so an interrupted download never leaves a file that looks valid.

**How do the tests work without data?**
`tests/synthetic.py` builds fake 6E quotes and bars as real DBN records, so they look exactly like Databento output. Their special days include a missing day, a stale quote, a carried quote and a daylight-saving change, and each has a documented expected answer. CI runs the 191 tests on Linux and Windows on every pull request.

**How do you know the numbers are right?**
- A data audit Gonzalo ran with Claude Code recomputed all 130 window changes from the raw Databento files, and they matched exactly.
- Shreya recomputed H1 and H2 with her own code from `roll_vs_control.csv`, and they matched.
- The README and slide numbers were checked against `outputs/`.

**Did you use AI?**
Yes. We used Claude Code to write and review code, and some PRs say so. It also ran automated reviews: a code review, a data audit and an adversarial review of the result. Every change went through a pull request reviewed by teammates, and the headline numbers were recomputed independently.

## 10. Challenges and discoveries (good material for "what was hard?")

- **`ts_event` isn't quote time.** It's the last trade, often hours old, so measuring quote age with it would have dropped good days.
- **Symbols repeat every ten years.** That forced every table to be keyed by expiry date.
- **Juneteenth moved one expiry.** It was the only mismatch with Databento's definitions in 65 contracts.
- **The tick halved in early 2016.** We found it in the quote widths and confirmed it in the definitions.
- **Rolling shows up in the listed spread, not outright volume.** The outright crossover comes about two days after spread trading peaks, so outright volume alone mistimes rolling.
- **Central-bank meetings cluster in roll weeks.** They structurally line up with expiries, which is the professor's first question.
- **The control week is thin by design.** That's the reason the null is weak.

---

## Known loose ends (team only, not for the audience)

- **PR #55's results table doesn't match the current CSV.** It was labelled "all 65 rolls" but showed main-test medians, and the CSV has since been regenerated with the Juneteenth fix and holiday drops. Current all-65 figures: 48,999 vs. 751 per day, 2.0 vs. 3.5 ticks. Main test: 50,095 vs. 773, 2.0 vs. 4.0. Quote these, not the PR.
- **`tests/synthetic.py` says a `bbo-1m` row appears only when the book changes.** That was the early finding; `spread.py` now says rows appear in almost every minute.
- **If the final slides were edited in PowerPoint outside the repo**, check their numbers against this sheet.
