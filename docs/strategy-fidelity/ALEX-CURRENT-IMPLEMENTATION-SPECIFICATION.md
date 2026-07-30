# ALEX CURRENT IMPLEMENTATION SPECIFICATION

**Version:** `alex_g_sr_v1` (`RULES_ALEXG.ruleVersion`) · implementation `alex_g_sr_v1.impl.1` (`ALEX_IMPLEMENTATION_VERSION`)
**Engine / APP_VERSION:** `12.6.0`
**Generated:** 2026-07-30
**Repository Commit:** `a332d048979c9173c59311c0fc6677f815555b98`
**Source file:** `index.html` (single-file application; all line numbers below refer to it)
**Milestone:** MOGO-002.8A — ALEX Strategy Specification Export (Repository Truth Audit)

> **Scope.** This document records only what the implementation currently does. Where behaviour
> could not be established from the code, the text says **"Unable to determine from implementation."**
> Nothing is inferred, recommended, or compared against any external source.
>
> **Two ALEX strategies exist in the repository.** This document specifies **`alex_g_sr_v1`**, the one
> that paper-trades. `ALEX_SCORE_V2` (`ALEX_V2_META`, `index.html:14952`) is a separate research
> strategy with its own state and storage keys; `alexV2AutoTrading.enabled` is `false`. It is out of
> scope here except where noted.

---

## SECTION 1 — SYSTEM OVERVIEW

### 1.1 Strategy philosophy as implemented

`RULES_ALEXG` (`index.html:2340`) is a frozen rule specification with three parts:

- **`originalAlexConcepts`** — 13 statements the constant describes as *"rules directly traceable to
  the source transcript."*
- **`hubTestStandardizations`** — 15 statements the constant describes as *"rules the transcript does
  not define, invented here and explicitly labeled as such."*
- **`config`** — 20 keys holding the executed parameter values.

The implemented method is support/resistance zone detection followed by one of two setup types:
**REPEATED ZONE REACTION** (`A_repeatedReaction`) and **BREAK & RETEST** (`B_breakRetest`).

The header comment on `RULES_ALEXG` states a change-control rule: *"Once alex_g_sr_v1 trades or zones
exist, these values must never change in place — any future rule or default change requires a new
ruleVersion."*

### 1.2 Paper trading workflow

ALEX operates a **simulated account only**. No code path places a real order.

```
poll tick (60s)
  └─ alexGCheckLivePositions()          monitor/close existing positions FIRST
  └─ if alexGAutoTrading.enabled:
       for each pair in SCAN_PAIRS (12 pairs):
         skip unless a new H1 boundary has passed since this pair's last evaluation
         └─ alexGEvaluatePairForLiveSetups()
              ├─ fetch W, D, H4, H1 candles (90 days)
              ├─ full reset + rebuild of zone/setup state
              └─ for each setup: gates → alexGAttemptOpenLivePosition()
```

### 1.3 Major components

| Component | Entry function | Line |
|---|---|---|
| Zone engine (Phase 2) | `alexGRunZoneEngine` / `alexGProcessTimeframeCandle` | 2996 / 2877 |
| Setup engine (Phase 3) | `alexGRunSetupEngine` / `alexGProcessTimeframeCandleWithSetups` | 3349 / 3323 |
| Trade construction (Phase 4, replay) | `alexGConstructTrade` | 3470 |
| Historical replay engine | `alexGRunSetupReplay` | 3609 |
| Live position construction | `alexGConstructLivePosition` | 3956 |
| Live open path | `alexGAttemptOpenLivePosition` | 4060 |
| Live evaluation | `alexGEvaluatePairForLiveSetups` | 4187 |
| Live monitoring / exit | `alexGCheckLivePositions` | 4409 |
| Position close | `alexGCloseLivePosition` | 4455 |
| Poll driver | `alexGLivePollTick` | 4524 |
| Provenance stamping | `alexGStampTradeProvenance` | 2461 |

### 1.4 State machine

**Reaction → cluster → zone:**

```
swing anchor detected (alexGCheckSwingAt)
   └─ pendingAnchors[]                       awaiting displacement confirmation
        └─ confirmed reaction                displacement >= 0.25 * ATR
             ├─ price inside an existing validated zone → appended as touch 4+
             └─ otherwise → provisionalClusters[]
                  └─ at exactly the 3rd reaction → validatedZones[]  (status 'validated')
```

**Zone status:** `validated` → `broken` (never returns to `validated`; no code path resets it).

**Zone quality:** `clean` ⇄ `choppy`, recomputed every candle.

**Position:** `open` → `closed`. There is no partially-closed or pending state.

### 1.5 High-level execution lifecycle

1. `alexGLivePollTick()` runs every 60,000 ms (`setInterval`, line 4514).
2. Open positions are checked and possibly closed **before** any new setup is considered.
3. If `alexGAutoTrading.enabled` is false, the function returns after monitoring.
4. Pair evaluation advances only when `Math.floor(Date.now()/3600000)*3600000` exceeds the pair's
   last recorded H1 evaluation time.
5. Zone and setup state is **fully reset and rebuilt** from freshly fetched candles on every
   evaluation.
6. Each setup passes through gates in fixed order (Section 8), and either opens a position or
   records a permanent terminal status.

---

## SECTION 2 — MARKET CONDITIONS

### 2.1 When ALEX is allowed to trade

There is **no market-condition filter of any kind** in the implemented entry path. No code reads
volatility regime, trend state, or ranging/trending classification to permit or deny a trade.

| Condition | Implemented? | Evidence |
|---|---|---|
| Trending markets required | **No** | `trendContext` is computed (`alexGComputeTrendContext`, 3199) and stored, but no conditional reads it |
| Ranging markets excluded | **No** | `RANGE_MIXED` is a recordable value; no gate references it |
| Minimum volatility | **No** | No ATR-ratio or volatility-band check exists in the ALEX entry path |
| Maximum volatility | **No** | Same |
| Spread filter | **No** | `entrySpreadPips` is recorded at entry; no threshold is compared against it |

**ATR is used, but not as a filter.** `calcATR` (5680) is used for three purposes only: zone-cluster
grouping tolerance, reaction displacement qualification, and stop distance. A trade is blocked when
ATR is *unavailable* (`ATR_UNAVAILABLE`, line 3979), never when ATR is too high or too low.

The `RULES_ALEXG.hubTestStandardizations` array contains the string:
*"Structural trend context computed from confirmed swing structure (not an indicator) — metadata
only, never gates, scores, or alters a trade."*

### 2.2 Exclusions

The only implemented market-level exclusion is the fixed instrument list `SCAN_PAIRS`
(`index.html:2003`), 12 pairs:

`GBP/USD · EUR/USD · GBP/JPY · AUD/USD · USD/JPY · GBP/CHF · GBP/CAD · NZD/USD · AUD/JPY · EUR/JPY · USD/CAD · USD/CHF`

---

## SECTION 3 — TIMEFRAMES

Four timeframes are processed: **H1, H4, D, W** — hardcoded as the array literal `['H1','H4','D','W']`.

**`RULES_ALEXG.config.zoneTimeframes` is declared with the same four values but is never read.** The
three loops that iterate timeframes (`alexGEnsureZoneState` 2741, `alexGRunZoneEngine` 2999,
`alexGRunSetupEngine` 3349) each use the hardcoded literal.

| Timeframe | Purpose | Inputs | Outputs | Dependencies |
|---|---|---|---|---|
| **H1** | Master clock; drives all evaluation. Also a zone timeframe. | H1 candles (`days*24+60`, capped 40,000) | Zone/setup state on H1; loop cursor for H4/D/W | None |
| **H4** | Zone timeframe | H4 candles (`days*6+60`, capped 10,000) | Zone/setup state on H4 | Catch-up driven by H1 clock |
| **D** | Zone timeframe | D candles (`days+60`, capped 3,000) | Zone/setup state on D | Catch-up driven by H1 clock |
| **W** | Zone timeframe | W candles (`ceil(days/7)+60`, capped 600) | Zone/setup state on W | Catch-up driven by H1 clock |

