# MOGO-003 — Evidence Platform Architecture

**Milestone:** MOGO-003 — Evidence Platform & Replay Trustworthiness · **Status:** ARCHITECTURE ONLY
**Date:** 2026-07-30 · **Revised:** 2026-07-30 (Engineering Authority rulings C1–C5)
**HEAD:** `592ca97` (`mogo-002-complete`) · **Engine:** `APP_VERSION` 12.7.1
**Nothing implemented. No production code modified. No commit.**

> **Governing principle, adopted permanently:**
> *"If MOGO cannot explain a trade six months later, then MOGO failed to capture enough evidence when
> the trade occurred."*

---

# 0. Superseding decisions — Engineering Authority, 2026-07-30

**This document was written before the Phase 1 specification and is superseded on two points. Where
this document and [`MOGO-003-PHASE-1-SPECIFICATION.md`](MOGO-003-PHASE-1-SPECIFICATION.md) conflict,
the Phase 1 specification governs.**

| Ruling | Supersedes | Governing statement |
|---|---|---|
| **C2 — Persistence tiers** | §4.7, §6.1, §6.4 of this document, which named a **file export** as the durable system of record and did not contemplate IndexedDB | The tier model in §6.1 below, as rewritten |
| **C3 — Phase 1 scope** | The `P1` row of §13, which scoped Phase 1 to *"loud write failure · capped buffers · whole-package JSON export"* | The expanded Phase 1 scope in §13 below, as rewritten |

**Two further rulings constrain implementation but do not change this document's architecture:**

- **C1** — the Evidence Package content hash is **SHA-256** over a deterministically canonicalised
  payload. `alexGStableHash` remains available for internal, non-security change detection and
  **must never be described or used as cryptographic tamper protection.**
- **C4** — the ALEX journal/ledger path is **out of scope for buffer capping and eviction entirely.**
  §8.3's "T1 buffer — capped, flushed" applies only to `fxhub_alexg_setups` and `fxhub_alexg_zones`.

---

# 1. Executive Summary

MOGO already has more evidence infrastructure than MOGO-002 credited. The decision-event bus
(`mogo.decision-event.v1`) is a **versioned, strategy-agnostic, validated, immutable** event schema
with 13 event types, a centralised reason-code registry and an evidence-completeness model. **The
correct architecture extends it rather than replacing it.**

**But the platform cannot be built where the data currently lives, and this is the finding that
determines everything else.**

### 1.1 ⚠️ The binding constraint — `localStorage` cannot host an evidence platform

Four measured facts about the current persistence layer:

| Finding | Evidence |
|---|---|
| **31 `localStorage` keys**, no namespace, one shared browser quota (~5 MB typical) | Enumerated from `index.html` |
| **Write failures are silently swallowed** | `saveAlexGRest()` is `try{ … }catch(e){}` — a bare swallow. `save()` (JVM) is the same shape |
| **Two persisted structures grow without bound** | `alexGSetupState` and `alexGZoneState` have **no cap** — every other capped store uses `.slice(0,200)` / `.slice(0,50)` |
| **No quota detection anywhere** | Zero occurrences of `QuotaExceeded` or any quota check |

Budget model, using the two forensic trades as real cases:

| Scenario | Cost/trade | Trades before 5 MB |
|---|---|---|
| Current capture (position + journal) | ~5.5 KB | **~950** |
| **With exit-path M1 candles** (GBP/USD needed 218 M1 candles = 32.7 KB) | ~38 KB | **~137** |

**And that budget is shared across 31 keys, two live strategies, unbounded zone/setup state, chart
drawings, Academy progress and the AI message log.**

**Conclusion: capturing the evidence MOGO-002 forensics proved necessary would exhaust the browser
quota in roughly 137 trades — and the failure would be silent.** An evidence platform whose storage
can fail without telling anyone is worse than no platform, because it produces confident conclusions
from partial data.

### 1.2 The architectural answer

**`localStorage` becomes a bounded working buffer. It stops being the system of record.**

Evidence is written automatically to a **durable, in-browser Evidence Package store (IndexedDB)**, and
from there to an **exportable disk artifact**. *(Revised per ruling C2 — the original text named the
file export as the sole durable tier; see §0 and §6.1.)* The repository already proves the file-artifact
pattern works: `docs/trader-intelligence/` is a file-backed, hash-chained, schema-validated,
provenance-complete evidence store built by offline Python tooling — **the same shape the tier-(c)
artifact needs, already operating at 43 MB with integrity checks passing.**

### 1.3 Verdict

**The architecture below is sufficient for ALEX, JVM, TJR and future strategies without redesign**,
because it is keyed on `strategyId` + `strategyVersion` and defines no strategy-specific field at the
platform layer. Strategy-specific detail lives in a typed `context` payload, exactly as the existing
decision-event schema already does.

---

# 2. Architectural Goals

