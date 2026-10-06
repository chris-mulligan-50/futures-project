# Euro FX Futures Roll Pressure
FINM 37000 — Futures and Related Derivatives

## Research Question

Do Euro FX futures calendar spreads move more during quarterly roll
weeks than during comparable non-roll weeks?

Traders maintain exposure by closing the expiring contract and opening
the next quarterly contract. We investigate whether concentrated
rolling is associated with unusual changes in the price difference
between those contracts.

Our main test compares spread changes during roll and control windows.
As an additional check, we examine whether those changes reverse
before the front contract expires.

## Hypotheses

We define the calendar spread as the second quarterly contract’s
price minus the front contract’s price.

- **Magnitude:** Absolute spread changes are larger during roll
  windows than during matched control windows.
- **Direction:** We examine whether spreads systematically rise or
  fall during roll windows. A rise makes rolling less favorable for
  long positions; a fall makes it less favorable for short positions.

Without evidence of traders’ rolling direction, we will not interpret
a directional movement as a cost to funds collectively.

## Data and Sample

We will use Databento GLBX.MDP3 data for individual quarterly Euro FX
futures (6E) contracts:

- Daily volume to examine migration from the front to the second contract.
- Bid and ask quotes to measure both contracts at a common observation time.
- Contract definitions to verify expiry dates and contract pairs.

The eight rolls from December 2024 through September 2026 informed
the project idea and will be reported as exploratory analysis.
The main test will use earlier rolls, with the date range determined
after verifying data coverage and download costs.

We will use named contracts rather than continuous futures series.
Missing or stale quotes and flagged data-quality dates will be
documented. API keys and raw vendor data will not be committed.

## Proposed Method — Pending Team Approval

The following specification is proposed for discussion. The team will
finalize the window definitions, observation time, quote-quality rules,
and statistical approach before examining the historical test results.

1. **Select windows.** Use the last full Monday–Friday week before
   the front contract expires as the proposed roll window. Match it
   with a control window four weeks earlier using the same contract pair.

2. **Measure spreads.** Observe both contracts’ bid and ask quotes
   at 10:00 a.m. America/Chicago each weekday. Calculate each midpoint,
   then subtract the front midpoint from the second midpoint.
   Apply a consistent quote-age limit; reject missing or stale observations.

3. **Compare changes.** Measure each window from the preceding
   Friday’s snapshot to its ending Friday’s snapshot, giving five
   daily changes. Compare absolute roll and control changes for
   magnitude, and report signed changes separately.

4. **Summarize results.** Report one paired comparison per quarterly
   roll, a sign test on the magnitude differences, and a confidence
   interval for their mean. Assess dependence across rolls when
   choosing the confidence-interval procedure.

5. **Check sensitivity.** Repeat the comparison using alternative
   window offsets and excluding pairs where either window contains
   a scheduled Fed or ECB policy decision.

6. **Check reversal.** Where usable quotes remain after the roll
   window, examine whether the spread moves back toward its earlier
   level before expiry. Report the available observation horizon.

### Open Decisions

These questions, first raised in Gonzalo's draft (#1), will be settled
in a method decision Issue. Each team member signs off there before
the main test is run.

- **Roll window rule.** A fixed calendar rule known in advance
  (proposed above) or the days around the observed volume crossover?
  Proposed: the fixed rule is the main test; the crossover is
  reported descriptively.
- **Number of control windows.** One control week per roll, or
  several earlier weeks to give a distribution of normal moves?
- **Carry and policy controls.** Flag or exclude windows containing
  Fed or ECB decisions (step 5), or also compare the spread with the
  level implied by the USD–EUR interest-rate differential?
- **Remaining parameters.** Snapshot time, quote-age limit,
  missing-data policy, and confidence-interval procedure.

## Deliverables and Limitations

We will produce:
- A reproducible pipeline for downloading data and comparing windows.
- Tables and figures showing spread changes for each roll and control pair.
- A short report explaining findings, uncertainty, and robustness checks.

Spread changes also reflect interest-rate expectations and other market
conditions. The analysis can identify patterns consistent with roll
pressure, but cannot establish actual costs paid by funds or prove
that rolling caused those movements.

The initial scope is limited to Euro FX futures. Positioning analysis,
a detailed interest-rate model, and a trading strategy are extensions.

## Task Roadmap

GitHub Issues will track:
1. Verify data coverage, cost, contract pairs, and expiry dates.
2. Implement downloads and synchronized spread measurements.
3. Implement the agreed window and data-quality rules.
4. Compare roll and control windows and run robustness checks.
5. Generate figures, tables, and the final report.

Each Issue should specify an owner, dependencies, and completion criteria.

## How to Run

The full analysis pipeline is not yet implemented. The available
notebook explores volume migration across the eight recent rolls.

Clone the repository and create a Python environment:

```bash
git clone https://github.com/chris-mulligan-50/futures-project.git
cd futures-project
python -m venv .venv
```

Activate it using the command for your terminal:

Windows Command Prompt:
```cmd
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Install the exploration dependencies:

```bash
python -m pip install databento pandas matplotlib ipykernel
```

Open `notebooks/roll_volume_exploration.ipynb` in VS Code or Jupyter,
select this environment, and run the cells in order. Enter your
Databento API key at the password prompt and review the estimated
cost before downloading.

Instructions for the full pipeline will be added when implemented.

## Team

- **Tech Lead:** Chris Mulligan
- **Communication Lead:** Sidharth Saha
- **Design Leads:** Shreya Enaganti and Gonzalo Romero

This plan builds on Gonzalo’s initial draft. The proposed method
remains subject to team review and approval.


## Related Work

Mou (2010, revised 2011) finds price pressure associated with predictable
commodity-index rolls. Irwin, Sanders, and Yan (2023) find that commodity
roll effects disappeared in their 2012–2019 sample, suggesting that
concentrated rolling does not necessarily impose additional costs.

CME’s September 2022 FX roll analysis documents concentrated activity
during the week before expiry alongside substantial liquidity. These
studies motivate testing for roll pressure in Euro FX without assuming
the effect exists.

References:
- [Mou: Front-Running the Goldman Roll](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1716841)
- [Irwin, Sanders & Yan: The Order Flow Cost of Index Rolling](https://experts.illinois.edu/en/publications/the-order-flow-cost-of-index-rolling-in-commodity-futures-markets/)
- [CME: Roll(ing) with it](https://www.cmegroup.com/articles/2022/price-discovery-complementary-liquidity-to-roll-forward-fx-risk.html)