**Master-clock mechanics** (`alexGRunZoneEngine`, 2996): for each H1 candle index, H1 is processed
once, then each of H4/D/W is advanced by a `while` loop that processes every candle whose close time
is `<= h1CloseTs`. More than one higher-timeframe candle can be processed per H1 step.

**Live dataset fetch** (`fetchAlexGReplayDatasets`, 3713) is called with `days = 90`. Fetch order is
W, D, H4, H1. Evaluation aborts if `datasets.H1.length < 60` (line 4201 region).

**Timeframe priority:** `config.htfPriority = {W:4, D:3, H4:2, H1:1}`, read only by
`alexGSetupSortComparator` (3589) for ordering. It does not gate, weight, or size any trade.

**Sub-H1 timeframes are not used anywhere in the ALEX path.**

---

## SECTION 4 — SESSIONS

### 4.1 Implemented session filtering: none

**No session, day-of-week, hour, weekend, holiday, or news rule blocks an ALEX trade.** Session data
is computed and stored as metadata only.

`RULES_ALEXG.hubTestStandardizations` contains: *"Zero session/day/news filtering in v1.0 — a
deliberate design choice, not a source gap; metadata is still recorded for later analysis."*

### 4.2 Session metadata that IS computed

`alexGComputeSessionMetadata` (3225) records four fields on every setup:

| Field | Source |
|---|---|
| `session` | `getSession(date).name` |
| `dayOfWeek` | `['Sun'…'Sat'][date.getUTCDay()]` |
| `hourOfDay` | `date.getUTCHours()` |
| `insideCurrentStrategyPreferredWindow` | `isPreferredTradingDay(date) && sess.priority` |

**`getSession(atDate)` (7922)** — UTC minutes-of-day boundaries:

| Window (UTC) | Name | `active` | `priority` |
|---|---|---|---|
| 720–959 (12:00–15:59) | `London/NY Overlap` | true | **true** |
| 480–1199 (08:00–19:59) | `London` | true | **true** |
| 1200–2099 (20:00–34:59¹) | `New York` | true | false |
| all other | `Off-hours` | false | false |

¹ The literal comparison is `utcM>=1200&&utcM<2100`. `utcM` has a maximum of 1439, so the effective
New York window is 20:00–23:59 UTC.

Evaluation order is sequential, so the Overlap test wins over London for 12:00–15:59.

**`isPreferredTradingDay(date)` (5726)** returns `date.getUTCDay() >= 1 && <= 3` — Monday, Tuesday,
Wednesday.

**Neither function is called from any ALEX gate.** Both are called only from
`alexGComputeSessionMetadata`, whose output is written to setup and position records.

### 4.3 Weekend and holiday handling

**No weekend rule and no holiday rule is implemented.** No calendar, holiday list, or market-closure
check exists in the ALEX path. Behaviour when the broker returns no candles for a closed market is
governed by the generic guards: evaluation aborts if `datasets.H1.length < 60`, and position
monitoring skips a cycle if `fetchBidAsk` returns falsy.

### 4.4 Kill zones

**Not implemented.** No such concept exists in the ALEX code.

---

## SECTION 5 — MARKET STRUCTURE

### 5.1 Swing / pivot identification

`alexGFindSwingPoints(candles, lookback)` (2693) and its single-candle equivalent
`alexGCheckSwingAt(candles, centerIdx, lookback)` (2709) use an identical test:

- **Swing high** at `i` when, for every `k` in `1..lookback`:
  `candles[i-k].h < c.h` **and** `candles[i+k].h < c.h`
  (implemented as `if(candles[i-k].h>=c.h||candles[i+k].h>=c.h) isHigh=false`)
- **Swing low** at `i` when, for every `k` in `1..lookback`:
  `candles[i-k].l > c.l` **and** `candles[i+k].l > c.l`

Comparisons are strict — an equal high or low disqualifies the pivot. The test requires `lookback`
candles on **both** sides, so confirmation lags by `lookback` bars.

`lookback` is `config.trendSwingLookback = 3` in both uses. `alexGProcessTimeframeCandle` (2877)
states this is *"reused as the zone-anchor swing lookback too (documented Hub choice)"* and also
assigns `sameInteractionMaxBarGap = lookback`.

### 5.2 Trend determination

`alexGComputeTrendContext(candles, idx, cfg)` (3199):

1. Slice the most recent `min(idx+1, trendSwingScanBars=200)` candles.
2. Find swing points with `lookback = 3`.
3. If `swingHighs.length < 2 || swingLows.length < 2` → `INSUFFICIENT_DATA`.
4. Compare the latest two of each:

| Condition | Result |
|---|---|
| `latestSwingHigh > previousSwingHigh` **and** `latestSwingLow > previousSwingLow` | `UPTREND` |
| `latestSwingHigh < previousSwingHigh` **and** `latestSwingLow < previousSwingLow` | `DOWNTREND` |
| otherwise | `RANGE_MIXED` |

Stored fields: `trendContext`, `latestSwingHigh`, `previousSwingHigh`, `latestSwingLow`,
`previousSwingLow`. **Record-only — no gate reads them.**

### 5.3 Higher High / Higher Low / Lower High / Lower Low

There are **no named HH/HL/LH/LL detectors**. The four concepts exist only implicitly inside the
`alexGComputeTrendContext` comparison above.

### 5.4 Break of Structure / Market Structure Shift

There is **no function named for break-of-structure or market-structure-shift**. The implemented
equivalent is **zone break detection** inside `alexGProcessTimeframeCandle` (2877), Step 3:

1. Determine `priorRole` = `zone.lastKnownRole`, or — only when that is still `null` —
   `alexGInferPriorZoneRole(zone, candles, idx)` (2867), which searches **strictly backward** from
   `idx-1` for the most recent close outside the zone boundaries, returning `'support'`,
   `'resistance'`, or `'unknown'`.
2. If `priorRole === 'unknown'`, **break detection is skipped entirely for this candle.**
3. Otherwise:
   - `breakingClose` = `priorRole==='support' ? bar.c < zone.low : bar.c > zone.high`
   - On a breaking close: `consecutiveBreakCloses++`, `inPenetrationEpisode = false`. When
     `consecutiveBreakCloses >= config.breakConfirmationCloses (1)` and status is still `validated`,
     the zone becomes `broken`, recording `brokenAtBar`, `brokenAt`, and
     `brokenDirection ∈ {downThroughSupport, upThroughResistance}`.
   - Otherwise `consecutiveBreakCloses = 0`, and a **wick-only** excursion
     (`wickBeyond && !closeBeyond`) opens a penetration episode if one is not already open.
4. **Role update always runs afterwards**, using this candle's own close:
   `newRole = alexGZoneRole(zone, bar.c)`; if `newRole !== 'inside'`, `zone.lastKnownRole = newRole`.

`alexGZoneRole(zone, price)` (2735): `price > zone.high → 'support'`; `price < zone.low →
'resistance'`; otherwise `'inside'`. Boundaries are exclusive on both comparisons, so a price exactly
equal to `zone.high` or `zone.low` returns `'inside'`.

---

## SECTION 6 — ZONE IDENTIFICATION

### 6.1 Formation requirements

A zone is created at **exactly the 3rd qualifying reaction** in a provisional cluster
(`alexGAcceptReaction`, 2792, `if(cluster.reactions.length===3)`).

A reaction qualifies when all of the following hold (`alexGProcessTimeframeCandle` Step 2):

