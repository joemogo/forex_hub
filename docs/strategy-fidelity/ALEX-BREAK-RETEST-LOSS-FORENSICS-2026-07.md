# ALEX Break & Retest — Loss Forensics, July 2026

**Milestone:** MOGO-002.8B follow-on · **Date:** 2026-07-30 · **HEAD:** `592ca97` · **Engine:** `APP_VERSION` 12.7.1
**Subjects:** two losing `B_breakRetest` paper trades — EUR/USD 14 Jul 2026, GBP/USD 28–29 Jul 2026
**Read-only forensic analysis. No production code modified. No rule changed. No commit or tag created.**

---

## 1. Executive finding

**Both trades are `PARTIALLY RECONSTRUCTABLE`. Neither can be reconstructed to the standard the
forensic questions require, and the reason is structural: the repository holds no trade data at all.**

What **is** verifiable from the supplied journal values is meaningful and internally consistent:

- **Both trades' stop/target geometry matches the implemented formula exactly** — implied R:R of 2.0063
  and 2.0000 against `config.minRR = 2.0`.
- **Both realized-R values are correct**, and — unusually — the v1.0 fixed-R defect did **not** distort
  them, because both exits landed exactly on the stop.
- **Both MAE values marginally exceed the stop distance** (+0.1 and +0.2 pips), which is exactly what a
  genuine stop fill looks like.
- **Both trades are SELL**, and that is not coincidence — see §1.1.

The two losses are **materially different in character**: EUR/USD never moved favourably by a single
pip (MFE 0.0), while GBP/USD reached **0.949R** before fully reversing.

**No implementation defect was found in either trade.** Every number checks out against the code.

### 1.1 ⚠️ A sample composed only of SELL trades

`alexGDetermineTradeDirection` maps `B_breakRetest` as:

```js
if(setup.brokenDirection==='downThroughSupport') return{direction:'sell'};
if(setup.brokenDirection==='upThroughResistance') return{direction:'buy'};
```

The repository's own v4.0 release log records, as a verified discovery:

> *"`alexGProcessTimeframeCandle`'s break-check falls back to `role='support'` whenever a zone's role
> is still unset, which makes it **structurally impossible** for the current frozen zone engine to ever
> produce a validated, never-broken resistance-role zone, or a genuine
> `brokenDirection='upThroughResistance'` — **verified empirically**."*

> **⚠️ CORRECTION — 2026-08-03. That quoted defect was SUPERSEDED before this document was written.**
> v4.0.1 (the "Alex G S&R ZONE-ROLE CORRECTION RELEASE") fixed exactly this, replacing the
> `role=zone.lastKnownRole||'support'` default with the deterministic, stateless
> `alexGInferPriorZoneRole(zone,candles,currentBarIndex)`, which searches strictly backward for the
> most recent completed close outside the zone and returns `'support'`/`'resistance'`/`'unknown'`,
> never defaulting — and skips break detection entirely when no prior role can be established rather
> than guessing. **v4.0.1 predates this document's own engine version, 12.7.1**, so the limitation
> quoted above did not hold at the time of these two trades. The paragraphs below are corrected
> accordingly; §§4–5, the loss classifications and the capture recommendations are unaffected.

**Both trades in this particular sample are SELL.** That is an observation about two trades, not a
structural property of the engine: since v4.0.1 the engine has been capable of producing Break &
Retest **BUY** trades, and verified replay RUN-001 (engine 12.9.0) later produced **three** of them
with `brokenDirection: upThroughResistance`, which is the empirical confirmation.

**Consequence for interpretation:** this sample — two SELL trades — describes *short*
break-and-retest behaviour in whatever market conditions July 2026 presented. **It provides no
evidence about the setup's BUY side**, simply because it contains none. Any conclusion drawn from
this sample must carry that caveat.

### 1.2 ⚠️ A sample-count discrepancy that must be reconciled

The MOGO-002.8B directive reported **Break & Retest: 6 trades, 5 wins, 1 loss**. This directive
presents **two** losing B&R trades. Those cannot both be true of the same sample.