| # | Goal | Rationale |
|---|---|---|
| **G1** | **Explain any trade six months later without reconstruction** | The governing principle |
| **G2** | **Never lose evidence silently** | Current `catch(e){}` makes silent loss the default |
| **G3** | **Reproducibility by identity, not by re-derivation** | A run must be citable by ID, not "90 days back from now" |
| **G4** | **One evidence model across all strategies** | ALEX, JVM, TJR must not diverge into three schemas |
| **G5** | **Capture at the moment of decision** | Nothing derivable after the fact is trustworthy |
| **G6** | **Bounded, predictable storage growth** | Two stores are currently unbounded |
| **G7** | **Additive to protected code** | 63 protected functions must stay byte-identical |
| **G8** | **Honest incompleteness** | An evidence gap must be recorded as a gap, never as absence |

**Explicit non-goals:** improving profitability · changing any strategy rule · adding educator
concepts · building analytics · implementing replay.

---

# 3. Evidence Philosophy

## 3.1 Five rules

1. **Evidence is captured, never reconstructed.** If a value can only be re-derived later, it is not
   evidence. MOGO-002 forensics failed precisely here — the break candle was never stored, and
   re-fetching would produce *a* sequence, not *the* sequence.
2. **Absence is recorded explicitly.** A missing value is `null` **plus a reason code**, never an
   empty field. The existing `EVIDENCE_FIELD_PROVENANCE` taxonomy (`OBSERVED` / `DERIVED` /
   `UNAVAILABLE` / `UNSAFE_TO_RECONSTRUCT` / `FUTURE_WORK`) already expresses this and should be used.
3. **Evidence is immutable once written.** Corrections supersede; they never overwrite. The Trader
   Intelligence layer already enforces this (`supersedesAssertionId`).
4. **Every artefact carries its own provenance.** Strategy version, engine version, commit hash,
   config hash — on the record, not inferred from context.
5. **Rejections are evidence.** A candidate that did not trade is as informative as one that did.
   MOGO-002.8B already established this for the suspension gate.

## 3.2 What "explainable" concretely means

A trade is explainable when a reader with **only the evidence package** can answer:
what fired, why it qualified, what the market looked like at that moment, why entry/stop/target were
those numbers, what happened between entry and exit, why it closed, and **what was not known**.

Today, MOGO can answer roughly a third of that — as the July forensics demonstrated.

---

# 4. Evidence Package Specification

Seven objects. **All keyed on `strategyId` + `strategyVersion`; none contains a strategy-specific
field at the platform layer.**

## 4.1 `Candidate`

| | |
|---|---|
| **Purpose** | Something the strategy noticed and evaluated, whether or not it traded |
| **Required fields** | `candidateId` · `runId` (nullable — live) · `strategyId` · `strategyVersion` · `engineVersion` · `commitHash` · `instrument` · `timeframe` · `observedAt` (UTC) · `candidateType` · `marketContextRef` · `sourceCandleRefs[]` · `evidenceCompleteness` |
| **Relationships** | 1 → many `Decision`; 0..1 → `QualifiedSetup` |
| **Persistence** | Durable. Buffered in browser, flushed to package |
| **Versioning** | Schema-versioned; immutable |
| **Duration** | Permanent |
| **Consumers** | Rule attribution · forensics · replay comparison |

**Scope rule (carried from MOGO-003 §7):** a candidate exists only where the strategy's own logic
defines one. **Every candle must not become a candidate.**

## 4.2 `QualifiedSetup`

| | |
|---|---|
| **Purpose** | A candidate that passed qualification; the frozen basis for any trade |
| **Required fields** | `setupId` · `candidateId` · all Candidate identity fields · `qualifiedAt` · `qualificationPriceRef` · **`structureRefs{}`** · `rulesPassed[]` · `rulesFailed[]` · `configSnapshotHash` · `evidenceCompleteness` |
| **`structureRefs{}`** | **The field MOGO-002 forensics most needed.** Strategy-typed: ALEX → `{zoneId, zoneLow, zoneHigh, breakCandleRef, retestCandleRef, penetrationDepth}`; JVM → `{aoiId, biasRefs}`; TJR → `{sessionId, sweepRef}` |
| **Persistence** | Durable, immutable |
| **Consumers** | Forensics · replay · rule attribution |

## 4.3 `Decision`

| | |
|---|---|
| **Purpose** | One evaluation of one rule against one candidate |
| **Required fields** | `decisionId` · `candidateId` · `ruleId` · `ruleVersion` · `result` (PASS/FAIL/NOT_APPLICABLE) · `reasonCode` (registry-validated) · `inputs{}` · `thresholds{}` · `decidedAt` · `parentDecisionId` · `sequenceNumber` |
| **Relationships** | Many → 1 `Candidate`; ordered chain via `parentDecisionId` |
| **Persistence** | Durable — **currently transient, 500-event cap, lost on reload** |
| **Consumers** | Rule attribution *(which rule reduces expectancy?)* · forensics · replay determinism checks |

> **This object already exists in memory** as `mogo.decision-event.v1`. **MOGO-003 should make it
> durable, not redesign it.** `inputs{}`/`thresholds{}` are the one genuine addition — today a
> `RULE_EVALUATED` records the verdict but not always the numbers that produced it.

## 4.4 `MarketContext`