1. A swing anchor exists at `idx - trendSwingLookback` per Section 5.1.
2. Its displacement-confirmation window has elapsed: `idx >= anchorIdx + rejectionConfirmWithinBars (1)`.
3. **Displacement test:** using candles from `anchorBarIndex+1` to `min(idx, awaitingUntilBarIndex)`:
   - swing low: `displacement = max(window highs) - anchor.price`
   - swing high: `displacement = anchor.price - min(window lows)`
   - qualifies when `atr && displacement >= rejectionDisplacementATRMultiplier (0.25) * atr`
   - **ATR is computed as of the anchor's own bar** (`candles.slice(0, anchorBarIndex+1)`), not "now".
4. **Not a duplicate interaction:** `alexGIsSameInteraction` (2783) rejects the anchor if any
   already-accepted reaction has the **same `swingType`** and `|barIndexA - barIndexB| <= 3`.

A failing anchor is silently dropped — the comment states *"fails the provisional reaction test —
silently does not count, per spec."*

### 6.2 Cluster assignment and measurements

`groupingTolerance = ATR(at anchor bar, period 14) * zoneClusterATRMultiplier (0.5)`.

`alexGAssignCluster` (2763) selects among clusters of the **same `swingType`** whose
`|price - center| <= groupingTolerance`, choosing by a fixed tie-break cascade:
nearest center → earlier `createdAtCloseTimeMs` → lower cluster `id` lexicographically.

If no cluster matches, a new one is created with `center = anchor.price`. After each reaction is
appended, `cluster.center` is recomputed as the **arithmetic mean of all reaction prices**.

### 6.3 Zone boundaries

At validation the zone is locked to the three reaction prices:

```
high   = Math.max(...prices)
low    = Math.min(...prices)
center = (high + low) / 2
```

**Boundaries are immutable after validation.** No code path recomputes `low`, `high`, or `center` on
an existing validated zone; touches 4+ are appended without altering them.

### 6.4 Minimum and maximum size

**Neither is implemented.** There is no minimum zone width, no maximum zone width, and no check on
`high - low` anywhere. Zone width is whatever the three reaction prices produce.

`zoneClusterATRMultiplier` bounds how far apart two reactions may be *to be grouped*; it is not a
size test on the resulting zone. It carries `experimentalParams` metadata:
`status: 'EXPERIMENTAL'`, `sensitivityRange: [0.25, 0.5, 0.75, 1.0]`, described as *"arbitrary
starting point pending controlled sensitivity testing, not tuned against historical outcomes."*

### 6.5 Invalidation

A zone's `status` becomes `'broken'` per Section 5.4. **No code path returns a broken zone to
`validated`.** A broken zone is permanently ineligible for `A_repeatedReaction` and becomes eligible
for `B_breakRetest` within the retest window.

### 6.6 Expiration / ageing

**Disabled.** `config.maxZoneAgeBars = null`. `zone.ageBars` is maintained every candle
(`idx - zone.formedAtBar`) but **no code reads it for any decision**.

`hubTestStandardizations` states: *"Zone aging is OFF by default (unlimited)."*

### 6.7 Retesting

Handled by `alexGEvaluateBreakRetest` — see Section 8.3.

### 6.8 Merging

**Zones are never merged.** Merging exists only at the pre-validation cluster stage (Section 6.2).
Once validated, a zone is independent; a new reaction whose price falls inside an existing validated
zone is appended to **that** zone (`hostZone` lookup, line 2804) rather than forming a new one.

The `hostZone` test is `anchor.price >= z.low && anchor.price <= z.high` — **inclusive**, unlike
`alexGZoneRole`'s exclusive comparison.

### 6.9 Priority

`config.htfPriority = {W:4, D:3, H4:2, H1:1}`, used only by `alexGSetupSortComparator` (3589) to
order setups. In the live path, setups are iterated in `alexGSetupState` array order
(`alexGSetupState.filter(s=>s.pair===oPair)`, line 4205) — **the comparator is not applied to the
live loop.**

---

## SECTION 7 — TOUCH LOGIC

### 7.1 Touch counting

One shared, bidirectional tally per zone: `zone.touches[]`. Reactions from above and below both
append to the same array. Each touch records `barIndex`, `price`, `timestamp`, `reactionId`,
`swingType`, and `fromSide`.

`fromSide` is computed by `alexGDetermineFromSide` (2752) from the close of the candle **before** the
anchor (`anchorBarIndex - 1`): `> refHigh → 'above'`, `< refLow → 'below'`, otherwise
`'inside_unknown'`. For a validated host zone the reference is the zone's own low/high; for a
provisional cluster both reference arguments are `cluster.center`.

### 7.2 Valid vs invalid touch

A "valid touch" is precisely a reaction that passed all four tests in Section 6.1. An anchor failing
displacement or the same-interaction test is discarded and never appears in `zone.touches`.

**Touch acceptance is deliberately independent of `zone.status`.** The code comment (2794–2803)
states that a price excursion closing beyond the far edge is legitimately both a break-relevant event
and a genuine reaction, and *"one must not gate the other."*

### 7.3 Zone strength tiers

Recomputed on every appended touch (line 2809):

```
touches.length < 3  → 'weak'
touches.length === 3 → 'valid'
touches.length >= 4  → 'strong'
```

**The tier saturates at `strong`.** No consumer distinguishes a 4-touch zone from a 12-touch zone.
The raw count remains available as `zone.touches.length` and `zoneTouchNumber`.

### 7.4 Fresh vs used zones

There is **no "fresh" or "used" flag.** The nearest equivalents are:

- `touchIndex < 3` → never eligible for any setup.
- For `B_breakRetest`: only the **first** qualifying retest per `breakCycleId` produces a setup
  (`alreadyUsed` check, line 3159).
- For live trading: a `signalId` decided once is **permanent** and never reconsidered
  (`alexGLiveSetupStatuses` dedup, line 4237).

### 7.5 Minimum and maximum touches

| | Value | Location |
|---|---|---|
| Minimum touches for zone validation | **3** | `alexGAcceptReaction`, 2827 |
| Minimum `touchIndex` for any setup | **3** (0-based → the 4th touch) | `alexGClassifyTouch`, 3291 |
| Minimum `zone.touches.length` for `A_repeatedReaction` | **4** | `alexGEvaluateRepeatedReaction`, 3168 |
| **Maximum touches** | **None implemented** | — |

---

## SECTION 8 — ENTRY CONDITIONS

### 8.1 Setup classification order

`alexGClassifyTouch` (3288) runs per newly accepted touch:

1. `alexGResolvePenetrationForTouch(...)` — resolves any matching penetration event.
2. If `touchIndex < 3` → `touch.setupEligibility = null`, **return**.
3. `correctedQuality = alexGCorrectedQuality(zone, idx, cfg)`.
4. **`alexGEvaluateBreakRetest` is evaluated FIRST.** If it qualifies → `B_breakRetest` record, return.
5. Otherwise `alexGEvaluateRepeatedReaction`. If it qualifies → `A_repeatedReaction` record, return.
6. Otherwise `touch.setupEligibility = null`.

**Precedence is fixed: BREAK & RETEST before REPEATED ZONE REACTION.** A reaction produces at most
one setup. `setupEligibility` is written exactly once and never overwritten.

### 8.2 `A_repeatedReaction` — required conditions (`alexGEvaluateRepeatedReaction`, 3165)

All must hold:

1. `zone.status === 'validated'` (never an already-broken zone)
2. `touchIndex >= 3`
3. `zone.touches.length >= 4`
4. `correctedQuality !== 'choppy'`

### 8.3 `B_breakRetest` — required conditions (`alexGEvaluateBreakRetest`, 3147)

All must hold:

1. `touchIndex >= 3`
2. `zone.status === 'broken'`
3. `zone.brokenAtBar != null && zone.brokenAt != null`
4. `idx > zone.brokenAtBar` (strictly after the break candle)
5. `idx - zone.brokenAtBar <= maxBarsBetweenBreakAndRetest (50)`
6. `touch.swingType` matches the required side:
   `downThroughSupport → 'high'`, `upThroughResistance → 'low'`