Possible explanations — **none verifiable from the repository**: the sample grew between reviews
(the GBP/USD trade closed 29 Jul, the day before this directive); the earlier count was approximate;
or one trade is outside the counted set.

**This is flagged, not resolved.** It matters because the 5/6 win rate was part of the basis for
keeping B&R active while suspending RZR.

> **RESOLVED — 2026-08-03 (MOGO-003 forensic reconciliation).** Both this document's two losing B&R
> trades and the directive's 6 trades / 5W-1L belong to the same **unverified Tier 1 live-paper
> record**, which persists only in browser `localStorage` and cannot be reconstructed. The discrepancy
> therefore cannot be settled from evidence, and neither figure may be compared with verified replay
> results. See `docs/MOGO-003-VERIFIED-REPLAY-RECORD.md` §RUN-001 and the annotation in
> `MOGO-002.8B-ALEX-SETUP-ISOLATION-AUDIT.md` §0.
>
> **§1.1's direction-lock finding was wrong and has been corrected in place.** It claimed ("every
> Break & Retest trade the engine can currently produce is a SELL") that the pre-v4.0.1 zone-role
> defect made BUY setups impossible. **That caveat did not apply even at the time**, because engine
> 12.7.1 — the version these two trades ran on — already contained the v4.0.1 correction. Verified
> replay RUN-001, on engine 12.9.0, produced **3 Break & Retest BUY trades** with
> `brokenDirection: upThroughResistance` (packages `…20260518|1`, `…20260507|1`, `…20260617|2`),
> confirming the capability empirically. This sample being SELL-only is a property of these two
> trades, not of the engine.
>
> **The EUR/USD 14 Jul 2026 trade was independently rediscovered by replay** — same date, timeframe,
> setup type and direction, identical stop (1.14001), entry 1.13862 vs 1.13842 and target 1.13583 vs
> 1.13523. The ~2-pip entry difference is consistent with a live fill under `maxLiveEntryDelayPips: 5`
> versus replay's candle-close entry. Package `PKG|alex_g_sr_v1|20260714|1`.

---

## 2. Evidence sources inspected

| Source | Present? | Finding |
|---|---|---|
| Repository trade/journal records | ❌ **None** | `grep` for `AGT\|` across `docs/`, `scripts/`, `tests/` returns nothing |
| Browser `localStorage` | ⚠️ Not accessible | Trades live in `fxhub_alexg_account` / `fxhub_alexg_journal` |
| Setup records | ⚠️ Not accessible | `fxhub_alexg_setups` — browser only |
| Zone state | ⚠️ Not accessible | `fxhub_alexg_zones` — browser only |
| **Historical candle cache** | ❌ **Does not exist** | No `localStorage.setItem` for any candle key. `fetchCandlesRange` fetches fresh from OANDA every call and **persists nothing** |
| **Decision events** | ❌ **Not persisted** | `decisionEventLog` is memory-only, 500-event cap, cleared on reload |
| Exported JSON/CSV | ❌ None found | No export artefact in the repository |
| Logs / screenshots | ❌ None | |
| Fixtures | ✅ Present | Synthetic only — no real trade data |
| Locally-available-but-git-excluded | ✅ Checked | `docs/trader-intelligence/` holds research evidence only, **no trade records** |

**The supplied journal row is the only evidence available**, exactly as the directive warned it might be.

---

## 3. Reconstruction-readiness decision

| Trade | Classification |
|---|---|
| **EUR/USD 14 Jul 2026** | **PARTIALLY RECONSTRUCTABLE** |
| **GBP/USD 28–29 Jul 2026** | **PARTIALLY RECONSTRUCTABLE** |

**Reconstructable:** trade geometry, R arithmetic, stop/target construction, direction logic, MAE/MFE
consistency, duration, R:R conformance, day-of-week.

**Not reconstructable:** everything requiring market data or engine state — break level, break candle
OHLC, retest candle, penetration depth, zone ID/boundaries, ATR at entry, higher-timeframe context,
the candle sequence through exit, and intrabar ordering.

**No candle sequence has been fabricated anywhere in this document.**

---

