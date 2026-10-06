# Euro FX Futures Roll Pressure
FINM 37000 — Futures and Related Derivatives

## Research Question

Do Euro FX futures calendar spreads move more during quarterly roll
weeks than during comparable non-roll weeks?

CME Euro FX futures (`6E`) expire every March, June, September, and
December. Anyone keeping a position, such as a fund hedging euro
exposure, must **roll** it: close the expiring (front) contract and
open the next (deferred) one. Because the contract calendar fixes the
timing, much of that volume lands in the same few days each quarter, and
other traders can anticipate it. If that crowding pushes the price of
switching against rollers, they pay a cost that appears on no fee schedule.

We define the **calendar spread** as the deferred (second quarterly)
contract's price minus the front contract's price. Our main test
compares spread changes in roll windows with matched control windows.
As an additional check, we examine whether those changes reverse before
the front contract expires.

## Hypotheses

Stated before the full test is run.

- **H1 (magnitude):** The absolute change in the calendar spread is
  larger in roll windows than in matched control windows.
- **H2 (direction):** We examine whether the spread systematically rises
  or falls in roll windows. A rise makes rolling less favorable for long
  positions; a fall makes it less favorable for short positions.
  Without evidence of which side dominates rolling, we will not interpret
  a directional move as a cost to funds collectively. Optional CFTC
  Traders in Financial Futures (TFF) positioning, used only as of its
  publication date to avoid look-ahead, could identify the dominant side.
- **H3 (cost, only if H1 and H2 hold):** Convert the average excess move
  into a dollar cost per contract rolled. For reference, one 6E tick is
  0.00005 USD per EUR, or USD 6.25 per 125,000 EUR contract.

## Preliminary Observation (motivation only, not a result)

A quick check of the last eight quarterly rolls (December 2024 through
September 2026) found the spread rose in all eight roll weeks, while in
comparable normal weeks it moved both ways. We treat this as motivation:

1. The idea came from looking at these same rolls, so they cannot also
   serve as the test. The main test will use earlier rolls (Databento
   GLBX.MDP3 history goes back to 2010, roughly 60 rolls), with the exact
   range set after verifying coverage and download costs. The recent
   eight will be reported separately as exploratory analysis.
2. A 6E calendar spread mostly reflects the USD–EUR interest-rate
   differential (carry), so Fed or ECB decisions can move it regardless
   of any roll.
3. Eight observations is a small sample.

## Data and Sample

We will use Databento `GLBX.MDP3` data for individual quarterly 6E contracts:

| Dataset / schema | Contents | Use |
|---|---|---|
| `ohlcv-1d` | Daily bars per named contract | Volume migration from front to deferred |
| `bbo-1m` (or `trades`) | Best bid/offer per minute | Midpoints for both contracts at a common time |
| `definition` | Contract specs and expirations | Expiry dates and contract pairs; optionally the listed spread's own quotes |
| CFTC TFF reports (optional) | Weekly positioning by trader type | Dominant roll direction (H2) |

- We use **named contracts** (for example `6EU6`, `6EZ6`), not continuous
  series, so no return is computed across a contract switch.
- Missing or stale quotes and flagged data-quality dates will be documented.
- The project must run without CFTC data; H2 then reduces to describing
  the direction of the average move.
- An earlier pilot quoted these requests at USD 0 on one team account.
  This may not hold for every account, so the pipeline will include a
  small, cheap sample mode and show estimated cost before downloading.
- API keys and raw vendor data are never committed.
  See [docs/DATABENTO_REFERENCE.md](docs/DATABENTO_REFERENCE.md).

## Proposed Method 

The team will finalize the window definitions, observation time,
quote-quality rules, and statistical approach before examining the
historical test results. Each member signs off in the method decision
Issue.

1. **Roll calendar.** Get each front contract's last trading day from
   Databento definitions (for 6E, two business days before the third
   Wednesday of the contract month) and pair it with the next quarterly
   contract.
2. **Select windows.** The roll window is the last full Monday–Friday
   week before the front contract expires. This fixed rule is known in
   advance and is the main test. The control window is the same weekday
   pattern four weeks earlier, for the same contract pair. The days
   around the observed volume crossover are reported descriptively only.
3. **Measure spreads.** Observe both contracts' bid and ask at
   10:00 a.m. America/Chicago each weekday. Compute each midpoint and
   subtract the front midpoint from the deferred midpoint, reported in
   ticks. Apply a consistent quote-age limit and reject missing or
   stale observations.
4. **Compare changes.** Measure each window from the preceding Friday's
   snapshot to its ending Friday's snapshot, giving five daily changes.
   Compare absolute roll and control changes for magnitude, and report
   signed changes separately.
5. **Summarize results.** Report one paired comparison per roll. Test
   the magnitude differences with a sign test and a Wilcoxon signed-rank
   test, and give a bootstrap confidence interval for their mean.
   Consecutive rolls may share rate regimes, so we assess dependence
   across rolls before choosing the interval procedure. We do not count
   minute rows as independent tests.
6. **Check sensitivity.** Repeat with alternative window lengths and
   offsets, with the listed spread's quotes versus legged outrights, and
   excluding pairs where either window contains a scheduled Fed or ECB
   policy decision.