| | |
|---|---|
| **Purpose** | What the market looked like at a decision moment — the object whose absence blocked July's forensics |
| **Required fields** | `contextId` · `capturedAt` · `instrument` · **`candleRefs[]`** (window around the decision) · `atr` + period · `spreadAtCapture` · `sessionUTC` · `dayOfWeekUTC` · `higherTimeframeState{}` · `nearbyStructure[]` |
| **Persistence** | **Durable and content-addressed** — see §6.3 |
| **Duration** | Permanent for traded candidates; **windowed for untraded** (§8.4) |
| **Consumers** | Forensics · replay · ML |

> **As built — Unit C2-M1, v12.13.0 (partial).** The target object above is unchanged; this records
> what actually ships. `objects.marketContexts[]` now carries **one bounded excerpt per captured
> replay trade**: the trade's **own timeframe only**, `EVIDENCE_CONTEXT_PRE_ENTRY_BARS` (50) bars
> before entry through the exit bar, each candle stored **verbatim** with its `barIndex` and an ISO
> timestamp, plus a `window` block (requested vs actual pre-entry bars, from/to bar indices and UTC
> bounds, candle counts, dataset size, truncation state) and the run's `datasetHash`.
> **Unit C2-M2, v12.14.0** then added `higherTimeframeContext`: a **20-bar window of each higher
> timeframe** (H4, D, W for an H1 trade, in ascending rank order), **anchored at the entry candle's
> close** so it contains only bars that had genuinely closed when the trade was taken. A timeframe
> with no dataset, no closed bar at the anchor, or a hole is listed in `omittedTimeframes` **with a
> reason**; a trade on the highest timeframe reports `NOT_APPLICABLE`.
> **Deliberately not yet delivered:** the content-addressed candle store (candles are excerpted per
> package, not deduplicated), context for **untraded** candidates, and
> `atr`/`spreadAtCapture`/`nearbyStructure` as first-class context fields (ATR and session already
> live on the setup's `contextRefs`). Live-paper capture retains no candles and records no context.

## 4.5 `Position`

| | |
|---|---|
| **Purpose** | An open simulated exposure |
| **Required fields** | `positionId` · `setupId` · identity block · `direction` · `entryPrice` · `entryTimestamp` · `entryFillBasis` (ask/bid/close) · `entrySpread` · `originalStop` · `currentStop` · `target` · `riskAmount` · `positionSize` · `pipValueBasis` · `balanceBefore` |
| **`originalStop` vs `currentStop`** | Identical today (nothing moves a stop). **Both required now**, so that if management is ever added the history remains comparable |
| **Consumers** | Journal · analytics · forensics |

## 4.6 `Outcome`

| | |
|---|---|
| **Purpose** | How the exposure resolved |
| **Required fields** | `outcomeId` · `positionId` · `exitPrice` · `exitTimestamp` · `exitReasonCode` · `exitDetectionSource` · `exitTriggerLevel` · **`realizedR`** · `plannedR` · `pnl` · `balanceAfter` · `mae` · `mfe` · **`timeToMFE`** · **`timeToMAE`** · `ambiguous` + `ambiguityBasis` · **`exitPathCandleRefs[]`** · `dataQualityFlags[]` |
| **`realizedR`** | Computed from actual exit — **`plannedR` alone is the v1.0 defect ALEX v1.1 fixed** |
| **`timeToMFE`** | Would have shown *when* the GBP/USD trade peaked at 0.949R. **IMPLEMENTED 2026-08-03 (v12.12.0, Unit C1)** for the replay capture path: `timeToMFE`/`timeToMAE` carry `{bars, minutes, barIndex, timestampUTC}`, recomputed over the same candles the engine walked and emitted **only** when the recomputation reproduces the protected `alexGComputeMAEMFE` extremes exactly. Provenance `DERIVED_FROM_OBSERVED_FIELDS`. Live-paper capture retains no candles, so it still records `UNAVAILABLE`. |
| **Consumers** | Analytics · forensics · loss classification |

## 4.7 `EvidencePackage`

| | |
|---|---|
| **Purpose** | The exportable, self-contained, verifiable unit — the system of record |
| **Required fields** | `packageId` · `packageSchemaVersion` · `createdAt` · `strategyId` + `strategyVersion` · `engineVersion` · `commitHash` · `mode` (LIVE_PAPER / REPLAY) · `runId` (replay) · `configSnapshot` + hash · `contentHash` · `objectCounts{}` · `completenessReport{}` |
| **Persistence** | **Tier (b) IndexedDB automatically; tier (c) disk artifact on successful export.** *(Revised per ruling C2 — originally "file-backed, outside the browser", which described only tier (c).)* |
| **Duration** | Permanent. **Never automatically deleted from tier (b).** |
| **`contentHash`** | **SHA-256** over the canonical package content, per ruling C1. **Integrity only — not authenticity, not a signature** (see Phase 1 spec §5.2) |
| **Consumers** | Everything |

**`completenessReport{}` is what makes the package honest** — it states which fields were unavailable
and why, so a later reader knows the boundary of what the package can support.

## 4.8 Relationship model

```
EvidencePackage
   └── Candidate ──┬── Decision (many, ordered)
                   ├── MarketContext (1, content-addressed, shareable)
                   └── QualifiedSetup (0..1)
                            └── Position (0..1)
                                     └── Outcome (0..1)
```

**Every arrow is optional downstream.** A candidate that never qualifies still yields a complete,
citable record — which is the point.

---

# 5. Replay Requirements

Replay is a **consumer** of the platform, not a special case. A replay run produces the same seven
objects, distinguished only by `mode: REPLAY` and a non-null `runId`.

**Required for a replay run to be citable:**

| Requirement | Current state |
|---|---|
| Explicit absolute `from`/`to` UTC range | ❌ "N days back from now" |
| `runId`, deterministic | ❌ None |
| Full config snapshot + hash | ❌ None |
| `commitHash` | ❌ Only `APP_VERSION` |
| Persisted trades and rejections | ❌ Session-only |
| Strategy-version linkage | 🟡 `ruleVersion` on trades; run-level absent |
| Deterministic rerun verification | ❌ No procedure |
| Dataset identity (hash of the candle set used) | ❌ None |

**One addition MOGO-002 did not name:** a **dataset content hash**. Without it, two runs over the same
declared date range cannot be proven to have used the same data — the broker may revise or gap-fill.
**Date range alone is insufficient for reproducibility.**

---

# 6. Persistence Requirements

## 6.1 Three tiers *(rewritten per ruling C2 — this table is the governing tier model)*

| Tier | Medium | Holds | Automatic? | Survives reload | Survives **profile clear** | Survives **device / disk loss** |
|---|---|---|---|---|---|---|
| **(a) Working buffer** | `localStorage` | Live account, open positions, hot journal, engine cursors | ✅ | ✅ | ❌ | ❌ |
| **(b) Evidence store** | **IndexedDB** | Complete evidence packages — **the automatic browser system of record** | ✅ **Fully — no user action** | ✅ | ❌ | ❌ |
| **(c) Durable artifact** | **Successfully completed disk export** | Self-contained, hash-verified evidence packages | 🟡 After one browser download grant | ✅ | ✅ | 🟡 Only if the file is itself backed up off-device |

**Tier (a) stops being the system of record.** It becomes a bounded buffer that flushes to tier (b).

> ⚠️ **IndexedDB does not survive browser-profile clearing, device loss, or disk loss.** Clearing site
> data removes `localStorage` and IndexedDB together. Tier (b) solves quota, silent failure, capacity
> and structure — **it solves none of those three.** Only a **successfully completed** tier-(c) export
> is intended to survive a profile clear, and even that survives device or disk loss only to the extent
> the operator backs the file up off-device. **MOGO must never claim otherwise.**

*(A former "T3 — Analysis store / offline tooling" tier is retained as a consumer concept only; it is
derived and regenerable, is not a persistence tier, and is out of scope for MOGO-003 Phase 1.)*

## 6.2 ⚠️ Write failure must become loud

**Current behaviour is the platform's single greatest risk.** `saveAlexGRest()` is `try{…}catch(e){}`
— a quota-exceeded write fails and **nothing anywhere reports it**. Under an evidence platform this
would mean silently losing exactly the records the platform exists to preserve.

**Required:** every persistence path must detect failure, surface it (Diagnostics + a
`DATA_UNAVAILABLE` decision event), and **mark affected evidence incomplete rather than absent**.

## 6.3 Candle storage — content-addressed and shared

Storing raw candles per trade is what blows the budget (~38 KB/trade). **Candles must be stored once
and referenced**, keyed by `instrument|timeframe|closeTimeUTC` with a content hash.

Two trades overlapping the same window share one stored candle set. `sourceCandleRefs[]` and
`exitPathCandleRefs[]` hold references, never copies.

## 6.4 Export

**No trade/journal export exists today.** The only export is `exportReplayDiagnosticsJSON/CSV`.
**A whole-package export is a required deliverable of Phase 1** — it is the only tier that survives a
cleared browser profile. *(Revised per ruling C2: export is necessary but no longer sufficient on its
own — automatic tier-(b) capture is what makes durability require no user action in the common case.)*

**Every export is hash-verified (C1), and a package is marked exported only after the write
completes.** A failed or cancelled export is never recorded as successful.

---

# 7. Replay Trustworthiness Requirements

Restating MOGO-003's earlier gate, now as platform requirements:

| # | Requirement | Satisfied by |
|---|---|---|
| T1 | Deterministic date range | Absolute UTC `from`/`to` in `EvidencePackage.configSnapshot` |
| T2 | Run identity | `runId`, deterministic, on every object |
| T3 | Config snapshot | `configSnapshot` + hash |
| T4 | Commit hash | `commitHash` on the package |
| T5 | Run metadata | The `EvidencePackage` header |
| T6 | Trade persistence | T2 durable tier |
| T7 | Version linkage | `strategyId` + `strategyVersion` on every object |
| T8 | Reproducibility | Rerun → compare `contentHash` of the R-space object set |

## 7.1 Determinism must be scoped honestly

MOGO-002 established ALEX replay is **deterministic in R-space and non-deterministic in money-space**
(`pipValuePerLot()` reads live `pairData`).

**The platform must not paper over this.** The reproducibility check compares the **R-space** object
set; money-denominated fields are marked `DERIVED` with a `LIVE_DATA_DEPENDENCY` flag until fixed.
Declaring a package "reproducible" when its P&L is not would be a false guarantee.

---

# 8. Data Lifecycle

## 8.1 Required evidence by stage

| Stage | Must exist | Exists today? |
|---|---|---|
| **Before entry** | Candidate · MarketContext · Decision chain · QualifiedSetup with `structureRefs` | 🟡 Setup record · `structureRefs` incl. **break/retest candle refs** (v12.10.0) · **rule attribution** (v12.11.0) · **lineage by reference**, a **bounded own-timeframe market context** (v12.13.0) and **higher-timeframe context anchored at entry** (v12.14.0), for traded replay trades only; **no candidate/untraded context, no content-addressed candle store, decisions still transient** |
| **During entry** | Fill basis · spread · delay from signal · original stop/target · sizing inputs | ✅ Mostly captured on the position |
| **During management** | Any stop/target change + trigger | ✅ N/A — nothing moves (must stay recorded as *deliberately none*) |
| **At exit** | Exit price/time/reason/detection source · trigger level · ambiguity · **exit-path candles** | 🟡 All present, plus **exit-path candle *references*** (v12.12.0, replay only). The candles themselves are still not stored — that is Unit C2 |
| **After close** | Realized R · MAE/MFE · **time-to-MFE/MAE** · data-quality flags | ✅ Realized R from the actual exit (v12.10.0) · MAE/MFE (engine) · **timing (v12.12.0, replay capture only; live paper retains no candles)** · data-quality flags |
| **During replay** | Everything above + run identity | 🟡 Run identity, absolute range, dataset/config hashes (v12.9.0) ✅; market context still absent |
| **During analytics** | Aggregations over durable packages | ❌ No analytics implemented — deliberately out of MOGO-003 scope |
| **During forensics** | The complete chain | 🟡 **Improved, not complete** — R-space, excursion extremes *and timing*, zone/break/retest refs and rule attribution are captured; market context and decision chains are not |

> **Status column refreshed 2026-08-03** to match the repository as built. The "Must exist" column is
> unchanged. **Unit C1 (excursion timing) is implemented and verified offline; browser verification —
> IndexedDB persistence of a timing-bearing package, in-browser `crypto.subtle` verification, and a
> real replay producing populated timing — is still PENDING. Unit C2 (market context) has NOT
> STARTED.** Nothing here was backfilled into existing packages.

## 8.2 ⚠️ Where evidence disappears today — five named leaks

| # | Leak | Mechanism |
|---|---|---|
| **L1** | **Decision events** | Memory-only, 500 cap, **destroyed on every page reload** |
| **L2** | **Candles** | **Never persisted at all.** `fetchCandlesRange` fetches and discards |
| **L3** | **Replay results** | Session-only (`alexGReplayTrades`) |
| **L4** | **Silent write failure** | `catch(e){}` — evidence can vanish with no signal |
| **L5** | **Setup/zone state overwritten** | Full reset+rebuild per pair per poll; the prior state is not versioned |

**L2 is the root cause of the July forensic failure.** L1 and L4 are the most dangerous, because they
lose evidence *without anyone knowing*.

## 8.3 Retention

| Class | Retention |
|---|---|
| Traded candidates + full chain | **Permanent** |
| Untraded candidates | Permanent (metadata); context windowed |
| MarketContext for traded | **Permanent** |
| MarketContext for untraded | **Windowed** — configurable, default 90 days |
| Replay packages | Permanent |
| Tier-(b) packages | **Permanent — never automatically deleted** (C4) |
| Tier-(a) buffer | Capped and flushed — **`fxhub_alexg_setups` and `fxhub_alexg_zones` only.** The ALEX journal/ledger is explicitly **never** capped or evicted (C4). No tier-(a) record may be evicted until its evidence is persisted in tier (b) |

## 8.4 The one deliberate compromise

**Untraded candidates do not retain full market context permanently.** Retaining every context for
every candidate is what makes the storage model unviable. Metadata and decision chains are permanent;
the candle window is windowed. **This is a stated trade-off, not an oversight** — and it should be
revisited if rule-attribution work later needs deeper history.

---

## 8.5 Unit C2-M1 design rationale (v12.13.0)

Four decisions in this milestone are worth stating explicitly, because each one traded something away.

**Bounded context, not a candle store.** The full P3 design is a content-addressed store that
deduplicates candles across packages. That is the right end state and it is also the expensive one:
it needs its own addressing scheme, retention policy and garbage-collection story, and §14 warns that
market context is what stresses the storage model. A bounded per-package excerpt buys the property
that actually blocked July's forensics — *a traded window that can be re-examined without a re-fetch*
— for roughly **6 KB per package** and no new subsystem. The cost is duplication: two trades over
overlapping candles each store their own copy. That is accepted for now and is the first thing the
candle store would fix.

**Why a re-fetch is not an option.** §10 of the July forensics established that re-fetching candles
produces *a* sequence, not *the* sequence the engine saw, and that reconstructing from it would be
fabrication. That is the whole reason the excerpt is stored verbatim from the in-memory arrays the
engine was walked over, tied to the run's `datasetHash`, rather than re-requested at capture time.

**Explicit truncation, and the entry bar is inviolable.** Every cap is declared: a truncated window
sets `truncated`, names a `truncationReason`, and reports `droppedPreEntryBars`. Validation *rejects*
a window that claims truncation without a reason, or reports dropped bars while denying truncation —
because a silent cap makes a partial window read as a complete one, which is precisely the class of
quiet failure this platform exists to prevent. The cap consumes **pre-entry context only and never
crosses the entry bar**: a window that does not contain the traded path cannot support the outcome it
is filed against, so when the path alone exceeds the ceiling the path is kept in full and the overrun
is declared (`pathExceedsMaxCandles`). This was not the first implementation — the original dropped
bars until the window fit and would have cut the entry bar off; the fixtures caught it.

**Lineage by reference, never by embedding.** `qualifiedSetups[].lineage` records only identifiers,
and validation enforces that every value is a string or null. Embedding the related objects would
duplicate data the package already holds, inflate the canonical form that `contentHash` covers, and
create two copies that can disagree. References keep a package a flat, hashable record while making
the zone → reaction → setup → position → outcome → context → package chain traversable. The same rule
is why `decisionChainRef` exists and is explicitly `null` with provenance `FUTURE_WORK`: the *shape*
of the relationship is declared even though no durable decision chain exists to point at yet
(CORR-5), which is honest in a way that omitting the field would not be.

**Higher-timeframe context deferred, not forgotten.** In C2-M1 `higherTimeframeContext` was present,
`null` and marked `FUTURE_WORK`. The W/D/H4 datasets were already in hand at the capture seam, so the
work was small — but it multiplies payload across four timeframes, and the sizing question deserved
its own decision rather than riding along with a milestone whose point was the traded window. A
package that captured a window therefore **gained** the higher-timeframe gap in its completeness
report as it shed the market-context gap, so it could never read as more complete than it was.

## 8.6 Unit C2-M2 design rationale (v12.14.0)

**The anchor is the entry candle's close, and that is the whole design.** Higher-timeframe context
answers "what did the larger structure look like *when this trade was taken*". A daily bar that closes
hours after entry is hindsight. It never touched the decision — the protected engine's no-lookahead
guarantees are unchanged — but storing it would put look-ahead *into the evidence*, where a later
reader could mistake it for what was known. So the capture scans candle close times and stops at the
last bar that had closed at the anchor, and **validation rejects** any stored context whose window
ends after its own anchor, or any candle starting after it. This is the one rule in the milestone
worth breaking a package over.

**Twenty bars, not two hundred.** Higher-timeframe context is orientation, not a second dataset: it
should show the structure the setup sat inside, and stop. Twenty bars per timeframe is enough to see
the prevailing swing and the nearby levels, and it keeps three extra timeframes cheaper than the
single own-timeframe window they accompany (+14.5 KB against +18.2 KB — §8.7).

**Ranking is mirrored, not re-derived.** `EVIDENCE_TIMEFRAME_RANK` duplicates
`RULES_ALEXG.config.htfPriority` so the evidence layer never depends on reading a protected constant
it could silently drift from, and a fixture asserts the two are identical — the same anti-drift
technique Unit B uses for its rule-attribution mirror. Ordering is by ascending rank, so the array is
deterministic and the canonical form is stable.

**Absence is enumerated, never implied.** Every higher timeframe either appears in `timeframes` with
observed candles or in `omittedTimeframes` with a reason (`DATASET_UNAVAILABLE`,
`NO_CLOSED_BAR_AT_ANCHOR`, `DATASET_INCOMPLETE_AT_ANCHOR`). A trade on the highest timeframe is
`NOT_APPLICABLE`, not a gap — nothing exists above it to capture.

## 8.7 Measured payload — and a corrected earlier estimate

Measured on RUN-001's real dataset shape (H1 2,220 · H4 600 · D 150 · W 73, 30-bar hold), on the
**exported** form (`JSON.stringify(pkg, null, 2)`, which is what reaches disk):

| Package content | Per package | 24-trade run |
|---|---|---|
| Through Unit C1 (no context) | **15.0 KB** | 360 KB |
| + C2-M1 own-timeframe window (81 candles) | **33.2 KB** (+18.2) | 796 KB |
| + C2-M2 higher-timeframe context (H4 20 · D 20 · W 8) | **47.6 KB** (+14.5) | **1.14 MB** |

⚠️ **The v12.13.0 note estimating "roughly 6 KB per package" measured *compact* JSON and understated
the on-disk figure roughly threefold.** These measured numbers supersede it. IndexedDB absorbs this
comfortably, but a long multi-pair run is now a megabyte-scale store, which makes the
content-addressed candle store (deduplicating candles shared by overlapping trades) the obvious next
economy rather than a theoretical nicety.

---

# 9. Versioning Strategy

**Four independent versions, all recorded on every package:**

| Version | Changes when |
|---|---|
| `packageSchemaVersion` | The evidence schema changes |
| `strategyVersion` | Any rule/filter/sizing/session change (MOGO-003 §13) |
| `engineVersion` | `APP_VERSION` |
| `commitHash` | Every commit |

**Rules:** schema changes are **additive-only** within a major version; readers must tolerate unknown
fields (the decision-event schema already has `unknownFields[]`); **no package is ever rewritten** —
a corrected package supersedes by ID; **mixed-version aggregation must be reported as mixed, never
silently averaged** (`alexGProvenanceSummary` already implements exactly this and should be the model).

---

# 10. Research Capability Requirements

**No analytics implemented.** This defines only what evidence makes each question answerable.

| Question | Required evidence | Available today? |
|---|---|---|
| Which setup contributes most? | `Outcome.realizedR` grouped by `QualifiedSetup.candidateType` | 🟡 Needs durable outcomes |
| Which confluence contributes most? | `Decision.inputs{}` per rule + outcome linkage | ❌ Inputs not captured |
| **Which rule reduces expectancy?** | **Full decision chain on both traded and rejected candidates** | ❌ **The single biggest gap** |
| Which session performs best? | `MarketContext.sessionUTC` + outcome | 🟡 Session recorded, not durable |
| Which loss classifications dominate? | `Outcome` + a classification field | ❌ No classification field |
| Which filters improve robustness? | Counterfactual: rejected candidates with enough context to evaluate what they would have done | ❌ Requires L2 fixed |

## 10.1 The counterfactual requirement

**"Which rule reduces expectancy?" cannot be answered from traded outcomes alone.** It requires
knowing what the *rejected* candidates would have done — which needs their market context and enough
forward candles to resolve a hypothetical outcome.

**This is the strongest argument for capturing MarketContext on rejected candidates**, and it is why
§8.4's windowing is a compromise rather than a clean answer.

## 10.2 Machine learning

No ML design is proposed. The platform serves it incidentally: labelled outcomes, structured
features (`Decision.inputs`), and honest completeness metadata. **Nothing in this architecture should
be justified by ML** — that would be speculative.

---

# 11. Known Repository Gaps

| # | Gap | Severity | Evidence |
|---|---|---|---|
| **R1** | Candles never persisted | **CRITICAL** | No candle `localStorage` key; `fetchCandlesRange` discards |
| **R2** | Decision events transient | **CRITICAL** | Memory-only, 500 cap |
| **R3** | Silent write failure | **CRITICAL** | `saveAlexGRest` `catch(e){}` |
| **R4** | No replay run identity | **CRITICAL** | `runAlexGReplay` returns a bare object |
| **R5** | No absolute date range | **CRITICAL** | `fetchCandlesRange` walks back from now |
| **R6** | Replay results session-only | **CRITICAL** | `alexGReplayTrades` |
| **R7** | No trade/journal export | **HIGH** | Only replay diagnostics export |
| **R8** | Unbounded `alexGSetupState` / `alexGZoneState` | **HIGH** | No cap found |
| **R9** | No quota detection | **HIGH** | Zero `QuotaExceeded` handling |
| **R10** | No commit hash on any artefact | **MEDIUM** | Only `APP_VERSION` |
| **R11** | Rule-level rejection detail unreachable | **MEDIUM** | `{qualifies:false}` discards which condition failed (`TRACE-LIM-001`); protected functions |
| **R12** | ~~No `timeToMFE`/`timeToMAE`~~ **RESOLVED for replay capture — v12.12.0 (Unit C1)** | **MEDIUM** | Was: extremes only. Now recomputed and emitted on newly captured replay packages, gated on exact agreement with the protected `alexGComputeMAEMFE`. **Still open for live paper**, which retains no candles to recompute from |
| **R13** | Money-space non-determinism | **MEDIUM** | `pipValuePerLot` reads live `pairData` |
| **R14** | TJR persists nothing | **LOW** | No `fxhub_tjr*` key — TJR has no evidence surface yet |

---

# 12. Engineering Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| **E1** | **Storage quota exhaustion, silently** | **High** | **Critical** | Three-tier model; loud failure; content-addressed candles |
| **E2** | **Protected-function pressure** — the richest evidence lives inside protected functions | **High** | High | Capture at non-protected seams (proven 3× in v1.1/002.8B); accept `TRACE-LIM-001` |
| **E3** | **Evidence capture changes trading behaviour** | Low | **Critical** | Capture must be fire-and-forget, never in a decision path; the decision-event bus already proves this pattern |
| **E4** | **Performance** — full context per candidate on a 60 s poll across 12 pairs × 4 timeframes | Medium | Medium | Buffer and batch; capture context only at qualification, not per candle |
| **E5** | **Schema churn** | Medium | High | Additive-only; `unknownFields[]`; version every package |
| **E6** | **Export becomes the new silent failure** | Medium | High | Verify `contentHash` on write; surface failures |
| **E7** | **Scope creep into analytics** | **High** | Medium | Platform stops at evidence; analytics is a later milestone |
| **E8** | **Third-party licensing** — packages may contain market data | Low | Medium | Broker data has its own terms; do not commit packages to a public repo (see MOGO-002 §12.1) |

---

# 13. Recommended Phase Breakdown

| Phase | Deliverable | Depends on | Exit criteria |
|---|---|---|---|
| **P1 — Durable capture & export** *(scope expanded per ruling C3)* | Loud write-failure detection · Evidence Package v1 schema + validation · **IndexedDB persistence** · **automatic evidence capture** · bounded working-buffer behaviour · export · **unexported-evidence warning** · **import and recovery** · **read-only historical backfill without fabricated evidence** · complete automated and browser-level validation | none | A live paper trade is captured automatically into tier (b) with no user action and exports as a complete, hash-verified, self-describing package; a forced quota failure is visibly reported |
| **P2 — Decision & candidate durability** | Persist decision chains and candidates; add `Decision.inputs{}`/`thresholds{}`; rejected candidates included | P1 | Every traded and rejected candidate has a retrievable, ordered decision chain |
| **P3 — Market context & candle store** | Content-addressed candle store; `MarketContext`; `sourceCandleRefs`/`exitPathCandleRefs`; `structureRefs` | P1, P2 | **The two July trades would be fully reconstructable if repeated today** |
| ↳ *P3 status* | **PARTIAL — v12.14.0 (Units C2-M1/M2):** `structureRefs` (v12.10.0), `exitPathCandleRefs` (v12.12.0), a bounded own-timeframe `MarketContext` (v12.13.0) and **higher-timeframe context (v12.14.0)** are delivered for captured replay trades. **The content-addressed candle store and untraded-candidate context are NOT delivered.** P3 was intentionally taken out of order, after P4/P5 items, because each delivered piece needed no new data — see §8.5 | — | Traded windows are re-examinable without a re-fetch; candidate-level reconstruction is not yet possible |
| **P4 — Replay trustworthiness** | Absolute date range · `runId` · config snapshot + hash · dataset hash · replay package persistence | P1–P3 | Two runs of the same declared range produce identical R-space `contentHash` |
| **P5 — Outcome completeness** | `realizedR` in replay · `timeToMFE`/`timeToMAE` · data-quality flags · loss-classification field | P4 | Every outcome answers "when did it peak?" |

> **P5 delivery status, 2026-08-03.** The phase plan above is unchanged; this records what has actually
> shipped against it, out of order relative to P2/P3 and deliberately so — these items needed no new
> data. `realizedR` shipped in **v12.10.0 (Unit A)**; `timeToMFE`/`timeToMAE` and the excursion
> `dataQualityFlags` shipped in **v12.12.0 (Unit C1)**, replay capture path only. The
> **loss-classification field is NOT implemented**. P2 (decision chains) and P3 (market context /
> candle store) remain **not started** — Unit C2 covers the bounded market-context excerpt and has not
> begun. Browser verification of the timing-bearing packages (IndexedDB persistence, in-browser
> `crypto.subtle` verification, and a real replay producing populated timing) is **still pending**.

**Deliberately excluded from MOGO-003:** analytics, metrics computation, the B1 resistance-role defect
fix (separate, protected-code, needs its own authorisation), transaction-cost modelling, and any
strategy change.

**Additionally excluded from Phase 1 by Engineering Authority ruling:** the **File System Access API**
(C3 — Phase 1 must not depend upon it), and **any capping, eviction, rewriting or bypass of the guarded
ALEX journal/ledger path** (C4).

---

# 14. Recommended Implementation Order

**P1 → P2 → P3 → P4 → P5**, and the ordering is load-bearing:

1. **P1 first** because it is the only phase that reduces *current* risk — today a cleared browser
   profile destroys all paper history, and a quota failure would do so silently.
2. **P2 before P3** because decision chains are cheap and small; market context is expensive. Getting
   the cheap high-value evidence first de-risks the storage model before it is stressed.
3. **P3 before P4** because a replay whose trades lack source-candle references reproduces the same
   forensic dead end at larger scale.
4. **P5 last** because outcome enrichment is only meaningful once outcomes are durable.

**P1 alone would have materially changed the July forensics** — the export would have supplied the
zone bounds, ATR, spread and ambiguity flags that were unavailable.

---

# 15. Definition of Done for MOGO-003

MOGO-003 is complete when **all** hold:

1. Every live paper trade produces a durable, exportable `EvidencePackage` with full identity.
2. **No persistence path can fail silently.**
3. Decision chains — traded and rejected — are durable and ordered.
4. Every traded candidate carries `sourceCandleRefs` resolving to stored candles.
5. A replay run has an absolute date range, a `runId`, a config snapshot and a dataset hash.
6. **Two identical replay runs produce identical R-space content hashes**, verified by an automated test.
7. Money-space non-determinism is **flagged**, not hidden.
8. `completenessReport{}` states what is missing and why, on every package.
9. **The two July Break & Retest losses would be fully reconstructable** if they occurred under the new platform. *(The concrete acceptance test.)*
10. Zero protected-function drift; full regression green.
11. Storage growth is bounded and measured.
12. The platform is demonstrated on **at least two strategies** (ALEX + JVM or TJR) with no schema change.

**Criterion 9 is the one that matters most** — it converts an abstract architecture into a test that
either passes or does not.

---

*MOGO-003 architecture, revised 2026-07-30 to incorporate Engineering Authority rulings C1–C5 (§0).
Nothing implemented; no production code modified; no strategy rule changed; no commit created.
Awaiting final Engineering Authority authorisation to implement Phase 1.*