## 4. EUR/USD forensic reconstruction

**14 Jul 2026 · H1 · BREAK & RETEST · SELL · entry 1.13842 · stop 1.14001 · target 1.13523 · −1.00R**

| # | Question | Finding | Evidence class |
|---|---|---|---|
| 1 | Durable trade ID | `AGT\|<setupId>` by construction; **actual value not available** | UNKNOWN |
| 2 | Strategy ID / version | `alex_g_sr_v1` — predates v1.1 (released 30 Jul) | STRONGLY SUPPORTED |
| 3 | Rule-set version | `alex_g_sr_v1`, `RULES_ALEXG` | STRONGLY SUPPORTED |
| 4 | Detection mode | Live paper trading; **exit** via historical-candle reconstruction | CONFIRMED |
| 5 | Signal timestamp | Qualification ≤ 03:00; **exact value not available** | UNKNOWN |
| 6 | Entry timestamp | 03:00 (timezone unconfirmed — §4.1) | STRONGLY SUPPORTED |
| 7 | Look-ahead-free? | Engine enforces it structurally (ATR ≤ qualification bar; outcome walk from `entryBarIndex+1`); **not independently verifiable for this trade** | STRONGLY SUPPORTED |
| 8 | Break level / source structure | **Not recorded** — `zoneLow`/`zoneHigh` exist on the record but were not supplied | UNKNOWN |
| 9 | Break candle OHLC | **Not recorded anywhere** | UNKNOWN |
| 10 | Break qualification basis | Implemented rule is **body close beyond the zone**, `breakConfirmationCloses = 1`; per-trade evidence absent | STRONGLY SUPPORTED (rule) / UNKNOWN (instance) |
| 11 | Retest candle sequence | **Not recorded** | UNKNOWN |
| 12 | Retest penetration depth | **Not recorded** | UNKNOWN |
| 13 | Entry-confirmation evidence | **None exists — MOGO implements no candlestick-confirmation gate** | CONFIRMED |
| 14 | Direction resolution | `brokenDirection='downThroughSupport'` → SELL. Forced by §1.1 | CONFIRMED |
| 15 | Entry-price construction | Live ask/bid at poll, within `maxLiveEntryDelayPips = 5` of qualification close | STRONGLY SUPPORTED |
| 16 | Stop construction | `zoneHigh + 0.25 × ATR`. Distance **15.9 pips**. Zone bounds and ATR are **individually unrecoverable** — two unknowns, one equation | CONFIRMED (formula) / UNKNOWN (inputs) |
| 17 | Target construction | `entry − 2.0 × risk` → implied R:R **2.0063** vs `minRR 2.0` | **CONFIRMED** |
| 18 | Spread assumption | Real bid/ask used live; `entrySpreadPips` recorded but not supplied | STRONGLY SUPPORTED |
| 19 | Slippage assumption | None modelled | CONFIRMED |
| 20 | Fill assumption | Exit at exact stop level (`exitTriggerLevel`) | CONFIRMED |
| 21 | HTF trend alignment | `trendContext` recorded on the record; **not supplied**. It never gates a trade | UNKNOWN (value) / CONFIRMED (non-gating) |
| 22 | Session / timezone | If 03:00 is UTC → **Off-hours**. **Timezone unconfirmed** | SUSPECTED |
| 23 | Opposing structure to target | **Not recorded — MOGO captures no opposing-level field** | UNKNOWN |
| 24 | Candle sequence to exit | **Unavailable — no candle cache exists** | UNKNOWN |
| 25 | Intrabar ambiguity | `ambiguous` flag exists; **not supplied**. MFE 0.0 makes a same-candle stop+target contact implausible | STRONGLY SUPPORTED (not ambiguous) |
| 26 | MAE/MFE verification | MAE **16.0** vs risk **15.9** → +0.1 beyond stop, consistent with a genuine fill. MFE **0.0** | **CONFIRMED** |
| 27 | Stop-vs-target ordering ambiguous? | **No** — target was never approached | **CONFIRMED** |
| 28 | Journal vs stored values | Internally consistent: R:R, realized R and MAE all reconcile | **CONFIRMED** |
| 29 | Met the implemented B&R rule? | Cannot be re-verified without zone state; the engine cannot create the setup otherwise | STRONGLY SUPPORTED |
| 30 | Faithful to the Alex-derived spec? | **Partially.** Break-and-retest structure is educator-supported (`AXR-004`). But the educator requires a **bullish/bearish engulfing confirmation** (`AXR-011`) which **MOGO does not implement**, and the stop anchor differs (zone boundary vs rejection formation, `AXR-020`) | **CONFIRMED divergence** |

