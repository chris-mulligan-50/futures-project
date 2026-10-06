# Databento — Account Reference

Reorganization of `databento_doc.md` (the raw doc-page dump), same treatment as
`NASDAQ_DATA_LINK_REFERENCE.md`. The original was one linear scroll mixing a billing snapshot, a
specs table, and a long normalization writeup with no separation between "what this costs" and "how
the data actually behaves." This file separates those.

**Source note:** reorganized from pasted Databento documentation, not a fresh pull. Where the source
text was ambiguous or a table's data cells were missing (see §7), that's noted rather than guessed at.

**For runnable pull code, see `DATA_PULL_GUIDE.ipynb` §2.** This file is the reference (what the
account actually has, what the data means); that notebook is the executable pull — and §2.5 of it
needs a second look in light of §2 below.

## Contents

- [1. Account snapshot](#1-account-snapshot)
- [2. ⚠️ Correction: the SPY pull in DATA_PULL_GUIDE.ipynb](#2-correction-the-spy-pull-in-data_pull_guideipynb)
- [3. Dataset: GLBX.MDP3 — specs](#3-dataset-glbxmdp3--specs)
- [4. Timestamps](#4-timestamps)
- [5. MBO normalization](#5-mbo-normalization)
- [6. Statistics normalization](#6-statistics-normalization)
- [7. Access tiers and release times](#7-access-tiers-and-release-times)
- [8. Symbology](#8-symbology)
- [9. Definition normalization — FX spots, spreads, combos](#9-definition-normalization--fx-spots-spreads-combos)
- [10. Status normalization](#10-status-normalization)
- [11. Matching algorithms](#11-matching-algorithms)
- [12. Historical eras: MDP 2 vs. MDP 3](#12-historical-eras-mdp-2-vs-mdp-3)
- [13. Used in this repo](#13-used-in-this-repo)

---

## 1. Account snapshot

**One subscription, one dataset.**

| Property | Value |
|---|---|
| Dataset | CME Globex MDP 3.0 (`GLBX.MDP3`) |
| Coverage | Futures · Options on futures |
| Tier | Plus |
| Cost | $1,200/month |
| Status | Renews 2026-09-01 |
| Live data | **Inactive** — this account has historical access, not a live real-time feed |

That's it — there is no separate equities or ETF entitlement on this account. Everything else in
this file describes the internals of `GLBX.MDP3` specifically. See §2 for why that matters.

---

## 2. ⚠️ Correction: the SPY pull in `DATA_PULL_GUIDE.ipynb`

`DATA_PULL_GUIDE.ipynb` §2.5 reconstructs a Databento pull for **SPY** (an NYSE Arca-listed ETF) to
produce `spy_clean.parquet` for the Kalshi project, guessing at a dataset name (`EQUS.SUMMARY`) with
an explicit `!! VERIFY` warning attached because no account information was available at the time.

**Now that the account is visible: this account has exactly one subscription, and it's `GLBX.MDP3` —
CME futures and options.** `GLBX.MDP3` does not carry SPY. SPY trades on NYSE Arca, not on any CME
Globex venue, and nothing in this dataset's specs (§3) lists equities or ETFs as covered instruments.

**What this means, plainly:** the SPY pull code in `DATA_PULL_GUIDE.ipynb` §2.5 is not just unverified
— it's very likely pulling against the wrong account/dataset entirely, unless one of these is true:

1. A **second Databento account or entitlement** exists that wasn't included in this doc dump (e.g. a
   personal/trial account separate from the paid `GLBX.MDP3` subscription).
2. The Kalshi project's `spy_clean.parquet` was **not actually sourced from Databento** despite the
   `submission.ipynb` abstract and `paper_functions.py` labeling it that way — it may have come from
   whichever teammate (George Lord or Max Zhalilo) held a different data access.
3. Databento was accessed under a **free/sample tier** for that one file, separate from the paid
   `GLBX.MDP3` subscription shown here.

**What HW1's Databento use *is* consistent with this account:** the CL/HO calendar-spread pull (§13)
is squarely CME futures — exactly what `GLBX.MDP3` covers. No correction needed there.

**Recommendation:** before writing any more code against §2.5's pattern, confirm which account/key
actually produced `spy_clean.parquet` — check `kalshi_market_making/.gitignore`'s `config.py` (if it
still exists locally) for a second key, or ask whichever teammate ran that pull. Don't extend the
`EQUS.SUMMARY` guess further without that confirmation.

---

## 3. Dataset: GLBX.MDP3 — specs

| Property | Value |
|---|---|
| Dataset ID | `GLBX.MDP3` |
| Full name | CME Globex MDP 3.0 |
| Asset class | Futures & Options |
| Available from | 2010-06-06 UTC |
| Venues | CME, CBOT, NYMEX, COMEX |
| Symbols | 650,000+ |
| Data categories | Normalized market data, Reference data |
| Schemas | `MBO`, `MBP-1`, `MBP-10`, `TBBO`, `Trades`, `BBO-1s`, `BBO-1m`, `OHLCV-1s`, `OHLCV-1m`, `OHLCV-1h`, `OHLCV-1d`, `Definition`, `Statistics`, `Status` |
| Encodings | DBN, CSV, JSON |
| Capture origin | Aurora DC3, FPGA network card, hardware timestamping, PTP-synced to UTC |
| Capture resolution | Nanosecond, immediate publication (data before 2017-05-21 has no capture timestamp — see §12) |

**What MDP 3.0 actually is:** CME's event-based feed for bid/ask/trade/statistical data, using Simple
Binary Encoding (SBE) and event-driven messaging. Since March 2017 it provides full per-order-event
granularity for every instrument's direct book (MBOFD) rather than the older aggregated-depth-per-
price-level model. It is the **sole** feed for everything on CME Globex — futures, options, spreads,
and combinations. (Exchange-traded spreads between futures outrights are classified as futures;
option combinations are classified as options.)

**Historical data availability varies by schema** — the source doc references a separate "See
details" page for the exact cutoffs per schema that wasn't captured here. Don't assume every schema
goes back to 2010-06-06; verify per schema before relying on early history for anything but OHLCV.

**Real-time data is included with any CME subscription; historical data is either usage-based or
included depending on plan** — this account's "Live data: Inactive" status (§1) means real-time isn't
currently active regardless of what's nominally bundled.

---

## 4. Timestamps

Every MDP 3.0 message normalizes to (up to) three timestamp fields:

| Databento field | MDP 3.0 tag | Meaning |
|---|---|---|
| `ts_recv` | N/A (Databento-assigned) | When Databento's capture server received the packet |
| `ts_event` | `60-TransactTime` | When CME's matching engine processed the event |
| `ts_in_delta` | `52-SendingTime` | When CME's matching engine sent the message |

Use `ts_event` for "when did this actually happen in the market"; use `ts_recv` for "when could I
have known about it" — the distinction matters for any latency-sensitive backtest assumption (see
`STRATEGY_TESTING_GUIDE.md` §III.5, "execution optimism": decision-to-action latency should never be
assumed at zero).

**Resolution caveat:** nanosecond precision only from 2015-11-20 onward within MDP 3.0 itself; data
before 2017-05-21 predates capture timestamping entirely (§12 covers the pre-2017 era in full — its
`ts_recv`/`ts_event` semantics are materially different).

---

## 5. MBO normalization

The `MBO` (market-by-order) schema is the highest-granularity schema in this dataset — every order
add/modify/cancel/trade/fill event, not aggregated depth. Four things to know before using it.

### 5.1 The `F_LAST` flag — required for correct top-of-book calculation

CME sends an "End of Event" flag (tag `5799-MatchEventIndicator`) on exactly one message per event,
even when that event spans multiple instruments. **Databento re-derives this into a per-instrument
`F_LAST` flag (`0x80`, 128), set on the last record for each `instrument_id` in the event** — this is
what makes the flag usable when you're only looking at a subset of instruments.

**Between records without `F_LAST` set, the book is mid-update and the apparent best bid/offer may
already have traded.** This is baked into Databento's own `MBP-1` and `Trades` schemas, but if you
work from raw `MBO` directly, you must respect `F_LAST` yourself or you will compute a top-of-book
that briefly reflects stale, already-crossed state. Records with `action = None` can still carry
`F_LAST`.

### 5.2 Order events → MBO actions

| CME message | Normalized MBO action(s) |
|---|---|
| Market Data Incremental Refresh — MBOFD | Add, Modify, Cancel |
| Market Data Incremental Refresh — Trade Summary | Trade, Fill |
| Market Data Incremental Refresh — Channel Reset | cleaR |

### 5.3 Trade Summary → Trade / Fill records — the subtle part

Each CME Trade Summary message carries **two repeating groups**: trade summaries, then order-ID
entries.

- Each trade summary → **one `Trade` record**.
- If the trade has a defined aggressor, its order-ID entry populates `order_id` on that `Trade`
  record. This is common when an incoming order partially fills and the remainder rests on the book.
- The **remaining (passive)** order-ID entries → **`Fill` records** — these correspond to resting
  orders that got hit, but do not themselves modify the book.
- **If the aggressing order already existed on the book** (e.g. a resting order gets modified to
  cross the book), a `Fill` record is emitted for it too.
- **If the aggressing order did not already exist on the book**, its `Fill` record is **suppressed**
  — but its order ID is still reported on the `Trade` record.

`MBP-n` and `Trades` schemas include the `Trade` records but never the `Fill` detail records —
`Fill` detail only exists in `MBO`.

**Side:** implied trades may have no defined aggressor side; these normalize with `side = None`.

### 5.4 Order priority (FIFO)

Databento does not expose CME's tag `37707-MDOrderPriority` directly, but **FIFO priority is
recoverable from message order** — messages for a single `instrument_id` are never reordered, even
when they share a timestamp. Daily MBO snapshots also preserve FIFO order.

### 5.5 The weekly MBO snapshot — a real gotcha

At the start of each weekly trading session, CME publishes a snapshot of orders that persisted from
the prior session (e.g. GTC orders). This snapshot is **not published in priority order** by CME.
Databento buffers the first event of the session per instrument, waits for "End of Event," sorts into
priority order, then publishes — so **publish order correctly reflects priority even though CME's
publish order didn't.**

Consequences you need to know before touching this data:

- `ts_event` on these snapshot records is the time CME **generated the snapshot**, not the original
  order-entry/modify time.
- `ts_recv` on all records in the snapshot is set to the `ts_recv` of the event's **final** record —
  meaning the early records' `ts_recv` doesn't match their true receive time. Databento marks this by
  setting **`F_BAD_TS_RECV`** on these records.
- **`F_SNAPSHOT`** is also set, so you can identify and special-case these records.

Additionally, Databento inserts its own **daily** order-book snapshot at 00:00:00 UTC every weekday
(Mon–Fri) to make historical MBO reconstruction more tractable across the market's actual Sun-night-
to-Fri-night weekly session structure. Order books can legitimately be locked or crossed before a
session opens or during the daily pause — CME accepts orders but doesn't execute until the opening
uncrossing.

---

## 6. Statistics normalization

Two families of statistics, from two different CME message types.

### 6.1 Daily statistics (from Market Data Incremental Refresh — Daily Statistics)

- Settlement price
- Cleared volume
- Open interest
- Fixing price

**Timing:** cleared volume and open interest normally publish the following UTC date — except for a
Friday session, which publishes the following **Sunday**. Settlement price publishes shortly after
that instrument's settlement window. CME does not publish a settlement price on the MDP feed for
instruments with no open interest or volume.

**Multiple records per date:** CME often sends several messages for the same `ts_ref` + stat
combination — preliminary values first, a final value last. **Always use the final message when one
is available**; treat earlier ones as provisional.

**`ts_ref`:** CME's tag `5796-TradingReferenceDate` (the trading session *date*) normalizes to
`ts_ref` as a nanosecond UNIX timestamp for consistency with other timestamp fields — **but the
source only has date precision.** Don't localize `ts_ref` to a timezone; treat it as a date label,
not a real event instant.

**`stat_flags`** (from tag `731-SettlPriceType`, settlement price records only):

| Bit | Decimal | Meaning |
|---|---|---|
| `1 << 0` | 1 | Final (vs. preliminary) settlement price |
| `1 << 1` | 2 | Actual (vs. theoretical) price |
| `1 << 2` | 4 | 1 = settling at the trading tick, 0 = at the clearing tick (relevant only for products with differing trading/clearing tick sizes) |
| `1 << 3` | 8 | Intraday settlement price, disseminated before the official EOD settlement calc |

### 6.2 Session statistics (from Market Data Incremental Refresh — Session Statistics)

- Opening and indicative opening price
- Trading session high and low
- Trading session highest bid / lowest offer

Published continuously through the session as these values change — these are not daily snapshots,
they're a live-updating stream during active trading.

### 6.3 Price limits

`HighLimitPrice` / `LowLimitPrice` from the Limits Banding message normalize to **upper/lower price
limit statistics**, published on every limits-banding update, with `ts_event` taken from tag
`60-TransactTime`.

---

## 7. Access tiers and release times

The source table's "License required" column header was present but its data cells were not captured
in the original doc dump — treat that column as unknown/unverified rather than assuming a value.

| Access method | Release time | License required |
|---|---|---|
| Live | Real-time | *(unspecified in source — verify with Databento)* |
| Historical | Delayed 20 minutes | *(unspecified in source — verify with Databento)* |
| Historical | Delayed 8 hours | *(unspecified in source — verify with Databento)* |

Given the account's "Live data: Inactive" status (§1), this account is presently operating in one of
the two delayed historical tiers, not the real-time tier — confirm which before assuming intraday
freshness on any newly-placed pull.

---

## 8. Symbology

Two distinct symbol fields, normalized from two different CME tags:

| Databento field | CME tag | Used for | Notes |
|---|---|---|---|
| `asset` | `6937-Asset` (Security Definition) | **Parent symbology** — requesting all contracts under a root | e.g. `stype_in="parent"`, `symbols=["CL.FUT"]` |
| `raw_symbol` | `55-Symbol` (Security Definition) | The literal traded symbol | Product code + month code + year |

**⚠️ Year-digit change in `raw_symbol`:** historically a single digit, e.g. `ESZ3` for E-mini S&P 500
December 2023. **CME has begun using a 2-digit year on some recently listed contracts**, e.g. `NGN25`
for Henry Hub Natural Gas July 2025. **Any symbol-parsing logic that assumes a fixed-length year
suffix will silently misparse newer contracts.**

This is directly relevant to HW1's approach (§13): it parses the expiry code off the last characters
of `symbol` and picks the two most-observed codes across the sample days. That heuristic survives a
digit-count change because it doesn't hardcode a length — but if you write a stricter regex-based
parser against CME futures symbols going forward, build in the 1-digit/2-digit ambiguity explicitly
rather than assuming last year's convention.

---

## 9. Definition normalization — FX spots, spreads, combos

### 9.1 FX spots

CME lists FX spot instruments alongside its futures. Databento sets `instrument_class = X` (FX spot)
whenever the instrument's CFI code begins with `IF`. `cfi` and `security_type` pass through from CME
unchanged — no Databento-side reinterpretation.

### 9.2 Spreads and combinations

`GLBX.MDP3` carries both exchange-listed spreads and user-defined spreads (UDS), split by what they
contain:

- **Futures-only spreads** (e.g. exchange-listed calendar spreads) are part of the **futures parent
  symbol**. Example: `ESH4-ESZ4` lives under `ES.FUT`. **These can have negative prices** — don't
  reject negative values as bad data if you're pulling calendar spreads directly.
- **Spreads containing options** (butterflies, covered spreads) are part of the **options parent
  symbol**. Example: `UD:1V: VT 2533938` lives under `ES.OPT`.

Use `instrument_class` in the `Definition` schema to generically identify a spread instrument;
`secsubtype` (normalized from CME's `SecuritySubType`) to identify the exchange-specific spread type;
and `asset` to identify the parent symbol of a strategy or UDS.

### 9.3 Leg definitions

Databento publishes **one definition record per leg** of a spread/combination. Records for the same
instrument are identical except for the `leg_`-prefixed fields:

| Field | MDP 3.0 tag | Meaning |
|---|---|---|
| `leg_count` | `555-NoLegs` | Number of legs in the spread |
| `leg_index` | N/A | 0-based index of this leg |
| `leg_instrument_id` | `602-LegSecurityID` | Instrument ID of the leg |
| `leg_side` | `624-LegSide` | Side taken for this leg when buying the spread |
| `leg_ratio_qty_numerator` | `623-LegRatioQty` | Quantity of the leg per unit of the spread |
| `leg_ratio_qty_denominator` | N/A | Always 1 for this dataset |
| `leg_price` | `566-LegPrice` | Tied price of the leg (hedged strategies) |
| `leg_delta` | `1017-LegOptionDelta` | Delta of the leg (hedged strategies) |
| `leg_raw_symbol`, `leg_instrument_class`, `leg_underlying_id` | N/A | Taken from the leg instrument's own definition |

`leg_ratio_price_numerator` / `leg_ratio_price_denominator` are **not populated** for this dataset —
don't expect values there.

**Race condition to handle:** CME can publish a spread's definition before its legs' own definitions
exist yet. Until a leg's definition arrives, the `leg_`-derived fields (raw symbol, instrument class,
underlying ID) are unset. **Databento republishes the affected leg records with
`security_update_action = Modify`** once the leg definition lands — so a consumer needs to handle a
definition record being updated in place, not just appended.

---

## 10. Status normalization

Status records come from Market Data Security Status messages. CME can send **one status update that
covers a whole group, a group+asset, or a single instrument** — Databento normalizes all three shapes
into **per-instrument** status records, so requesting `Status` schema data for several instruments in
the same group will show multiple near-identical records differing only by `instrument_id`.

**Caveat on `is_trading` / `is_quoting` / `is_short_sell_restricted`:** these state fields are driven
purely by CME's status updates. A group-level update generates a status record for **every**
instrument with a definition, regardless of whether that instrument has actually activated or
expired yet — meaning `is_trading`/`is_quoting` **can read incorrectly for an instrument before its
activation date.** Don't treat a `Status` record as ground truth for "is this contract live" without
cross-checking against the instrument's own activation date from the `Definition` schema.

---

## 11. Matching algorithms

CME runs multiple matching algorithms across its product universe; **FIFO is the most common** but
not universal. The source doc points to CME's own "Supported Matching Algorithms" page for the exact
algorithm per product — if a strategy's fill-queue assumption depends on matching behavior for a
specific instrument, verify which algorithm that instrument actually uses rather than assuming FIFO.

---

## 12. Historical eras: MDP 2 vs. MDP 3

CME introduced full per-order-event granularity (MBOFD) on **2017-05-21**. Data before that date
comes from the legacy MDP 2 / FIX-FAST protocol and behaves differently in ways that will silently
break assumptions carried over from post-2017 data.

| | Before 2017-05-21 (MDP 2) | From 2017-05-21 (MDP 3) |
|---|---|---|
| Source | FIX flat files | Direct UDP multicast capture at DC3 |
| `ts_recv` | **Set equal to `ts_event`** — no true capture timestamp exists | Real capture-server-received timestamp |
| Flag consequence | **`F_BAD_TS_RECV` is set on every MDP 2 record** — this is expected, not an error | Not set for this reason |
| Both `ts_recv`/`ts_event` source | CME tag `52-SendingTime` | `ts_event` = tag `60-TransactTime`; `ts_recv` = Databento's own capture |
| Timestamp resolution | Millisecond until 2015-11-20; nanosecond after | Nanosecond throughout |
| `MBO` schema | **Not available** — MDP 2 predates full-depth MBO | Available |
| Highest granularity available | `MBP-10` | `MBO` |
| `Status` schema | Materially sparser before Nov 2015 — normal-schedule status changes often didn't generate a message pre-2015 | Fuller coverage |

**Practical rule:** any pull spanning the 2017-05-21 boundary needs to branch its handling — treat
`ts_recv` as untrustworthy pre-boundary (it's a duplicate of `ts_event`, not an independent capture
time), don't request `MBO` for pre-2017 dates (it doesn't exist; fall back to `MBP-10`), and don't
expect status coverage before ~2015 to be complete.

---

## 13. Used in this repo

| Use | Dataset | Schema | Consistent with this account? |
|---|---|---|---|
| HW1 — CL (WTI) / HO (Heating Oil) calendar spread, Dec 12–19 2025 | `GLBX.MDP3` | `ohlcv-1m` | ✅ Yes — CME futures, within the account's coverage window |
| Kalshi project — SPY 1s OHLCV | *(assumed Databento, dataset unverified)* | `ohlcv-1s` | ❌ **No** — see §2. `GLBX.MDP3` doesn't carry SPY; this needs a different source or a different account before the pull code in `DATA_PULL_GUIDE.ipynb` §2.5 can be trusted |

HW1's symbol-parsing approach (filter to `root == 'CL'`/`'HO'`, extract expiry code from the trailing
characters of `symbol`, keep the two most-observed codes across the sample) is worth revisiting in
light of §8's year-digit change — it happens to be robust to that change by construction, but a
tighter regex written for a specific contract month format would not be.
