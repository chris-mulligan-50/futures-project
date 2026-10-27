# Presentation Transcript

Euro FX futures roll pressure: 8 slides, 5 minutes.

**How to use this.** Each slide has a target time, a running clock, what's on screen, the script, and one sentence to fall back on if you're behind. The main script is about 900 words, on purpose a little long: about 6 minutes at a calm 150 words a minute, or about 5½ at a brisker 165. If the run-through goes over, swap the longest slides' text for their "If behind" lines. The **Extra** boxes (about 2½ minutes in total) are for when you're ahead of the clock, or for Q&A. *Italic brackets* are cues for where to point. Every number matches `outputs/` and `docs/QA_CHEATSHEET.md`.

| Slide | Topic | Time | Clock at end | Suggested speaker |
|---|---|---|---|---|
| 1 | The question | 0:25 | 0:25 | Sid |
| 2 | Why rolls might cost something | 0:35 | 1:00 | Sid |
| 3 | How we test it | 0:45 | 1:45 | Chris |
| 4 | What we built and checked | 0:25 | 2:10 | Chris |
| 5 | What the data show before any test | 0:40 | 2:50 | Chris |
| 6 | Main result | 0:50 | 3:40 | Gonzalo |
| 7 | Robustness | 0:35 | 4:15 | Gonzalo |
| 8 | What we can and can't conclude | 0:45 | 5:00 | Shreya |

The speaker split follows who built each part (see "Who knows what" in the Q&A sheet), so whoever presents a slide can also take questions on it. Change it freely. Each handoff costs a few seconds, so keep them to about three.

---

## Slide 1: Euro FX futures roll pressure

**0:25, clock 0:25.** On screen: the question, and a diagram rolling 6EU6 (front) into 6EZ6 (deferred).

Good afternoon. We're Chris, Sid, Shreya and Gonzalo.

Euro FX futures, ticker 6E, expire every quarter. A fund hedging euro exposure can't hold a contract past expiry, so it *rolls*. *[point to the diagram]* It closes the expiring front contract and opens the next one. The price of that switch is the **calendar spread**: deferred minus front, in ticks worth 6.25 dollars per contract.

Our question: **does that spread move more in quarterly roll weeks than in comparable normal weeks?**

**If behind, just say:** "We test whether the price of rolling a Euro FX future, the calendar spread, moves more in roll weeks than in normal weeks."

---

## Slide 2: Why rolls might cost something

**0:35, clock 1:00.** On screen: three lines of motivation, the H1/H2/H3 boxes, and a note on where the idea came from.

Why would rolling cost anything? The calendar fixes the timing, so rollers all trade in the same few days each quarter, and everyone knows when. If that crowding pushes the spread against them, they pay a cost no fee schedule shows.

*[point to the H boxes]* Three hypotheses. **H1, magnitude:** the spread moves more in roll weeks than in matched control weeks. **H2, direction:** it moves the same way each time. **H3, cost:** only if both hold, we put a dollar figure on it.

*[point to the bottom box]* The idea came from the eight most recent rolls, where the spread seemed to rise every roll week. It actually rose in four of eight, and since those rolls gave us the idea, they're kept out of the test.

> **Extra, if time:** There's precedent. Mou, in 2010, found price pressure around the predictable Goldman commodity-index roll, and Irwin, Sanders and Yan later found it had faded by 2012 to 2019. So we tested for an effect without assuming one. Also, direction alone isn't a cost to funds as a group: long and short hedgers roll in opposite directions, so a rising spread hurts one side and helps the other.

**If behind, just say:** "Rolling happens on a fixed schedule, so it could be crowded. H1 asks if the spread moves more, H2 if it moves in one direction, and H3 prices it only if both hold."

---

## Slide 3: How we test it

**0:45, clock 1:45.** On screen: four definitions on the left, a timeline with the control and roll weeks, and three test boxes along the bottom.

The spread is the deferred midpoint minus the front midpoint, from the best bid and ask at 10 a.m. Chicago time each weekday.