### 4.1 Timezone caveat

`openedAt` is stored as an ISO-8601 UTC string, but the journal UI renders with
`toLocaleString('en-GB', …)` — **local time**. Whether "03:00" is UTC or local **cannot be determined
from the supplied row**. This changes the session attribution entirely (03:00 UTC = Off-hours;
03:00 BST = 02:00 UTC, still Off-hours; but a different local offset could place it elsewhere).

### 4.2 Loss classification — EUR/USD

**Primary: `IMMEDIATE_THESIS_FAILURE`** — evidence class **CONFIRMED**.
MFE of exactly **0.0 pips** means the executable price never moved one pip in favour after entry. The
short thesis failed instantly.

**Secondary, all `SUSPECTED`** (each would need the candle sequence to confirm):
`FALSE_BREAK` · `WEAK_RETEST` · `LATE_ENTRY` · `STRUCTURE_RECLAIM`.

**`NO_CONFIRMATION` — CONFIRMED as a fact about the engine, not about this trade:** MOGO has no
confirmation gate, so no B&R trade can ever have one. This is a systemic property.

**Explicitly NOT assigned:** `IMPLEMENTATION_DEFECT` (every number reconciles), `DATA_INTEGRITY_DEFECT`
(no inconsistency found), `NEAR_ONE_R_REVERSAL` (contradicted by MFE 0.0).

---

## 5. GBP/USD forensic reconstruction

**28–29 Jul 2026 · H1 · BREAK & RETEST · SELL · entry 1.32920 · stop 1.33018 · target 1.32724 · −1.00R**

Questions 1–15 and 18–24 resolve **identically to §4** (same engine, same version, same absent
records). Only the differing items are restated:

| # | Question | Finding | Evidence class |
|---|---|---|---|
| 16 | Stop construction | Distance **9.8 pips** — notably **38% tighter** than the EUR/USD stop, implying a materially smaller `zoneHigh + 0.25×ATR` composite | CONFIRMED (formula) / UNKNOWN (inputs) |
| 17 | Target construction | Implied R:R **exactly 2.0000** | **CONFIRMED** |
| 22 | Session | If 21:00 is UTC → **New York**. Timezone unconfirmed | SUSPECTED |
| 25 | Intrabar ambiguity | MFE 9.3 (0.949R) then a full reverse to stop. **Target was never reached**, so no same-candle stop+target contact is possible | **CONFIRMED not ambiguous** |
| 26 | MAE/MFE verification | MAE **10.0** vs risk **9.8** → +0.2 beyond stop. MFE **9.3** = **0.949R** | **CONFIRMED** |
| 27 | Ordering ambiguous? | **No** | **CONFIRMED** |
| 28 | Journal vs stored | Fully consistent | **CONFIRMED** |

### 5.1 Duration and the overnight window

Open 28 Jul **21:00** → close 29 Jul **00:38** — **3h38m**, spanning midnight and, if the timestamps
are UTC, the New York → Sydney handover. **The engine applies no session restriction whatsoever**
(`ALEX_X_007`), so the trade was held across a low-liquidity window by design.

**⚠️ Note on v1.1:** both trades opened on a **Tuesday**, so the new Monday–Wednesday gate would
**not** have blocked either. The gate is irrelevant to both losses.

### 5.2 Loss classification — GBP/USD

**Primary: `NEAR_ONE_R_REVERSAL`** — evidence class **CONFIRMED**.
MFE **9.3 pips against a 9.8-pip risk = 0.949R**. The trade travelled almost a full R in favour, then
reversed the entire distance to stop.