7. `touch.fromSide` matches:
   `downThroughSupport → 'below'`, `upThroughResistance → 'above'`
8. No existing setup with the same `zoneId`, type `B_breakRetest`, and `breakCycleId`

**Note:** condition 1 for `B_breakRetest` does **not** require `zone.touches.length >= 4` — only
`touchIndex >= 3`.

### 8.4 Corrected quality (`alexGCorrectedQuality`, 3137)

```
recent = penetrationEvents where
           startBarIndex <= atBarIndex
       AND startBarIndex > atBarIndex - choppyLookbackBars (50)
       AND countsTowardChoppy === true
return recent.length >= maxPenetrationsBeforeChoppyFlag (3) ? 'choppy' : 'clean'
```

This is **separate from `zone.quality`**, which the Phase 2 loop also maintains using every wick-only
penetration regardless of later resolution. Only `correctedQuality` gates setup eligibility.

### 8.5 Live entry gates — order of evaluation

`alexGEvaluatePairForLiveSetups` (4187) then `alexGConstructLivePosition` (3956):

| # | Gate | Failure status / reason |
|---|---|---|
| 1 | Signal already decided (`alexGLiveSetupStatuses`) | skipped; `STATE_SIGNAL_ALREADY_DECIDED` |
| 2 | **Activation cutoff** — `activatedAt` set and `qualificationTimestamp >= activatedAt` | `IGNORED — BEFORE ACTIVATION` / `CONFIG_BEFORE_ACTIVATION` |
| 3 | **Signal staleness** — `(now - qualificationTimestamp)/60000 > maxLiveSignalAgeMinutes[tf]` | `IGNORED — STALE SIGNAL` |
| 4 | Duplicate (`tradedSignals`, open, closed, journal) | `DUPLICATE` |
| 5 | Direction resolvable | `BLOCKED — INVALID DIRECTION` |
| 6 | **One open trade per pair+timeframe** | `BLOCKED — EXISTING POSITION` / `EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME` |
| 7 | ATR available and `> 0` | `BLOCKED — INVALID STOP` / `ATR_UNAVAILABLE` |
| 8 | Bid/ask available | `BLOCKED — NO BID/ASK` / `LIVE_BID_ASK_UNAVAILABLE` |
| 9 | **Entry delay** — `|liveFill - qualificationClose|/pip <= maxLiveEntryDelayPips (5)` | `BLOCKED — ENTRY MOVED` / `ENTRY_MOVED_TOO_FAR_FROM_SIGNAL` |
| 10 | Stop finite and on the correct side of fill | `BLOCKED — INVALID STOP` / `INVALID_STOP` |
| 11 | Pip value available | `BLOCKED — NO PIP VALUE` / `PIP_VALUE_UNAVAILABLE` |
| 12 | Position size finite and `> 0` | `BLOCKED — NO PIP VALUE` / `PIP_VALUE_UNAVAILABLE` |
| 13 | `tradeId` not already open/closed | `DUPLICATE` |

**Every status is permanent.** Once recorded for a `signalId`, gate 1 prevents re-evaluation forever.

### 8.5.1 Staleness thresholds

`config.maxLiveSignalAgeMinutes = {H1:60, H4:240, D:1440, W:10080}` — one bar-period per timeframe.
If the timeframe key is absent, `alexGIsSetupSignalStale` returns `false` (no staleness gate).

### 8.6 Entry trigger and price

**Entry is the live executable price at the moment of the poll:**
`liveFillPrice = direction==='buy' ? ba.ask : ba.bid` (line 3987).

It is **not** the qualification candle close; `qualificationClose` is used only for the entry-delay
test and for `qualificationPlannedTarget`.

### 8.7 Direction (`alexGDetermineTradeDirection`, 3396)

Derived **only** from frozen setup fields, never from live price:

| Setup type | Field | → Direction |
|---|---|---|
| `A_repeatedReaction` | `zoneRoleAtQualification === 'support'` | `buy` |
| `A_repeatedReaction` | `zoneRoleAtQualification === 'resistance'` | `sell` |
| `A_repeatedReaction` | otherwise (`inside`/null) | `null`, `INVALID_ZONE_ROLE_INSIDE` |
| `B_breakRetest` | `brokenDirection === 'downThroughSupport'` | `sell` |
| `B_breakRetest` | `brokenDirection === 'upThroughResistance'` | `buy` |
| `B_breakRetest` | otherwise | `null`, `INVALID_BROKEN_DIRECTION` |
| any other type | — | `null`, `UNSUPPORTED_SETUP_TYPE` |

### 8.8 Optional conditions

**There are no optional entry conditions.** Every implemented check is pass/fail. Psychological
levels, trend context, and session metadata are computed and stored but read by no gate.

---

## SECTION 9 — CONFIRMATION LOGIC

### 9.1 The only implemented confirmation

**ALEX implements exactly one confirmation mechanism: the ATR-normalized displacement test** in
Section 6.1 step 3.

```
swing low  : displacement = max(window highs) - anchor.price
swing high : displacement = anchor.price - min(window lows)
qualifies  : displacement >= 0.25 * ATR(14, as of anchor bar)
window     : anchorBarIndex+1 .. min(idx, anchorBarIndex + 1)
```

With `rejectionConfirmWithinBars = 1`, the window is **one candle**.

Confirmation occurs on the **same timeframe** as the zone. `hubTestStandardizations` records:
*"Same-timeframe rejection confirmation (a Weekly zone confirms on a Weekly candle, etc.)."*

### 9.2 Candlestick patterns

| Pattern | Implemented? |
|---|---|
| Bullish engulfing | **No** |
| Bearish engulfing | **No** |
| Morning Star / Evening Star | **No** |
| Doji | **No** |
| Pin bar / hammer | **No** |
| Momentum or "strong" candle | **No** |
| Body-percentage test | **No** |
| Close-location test | **No** |
| Volume | **No** — no volume field is read anywhere in the ALEX path |

**No named candlestick-pattern detector exists in the ALEX implementation.**

### 9.3 Wick handling

`config.requireWick = false` and `config.minWickRatio = 0.0`.

**Neither key is read by any function.** A repository-wide search finds them declared in
`RULES_ALEXG.config` and carried into `configurationSnapshot`, with no consumer.
`hubTestStandardizations` states: *"Wick strength is recorded but never required (requireWick
defaults false) — the source never mentions wicks."*

Wick data **is** used in one place unrelated to these keys: penetration-episode detection uses
`bar.l < zone.low` / `bar.h > zone.high` (Section 5.4).

---

## SECTION 10 — STOP LOSS

### 10.1 Live calculation (`alexGConstructLivePosition`, 3994–3999)

```javascript
stopATRBuffer = cfg.stopATRBuffer;                       // 0.25
stop = direction==='buy'
     ? setup.zoneLow  - stopATRBuffer * atrAtEntry
     : setup.zoneHigh + stopATRBuffer * atrAtEntry;
```

| Element | Value |
|---|---|
| **Anchor** | `setup.zoneLow` (buy) / `setup.zoneHigh` (sell) — the **frozen zone boundary**, not the reaction price and not the candle extreme |
| **Buffer** | `0.25 × ATR` |
| **ATR** | `alexGComputeATRAtEntry` (3412) = `calcATR(candles.slice(0, qualificationBarIndex+1), 14)` — as of the **qualification bar**, not the fill moment |
| **ATR method** | Simple arithmetic mean of the last 14 True Ranges (`calcATR`, 5680); TR = `max(h-l, |h-prevC|, |l-prevC|)`. Not Wilder smoothing. |

### 10.2 Validity check

```javascript
if(!isFinite(stop) || (direction==='buy' && !(stop < liveFillPrice))
                   || (direction==='sell' && !(stop > liveFillPrice)))
    → BLOCKED — INVALID STOP / INVALID_STOP
```

The stop must be strictly on the correct side of the fill.

### 10.3 Minimum and maximum distance

