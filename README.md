# FINM 37000: Futures Project

## Do Funds Pay a Hidden Cost When They Roll Euro FX Futures?

**Tech Lead:** Chris Mulligan

**Communication Lead:** Sidharth Saha

**Design Leads:** Shreya Enaganti, Gonzalo Romero

> **Status: first draft of the idea (Gonzalo), open for edits.** Sections marked
> **[TO DISCUSS]** are open decisions. Please edit, comment on the PR, or rewrite
> anything that does not match what we agree on. The "How to run" section describes
> what we plan to build. None of it exists yet.

---

## 1. The idea in one paragraph

CME Euro FX futures (`6E`) expire every quarter (March, June, September, December).
Anyone who wants to keep a position, such as a fund hedging euro exposure, has to
**roll** it: close the expiring (front) contract and open the next (deferred) one.
Most of that volume moves in the same few days each quarter, because almost everyone
rolls before the front contract stops being liquid. Our hypothesis is that this
crowding pushes the price of switching (the **calendar spread**, deferred minus
front) against the people rolling. Because the roll dates are predictable, other
traders can position ahead of the flow. If that happens, rollers pay a cost that
appears on no fee schedule. We test it by asking:

> **Does the calendar spread move more during roll week than during a comparable
> normal week, and in the direction that hurts the rollers?**

## 2. Why this might happen

- **Predictable, concentrated flow.** Roll timing is set by the contract calendar.
  It is not driven by news, so the demand to trade the spread is known in advance.
- **Limited liquidity on one side.** If most rollers are positioned the same way
  (for example, mostly long euro), they all trade the spread in the same direction
  at the same time.
- **Precedent in other markets.** Similar roll-pressure effects have been documented
  for commodity index rolls (e.g. the "Goldman roll", Mou 2010) and for the U.S.
  Treasury futures roll (study linked on the course page). We want to know whether
  something similar shows up in a deep FX futures market.

## 3. What we have seen so far (preliminary, not a result)

We ran a quick check on the **last 8 quarterly rolls (Dec 2024 to Sep 2026)**. For each
roll we compared how much the spread moved in roll week with how much it moved in a
normal week about one month earlier.

- In **all 8 roll weeks** the spread rose; in the normal weeks it moved **both ways**.

Treat this as **motivation only**:

1. We came up with the idea while looking at these same 8 rolls, so they cannot also
   serve as the test. The formal test will use **earlier rolls** (Databento GLBX.MDP3
   history goes back to 2010, roughly 60 rolls) that we have not looked at yet. The
   recent 8 will be reported separately.
2. The spread also moves for other reasons. A 6E calendar spread mostly reflects
   the USD-EUR interest-rate differential (carry), so Fed or ECB meetings and rate
   repricing inside a window can move it regardless of any roll.
3. Eight observations is a small sample. The script behind the quick-check chart
   still needs to be cleaned up and committed so others can reproduce it.

## 4. Hypotheses (stated before the full test)

- **H1 (size):** The absolute change in the deferred-minus-front spread is larger in
  the roll window than in a matched control window.
- **H2 (direction):** In the roll window the spread moves in the direction that
  costs the dominant rollers. If rollers are net long, they sell the front and buy
  the deferred contract, so the spread rises. **[TO DISCUSS]**: how do we identify
  who the dominant roller is? Option: CFTC Traders in Financial Futures (TFF) net
  positioning, used only as of its **publication date** to avoid look-ahead.
- **H3 (cost, if H1/H2 hold):** Turn the average excess move into a dollar cost per
  contract rolled and per USD 1bn of notional hedged. For reference, one outright
  6E tick is 0.00005 USD per EUR, or USD 6.25 per 125,000 EUR contract.

## 5. Data

| Source | What | Why |
|---|---|---|
| Databento `GLBX.MDP3`, `ohlcv-1d` | Daily bars for each named quarterly 6E contract | Volume migration: identify when the roll actually happens |
| Databento `GLBX.MDP3`, `bbo-1m` (or `trades`) | Minute best bid/offer for front and deferred contracts | Build the spread from mid prices at fixed times each day |
| Databento `definition` | Contract specs, expirations, listed calendar-spread instruments | Exact expiry dates; optionally use the listed spread's own quotes |
| CFTC TFF reports (optional) | Weekly net positioning by trader type | Sign of the dominant roll (H2) |