*[point to the timeline]* The **roll week** is the last full week before expiry. The **control week** is four weeks earlier, for the same two contracts: same rate environment, but before rolling starts. For each week we take the net move from one Friday's snapshot to the next.

Our statistic, **d**, is the absolute roll-week move minus the absolute control-week move. That's **one number per roll**, so the unit of analysis is the roll, not the minute.

*[point to the bottom row]* We test d with a sign test, a Wilcoxon signed-rank test and a bootstrap 95% interval, on **57 held-out rolls from 2010 to 2024**. All of this was fixed in an analysis plan before we saw any results.

> **Extra, if time:** Thousands of minute quotes aren't thousands of independent observations, which is why we reduce each roll to one number. None of the three tests assumes normal data, which matters because the moves are fat-tailed. We also run a second, block bootstrap that resamples a year of rolls at a time, in case nearby rolls share a rate regime, and it gives nearly the same interval.

**If behind, just say:** "For each of 57 held-out rolls, we compare the spread's move in the roll week with its move four weeks earlier. That gives one number per roll, which we test three ways."

---

## Slide 4: What we built and checked

**0:25, clock 2:10.** On screen: a five-stage pipeline, every stage merged, and three numbers: 64 of 65, 7 days, 190+.

*[point to the pipeline]* We built a tested Python pipeline in five stages, each merged through pull requests the whole team reviewed.

*[point to the numbers]* Three checks that it works. Our expiry rule **matches Databento's definitions for 64 of 65 contracts**. The miss was June 2023, moved a day by Juneteenth, and we now handle it. Only **7 snapshot days were dropped** across 65 rolls: 5 CME holidays and 2 days with no quotes. And **more than 190 tests** run on every pull request.

> **Extra, if time:** The expiry rule is two business days before the third Wednesday. The tests run on Linux and Windows using synthetic Databento-format data, so they need no API key. One gotcha we caught: symbols repeat every ten years, so 6EU6 is both September 2016 and September 2026, and every table is keyed by expiry date instead.

**If behind, just say:** "The pipeline is tested and reviewed. Our expiry dates match Databento for 64 of 65 contracts, and only 7 days of data were dropped."

---

## Slide 5: What the data show before any test

**0:40, clock 2:50.** On screen: a bar chart of listed-spread volume (about 12% the week before, 83% in the roll week, 1% in the control week) and four findings.

Four facts from before the test, none of them using spread changes.

*[point to the chart]* **Rolling is concentrated.** About 83% of listed calendar-spread volume trades in the roll week, and about 1% in the control week. So our window is in the right place.

**Outright volume lags.** It crosses over to the deferred contract three days before expiry, about two days after spread trading peaks.

**The control is thin, and hold on to this one.** Its deferred contract trades 1 to 2% of roll-week volume and is quoted about twice as wide.

**Meetings line up.** Answering the professor's question, a Fed or ECB decision falls in 29 of 57 roll windows but only 1 control window. So we rerun the test without them.

> **Extra, if time:** The volume shares come from the eight recent rolls. The outright crossover holds in 63 of 65 rolls, so timing the roll by outright volume would place it too late. Meetings line up because both the meetings and the expiries fall mid-month.

**If behind, just say:** "Rolling is concentrated in our roll week, the control week is thinly traded, and Fed and ECB meetings cluster in roll weeks, so we check them separately."

---

## Slide 6: No evidence of a roll effect

**0:50, clock 3:40.** On screen: a bar chart of mean absolute move (3.22 vs. 2.70 ticks) and four stat callouts.

Here's the main result: **no evidence of a roll effect.**

*[point to the chart]* The spread moved 3.22 ticks on average in roll weeks, against 2.70 in control weeks. So the mean of d is **plus 0.52 ticks**. That's about 3 dollars per contract, under one tick, and less than the bid-ask spread a roller pays anyway.