**Neither is implemented.** There is no minimum stop distance in pips, no maximum, and no cap
relative to ATR or account size. The only constraint is the strict-side test above.

### 10.4 Fixed-pip or dynamic stops

**Not implemented.** The stop is ATR-derived and **frozen at entry**. No code path modifies
`pos.stop` after the position is created.

### 10.5 Replay-path stop

`alexGConstructTrade` (3470) uses the same formula against the **setup's zone** with entry at the
qualification close rather than a live fill.

---

## SECTION 11 — TARGETS

### 11.1 Live calculation (4001–4006)

```javascript
minRR = cfg.minRR;                                       // 2.0
riskDistance = Math.abs(liveFillPrice - stop);
target = direction==='buy'
       ? liveFillPrice + minRR * riskDistance
       : liveFillPrice - minRR * riskDistance;
```

**The target is a fixed 2.0 × risk multiple of the live fill.** Despite the parameter name `minRR`,
it is used as an exact multiplier, not a floor — no code path selects any other ratio.

### 11.2 Second recorded target

```javascript
riskDistanceFromQualClose   = |qualificationClose - stop|
qualificationPlannedTarget  = qualificationClose ± minRR * riskDistanceFromQualClose
```

`qualificationPlannedTarget` is **recorded only**. The live target (`liveFillAdjustedTarget`, equal to
`target`) is the one monitored for exit.

### 11.3 Not implemented

| Feature | Status |
|---|---|
| 1R target | Not implemented |
| Structure-based target | Not implemented |
| Dynamic / moving target | Not implemented — `pos.target` is never modified after entry |
| Multiple targets (TP1/TP2) | Not implemented |
| Scaling out | Not implemented |
| Partial exits | Not implemented — a position closes in full or not at all |

---

## SECTION 12 — RISK MANAGEMENT

### 12.1 Risk percent and sizing (4008–4018)

```javascript
riskPercent      = cfg.riskPercent;                      // 1.0
riskAmount       = balanceBefore * (riskPercent / 100);
riskDistancePips = riskDistance / pip;
positionSize     = riskDistancePips > 0
                 ? riskAmount / (riskDistancePips * pipValue)
                 : null;
```

`balanceBefore` is `alexGAccount.balance` at the moment of construction.

**`pipSize(pair)` (11627):** `pair.includes('JPY') ? 0.01 : 0.0001`.

**`pipValuePerLot(pair)` (11628):**
- quote currency `USD` → `pip * 100000`
- otherwise → `(pip * 100000) / rate`, where `rate` comes from `pairData['USD_'+quote].price` or
  `pairData[pair].price`
- **if no rate is available → returns `null`**, and the trade is blocked. The comment states this
  prevents *"risk-sizing on a fabricated number."*

### 12.2 Concurrency limits

| Limit | Implemented | Value |
|---|---|---|
| One open trade per **pair + timeframe** | **Yes** | line 3972 |
| Maximum concurrent trades overall | **No** | — |
| Maximum trades per day | **No** | `alexGAutoTrading.tradedToday` exists and is described in the code as *"only a secondary, non-controlling guard"* |
| Maximum trades per pair across timeframes | **No** | Four timeframes may each hold a position on the same pair simultaneously |

### 12.3 Loss and drawdown controls

| Control | Implemented |
|---|---|
| Maximum daily loss | **No** |
| Maximum drawdown halt | **No** |
| Equity floor / minimum balance | **No** |
| Trade suspension after N losses | **No** |
| Automatic disable on loss | **No** |

Drawdown is **displayed** (Section 16) but never acted upon. The only way trading stops is the manual
`toggleAlexGLiveTrading()` control or a failed ledger commit.

### 12.4 Ledger integrity guard

`commitAlexGLedger()` performs a version-guarded write. On rejection, `alexGCloseLivePosition` restores
both `alexGAccount` and `alexGJournalEntries` from pre-mutation snapshots and returns
`{error, blocked:true, integrityCompromised}` — the close is treated as not having happened.

---

## SECTION 13 — TRADE MANAGEMENT

**No post-entry trade management of any kind is implemented.**

| Feature | Implemented? | Evidence |
|---|---|---|
| Move to break-even | **No** | No code writes `pos.stop` after creation |
| Trailing stop | **No** | Same |
| Scale out / partial close | **No** | `alexGCloseLivePosition` closes the entire position |
| Scale in / add to position | **No** | One position per pair+timeframe |
| Manual intervention | **No** | No per-trade manual close control exists for ALEX positions |
| Automatic close on time | **No** | No maximum-duration or bar-count exit |
| Session close / end-of-day close | **No** | No time-based exit |
| News handling | **No** | No news source is consulted anywhere |

**A position closes only when the stop or the target is reached**, or when the account is reset via
`resetAlexGLiveAccount()`.

MAE/MFE are tracked continuously but are **record-only** — `alexGUpdatePositionExcursionAndCheckExit`
(4307) updates `maePips`, `mfePips`, `maeR`, `mfeR` and returns only `{hitStop, hitTarget, exitVal}`.
Excursion values never trigger an action.

---

## SECTION 14 — TRADE FILTERS

Complete list of everything that can prevent an ALEX trade:

| # | Filter | Threshold | Location |
|---|---|---|---|
| 1 | Pair not in `SCAN_PAIRS` | 12-pair list | 2003 |
| 2 | No new H1 boundary since last evaluation | — | 4537 |
| 3 | Insufficient H1 data | `< 60` candles | ~4201 |
| 4 | Touch index too low | `touchIndex < 3` | 3291 |
| 5 | Zone touches too few (`A` only) | `< 4` | 3168 |
| 6 | Zone broken (`A` only) | `status !== 'validated'` | 3166 |
| 7 | Zone not broken (`B` only) | `status !== 'broken'` | 3149 |
| 8 | Retest too late (`B` only) | `> 50` bars since break | 3153 |
| 9 | Retest on wrong side (`B` only) | `swingType`/`fromSide` mismatch | 3156 |
| 10 | Break cycle already used (`B` only) | one setup per `breakCycleId` | 3159 |
| 11 | **Choppy zone** (`A` only) | `>= 3` qualifying penetrations / 50 bars | 3137, 3169 |
| 12 | Signal already decided | permanent | 4237 |
| 13 | **Before activation** | `qualificationTimestamp < activatedAt` | 4165 |
| 14 | **Stale signal** | `> {H1:60, H4:240, D:1440, W:10080}` minutes | 4177 |
| 15 | Duplicate signal / trade | four-store check | 3959 |
| 16 | Unresolvable direction | role `inside` / unknown break direction | 3396 |
| 17 | **Existing position on same pair+timeframe** | — | 3972 |
| 18 | ATR unavailable or `<= 0` | — | 3978 |
| 19 | Bid/ask unavailable | — | 3983 |
| 20 | **Entry moved too far** | `> 5` pips from `qualificationClose` | 3991 |
| 21 | Invalid stop side | strict inequality | 3996 |
| 22 | Pip value unavailable | `pipValuePerLot` returns `null` | 4009 |
| 23 | Position size non-finite or `<= 0` | — | 4016 |
| 24 | Application lock | `mogoLockBlocked()` | toggle path |

**Not implemented as filters:** spread, volatility band, trend direction, session, day of week, news,
economic calendar, correlation, exposure, distance-to-level, maximum touches, zone age.

---

## SECTION 15 — PAPER TRADING ENGINE

### 15.1 Trade lifecycle

```
setup qualifies → gates (Section 8.5) → alexGConstructLivePosition
   → position object built (status 'open')
   → alexGStampTradeProvenance(position)
   → pushed to alexGAccount.openPositions
   → journal OPEN record created (buildAlexJournalOpenRecord → upsertJournalOpenRecord)
   → commitAlexGLedger()
        ├─ ok      → saveAlexG(), render, alert, toast, notification
        └─ rejected→ full rollback of account + journal
   ...
   → monitored every 60s by alexGCheckLivePositions
   → alexGCloseLivePosition(...) → status 'closed'
```