**Secondary: `PARTIAL_FOLLOW_THROUGH_REVERSAL`** — **STRONGLY SUPPORTED**. The break thesis produced
real follow-through and then failed.

**`STOP_PLACEMENT_SENSITIVE`** — **SUSPECTED**. A 9.8-pip stop is tight in absolute terms; whether it
was too tight for GBP/USD volatility that session **cannot be determined without the ATR value**,
which is not recorded on the supplied row.

**`SPREAD_SENSITIVE`** — **SUSPECTED**. On a 9.8-pip risk, a 1–2 pip spread is **10–20% of risk**. The
MFE is computed on the executable side (ask for a sell), so spread is already inside the 9.3 figure —
but its magnitude is unknown.

**Explicitly NOT assigned:** `IMMEDIATE_THESIS_FAILURE` (**contradicted** — MFE 9.3), and both
defect classifications (nothing inconsistent found).

---

## 6. Comparison of the two losses

| | EUR/USD | GBP/USD |
|---|---|---|
| MFE | **0.0 pips (0.000R)** | **9.3 pips (0.949R)** |
| MAE | 16.0 (risk 15.9) | 10.0 (risk 9.8) |
| Risk distance | 15.9 pips | **9.8 pips** |
| Duration | 1h28m | 3h38m |
| Session (if UTC) | Off-hours | New York |
| Character | **Instant failure** | **Near-miss reversal** |
| Classification | `IMMEDIATE_THESIS_FAILURE` | `NEAR_ONE_R_REVERSAL` |

**These are different failure modes and must not be aggregated.** One thesis was wrong from the first
tick; the other was substantially right and then failed. Averaging them into "2 losses" destroys the
only information they carry.

### 6.1 Most likely explanation for each

| Trade | Most likely | Basis |
|---|---|---|
| **EUR/USD** | **Insufficient evidence to distinguish** between *bad setup selection*, *weak break*, and *normal strategy variance* | MFE 0.0 is consistent with all three. Distinguishing them requires the break and retest candles, which do not exist |
| **GBP/USD** | **Normal strategy variance**, with a secondary *trade-management question* | A 0.949R excursion followed by a full reverse is textbook variance for a fixed-stop, fixed-target system. **STRONGLY SUPPORTED** |

**Neither is a wrong-direction error** in the sense of a logic fault — direction was resolved
correctly from `brokenDirection` in both cases. Direction was genuinely available in engine 12.7.1
(see the §1.1 correction: v4.0.1 had already restored BUY-side capability); **this particular sample
simply happens to contain only SELL trades.**

**Neither shows a historical-evaluation defect or data-integrity problem.** Every supplied value
reconciles against the implemented formulas.

### 6.2 ⚠️ What must not be concluded

**No strategy rule change is justified by these two trades**, and the directive is right to forbid it:

- **n = 2.** Under the MOGO Research & Validation Standard §9 this is below Tier 1.
- The two failures have **different mechanisms**, so they do not even constitute two observations of
  one phenomenon.
- The sample contains **only SELL trades** (§1.1), so it is not a representative sample of the setup.
- The GBP/USD 0.949R excursion is *suggestive* of a break-even rule — but break-even is
  `AXR-060`, **zero educator mentions across 9 sources**, and adding it from two trades would be
  optimising on noise and fabricating an educator rule simultaneously.

---

## 7. Confirmed failure reasons

- **EUR/USD:** `IMMEDIATE_THESIS_FAILURE` — MFE 0.0.
- **GBP/USD:** `NEAR_ONE_R_REVERSAL` — MFE 0.949R then full reversal.
- **Both:** stop fills genuine; R arithmetic correct; R:R conformant to `minRR = 2.0`.
- **Both:** no confirmation gate existed, because the engine implements none.

## 8. Suspected failure reasons

`FALSE_BREAK` · `WEAK_BREAK` · `WEAK_RETEST` · `LATE_ENTRY` · `STRUCTURE_RECLAIM` (EUR/USD) ·
`STOP_PLACEMENT_SENSITIVE` · `SPREAD_SENSITIVE` · `OPPOSING_LEVEL_REACTION` (GBP/USD).