*[point to the callouts]* And it's inside the noise. The **95% interval runs from minus 0.96 to plus 2.19**, which includes zero. The sign and Wilcoxon p-values are 0.89 and 0.37.

There's no consistent direction either. The spread rose in **24 of the 50 roll weeks** where it moved at all, which is a coin flip.

With neither H1 nor H2 holding, we don't compute H3. There's nothing to price.

> **Extra, if time:** Even that half tick comes mostly from a few event weeks: December 2017, with a Fed hike and an ECB meeting; March 2023, the week of SVB; and March 2020, COVID. Drop just the largest one and the mean falls to about 0.05.

**If behind, just say:** "Roll weeks moved about half a tick more than control weeks, but the interval includes zero, the p-values are far from significant, and there's no consistent direction."

---

## Slide 7: Robust under every planned check

**0:35, clock 4:15.** On screen: a dot-and-interval plot, one row per specification, with a vertical line at zero. Two rows are starred as added after the plan.

*[point to the plot]* Same H1 estimate, different specifications. The vertical line is zero.

Every planned check agrees. Keeping only rolls with narrow quotes gives plus 0.40. Dropping any roll with a Fed or ECB decision gives plus 0.52. *[point to the footnote]* The carry-adjusted versions, which use observed interest rates, also include zero.

The starred rows came after the plan, to check whether the thin control was hiding an effect. Two weeks out, there's nothing. Three weeks out gives plus 1.17. The main interval includes zero, but the block-bootstrap interval just excludes it. We added that check after seeing results, so we call it **inconclusive**.

> **Extra, if time:** The three-week result is driven by the same few large roll weeks. The last row is the eight recent rolls that gave us the idea: they go the other way, at minus 0.88, so the pattern that started the project didn't hold up.

**If behind, just say:** "Narrow quotes only, no central-bank weeks, carry-adjusted: every planned check includes zero. The one borderline result came from a check we added afterwards, so we call it inconclusive."

---

## Slide 8: What we can and can't conclude

**0:45, clock 5:00.** On screen: two columns, "What we can say" and "What we can't say", with the work cut for time in a footnote.

*[point to the left column]* What we can say: there's **no detectable roll-week effect in 57 held-out rolls**, and the checks agree. Every choice, and every later change, is logged.

*[point to the right column]* What we can't say is that there's **no effect**. The control week's noisy quotes inflate its moves, and that biases the test toward finding nothing. In simulation, a roll-week move 1.5 times the control's is caught only **29 to 43% of the time**. We can't say who pays, or that rolling caused any move. And the main test ran before our last sign-off, which the plan's deviation log records.

*[point to the footnote]* Next steps we cut for time: a reversal check, other currencies, and CFTC positioning data.

**Bottom line: no evidence of a roll-week effect, but "we didn't find it" is not "it isn't there."** Thank you, we're happy to take questions.

> **Extra, if time:** A move twice the control's would be caught 68 to 85% of the time, so we'd probably have caught a large effect, but a moderate one could slip through. We can't say who pays because the spread mostly tracks the dollar-euro interest-rate gap, and rollers sit on both sides.

**If behind, just say:** "No detectable effect, but the thin control week biases the test toward none, so this is weaker than a flat no. Thank you, we're happy to take questions."

---

## Numbers to say out loud

| Say | What it is |
|---|---|
| "plus 0.52 ticks, about 3 dollars" | H1 mean of d, 57 rolls (USD 3.25) |
| "minus 0.96 to plus 2.19" | its 95% interval |
| "p of 0.89 and 0.37" | sign test and Wilcoxon |
| "24 of 50" | roll weeks where the spread rose (H2) |
| "3.22 versus 2.70 ticks" | mean absolute move, roll vs. control |
| "29 to 43 percent" | power for a move 1.5 times the control's |
| "29 of 57 versus 1" | roll vs. control windows with a Fed or ECB decision |

For anything asked beyond the slides, use `docs/QA_CHEATSHEET.md`. If it isn't there, say what we measured and what we didn't. Don't guess.