### 15.2 Order creation

No order is transmitted. A position is a plain object appended to `alexGAccount.openPositions`.
`tradeId = 'AGT|' + setupId`; `signalId` from `alexGLiveSignalId(setup)`.

Provenance stamping (`alexGStampTradeProvenance`, 2461) adds version identity **after** the protected
constructor returns. The header comment states these fields are *"observability metadata only — no
value below is ever read by entry, stop, target, sizing or exit logic."*

### 15.3 Trade monitoring — two independent mechanisms

`alexGCheckLivePositions` (4409) runs **before** any new-setup scan on every tick:

**(a) Historical candle reconstruction** — `alexGReconstructExitFromCandles` (4338) walks completed M1
executable-price candles from `pos.lastExitCheckTimestamp` to now:
- BUY uses **only the bid side**; SELL uses **only the ask side** — never mid.
- MAE/MFE updated from each candle's high/low, never shrinking from recorded extremes.
- Stops at the **first** candle crossing stop or target; later candles are not processed.
- A candle crossing **both** is resolved **conservatively as a Loss** and flagged `ambiguous: true`.
- If the fetch fails (`candles === null`), `lastExitCheckTimestamp` is **not** advanced and no
  snapshot fallback is used for that interval.

**(b) Current snapshot** — `alexGUpdatePositionExcursionAndCheckExit` (4307), only if (a) did not close:
- `hitStop`: buy `ba.bid <= stop`; sell `ba.ask >= stop`
- `hitTarget`: buy `ba.bid >= target`; sell `ba.ask <= target`
- If `fetchBidAsk` returns falsy, the cycle is skipped (`continue`).

Stop is checked **before** target in the snapshot path.

### 15.4 Trade closure (`alexGCloseLivePosition`, 4455)

```javascript
movePips = (exitPrice - entry)/pip * (direction==='buy' ? 1 : -1)
pnl      = movePips * pipValue * positionSize
resultR  = result==='Win' ? plannedRR : -1
balance  = parseFloat((balance + pnl).toFixed(2))
```

**`resultR` is a fixed ±R, not recomputed from the actual exit price** — the comment states *"fixed R
per the frozen methodology, not recomputed from actual slippage."* A win always records `+2.0`R and a
loss always `-1`R regardless of the realised exit.

Idempotence: if the `tradeId` is not in `openPositions`, the function returns immediately.

### 15.5 Outcome recording

The closed position is `unshift`ed onto `alexGAccount.closedPositions` with `exitPrice`, `closedAt`,
`result`, `resultR`, `pnl`, `balanceAfter`, exit bid/ask/spread, `exitTriggerLevel`,
`exitDetectionSource` (`live_snapshot` or `historical_candle`), `exitDetectedAt`, candle window, and
`ambiguous` / `ambiguousMode`.

### 15.6 Journal updates

`journalNoteCloseAlex(pos, closed)` → `applyJournalCloseUpdate` **updates the existing OPEN record in
place by `tradeId`** (never appends a second row). If no open record exists, one is built from the
closing position's own fields so a close never produces no record.

### 15.7 Dashboard and statistics updates

`renderAlexGLivePanel()` is called after every close and after every monitoring cycle. All statistics
are recomputed from `alexGAccount` on each render — none is stored.

`alexGAutoTrading.log` receives a `CLOSED` entry and is truncated to the most recent **200** entries.

---

## SECTION 16 — DASHBOARD

Nine metrics rendered by `renderAlexGLivePanel` (4714–4744), each recomputed on render:

| # | Label | Calculation |
|---|---|---|
| 1 | **Alex balance** | `alexGAccount.balance.toFixed(2)`; coloured by `pnlTotal >= 0` |
| 2 | **Open positions** | `alexGAccount.openPositions.length` |
| 3 | **Closed positions** | `alexGAccount.closedPositions.length` |
| 4 | **Wins** | `decided.filter(p=>p.result==='Win').length` |
| 5 | **Losses** | `decided.length - wins` |
| 6 | **Win rate** | `decided.length ? Math.round(wins/decided.length*100)+'%' : '—'` |
| 7 | **Net R** | `decided.reduce((s,p)=>s+(p.resultR||0),0)`, 2dp, signed |
| 8 | **P&L** | **`alexGAccount.balance - 10000`** — a hardcoded literal, not a stored starting balance |
| 9 | **Current drawdown** | See below |

Where `decided = closedPositions.filter(p => p.result==='Win' || p.result==='Loss')`.

**Drawdown (labelled "Current drawdown"):**
```javascript
let equity=0, peak=0, maxDD=0;
decided.forEach(p=>{ equity+=(p.resultR||0); peak=Math.max(peak,equity); maxDD=Math.max(maxDD,peak-equity); });
```
This is the **maximum** peak-to-trough R drawdown over the whole closed history, displayed under the
label "Current drawdown". It is expressed in R, not currency, and iterates `closedPositions` in stored
order (most recent first, since closes are `unshift`ed).

**Setups table** (`renderAlexGLiveSetupsPanel`): the most recent **50** entries of
`alexGLiveSetupStatuses`, with columns Pair, TF, Setup, Dir, Qualified, Zone, Touch#, Status.

**Trade Inspector — a second consumer outside the live panel.** The Trade Inspector page computes a
"Strategy Compliance" display that reads two stored ALEX fields, `zoneTouchNumber` and
`zoneQualityAtQualification`, plus `plannedRR >= 2` and session/day checks derived from `openedAt` via
`getSession()`. These are **display-only Pass/Fail indicators computed after the fact**; they gate
nothing. Anything not computable from stored data renders as "Not Evaluated."

---

## SECTION 17 — JOURNAL

### 17.1 Stored fields (`buildAlexJournalOpenRecord`, 2245)

**Identity:** `journalEntryId` (`'ALEXJ|'+tradeId`), `tradeId`, `strategy` (`'alex_g_sr_v1'`),
`strategyId`, `strategyLabel` (`'ALEX'`), `ruleVersion`

**Source:** `tradeSource` (`'TEST'` if `isDeveloperTrade`, else `'AUTO'`), `isDeveloperTrade`

**Instrument / setup:** `pair`, `timeframe`, `setupType`, `setupLabel`

**Trade:** `direction`, `entry`, `stop`, `target`, `plannedRR`, `riskPercent`, `riskAmount`,
`positionSize`

**Lifecycle:** `openedAt`, `closedAt`, `exitPrice`, `result`, `resultR`, `pnl`, `status`
(`OPEN`/`CLOSED`), `exitDetectionSource`, `durationMs`

**Excursion:** `maePips`, `mfePips`, `maeR`, `mfeR`

**Zone:** `zoneId`, `zoneLow`, `zoneHigh`, `zoneCenter`, `zoneTouchNumber`, `zoneStrength`,
`zoneQualityAtQualification`, `zoneRoleAtQualification`, `reactionId`, `breakCycleId`,
`brokenDirection`, `barsSinceBreak`

**Execution context:** `atrAtEntry`, `qualificationTimestamp`, `qualificationClose`, `liveFillPrice`,
`entryDelayPips`

**Psychological levels:** `nearestPsych500Level`, `distanceToPsych500Pips`, `nearestPsych100Level`,
`distanceToPsych100Pips`

**Context metadata:** `trendContext`, `session`, `dayOfWeek`, `hourOfDay`

**Configuration:** `configurationSnapshot`

**Explanations** (from `computeAlexExplanations`): `whyQualified`, `howEntryWasCalculated`,
`howStopWasCalculated`, `howTargetWasCalculated`, `whyClosed`

### 17.2 Not stored

| Field | Status |
|---|---|
| Screenshots / images | **Not implemented** — no image capture or storage exists for ALEX journal records |
| User tags | **Not implemented** |
| Free-text user notes | **Not implemented** |
| Manual grade / rating | **Not implemented** |