7. **Check reversal.** Where usable quotes remain after the roll window,
   examine whether the spread moves back toward its earlier level before
   expiry. Report the available observation horizon.

### Open Decisions

To be settled in the method decision Issue before the main test runs.

- **Number of control windows.** One control week per roll (proposed),
  or several earlier weeks to give a distribution of normal moves.
- **Carry and policy controls.** Flag or exclude windows containing Fed
  or ECB decisions (proposed, step 6), or also compare the spread with the
  level implied by the USD–EUR rate differential.
- **Remaining parameters.** Snapshot time, quote-age limit, missing-data
  policy, and confidence-interval procedure.

## Deliverables and Scope

We will produce:
- A reproducible pipeline for downloading data and comparing windows.
- Tables and figures showing spread changes for each roll and control
  pair (planned: `outputs/roll_vs_control.csv`,
  `outputs/figures/roll_vs_control.png`).
- A short report (`outputs/report.md`) explaining findings, uncertainty,
  and robustness checks.

**In scope:** one market (Euro FX, 6E), quarterly rolls, the pipeline,
and the report.

**Extensions if time allows:** CFTC positioning, a detailed
interest-rate model, a trading strategy that front-runs the roll, other
currencies (6J, 6B), and tick-level order-book analysis.

**Limitations.** Spread changes also reflect interest-rate expectations
and other market conditions. The analysis can identify patterns
consistent with roll pressure, but cannot establish actual costs paid by
funds or prove that rolling caused those movements.

## Task Roadmap

Each task will be tracked as a GitHub Issue with an owner, dependencies,
and completion criteria. Issue numbers will be added here once opened.

| # | Task | Depends on |
|---|---|---|
| 1 | Repo setup: package skeleton, `.gitignore`, API-key handling | — |
| 2 | Verify data coverage, cost, contract pairs, and expiry dates | — |
| 3 | Data download and cache: daily bars, minute BBO, definitions, sample mode | 1, 2 |
| 4 | Roll calendar: expiries per quarter, front/deferred volume-share table and chart | 3 |
| 5 | Spread construction: fixed-time snapshots, deferred minus front in ticks, data-quality checks | 3 |
| 6 | Method decision: settle Open Decisions above; team sign-off | — |
| 7 | Window selection: roll and control windows under the agreed rule, with tests | 4, 6 |
| 8 | Statistics: paired roll-vs-control comparison, held-out and recent rolls reported separately | 5, 7 |
| 9 | Robustness: alternative windows, central-bank exclusions, reversal check | 8 |
| 10 | Carry and central-bank controls: Fed and ECB calendar, optional rate-implied spread | 6 |
| 11 | Optional CFTC positioning aligned to publication date | 8 |
| 12 | Reproduce the preliminary eight-roll check in the pipeline and commit its script | 5 |
| 13 | Figures, tables, and final report | 8, 9 |

## How to Run

The full analysis pipeline is not yet implemented. The available
notebook explores volume migration across the eight recent rolls.

```bash
git clone https://github.com/chris-mulligan-50/futures-project.git
cd futures-project
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set your Databento key in the environment; never commit it:

```bash
export DATABENTO_API_KEY="your-key"      # Windows PowerShell: $env:DATABENTO_API_KEY="your-key"
```

Open `notebooks/roll_volume_exploration.ipynb` in VS Code or Jupyter,
select this environment, and run the cells in order. Review the
estimated cost before downloading.

**Planned interface (not yet built):**

```bash
python -m euro_roll download --sample    # small, cheap sample run
python -m euro_roll download --start 2010-01-01 --end 2026-09-30
python -m euro_roll analyze              # writes outputs/
```

### Planned repository layout

```
src/euro_roll/   download, expiries, spread, windows, stats, report
tests/           synthetic tests for roll dates, window selection, spread sign
data/            local cache (git-ignored; vendor data is not committed)
outputs/         generated tables and figures
notebooks/       exploration only; final results come from the scripts
docs/            reference material
```

## Team and Workflow

- **Tech Lead:** Chris Mulligan (owns the main repository)
- **Communication Lead:** Sidharth Saha
- **Design Leads:** Shreya Enaganti and Gonzalo Romero

This plan builds on Gonzalo's original draft. Work happens on a branch
and is merged to `main` by pull request; every team member reviews
every PR, and the Tech Lead merges once the team agrees.

## Related Work

- Mou (2010, revised 2011) finds price pressure associated with
  predictable commodity-index rolls.
  [Front-Running the Goldman Roll](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1716841)
- Irwin, Sanders, and Yan (2023) find that commodity roll effects
  disappeared in their 2012–2019 sample, suggesting concentrated rolling
  does not necessarily impose additional costs.
  [The Order Flow Cost of Index Rolling](https://experts.illinois.edu/en/publications/the-order-flow-cost-of-index-rolling-in-commodity-futures-markets/)
- CME's September 2022 FX roll analysis documents concentrated activity
  in the week before expiry alongside substantial liquidity.
  [Roll(ing) with it](https://www.cmegroup.com/articles/2022/price-discovery-complementary-liquidity-to-roll-forward-fx-risk.html)

These studies motivate testing for roll pressure in Euro FX without
assuming the effect exists.