**Every one requires the candle sequence to promote or discard. None is asserted as fact.**

## 9. Remaining unknowns

Break level · break candle OHLC · retest candle and depth · zone ID and boundaries · ATR at entry ·
`trendContext` value · session (timezone unconfirmed) · spread at entry · full candle sequence ·
opposing structure between entry and target · the exact `setupId`/`tradeId` · **and the §1.2 sample-count
discrepancy**.

## 10. Historical-evaluation risks

1. **No candle cache exists.** Re-fetching July 2026 candles today would produce *a* sequence, not
   *the* sequence the engine saw. Any reconstruction from a fresh fetch is **unverifiable** and would
   be a fabrication risk.
2. **Exit detection was `historical_candle`** for both — the M1 reconstruction path
   (`alexGReconstructExitFromCandles`), meaning the exits were detected by replaying candles across a
   polling gap, not observed live. That path is conservative and flags ambiguity, but **the M1 candles
   it used were never retained**.
3. **`LOOK_AHEAD_RISK` — not assigned.** The engine's look-ahead controls are genuinely strong. But
   `lookaheadPass` is a **replay-only** field; it is not stored on live trades, so no per-trade proof
   exists either way.

## 11. Data-integrity risks

**No data-integrity defect was found.** Every supplied value reconciles.

Two standing risks, neither implicated here:

- **Realized R happened to be correct.** Under v1.0, `resultR` was a fixed `−1`. It matched the true
  realized R **only because both exits landed exactly on the stop**. Had either exited off-level, the
  journal would have recorded `−1.00R` regardless. This is the defect ALEX v1.1's `alexGRealizedR()`
  fixes — and these two trades are a coincidental clean case, not evidence the defect was harmless.
- **Trade records exist only in browser `localStorage`.** No backup, no export, no version control. A
  cleared browser profile destroys the entire paper-trading history irrecoverably.

## 12. Lessons supported by evidence

1. **MFE is the single highest-value field already captured.** It alone separates the two failure modes
   and required no additional instrumentation. **CONFIRMED.**
2. **The absence of source-candle references is the binding constraint on all forensics.** Every
   unanswerable question traces to it. **CONFIRMED.**
3. **Timestamp timezone must be unambiguous on the record**, not inferred from a display format.
   **CONFIRMED.**
4. **This is a two-trade, SELL-only sample** and cannot support a two-sided conclusion about the
   setup. The engine could produce BUY setups at this version (§1.1 correction); the sample contains
   none. **CONFIRMED.**
5. **Loss classification cannot be derived after the fact** from what is stored today. It must be
   captured, or derivable from captured data, at the time. **CONFIRMED.**

## 13. Fields MOGO must capture going forward

### 13.1 Required for replay trustworthiness

| Field | Why |
|---|---|
| **Source candle references** (timestamp + OHLC or content hash, not array index) | Without it no trade is traceable to its data. **The single most important gap.** |
| **Break candle** (timestamp, OHLC) | The break is the thesis; unverifiable today |
| **Retest candle(s)** + penetration depth | Distinguishes weak from clean retests |
| **Zone ID + locked boundaries at entry** | `zoneLow`/`zoneHigh` are stored but were not surfaced; zone identity must survive |
| **ATR at entry** | Stored as `atrAtEntry` — must be surfaced in any export; without it stop-tightness is unassessable |
| **Signal vs entry timestamp, both explicit UTC** | Resolves §4.1 permanently |
| **Spread at entry and exit** | Stored; must be exported. On a 9.8-pip risk, spread is 10–20% of risk |
| **Historical-sequencing ambiguity flag** | `ambiguous` exists — must be surfaced |
| **Replay-run ID** | MOGO-003 B3 |

### 13.2 Useful for later rule attribution

Confirmation candle (if a gate is ever added) · setup state at entry (full frozen record) ·
higher-timeframe context (`trendContext` is captured but never exported) · session (explicit, from
stored UTC) · original stop vs current stop (identical today — meaningful only if management is ever
added) · nearby opposing structure between entry and target.