The only "reason" fields are the five machine-generated explanation strings above.

### 17.3 Write rules

- `upsertJournalOpenRecord` refuses to create a second row for an existing `tradeId`.
- `applyJournalCloseUpdate` updates in place and *"never replaces or recalculates the frozen
  entry-time fields."*
- Records are `unshift`ed — newest first.

---

## SECTION 18 — CONFIGURATION

All parameters live in `RULES_ALEXG.config` (`index.html:2374`). **There is no configuration file** —
the object is a `const` in `index.html`. No UI control writes to it.

| Parameter | Default | Range | Read by | Dependencies |
|---|---|---|---|---|
| `zoneTimeframes` | `['H1','H4','D','W']` | — | **NOTHING — declared but never read** | — |
| `htfPriority` | `{W:4,D:3,H4:2,H1:1}` | — | `alexGSetupSortComparator` | Ordering only |
| `zoneClusterATRMultiplier` | `0.5` | `experimentalParams.sensitivityRange: [0.25,0.5,0.75,1.0]` | `alexGAcceptReaction` | `atrPeriod` |
| `atrPeriod` | `14` | Unspecified | `calcATR` calls | — |
| `rejectionConfirmWithinBars` | `1` | Unspecified | `alexGProcessTimeframeCandle` | — |
| `rejectionDisplacementATRMultiplier` | `0.25` | Unspecified | `alexGProcessTimeframeCandle` | `atrPeriod` |
| `requireWick` | `false` | — | **NOTHING — never read** | — |
| `minWickRatio` | `0.0` | — | **NOTHING — never read** | — |
| `breakConfirmationCloses` | `1` | Unspecified | `alexGProcessTimeframeCandle` | — |
| `maxPenetrationsBeforeChoppyFlag` | `3` | Unspecified | `alexGCorrectedQuality`, Phase 2 loop | `choppyLookbackBars` |
| `choppyLookbackBars` | `50` | Unspecified | Same | — |
| `maxZoneAgeBars` | `null` | — | **NOTHING — never read (ageing OFF)** | — |
| `maxBarsBetweenBreakAndRetest` | `50` | Unspecified | `alexGEvaluateBreakRetest` | — |
| `psychLevelIntervalPips500` | `500` | — | `alexGComputePsychLevels` | `pipSize` |
| `psychLevelIntervalPips100` | `100` | — | `alexGComputePsychLevels` | `pipSize` |
| `trendSwingLookback` | `3` | Unspecified | Swing detection **and** `sameInteractionMaxBarGap` | — |
| `trendSwingScanBars` | `200` | Unspecified | `alexGComputeTrendContext` | `trendSwingLookback` |
| `stopATRBuffer` | `0.25` | Unspecified | `alexGConstructLivePosition`, `alexGConstructTrade` | `atrPeriod` |
| `riskPercent` | `1.0` | Unspecified | `alexGConstructLivePosition` | Account balance |
| `minRR` | `2.0` | Unspecified | `alexGConstructLivePosition` | `stopATRBuffer` |
| `maxLiveEntryDelayPips` | `5` | Unspecified | `alexGConstructLivePosition` | `pipSize` |
| `maxLiveSignalAgeMinutes` | `{H1:60,H4:240,D:1440,W:10080}` | — | `alexGIsSetupSignalStale` | Timeframe |

**Other constants outside `config`:**

| Constant | Value | Location |
|---|---|---|
| `SCAN_PAIRS` | 12 pairs | 2003 |
| Starting balance | `10000` | 2100, and hardcoded again at 4732 for P&L |
| Poll interval | `60000` ms | 4514 |
| Live dataset window | `90` days | ~4200 |
| `ALEX_PROVENANCE_SCHEMA_VERSION` | `'mogo.strategy-provenance.v1'` | 2422 |
| `ALEX_IMPLEMENTATION_VERSION` | `'alex_g_sr_v1.impl.1'` | 2423 |
| Auto-trading log cap | 200 | 4494 |
| Setups table display cap | 50 | 4752 |

**Storage keys:** `fxhub_alexg_account`, `fxhub_alexg_account_version`, `fxhub_alexg_auto`,
`fxhub_alexg_journal`, `fxhub_alexg_setups`, `fxhub_alexg_zones`.

**Range column note:** with the single exception of `zoneClusterATRMultiplier`, which carries an
explicit `sensitivityRange`, **no parameter declares a permitted range anywhere in the repository.**
"Unspecified" means no range is stated; it does not mean unbounded.

---

## SECTION 19 — RULE REGISTRY

Rule IDs `ALEX_SR_*` are the specification IDs used by
`docs/strategy-fidelity/manifests/alex_g_sr_v1.specification.json`. `ALEX_X_*` are extra
implementation rules from the implementation manifest. `ALEX_ACTIVATION_CUTOFF` and
`ALEX_SIGNAL_STALENESS` are the two IDs emitted at runtime in decision events.