- We use **named contracts** (e.g. `6EU6`, `6EZ6`), not continuous symbols, so that
  no return is computed across a contract switch.
- A small earlier pilot quoted these 6E requests at **USD 0** on one team account.
  That may not hold for every account, so we will build a small sample mode.
- The project must run **without CFTC data**. H2 then falls back to a
  "direction of the average move" description.

## 6. Method (draft)

1. **Roll calendar.** For each quarter, get the front contract's last trading day
   from Databento definitions (6E: two business days before the third Wednesday
   of the contract month).
2. **Roll window.** **[TO DISCUSS]** Option A: a fixed rule based on the calendar,
   e.g. the 5 business days ending N days before expiry, known in advance (preferred
   as the main test). Option B: the days around the volume crossover, defined
   after the fact (descriptive only).
3. **Control window.** Same length and weekday pattern, about 20 business days
   earlier. **[TO DISCUSS]**: also use several control weeks per roll to get a
   distribution of "normal" moves?
4. **Spread measure.** Deferred mid minus front mid at a fixed daily snapshot
   (e.g. a set time in the U.S. session), in ticks. Window move = last snapshot minus
   first snapshot.
5. **Controls for carry.** Compare the observed spread to the spread implied by the
   USD-EUR rate differential, or at least flag windows that contain Fed or ECB
   meetings. **[TO DISCUSS]**: how far do we go here?
6. **Statistics.** Each roll is paired with its own control, which gives one
   difference per roll. We report a sign test, a Wilcoxon signed-rank test, and a
   bootstrap confidence interval on the mean difference, all on the held-out rolls.
   Rolls are treated as independent observations. We do not count the thousands of
   minute rows as independent tests.
7. **Robustness.** Different window lengths and offsets, the listed spread's quotes
   versus legged outrights, and excluding windows with central-bank meetings.

## 7. Scope

**In scope:** one market (Euro FX, 6E), quarterly rolls, a reproducible pipeline,
and a short report with figures and tables.

**Out of scope for now (extensions if time allows):** a trading strategy that
front-runs the roll, other currencies (6J, 6B), and tick-level order-book analysis
of the roll days.

## 8. How to run (planned)

```bash
git clone https://github.com/chris-mulligan-50/futures-project.git
cd futures-project
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

# Databento key: read from the environment, never committed
export DATABENTO_API_KEY=...                         # Windows: $env:DATABENTO_API_KEY="..."

python -m euro_roll download --start 2010-01-01 --end 2026-09-30   # cached under data/
python -m euro_roll analyze                                          # writes outputs/
python -m euro_roll download --sample                                # small, cheap sample run
```

Outputs (planned): `outputs/roll_vs_control.csv` (one row per roll),
`outputs/figures/roll_vs_control.png` (the chart from Section 3, for all rolls), and
`outputs/report.md`.

## 9. Proposed repository layout (to be set up by the Tech Lead)

```
src/euro_roll/      download.py, calendar.py, spread.py, windows.py, stats.py, report.py
tests/              synthetic tests for roll dates, window selection, spread sign
data/               local cache (git-ignored, vendor data is not committed)
outputs/            generated tables and figures
notebooks/          exploration only. The final results come from the scripts
```

## 10. Draft task list (to become GitHub Issues)

These are a starting point for the issue roadmap. Split, merge, or reassign them as we
agree.

1. Repo setup: package skeleton, `pyproject.toml`, `.gitignore` for data, API-key handling.
2. Data download and cache: daily bars, minute BBO, and definitions for named 6E contracts, plus sample mode.
3. Roll calendar: expiries per quarter, plus a front/deferred volume-share table and chart.
4. Spread construction: fixed-time snapshots, deferred minus front in ticks, data-quality checks.
5. Window selection: roll and control windows under the agreed rule, with tests.
6. Statistics: paired roll-vs-control comparison and tests, held-out versus recent rolls reported separately.
7. Carry and central-bank controls: Fed and ECB meeting calendar, optional rate-implied fair spread.
8. Optional CFTC positioning: sign of the dominant roll, aligned to publication date.
9. Report and figures: generated report, README results section.
10. Reproduce the preliminary 8-roll check in the pipeline (and commit the script behind the chart).