### 13.3 Optional future analytics

Loss classification field · exact failure reason · time-to-MFE and time-to-MAE (would have shown
*when* GBP/USD peaked, materially sharpening §5.2) · excursion path rather than extremes only.

## 14. Replay hypotheses

**Testable once replay is trustworthy — stated as hypotheses, not conclusions:**

- **H1:** B&R losses cluster into two distinct modes (MFE ≈ 0 vs MFE ≥ 0.8R) rather than a continuum.
  *Test:* MFE distribution across a Tier 2 sample.
- **H2:** Tighter stops (as a fraction of ATR) correlate with higher loss rate. *Test:* group outcome
  by `riskDistancePips / atrAtEntry`. **Requires ATR to be exported.**
- **H3:** Off-hours and overnight holds show worse outcomes than London/NY. *Test:* group by session.
  **Directly relevant to the unimplemented `AXR-080` session rule.**
- **H4:** The absent confirmation gate (`AXR-011`) would have filtered the MFE ≈ 0 cluster.
  *Test:* retrospective engulfing detection on break/retest candles. **Requires candle retention.**
- **H5 — RETIRED (2026-08-03).** It read: *"Fixing B1 changes the win rate materially, because the
  current sample is SELL-only."* It presumed a defect that v4.0.1 had already fixed before engine
  12.7.1, so there is nothing to fix. The residual question is only about **sample composition**: does
  BUY-side Break & Retest behave differently from SELL-side? *Test:* compare outcomes by direction
  across a sample large enough to contain both — RUN-001 holds 5 SELL and 3 BUY, far too few to
  answer it.

**H4 is the one that could change strategy design, and it is not testable today.**

## 15. Is any immediate strategy change justified?

# ❌ NO

**n = 2, two different mechanisms, a SELL-only sample, and an unreconciled sample-count
discrepancy.** Nothing here meets even Tier 1 under the Research & Validation Standard.

**What *is* justified is data capture** (§13.1) — which changes no rule, no entry, no exit, and no
parameter, and is a prerequisite for MOGO-003 Phase 1 regardless.

## 16. Exact export required to complete this analysis

Current evidence is insufficient. To finish, export from the browser (DevTools console):

```js
copy(JSON.stringify({
  account : JSON.parse(localStorage.getItem('fxhub_alexg_account')),
  journal : JSON.parse(localStorage.getItem('fxhub_alexg_journal')),
  setups  : JSON.parse(localStorage.getItem('fxhub_alexg_setups')),
  zones   : JSON.parse(localStorage.getItem('fxhub_alexg_zones'))
}, null, 2))
```

**That yields** (per trade): `tradeId` · `setupId` · `zoneId` + `zoneLow`/`zoneHigh`/`zoneCenter` ·
`atrAtEntry` · `qualificationTimestamp` and `qualificationClose` · `entryDelayPips` ·
`entryBid`/`entryAsk`/`entrySpreadPips` · `exitBid`/`exitAsk`/`exitSpreadPips` ·
`exitTriggerLevel`/`exitDetectionSource`/`exitCandleStart`/`exitCandleEnd` · `ambiguous` ·
`trendContext` · `session`/`dayOfWeek`/`hourOfDay` · `brokenDirection`/`barsSinceBreak` ·
`zoneTouchNumber`/`zoneStrength` · `configurationSnapshot` · full `openedAt`/`closedAt` in UTC.

**That would raise both trades from `PARTIALLY` to substantially reconstructable** — resolving
questions 1, 5, 8, 16 (inputs), 18, 21, 22, 25 and the §1.2 count discrepancy.

**It would still NOT yield:** the break candle OHLC, the retest candle sequence, or the candle path to
exit. **Those were never stored and cannot be recovered** — re-fetching would produce a different
dataset and any reconstruction from it would be fabrication.

**⚠️ Also export this history for its own sake.** It exists in exactly one browser profile with no
backup and no version control.

---

*Read-only forensic analysis. No production code modified; no strategy rule changed; no filter added;
no historical trade altered; no commit or tag created; nothing pushed.*