| Rule ID | Rule Name | Description | Impl. | Config. | Default | Dependencies | Source File | Function | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| `ALEX_SR_001` | S/R definition | Role from price position vs zone | Yes | No | — | — | index.html:2735 | `alexGZoneRole` | High |
| `ALEX_SR_002` | S/R jointly the AOI | One zone object carries both roles via `lastKnownRole` | Yes | No | — | — | index.html:3249 | `alexGCreateSetupRecord` | High |
| `ALEX_SR_003` | Never trade against role | `inside` → `INVALID_ZONE_ROLE_INSIDE` | Yes | No | — | — | index.html:3396 | `alexGDetermineTradeDirection` | High |
| `ALEX_SR_004` | Bidirectional touch tally | One shared `touches[]` | Yes | No | — | — | index.html:2752, 2792 | `alexGDetermineFromSide`, `alexGAcceptReaction` | High |
| `ALEX_SR_005` | 3 validate, 4th tradeable | `touchIndex>=3` and `touches.length>=4` | Yes | No | — | — | index.html:3165 | `alexGEvaluateRepeatedReaction` | High |
| `ALEX_SR_006` | Strength tiers | `<3 weak / ===3 valid / >=4 strong` | Yes | No | — | — | index.html:2792 | `alexGAcceptReaction` | High |
| `ALEX_SR_007` | More touches better | Tier **saturates** at `strong`; raw count retained, unused | **Partial** | No | — | — | index.html:2792 | `alexGAcceptReaction` | High |
| `ALEX_SR_008` | Zones must be tight | No formula in source; `zoneClusterATRMultiplier` substituted | **Substituted** | Yes | `0.5` | `atrPeriod` | index.html:2763 | `alexGAssignCluster` | Medium |
| `ALEX_SR_009` | Four zone timeframes | H1/H4/D/W processed; **config key unread** | Yes | **No (dead key)** | `['H1','H4','D','W']` | — | index.html:2996 | `alexGRunZoneEngine` | High |
| `ALEX_SR_010` | HTF more respected | Ordering only; never gates/weights/sizes | **Partial** | Yes | `{W:4,D:3,H4:2,H1:1}` | — | index.html:3589 | `alexGSetupSortComparator` | High |
| `ALEX_SR_011` | Break and retest | Full ordered sequence enforced | Yes | Yes | `maxBars…=50` | Break state | index.html:3147 | `alexGEvaluateBreakRetest` | High |
| `ALEX_SR_012` | Psych levels confluence | Raw distances recorded; **never used as confluence** | **Record-only** | Yes | `500`/`100` | `pipSize` | index.html:3184 | `alexGComputePsychLevels` | High |
| `ALEX_SR_013` | Trend direction | Computed; **never gates** | **Record-only** | Yes | `lookback 3`, `scan 200` | — | index.html:3199 | `alexGComputeTrendContext` | High |
| `ALEX_X_001` | Stop/TP/risk/R:R mechanism | Entire risk model | Yes | Yes | `0.25`/`1.0`/`2.0` | ATR, balance, pip value | index.html:3956 | `alexGConstructLivePosition` | High |
| `ALEX_X_002` | Live entry-delay gate | Rejects fill > N pips from qualification close | Yes | Yes | `5` | `pipSize` | index.html:3991 | `alexGConstructLivePosition` | High |
| `ALEX_X_003` | Signal staleness | One bar-period per timeframe | Yes | Yes | `{60,240,1440,10080}` | Timeframe | index.html:4177 | `alexGIsSetupSignalStale` | High |
| `ALEX_X_004` | Activation cutoff | `qualificationTimestamp >= activatedAt` | Yes | No | `null` until toggled ON | Toggle | index.html:4165 | `alexGIsSetupEligibleForLiveTrading` | High |
| `ALEX_X_005` | Choppy-zone filter | `>=3` qualifying penetrations / 50 bars | Yes | Yes | `3` / `50` | Penetration events | index.html:3137 | `alexGCorrectedQuality` | High |
| `ALEX_X_006` | Rejection confirmation | 1-bar window, `>=0.25 ATR` displacement | Yes | Yes | `1` / `0.25` | `atrPeriod` | index.html:2877 | `alexGProcessTimeframeCandle` | High |
| `ALEX_X_007` | Zero session filtering | Metadata computed, never gates | **Deliberately absent** | No | — | — | index.html:3225 | `alexGComputeSessionMetadata` | High |
| `ALEX_X_008` | `ALEX_SCORE_V2` | Second Alex-named strategy, shadow only | Yes (disabled) | — | `enabled:false` | — | index.html:14952 | `ALEX_V2_META` | High |
| — | One trade per pair+TF | Overlap rule | Yes | No | — | Open positions | index.html:3972 | `alexGConstructLivePosition` | High |
| — | Duplicate signal guard | Four-store check | Yes | No | — | — | index.html:3959 | `alexGConstructLivePosition` | High |
| — | Permanent status dedup | A decided `signalId` is never re-evaluated | Yes | No | — | — | index.html:4237 | `alexGEvaluatePairForLiveSetups` | High |
| — | Same-interaction dedup | Same `swingType` within 3 bars | Yes | Yes (via `trendSwingLookback`) | `3` | — | index.html:2783 | `alexGIsSameInteraction` | High |
| — | Break confirmation closes | `>=1` closing beyond | Yes | Yes | `1` | Prior role | index.html:2877 | `alexGProcessTimeframeCandle` | High |
| — | Prior-role inference | Strictly backward search | Yes | No | — | — | index.html:2867 | `alexGInferPriorZoneRole` | High |
| — | Zone ageing | `maxZoneAgeBars` never read | **No** | Yes (dead) | `null` | — | index.html:2374 | — | High |
| — | Wick requirement | `requireWick`/`minWickRatio` never read | **No** | Yes (dead) | `false` / `0.0` | — | index.html:2374 | — | High |
| — | Ambiguous-candle resolution | Both levels in one candle → Loss | Yes | No | conservative | — | index.html:4338 | `alexGReconstructExitFromCandles` | High |
| — | Fixed R on close | `+plannedRR` / `-1` | Yes | No | — | — | index.html:4455 | `alexGCloseLivePosition` | High |

---

## SECTION 20 — KNOWN LIMITATIONS

Observable from the implementation only.

1. **`config.zoneTimeframes` is dead configuration.** Declared with four values, never read; all three
   loops use a hardcoded `['H1','H4','D','W']` literal. Editing the config key has no effect.

2. **`config.requireWick` and `config.minWickRatio` are dead configuration.** Declared, carried into
   every `configurationSnapshot`, read by nothing.

3. **`config.maxZoneAgeBars` is dead configuration.** `zone.ageBars` is maintained every candle but no
   code reads it.

4. **`zoneStrength` saturates at `strong`.** A 4-touch and a 40-touch zone are indistinguishable to
   every consumer.

5. **Two independent choppy calculations coexist, and one is entirely unread.** `zone.quality`
   (Phase 2 loop, line 2986) counts every wick-only penetration; `alexGCorrectedQuality` counts only
   `countsTowardChoppy===true` events. **`zone.quality` is initialised at zone creation, rewritten on
   every candle, and never read by any code path** — it appears elsewhere only in comments. It is
   nonetheless persisted inside `fxhub_alexg_zones`. Only `alexGCorrectedQuality`'s value gates
   eligibility and is stored on records as `zoneQualityAtQualification`.

6. **`resultR` is fixed, not realised.** A win records `+plannedRR` (2.0) and a loss `-1` regardless of
   the actual exit price. Reported Net R therefore does not reflect slippage or ambiguous-candle exits.

7. **Dashboard P&L uses a hardcoded `10000`.** `pnlTotal = alexGAccount.balance - 10000`. If the
   account balance were ever restored from a state with a different starting balance, this figure
   would be wrong.

8. **"Current drawdown" displays maximum historical drawdown.** The computation is a running
   peak-to-trough maximum over all decided trades, in R.

9. **The drawdown loop iterates `closedPositions` in stored order**, which is newest-first
   (`unshift`), not chronological.

10. **`alexGSetupSortComparator` is not used in the live path.** Live setups are iterated in array
    order, so `htfPriority` does not influence which setup is attempted first when several qualify in
    one evaluation.

11. **Four simultaneous positions per pair are possible.** The overlap rule is per pair **and**
    timeframe.

12. **No maximum concurrent trades, daily loss limit, or drawdown halt exists.** With 12 pairs × 4
    timeframes, up to 48 positions could be open simultaneously.

13. **`alexGAutoTrading.tradedToday` is non-controlling.** It is maintained but the code describes it
    as *"only a secondary, non-controlling guard."*

14. **Per-condition rejection reasons are not recoverable for the two core setup evaluators.**
    `alexGEvaluateBreakRetest` and `alexGEvaluateRepeatedReaction` return `{qualifies:false}` without
    indicating which condition failed.

15. **Decision events are memory-only.** No storage key persists them, so historical decision traces
    cannot be reconstructed after a reload.

16. **Every live evaluation performs a full reset and rebuild** of zone and setup state from 90 days
    of freshly fetched candles, for each pair, on every new H1 boundary.

17. **A failed executable-candle fetch leaves the exit gap unprocessed.** `lastExitCheckTimestamp` is
    not advanced and no snapshot fallback is applied for that interval; the gap is retried next poll.

18. **A same-candle stop-and-target crossing is always resolved as a Loss** in the historical
    reconstruction path, flagged `ambiguous: true`.

19. **`alexGZoneRole` uses exclusive boundaries; the `hostZone` lookup uses inclusive boundaries.** A
    price exactly at `zone.low` or `zone.high` is `'inside'` for role purposes but *is* accepted as a
    touch of that zone.

20. **Positions opened before the provenance release lack version fields** and are classified
    `LEGACY_UNVERSIONED`. No migration back-fills them.

21. **Stop, target and position size are frozen at entry** and are never modified for the life of the
    trade.

22. **The `minRR` parameter name does not match its use.** It is applied as an exact multiplier, not a
    minimum.

23. **Two strategies claim the ALEX name.** `alex_g_sr_v1` paper-trades; `ALEX_SCORE_V2` is shadow-only
    with `alexV2AutoTrading.enabled === false`.

24. **Unable to determine from implementation:** the intended permitted range for every configuration
    parameter except `zoneClusterATRMultiplier`. No range, bound, or validation is declared anywhere in
    the repository.

25. **Unable to determine from implementation:** the behaviour of `alexGEvaluateBreakRetest` when a
    zone breaks a second time after a completed retest cycle. The `breakCycleId` incorporates
    `brokenAt`, but no code path re-sets `zone.status` from `'broken'` back to `'validated'`, so
    whether a second break cycle can occur is not determinable from the code alone.

---

*End of specification. This document records the implementation at commit `a332d04`, `APP_VERSION`
12.6.0. No code was modified in its production.*
