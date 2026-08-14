# ALEX Forward Trade-Frequency & Observation-Continuity Audit

**Status:** READ-ONLY INVESTIGATION · **ZERO CODE CHANGES** · CAMPAIGN UNTOUCHED · NOTHING REPAIRED
**Date:** 2026-08-13 · **HEAD:** `7fbb73ec7485c9b578af0eb5e58c8507da7f4d5a`
**ALEX:** frozen · drift 0 · forward cutoff unchanged · **live-money NOT AUTHORIZED**

---

## ⚠️ CORRECTION TO PART 1

**Part 1 of this audit (repository-only) reported "97% observation downtime". That figure is correct
for the window it examined and WRONG as a description of the campaign.**

Part 1 could only see the **pre-ledger** window (`02:43:57Z` → `13:41Z` on 2026-08-11), captured
before MOGO-013 activated durable observation. The live durable ledger — read in Part 2 — shows the
campaign has since run at **~84% observation continuity**, writing an observation **11 seconds
before this audit looked at it**.

**The 10.28-hour gap was real, but it belongs to the pre-ledger era and is not representative.**
Part 1's finding is retained below as the historical record; Part 2 supersedes its conclusion.

A second Part 1 error, now corrected: an mtime read as `18:51:48Z` was **local EDT**, i.e.
`22:51:48Z`. The store was being written continuously, not stale for four hours.

---

# PART 2 — LIVE DURABLE LEDGER CAPTURE

## How the capture was done, and why it was safe

The campaign runs in a **dedicated Chrome profile** (`~/MOGO-EVIDENCE-PROFILE/profile`, confirmed as
the only `--user-data-dir` in a running Chrome). The Claude-in-Chrome extension is attached to a
*different* profile, and Chrome partitions storage per profile — so the campaign's IndexedDB was
**not reachable** from the extension. A same-origin probe page confirmed it: `databases: []`,
`localStorage: []`, `scripts: 0`.

That probe page was deliberately a **404 path** (`/__mogo_readonly_probe__`, 460 bytes, zero
`<script>` tags), verified by `curl` first. **A second tab at `http://localhost:8751/` would have
booted a second instance of the trading app** — a second polling loop against the same IndexedDB.
That was never done. The probe tab was closed afterwards.

The ledger was therefore read **from disk**, read-only, by extracting strings from the LevelDB files
of the live profile. **Nothing was opened for write, no IndexedDB version was requested (which would
have fired `versionchange` on the campaign tab), and the campaign was never contacted.**

---

## 1. Exact authoritative activation timestamp — OBSERVED

`2026-08-11T02:43:57.894Z` (`1786416237894`) — unchanged, matching `fxhub_alexg_auto` and every
prior milestone record.

## 2–3. Durable observations after activation — OBSERVED

| | |
|---|---|
| Earliest durable observation | **`2026-08-11T14:59:07Z`** |
| Latest durable observation | **`2026-08-13T22:52:48Z`** |
| Span | **55.89 hours** |
| Max observation sequence | **`OBS\|22109`** |
| Distinct sequences recovered by string extraction | 6,206 |
| Distinct scan ids | **672** |
| Records carrying `FORWARD_LIVE_OBSERVATION` | 841 |
| Store size on disk | **20 MB** |
| Last write, relative to this audit | **11 seconds** |

The earliest durable observation matches MOGO-013's recorded `seq 1` at `2026-08-11T14:59:03.962Z`
to within the record's own occurrence/record delta. **Nothing was backfilled.**

**DERIVED:** ~22,109 observations over 55.89 h ≈ **396 observations/hour** — the same order as
MOGO-013's ~600/hour projection. **The ledger is healthy and currently writing.**

## 4. Instrument coverage — OBSERVED

11 pairs, by observation-string frequency:

| Pair | Count | | Pair | Count |
|---|---|---|---|---|
| GBP_CHF | 1,821 | | GBP_CAD | 698 |
| USD_JPY | 1,217 | | USD_CHF | 657 |
| AUD_USD | 1,149 | | USD_CAD | 595 |
| NZD_USD | 724 | | AUD_JPY | 527 |
| EUR_JPY | 721 | | GBP_JPY | 370 |
| | | | **GBP_USD** | **53** |

**Anomaly (DERIVED):** GBP_USD is an order of magnitude below every other pair — 53 against a 370–1,821
range. In Campaign C1, GBP_USD was the **highest**-yielding pair (25 trades). **UNKNOWN** whether
this reflects genuine market structure, a data-feed problem for that instrument, or late
registration. Flagged, not diagnosed.

Setup mix: `B_breakRetest` 3,988 · `A_repeatedReaction` 309.

## 5–6. Cadence and gaps — OBSERVED

| Metric | Value |
|---|---|
| Median inter-observation gap | **1.47 min** |
| Mean gap | 2.88 min |
| Gaps > 10 min | **12** |
| Gaps > 60 min | **3** |
| Total time inside >10-min gaps | **8.8 h of 55.89 h** |
| **Observation continuity** | **≈ 84.3%** |

### Largest gaps, ranked

| Duration | From → To |
|---|---|
| **130.8 min** | `2026-08-11T18:51:03Z` → `2026-08-11T21:01:54Z` |
| **98.0 min** | `2026-08-12T19:16:17Z` → `2026-08-12T20:54:16Z` |
| **72.5 min** | `2026-08-12T13:23:54Z` → `2026-08-12T14:36:22Z` |
| **58.5 min** | `2026-08-13T19:02:26Z` → `2026-08-13T20:00:55Z` |
| **52.2 min** | `2026-08-13T10:28:58Z` → `2026-08-13T11:21:09Z` |
| **48.1 min** | `2026-08-12T10:22:42Z` → `2026-08-12T11:10:51Z` |
| 11.0 min × 6 | scattered |

**DERIVED:** six substantial interruptions across 2.3 days, at irregular times of day, each followed
by a clean resumption at normal cadence. The repeated exact **11.0-minute** gaps are a distinct,
regular pattern and probably a different mechanism from the long ones.

## 7. Was the ~10.28-hour gap genuine? — **YES, and it is pre-ledger**

**OBSERVED:** activation `02:43:57.894Z`; first decision event `13:00:58.008Z`; first live setup
evaluation `13:00:46Z`. **Gap = 10.28 h**, with all 300 backlogged setups evaluated in a 28-second
burst on resumption.

**But it ended before durable observation began.** The ledger's first record is `14:59:07Z`, ~2 h
after that gap closed. **No comparable gap exists in the durable era** — the largest since is 130.8
minutes. Part 1's "97% downtime" describes only the pre-ledger window.

## 8–9. Observation vs ALEX evaluation — they are the same record

**OBSERVED:** durable records are `schemaVersion: mogo.observation.v1`, `kind: EVALUATION`, carrying
`derivedActivationCutoffPassed`, `derivedStale`, `derivedDying` and `ruleAttribution` (~5,900 each).
An observation **is** an evaluation.

**DERIVED:** scenario **A — "market observed continuously but ALEX evaluation failed" — is NOT
supported.** There is no evidence of observation continuing while evaluation stopped, because the
persisted unit is the evaluation itself. In every gap, **both** stopped together.

**UNKNOWN:** this same fact makes **B (observation stopped)** and **C (persistence stopped while
runtime continued)** **indistinguishable** with this evidence. A gap looks identical either way.

## 10. Evidence of suspension / throttling / connectivity loss

**OBSERVED:** Chrome is running with the evidence profile *now*. At the Part 1 capture the tab was
`visibilityState: hidden`, `hasFocus: false`, page age 666 min. MOGO-012 already concluded the fix
was operational — *"keep the host awake and the tab foregrounded"*. MOGO-013 disclosed that
credentials are memory-only and a reload needs manual reconnection.

**DERIVED:** irregular multi-tens-of-minutes gaps with clean resumption at full cadence are most
consistent with the **whole page being paused and resumed** — host sleep or background-tab
throttling — rather than a subsystem failing (which would more typically degrade, error, or produce
partial records).

**UNKNOWN:** no connectivity, session-expiry or OANDA-error evidence was recoverable by this method.
Absence here is **not** proof none occurred. **Absence of evidence is not evidence the application
was down.**

## 11. Genuine forward ALEX trades — OBSERVED

**Exactly ONE `status: "TRADE OPENED"` exists in the entire durable store.** This corroborates the
operator's report.

| Field | Value |
|---|---|
| Observation | `OBS\|6262` |
| `occurredAt` | **`2026-08-12T06:01:02.733Z`** |
| Pair / timeframe | **AUD_JPY · H1** |
| Setup type | **`B_breakRetest`** |
| Direction | **buy** |
| `derivedActivationCutoffPassed` | true |
| `derivedStale` | **false** |
| `derivedDying` | true |
| Strategy / engine | `alex_g_sr_v1` / `12.19.0` |

**DERIVED:** ~22,109 evaluations → **1 trade**. The trade fired ~15 h into the durable era; **none in
the ~41 h since.**

## 12. Rejection reasons, post-activation only — OBSERVED

| Reason | Occurrences |
|---|---|
| `SIGNAL_TOO_OLD_AT_FIRST_EVALUATION` | **~200** (75 full + truncated variants) |
| `ALEX_ACTIVATION_CUTOFF` | **~119** |
| `STALENESS` (marker) | 198 |

**⚠️ The sharpest open question.** `ALEX_ACTIVATION_CUTOFF` rejections should decay toward zero as
historical setups age past the boundary — that is expected and healthy. **`SIGNAL_TOO_OLD` should
not persist at ~200 occurrences across 55 h if observation is 84% continuous and the median gap is
1.47 minutes.** A signal qualifying at candle close should be evaluated within ~90 seconds, not
after it has gone stale.

Two candidate explanations, **not distinguished by this evidence**:

1. staleness is concentrated inside the six long gaps (benign — an artefact of the interruptions); or
2. there is a systematic staleness path independent of the gaps — plausibly the hourly signal
   **re-creation** behaviour MOGO-012-INC-001 documented, where a signal's age climbed 361 → 421 →
   540 minutes across successive captures.

**If (2), trade frequency is being suppressed by a mechanism unrelated to uptime.** Determining which
requires joining each `SIGNAL_TOO_OLD` record's timestamp against the gap intervals — a read-only
analysis, not attempted here.

---

## Most likely failure layer

**D — browser/runtime suspension or throttling.** *Moderate-to-high confidence* for the six gaps.

Supporting: irregular timing; clean full-cadence resumption; hidden/unfocused tab with a 666-minute
page age at the Part 1 capture; MOGO-012's independent operational conclusion; MOGO-013's disclosed
memory-only credentials.

Against/unresolved: **B and C are indistinguishable** from D by this evidence, because the persisted
unit is the evaluation — if persistence alone had stopped, the trace would look identical.

**E (connectivity)** — **G, insufficient evidence.** **A (evaluation failed while observation
continued)** — **not supported.**

## What this does and does not explain about trade frequency

**Revised, and materially different from Part 1:**

* Observation is **~84% continuous**, not ~3%. Uptime is *a* factor, not *the* factor.
* Campaign C1 (same `alex_g_sr_v1_1`, same engine 12.19.0) implies ≈1.77 trades/day → **≈4.1 expected
  over 2.33 days**, and **≈3.5 after an 84% uptime haircut**. **Observed: 1.**
* So roughly **2–3 trades are unexplained by downtime alone.** That is a real gap, though the sample
  is far too small for significance — a single AUD_JPY entry cannot support a rate estimate.
* **Over-constraint remains unsupported but is no longer excluded.** The evidence now points at the
  **staleness path (§12)** as the most probable suppressor, which is a *timing/observation* mechanism
  rather than a strategy-rule mechanism.

## What remains unknown

1. Whether `SIGNAL_TOO_OLD` rejections sit inside or outside the observation gaps — **the single
   highest-value unanswered question**.
2. Whether B, C or D caused the gaps.
3. Why GBP_USD carries ~10× fewer observations than its peers.
4. Any connectivity or session-expiry events.
5. Full per-record fidelity — string extraction from LevelDB recovers markers and timestamps, not
   complete structured records. Counts are **lower bounds**.
6. The educator's actual trades for this period — **absent from MOGO entirely**; still missing
   external evidence, still unrepresentable until `BACKLOG-004`'s Decision-Difference Case exists.

## Smallest next action

**One read-only join: for each `SIGNAL_TOO_OLD_AT_FIRST_EVALUATION` record, compare its timestamp
against the six gap intervals.**

* If staleness clusters **inside** the gaps → the cause is uptime; the fix is operational (keep the
  host awake / tab foregrounded) and **no strategy change is warranted**.
* If staleness occurs **outside** the gaps → there is a systematic re-creation/staleness path, and
  *that* — not any ALEX rule — is what suppresses trade frequency.

This needs no new code and no instrumentation: the timestamps are already in the durable store. It
should be done **before** anything else is considered, and certainly before any rule, threshold or
configuration is looked at.

## Boundaries honoured

ALEX frozen and unmodified · protected drift **0** · forward cutoff `2026-08-11T02:43:57.894Z`
unchanged · **campaign never contacted** · no second app instance created · no strategy, threshold,
config or code changed · no rebaseline · no trade manufactured · no evidence mutated · no
instrumentation added · Campaign C1 intact · live-money **NOT AUTHORIZED**.

**An operational problem is diagnosed (§5–7, §10) and an open question is raised (§12). Nothing was
repaired.**

---

# PART 3 — SIGNAL_TOO_OLD vs OBSERVATION-GAP JOIN

**Read-only. No code, evidence, threshold, rule, configuration or runtime behaviour changed.**
Analysis performed with a throwaway script in the session scratchpad against the live profile's
LevelDB files, read byte-for-byte. The campaign was never contacted.

**Method note:** records were recovered by **file order**, not by sorting — within a serialized
IndexedDB record the field strings are contiguous, so the nearest preceding timestamp and instrument
to a reason marker belong to that record. Counts are **lower bounds**; numeric fields
(`signalAgeMinutesAtFirstEvaluation`) are binary doubles and are **not recoverable** by string
extraction, so §4 of the request cannot be answered from this evidence.

## Result — the question is settled

| Classification | Count | % of dated |
|---|---|---|
| **NOT_GAP_ASSOCIATED** | **158** | **86.8%** |
| GAP_ASSOCIATED | 24 | 13.2% |
| INDETERMINATE (no recoverable timestamp) | 22 | — |
| **Total recovered stale markers** | **204** | |

*GAP_ASSOCIATED = inside a >10-min observation gap, or within 15 minutes of resumption.*

**86.8% of staleness rejections occur during healthy, continuous observation.** Runtime gaps are a
real but minor contributor.

## The mechanism — clock-locked to the H1 candle boundary

Minute-of-hour distribution of the 158 NOT_GAP_ASSOCIATED events:

| Minute | Count |
|---|---|
| **:00** | **85** |
| **:01** | **65** |
| :59 | 6 |
| :58 | 2 |
| all other minutes | **0** |

**94.9% land in minutes :00–:01. Not one occurs between :02 and :57.** They appear in **49 distinct
hours of the 56.3-hour span** — i.e. nearly every hour, continuously, whether or not the runtime was
healthy.

**DERIVED:** this is not downtime and not market conditions. At each **H1 candle close** the engine
re-derives signals; the re-created signal carries its **original** qualification timestamp, so at
"first live evaluation" it is already older than the staleness threshold and is rejected
immediately. This is precisely the hourly **re-creation** behaviour MOGO-012-INC-001 documented,
where one signal's age climbed **361 → 421 → 540 minutes** across successive hourly captures.

**Stale rejections do NOT cluster after runtime resumes** (only 24 events, 13.2%, are gap-adjacent
at all). They cluster on the **hour boundary**.

## Stale events by instrument

| Pair | Stale events | | Pair | Stale events |
|---|---|---|---|---|
| EUR_JPY | 61 | | GBP_USD | 18 |
| AUD_USD | 51 | | USD_CHF | 3 |
| AUD_JPY | 42 | | GBP_JPY | 2 |
| NZD_USD | 26 | | USD_CAD | 1 |

**GBP_CHF — the most-observed pair (941 mentions) — has ZERO stale events.** The staleness path is
concentrated in a subset of instruments, which argues against a global clock/threshold bug and for
something signal- or zone-specific.

## GBP_USD anomaly

| Pair | Mentions | Span (h) | First observation |
|---|---|---|---|
| GBP_CHF | 941 | 56.2 | `2026-08-11T14:59:11Z` |
| GBP_CAD | 612 | 56.0 | `14:59:13Z` |
| USD_JPY | 611 | 56.0 | `14:59:10Z` |
| EUR_JPY | 609 | 56.0 | `14:59:17Z` |
| USD_CHF | 590 | 56.0 | `14:59:19Z` |
| NZD_USD | 584 | 56.0 | `14:59:14Z` |
| AUD_USD | 582 | 56.0 | `14:59:09Z` |
| USD_CAD | 547 | 56.0 | `14:59:18Z` |
| AUD_JPY | 472 | 56.0 | `14:59:15Z` |
| GBP_JPY | 255 | 56.0 | `14:59:07Z` |
| **GBP_USD** | **50** | **53.9** | **`2026-08-11T17:00:03Z`** |

**OBSERVED:** GBP_USD entered the rotation **~2 hours after every other pair** and carries **≈0.93
observations/hour against GBP_CHF's ≈16.7** — roughly **18× less**. Its stale ratio is also the worst
of any instrument: **18 stale events out of 50 observations (36%)**.

**DERIVED:** the late start explains 2 of 56 hours; it does **not** explain the order-of-magnitude
density difference. This is **instrument-specific under-observation**, not a runtime-gap artifact —
GBP_USD's observations span the same period as its peers, just far more sparsely.

**Why it matters:** GBP_USD was Campaign C1's **highest**-yielding pair (25 trades of 226).

**Classification — GBP_USD: INDETERMINATE.** Candidate causes not distinguished by this evidence:
market-data availability for that instrument, a stalled per-pair cursor, or scan-rotation
deprioritisation. **Not diagnosed. Not repaired.**

## FINAL CLASSIFICATION

### **C — BOTH, overwhelmingly dominated by B**

* **B — SYSTEMATIC STALENESS PATH DURING HEALTHY RUNTIME: confirmed.** 86.8% of stale rejections,
  94.9% of them locked to minutes :00–:01, recurring in 49 of 56 hours. **High confidence.**
* **A — runtime gaps: real but secondary.** 13.2%.
* **D — insufficient evidence:** applies only to the 22 undated markers and to the *precise*
  mechanism (numeric age fields are unreadable by this method).

**Consequence for trade frequency:** the suppressor is a **timing/observation** mechanism, not an
ALEX rule. The staleness guard is behaving exactly as written; it is being fed signals whose
qualification timestamps are stale **by construction** at every hourly re-derivation. **No evidence
supports over-constraint of the frozen strategy, and no rule change is warranted.**

## Smallest next diagnostic action

**Capture one full hourly boundary for a single affected pair — read-only.** For AUD_JPY or EUR_JPY,
read the records written between `:59:30` and `:01:30` of any hour and compare three fields:
`qualificationTimestamp`, `firstLiveEvaluationTimestamp`, and the staleness threshold.

That single comparison distinguishes the two remaining possibilities:

1. **`firstLiveEvaluationTimestamp` is being reset on each re-derivation** while
   `qualificationTimestamp` stays original → the signal is *permanently* stale from birth and can
   never trade. A correctness defect in signal identity/lifecycle.
2. **The signal genuinely is old** and the threshold is simply shorter than the H1 re-derivation
   interval → a threshold/cadence mismatch, not a defect.

These have very different implications and **must not be conflated**. This needs no new
instrumentation — both fields are already persisted.

**Smallest operational change worth investigating separately** (for the 13.2% gap contribution, and
independent of the above): keeping the host awake and the campaign tab foregrounded, as MOGO-012
already concluded. That addresses the minority cause only and **will not** fix the hourly staleness
path.

## Boundaries honoured

ALEX frozen · frozen rules, signal-age thresholds, market-data handling, runtime behaviour, evidence,
paper-trading configuration, authorization and production code **all unchanged** · forward cutoff
`2026-08-11T02:43:57.894Z` unchanged · Campaign C1 intact · campaign running uninterrupted
(ledger written 16 s before this analysis closed) · live-money **NOT AUTHORIZED**.

**A systematic problem is identified. Nothing was repaired.**

---

# PART 4 — H1 RE-DERIVATION / STALE-FROM-BIRTH DIAGNOSTIC

**Read-only. ALEX unmodified. No rule, threshold, signal-age limit, market-data behaviour,
instrumentation, evidence or campaign state changed.**

## 4.0 Method change, and why

The intended record-level lineage read (`qualificationTimestamp` vs `firstLiveEvaluationTimestamp`
for one pair across one boundary) **could not be completed from the persisted bytes**, for a
structural reason:

* `.ldb` files are **Snappy-compressed** — field names come back garbled
  (`qualificEsLTimestampN`, `firstLiveEvalu>R`).
* V8 serialization **dedupes repeated strings via a string-ID table**, so a field name appears
  literally only on its *first* occurrence per context. The current WAL contains **7** `occurredAt`
  and **zero** occurrences of `qualificationTimestamp`, `firstLiveEvaluationTimestamp` or `signalId`.
* Numeric fields are binary doubles — `signalAgeMinutesAtFirstEvaluation` is unreadable by string
  extraction.
* The profile is **locked** by the running campaign; opening it with a second Chrome was refused as
  unsafe.

Values are present but **cannot be reliably bound to field names**, so a fabricated lineage table
was not produced. Instead the question was answered from the **authoritative source: the frozen
implementation in `index.html`**, which states exactly what happens. This is §5 of the request,
performed read-only, and it settles the question conclusively.

## 4.1 The code path — H1 close → re-derivation → staleness guard

| Step | Location | Behaviour |
|---|---|---|
| Full rebuild every poll | `index.html:4557-4559` | `delete alexGZoneState[oPair]` · filter out the pair's setups · `alexGRunSetupEngine(oPair,datasets)` over **90 days** of candles |
| Signal identity | `4252-4254` | `AGL\|{strategy}\|{pair}\|{timeframe}\|{setupId}\|{qualificationTimestamp}` — **stable**; the same setup always yields the same `signalId` |
| Dedup claim | `4591-4600` | *"Already decided once — **PERMANENT, never reconsidered** on a later poll even though the same historical setup will keep reappearing every full rebuild"* |
| First-evaluation stamp | `4602` | `const firstLiveEvaluationTimestamp = nowMs` — **set to now on every evaluation** |
| Staleness gate | `4532-4536` | `(nowMs - setup.qualificationTimestamp)/60000 > maxAge` |
| Threshold | `2445` | `maxLiveSignalAgeMinutes: {H1:60, H4:240, D:1440, W:10080}` — **one bar-period per timeframe**, deliberate and documented |
| Durable record key | `12888` | `'EVAL\|'+signalId+'\|'+firstLiveEvaluationTimestamp` |

**`qualificationTimestamp` is never reassigned.** It is the qualifying candle's own time, carried
through every rebuild — correctly.

## 4.2 The actual defect — the dedup is not permanent

```js
function alexGRecordLiveSetupStatus(entry){
  if(alexGLiveSetupStatuses.some(e => e.signalId === entry.signalId)) return;
  alexGLiveSetupStatuses.unshift(entry);
  if(alexGLiveSetupStatuses.length > 300) alexGLiveSetupStatuses.length = 300;   // ← eviction
}
```

`alexGLiveSetupStatuses` is **simultaneously the dedup set and a 300-entry ring buffer**. The dedup
at `4594` reads that same array.

**Therefore the documented "PERMANENT, never reconsidered" contract is violated by silent
truncation.** Once a `signalId` is evicted past position 300, the next full rebuild no longer sees
it, re-decides the identical setup, stamps a **new** `firstLiveEvaluationTimestamp`, and — because
the durable natural key includes that stamp — writes a **new** observation.

**This is exactly the hourly re-creation MOGO-012-INC-001 recorded**, with one signal's age climbing
**361 → 421 → 540 minutes** across successive hourly captures: the same signal, re-decided, ageing.

## 4.3 Which explanation the evidence supports

**Not B, and not C.** The precise answer is **A + D**:

* **A — GENUINELY STALE: confirmed for the rejection itself.** `alexGIsSetupSignalStale` returns
  true only when age > one bar-period. **An H1 setup rejected as stale is therefore, by definition,
  more than 60 minutes old at evaluation — it cannot be a freshly-qualified candle.** The 158
  NOT_GAP_ASSOCIATED events are re-decisions of setups that were already correctly ineligible.
* **B — NOT confirmed as trade-suppressing.** `qualificationTimestamp` is inherited *correctly*; a
  newly-qualified setup at an H1 close has age ≈ 0–1 min and **passes** the guard. Nothing is
  "stale from birth".
* **C — NOT supported.** One bar-period is coherent with an hourly re-derivation cadence; fresh
  candidates are evaluated well inside it.
* **D — what the evidence actually establishes:** a **bounded-buffer defect in the dedup contract**.
  It produces duplicate evaluations and inflated stale counts — an **evidence-integrity** problem,
  **not** a trading-outcome problem.

### The safety question, checked explicitly

Eviction could in principle allow a *traded* signal to be re-evaluated and traded twice. **It cannot:**
double-trading is guarded by `alexGAutoTrading.tradedSignals[signalId]` — a **separate, persisted,
unbounded** map (written `4503`, checked `4281`, persisted via `saveAlexG`), described at `2162` as
*"the controlling duplicate-trade guard"*. **The 300-ring is not the trade guard. No double-trade
risk exists.**

## 4.4 Campaign impact — quantified, and deliberately not overstated

| Category | Count | Interpretation |
|---|---|---|
| NOT_GAP_ASSOCIATED stale events | **158** | **Not missed trades.** Provably >1 bar-period old; re-decisions of already-ineligible setups. |
| GAP_ASSOCIATED stale events | **24** | **The only genuinely missed opportunities** — setups that aged past one bar-period *while the runtime was down*. Caused by downtime, not by code. |
| INDETERMINATE | 22 | No recoverable timestamp. |

Affected instruments (stale events): EUR_JPY 61 · AUD_USD 51 · AUD_JPY 42 · NZD_USD 26 ·
GBP_USD 18 · USD_CHF 3 · GBP_JPY 2 · USD_CAD 1. **GBP_CHF: 0.**

**Can any be established as otherwise trade-qualified? NO — not one.** Staleness is evaluated
*before* direction, overlap, ATR, entry-delay, stop validity, target and pip-value gates
(`4270-4275`). Those gates were never run for a stale-rejected setup, so **no stale rejection can be
called a missed trade.** The 24 gap-associated events are *lost opportunities to evaluate*, not lost
trades.

**Cannot be reconstructed:** per-record numeric ages; whether any of the 24 would have passed the
remaining gates; the 22 undated markers; anything evicted from the 300-ring before capture.

**This materially corrects Part 3's implication.** Part 3 established the staleness pattern is
systematic and clock-locked — that stands. Its suggestion that this *suppresses legitimate
candidates* is **not supported by the code**: the suppressor of trade frequency is **downtime**
(15.7%), not the staleness path.

## 4.5 GBP_USD — next diagnostic only

**OBSERVED:** `GBP_USD` appears just 3 times in `index.html`; at `2086` it is
`let activePair='GBP_USD'` — the **default UI chart pair**. It sits in the pair list at `1961`.

**UNKNOWN and not pursued:** whether being the active chart pair changes its live-scan handling,
whether it is in the live-scan set at all, or whether its market data is fetched on a different path.

**Smallest next diagnostic (not performed):** enumerate the pair set actually iterated by the live
scan loop and confirm whether `GBP_USD` is a member, then compare its per-scan fetch behaviour with
one healthy peer. **No repair attempted.**

## 4.6 CLASSIFICATION

### 🟢 **GREEN — stale behaviour is correct; no trade-suppressing defect**

The staleness rule is deliberate, documented, correctly implemented, and correctly fed. No
legitimate forward-paper candidate is being suppressed by signal re-derivation or timestamp
handling. **No rule, threshold or strategy change is warranted.**

Not **YELLOW**: the evidence is sufficient and conclusive — the implementation settles it.
Not **RED**: no forward-paper *evaluation outcome* is wrong, and no double-trade risk exists.

### Two real findings carried forward, neither a trading defect

1. **Dedup-contract violation (evidence integrity).** `alexGLiveSetupStatuses` serves as both dedup
   set and 300-entry ring; truncation breaks the documented "permanent" guarantee, producing
   duplicate observations and inflating stale counts. **Smallest auditable repair, NOT implemented:**
   separate the dedup key set from the display ring — keep an unbounded `Set` of decided `signalId`s
   (as `tradedSignals` already does) and let the 300-entry array remain display-only. This changes
   **no** trading decision; it stops re-deciding already-decided signals. It touches a protected
   function, so it requires the full drift-gate and governance path.
2. **Downtime is the actual frequency constraint** — 15.7%, cause of all 24 genuinely missed
   evaluation opportunities. Operational, already diagnosed in MOGO-012.

## 4.7 Boundaries honoured

ALEX frozen · drift **0** · no rule, threshold, signal-age limit, market-data behaviour, runtime
behaviour, evidence, paper-trading configuration, authorization or production code changed · forward
cutoff unchanged · no instrumentation added · campaign uninterrupted · C1 intact · live-money
**NOT AUTHORIZED**.

**Diagnosis complete. Nothing repaired.**

---

# PART 5 — INDEPENDENT VERIFICATION (ADVERSARIAL RE-AUDIT)

**Read-only. Nothing repaired. ALEX drift 0. Every prior finding was challenged, not assumed.**

## 5.1 Verification matrix

| # | Finding | Verdict | Independent path used |
|---|---|---|---|
| 1 | Frozen ALEX rules not responsible | **PARTIALLY_CONFIRMED** | git byte-compare of `RULES_ALEXG` at the C1 commit vs now |
| 2 | Staleness threshold behaviour correct | **CONFIRMED** | same byte-compare + the H1 cadence gate in code |
| 3 | 300-entry dedup harmless to trading | **CONFIRMED** | separate guard (`tradedSignals`) traced independently |
| 4 | ~24 candidates aged out in gaps | **PARTIALLY_CONFIRMED** | independent `scanId` epoch clock |
| 5 | GBP_USD materially under-observed | **CONFIRMED — and understated** | `SCAN_PAIRS` config vs observed instrument set |
| 6 | Continuity is the highest-impact issue | **REFUTED as stated** | coverage loss vs time loss, weighted by C1 yield |

## 5.2 Finding 1 — rules — **PARTIALLY_CONFIRMED**

**Independent path:** C1 ran at commit `f7f0c40`. `index.html` *did* change since (+1,022/−17), so
"app version unchanged" is not sufficient. I extracted the `RULES_ALEXG` object literal from both
revisions and hashed it:

```
C1  (f7f0c40) RULES_ALEXG : 5416 bytes  sha256 b5537c9b6711f2c2e28098ed706496de…
now (working)  RULES_ALEXG : 5416 bytes  sha256 b5537c9b6711f2c2e28098ed706496de…
IDENTICAL: True
```

The drift baseline (`regression-baseline.json`, commit `00c8a39`) was verified by `git merge-base`
to be an **ancestor of the C1 commit**, so "drift 0" genuinely covers the C1→now window rather than
a later re-baseline.

**Confirmed:** no ALEX rule, threshold or parameter changed between the C1 replay and the live
campaign. The C1 comparison is methodologically valid.

**Why only PARTIAL:** the operator's original premise was that *"before the fuller ALEX rule set was
ingested/frozen, earlier versions appeared to generate trades more frequently."* C1 was collected
**2026-08-06 — after** any such expansion. **There is no pre-freeze replay campaign in the
repository**, so the pre-freeze-vs-post-freeze comparison the premise implies is **UNVERIFIABLE**.
What is verified is narrower: nothing changed between C1 and now.

## 5.3 Finding 2 — staleness — **CONFIRMED**, with a new mechanism

`maxLiveSignalAgeMinutes:{H1:60,H4:240,D:1440,W:10080}` is byte-identical across C1→now.

**New evidence that strengthens it** (`index.html:5000-5007`):

```js
const currentH1Boundary = Math.floor(Date.now()/3600000)*3600000;
for (const pair of SCAN_PAIRS) {
  const lastEval = (alexGLastEvaluatedCloseTime[oPair] && alexGLastEvaluatedCloseTime[oPair].H1) || 0;
  if (currentH1Boundary <= lastEval) continue;      // ← advance once per H1 close, per pair
  await alexGEvaluatePairForLiveSetups(oPair, __scanId);
}
```

**Evaluation advances exactly once per pair per H1 boundary.** The :00/:01 clustering documented in
Part 3 is therefore **the designed cadence, not a symptom** — that is simply the only minute in which
evaluation runs. Part 4's conclusion is independently reinforced.

## 5.4 Finding 3 — dedup — **CONFIRMED**; classification refined

Each sub-question checked separately:

| Question | Answer | Evidence |
|---|---|---|
| Re-evaluation after eviction? | **Yes** | `alexGRecordLiveSetupStatus` truncates the same array the dedup reads (`4261-4265`) |
| Double-trade protection intact? | **Yes** | `alexGAutoTrading.tradedSignals` — separate, **persisted** via `saveAlexG`, **unbounded** (`4281` check / `4503` write / `2162` "controlling duplicate-trade guard") |
| Could a legitimate *new* candidate be wrongly suppressed? | **No** | `signalId` includes `setupId` **and** `qualificationTimestamp` (`4253`); a genuinely new setup cannot collide |
| Could a rejected candidate later become valid but stay blocked? | **No** | staleness only increases with time; activation-cutoff (`qualificationTimestamp < activatedAt`) is permanent. Neither can become valid |

**New:** `alexGLiveSetupStatuses` is **ephemeral** (never persisted — Part 1 captured it as
`EPHEMERAL_`). A page reload therefore wipes **all** dedup state, which is a *larger* re-decision
trigger than the 300-entry cap. `tradedSignals` survives reload; the dedup does not. That asymmetry
is correct for safety and is the reason the defect stays non-trading.

**Classification: EVIDENCE_INTEGRITY + PERFORMANCE.** Not TRADING_CORRECTNESS.

## 5.5 Finding 4 — gaps — **PARTIALLY_CONFIRMED**

**Independent clock:** `scanId` embeds an epoch — `SCAN|<epoch_ms>-<n>`. Rebuilding the series from
655 distinct scan epochs, entirely separately from the ISO `occurredAt` strings:

| Metric | ISO-string path | scanId-epoch path |
|---|---|---|
| Gaps > 10 min | 12 | **12** |
| Largest | 130.8 min | **130.7 min** |
| Next four | 98.0 / 72.5 / 58.5 / 52.2 | **97.9 / 72.4 / 58.4 / 52.1** |
| Time in gaps | 15.7% | **15.5%** |
| Continuity | 84.3% | **84.5%** |

Two different encodings agree to within 0.1 minute on every gap. **Gap count, durations and
boundaries: CONFIRMED.** Because `scanId` is per-scan (all pairs together), the gaps are **global to
the scanner**, not instrument-specific — independently confirming that scenario A ("observation
continued, evaluation failed") is not what happened.

**Why only PARTIAL — two honest limitations:**

1. **A test I ran was invalid and is discarded.** I attempted to rule out "extraction artifact" by
   checking whether observation sequence numbers advance across each gap. Compaction reorders
   records across `.ldb` files, so the timestamp↔sequence pairing broke (it returned negative
   advances). **That test proves nothing and is not used.**
2. **The figure "24" is parameter-dependent, not measured.** It follows from *my* choice of a
   15-minute post-resume attribution window. The underlying gaps are solid; the split between
   `LOST_EVALUATION_OPPORTUNITY` and `NOT_GAP_CAUSED` moves with that parameter. Per the request's
   own vocabulary: **≈24 LOST_EVALUATION_OPPORTUNITY, ≈158 NOT_GAP_CAUSED, 22 INDETERMINATE** — with
   the caveat that the boundary is a judgement, and **none is a missed trade** (Part 4 §4.4).

## 5.6 Finding 5 — instrument coverage — **CONFIRMED, AND MATERIALLY UNDERSTATED**

**Independent path: configured scanner membership vs observed set.**

```js
const SCAN_PAIRS = ['GBP/USD','EUR/USD','GBP/JPY','AUD/USD','USD/JPY','GBP/CHF',
                    'GBP/CAD','NZD/USD','AUD/JPY','EUR/JPY','USD/CAD','USD/CHF'];   // 12 pairs
```

Observed occurrences in the durable ledger:

| Pair | Count | | Pair | Count |
|---|---|---|---|---|
| GBP_CHF | 1,078 | | USD_CAD | 611 |
| EUR_JPY | 745 | | AUD_JPY | 538 |
| NZD_USD | 741 | | GBP_JPY | 313 |
| GBP_CAD | 722 | | **GBP_USD** | **54** |
| USD_JPY | 717 | | **EUR_USD** | **0** |
| AUD_USD | 701 | | | |
| USD_CHF | 677 | | | |

**`EUR_USD` — a configured scan pair — has ZERO observations.** This was missed entirely by the
earlier audit, which only counted pairs that *appeared*. **Two of twelve configured instruments
(17%) are effectively unobserved.**

**`SCAN_PAIRS[0]` ruled out** as an explanation: it is referenced only by `generateTestAlexTrade`, a
developer-mode tool that explicitly *"never touches alexGAutoTrading.tradedSignals or
alexGLiveSetupStatuses"*.

**Earliest divergence layer — DATA RETRIEVAL** (`index.html:4555-4556`):

```js
const datasets = await fetchAlexGReplayDatasets(oPair, 90);
if (!datasets.H1 || datasets.H1.length < 60) return;      // ← SILENT early return
```

Configuration ✅ (both pairs listed) · scheduling ✅ (loop iterates all `SCAN_PAIRS`) · **data
retrieval ❌ — returns with no observation, no decision event and no error**. Evaluation and
persistence are never reached, which is exactly consistent with a zero/near-zero record count.

**Caveat, stated honestly:** absence in a Snappy-compressed store is weaker evidence than presence.
`0` for EUR_USD is strong but not conclusive; `54` for GBP_USD is a hard positive count against a
peer median of ~710.

## 5.7 Finding 6 — root cause and priority — **REFUTED as stated**

### Root cause of the gaps — now differentiated, and *not* uniformly throttling

The operator's caution was correct: throttling must not be assumed from a hidden tab. LevelDB's own
operational `LOG` — independent of every application record — contains database-open events:

```
LOG.old : 2026/08/12-09:24:25.925  Recovering log #71     → 2026-08-12T13:24:25Z
LOG     : 2026/08/12-10:36:18.690  Recovering log #71     → 2026-08-12T14:36:18Z
```

Against the **72.5-minute gap: `13:23:54Z → 14:36:22Z`.** The database closed **31 seconds after**
the last observation and reopened **4 seconds before** the first one after.

| Gap | LOG coverage | Recovery event? | Attribution | Confidence |
|---|---|---|---|---|
| **72.5 min** (08-12 13:23→14:36) | yes | **YES — reopen** | **Runtime restart / page reload** | **High** |
| 98.0 min (08-12 19:16→20:54) | yes | **No** | DB stayed open → **not a restart**; suspension/throttling/app stall | Moderate |
| 58.5 min (08-13 19:02→20:00) | yes | **No** | as above | Moderate |
| 52.2 min (08-13 10:28→11:21) | yes | **No** | as above | Moderate |
| 130.8 min (08-11 18:51→21:01) | **no** — predates LOG | — | **UNKNOWN** | — |
| 48.1 min (08-12 10:22→11:10) | **no** — predates LOG | — | **UNKNOWN** | — |

| Hypothesis | Confidence |
|---|---|
| Runtime restart / reload | **High — proven for one gap** |
| Browser throttling or host sleep | **Moderate** — consistent with three gaps where the DB stayed open, but not *proven*; no direct throttling evidence exists |
| Network/API interruption | **Low** — no error records recovered; `ENGINE_ERROR` is emitted on failure (`5014`) and none was found |
| App/session failure | **Low** — same reason |
| Scheduling behaviour | **Ruled out** — the H1 gate skips *evaluation*, not *polling*; poll records are written regardless (`4995`) |
| Unknown | **Applies to 2 of 6 large gaps** |

### Why the priority claim is refuted

| Defect | Nature | Magnitude |
|---|---|---|
| **Instrument coverage** | **Systematic, permanent, biased** | **2 of 12 pairs (17%) — including GBP_USD, which produced 25 of C1's 226 trades (11%)** |
| Observation continuity | Intermittent, roughly unbiased | 15.5% of wall-clock time |

Coverage loss is **worse than the raw percentages suggest** because it is not random: a missing pair
removes **100%** of its opportunities for the whole campaign, and one of the two missing pairs was
C1's single best producer. Downtime removes a random ~15% slice. **Coverage is the higher-impact
integrity defect.**

## 5.8 CAMPAIGN-INTEGRITY VERDICT

### 🟡 **YELLOW — usable, but every frequency or performance statistic must be qualified**

**Supporting evidence:** the engine is running correctly and the rules are provably unchanged
(§5.2–5.3); trading correctness is intact with no double-trade risk (§5.4); the durable ledger is
healthy and currently writing. **But** the campaign observed only **10 of 12 configured
instruments** for its entire duration, and **15.5%** of wall-clock time is missing, of which at
least one interval was a **confirmed runtime restart**.

**Not GREEN:** a 17% instrument-coverage hole that includes C1's top producer is a material,
systematic bias — not a rounding error.
**Not RED:** nothing recorded is *wrong*. Every persisted observation is accurate, rules are
unchanged, no trade was incorrectly opened or blocked, and no evidence is corrupted. The campaign is
**incomplete, not compromised** — it can be interpreted once qualified with the coverage caveat.

## 5.9 SINGLE HIGHEST-VALUE NEXT ACTION

**Diagnose why `fetchAlexGReplayDatasets` returns fewer than 60 H1 candles for `EUR_USD` and
`GBP_USD`.**

Read-only, one function, existing architecture, no new instrumentation: call the existing fetch for
those two pairs alongside one healthy peer (e.g. `USD_JPY`) and compare returned candle counts and
any API response. That single comparison distinguishes an **upstream data/instrument availability
problem** from an **application-side fetch defect**, and it is prerequisite to any repair.

**Why this outranks the continuity work:** it addresses a *systematic, biased, permanent* 17%
coverage loss rather than an intermittent, roughly unbiased 15% time loss — and it is cheaper to
diagnose.

**If a repair is later warranted** (described, **not implemented**): the silent early return at
`index.html:4556` should emit an existing `ENGINE_ERROR`/`DATA_UNAVAILABLE` decision event before
returning, so a pair dropping out of coverage becomes visible instead of silent. That touches a
protected function and requires the full drift-gate and governance path.

## 5.10 Boundaries honoured

ALEX frozen · **drift 0** (63 functions, 4 constants) · C1 intact (1,160/1,160) · forward cutoff
unchanged · paper-campaign history intact and uninterrupted · no rules, thresholds, pair
configuration, evidence, cutoff or trading authority modified · no instrumentation added ·
live-money **NOT AUTHORIZED**.

**One prior test was found invalid and discarded rather than reported. Two prior findings were
corrected. Nothing was repaired.**

---

# PART 6 — RELIABILITY REPAIR (autonomous mandate)

**Commit `c24b96b` · pushed · canonical 20 suites 1,171/1,171 · platform 1,049/1,049 · ALEX drift 0**

## 6.1 Root cause, refined by a cleaner discriminator

`signalId` embeds the pair (`AGL|{strategy}|{pair}|…`), which separates EVALUATION records from
POLL records. That split changed the diagnosis:

| Pair | EVALUATION records | Meaning |
|---|---|---|
| 10 healthy pairs | 249–930 | normal |
| **GBP_USD** | **0** (but ~54 poll appearances) | **attempted ~once per H1 boundary, produced zero evaluations** |
| **EUR_USD** | **0** (and 0 poll appearances) | **never attempted — skipped before the poll record was written** |

These are **two different defects**, not one. Verified by raw binary search in both encodings:
EUR_USD appears **zero** times anywhere in the store.

## 6.2 What was fixed

Two silent paths, both in **non-protected** functions:

1. `alexGEvaluatePairForLiveSetups()` returned early on a short H1 dataset with **no record of any
   kind**. Now emits `ENGINE_ERROR` / `DATA_INSUFFICIENT_HISTORY` carrying the pair, per-timeframe
   received counts, completeness state, pagination termination reason and HTTP status.
2. `alexGLivePollTick()` skipped a pair whose cursor had not fallen behind the H1 boundary, also
   with no trace. The poll observation now carries `instrumentsConfigured` and `instrumentsSkipped`,
   so configured-vs-evaluated makes a starved instrument detectable.

`DATA_INSUFFICIENT_HISTORY` was registered in `REASON_CODE_REGISTRY` **first** — the initial attempt
emitted an unregistered code that `validateDecisionEvent()` silently dropped, which the new fixtures
caught before commit. That is the registry's own documented rule, and it very nearly bit again.

**11 new fixtures**, observability only. No rule, threshold, return value or decision path changed;
drift stayed 0.

## 6.3 The dedup fix was attempted, broke 20 fixtures, and was REVERTED

The mandate's item 10 (separate the permanent decided-signal set from the bounded display ring) was
implemented without touching the protected recorder — an unbounded `Set` written at the six
non-protected call sites, read by the dedup check.

**The regression gate caught a real bug:** the campaign-reset path clears the ring but would not have
cleared the Set, permanently blocking every future trade after a reset. Fixing that still left 20
failures in `run_v017_step2a_pipeline_observability_tests.js`, because the suites reset
`alexGLiveSetupStatuses` directly and cannot know about a second structure.

**That is the real finding: any parallel set is a second source of truth that desynchronizes
whenever the ring is reset externally.** The correct fix keeps one source of truth, which requires
modifying the **protected** `alexGRecordLiveSetupStatus`. Shipping desynchronizable duplicate state
into a live trading path — for a defect independently classified twice as EVIDENCE_INTEGRITY, not
trading correctness — is the wrong trade. **Reverted; escalated as a governance item.**

## 6.4 JVM is not affected — and shows the correct pattern

Only **ALEX** and **JVM** are paper-authorized (`scanning/paperTrading/automation/journal: true`).
**TJR is `status:'development'` with all four false — not paper-authorized.** There is no
`jvmAutoTrading`; JVM runs through the shared scanner.

JVM's `scanPair()` **already** uses the governed completeness abstraction:

```js
const completenessState=marketDataCompletenessOf(candles);
const evaluable=completenessState===MARKET_DATA_COMPLETENESS.COMPLETE?candles:null;
```

It suppresses evaluation on incomplete data rather than returning silently, and still records the
candles for diagnostics. **ALEX's live path was the outlier** — a bare `length<60` check that
bypassed the shared abstraction ADR-011 introduced. The shared market-data layer is sound.

---

# PART 7 — LOOP CORRECTNESS PROVEN OFFLINE (commit `c443ed6`)

Rather than repeat "blocked on runtime access", the scan loop was driven **directly** in the fixture
harness: the real `alexGLivePollTick()`, a controllable clock, and healthy per-granularity data for
all 12 configured instruments.

| Fixture | Result |
|---|---|
| LOOP-1 one tick evaluates all 12 instruments | ✅ 12/12 |
| LOOP-2 no cursor lands **ahead** of the H1 boundary | ✅ none |
| LOOP-3 cursors land exactly **on** the boundary | ✅ 12/12 |
| LOOP-4 all 12 re-evaluate after one hour | ✅ 12/12 |
| LOOP-5 a second tick in the same hour re-evaluates nothing | ✅ cadence gate holds |
| RESIL-1 one short-data instrument does not poison the other 11 | ✅ 11/11 healthy |
| RESIL-2 a failing instrument **sets no cursor** → retried, never starved | ✅ |
| RESIL-3 the failure is recorded, instrument named | ✅ |
| RESIL-4 automatic recovery once data returns | ✅ |

## What this refutes

**REFUTED:** scheduling defect · iteration-order defect · cursor-handling defect · `SCAN_PAIRS`
membership (byte-identical in every commit examined) · external cursor advancement (no writer outside
the live path and replay) · `SCAN_PAIRS[0]` special-casing (referenced only by a developer-mode tool).

## What this narrows it to

**RESIL-2 is the decisive one.** A pair whose fetch comes back short returns *before*
`alexGRunSetupEngine`, so its cursor is never set — `lastEval` stays 0, the gate always passes, and
the pair is attempted on **every** tick. It would therefore appear in `instrumentsEvaluated` roughly
**655** times, not zero.

**EUR_USD appears zero times. It is therefore NOT failing the fetch — it is being skipped by the
cursor gate**, which requires its cursor to sit at or ahead of the local `currentH1Boundary` on every
single tick for 56 hours.

**Single remaining hypothesis:** EUR_USD's last *complete* H1 candle in production carries a close
time one boundary ahead of the app's locally-computed `currentH1Boundary` — a data/clock-alignment
condition specific to that instrument, which the synthetic data cannot reproduce.

**The `instrumentsSkipped` diagnostic shipped in `c24b96b` records exactly the two numbers that
settle it** — `lastEvaluatedH1` and `currentH1Boundary`, per skipped pair, per tick. The next time
the campaign runs this is answered from the ledger directly, with no forensics.

GBP_USD is a *different* case: ~54 poll appearances ≈ one per H1 boundary is the **correct** cadence,
so it is being evaluated as designed and producing no setups. Whether that is genuine (no qualifying
structure) or a short-dataset early return is now distinguishable by the same new diagnostic.

---

# PART 1 — REPOSITORY-ONLY AUDIT *(historical; superseded by Part 2 where they differ)*

Window: activation `02:43:57.894Z` → `13:40:51.833Z`, 2026-08-11 (pre-ledger).

**OBSERVED:** 0 paper trades (0 open / 0 closed / 0 journal / 0 evidence packages, balance
$10,000.00). 300 setups qualified across 10 pairs — **299 `IGNORED — BEFORE ACTIVATION`**, **1
`IGNORED — STALE SIGNAL`** (`SIGNAL_TOO_OLD_AT_FIRST_EVALUATION`). First decision event
`13:00:58.008Z`; all 300 evaluated in 28 s; signal age at evaluation min 7.0 h, median 63 days, max
241 days; 80 scans in 40 min at ~24 s once running; tab hidden and unfocused.

**Campaign C1 reference (OBSERVED):** same strategy `alex_g_sr_v1_1`, same engine 12.19.0 — **226
trades / 11 pairs / 128 days = 1.77/day ≈ 12.4 per 7 days**. Its only rejection reason was
`EXISTING_OPEN_TRADE_SAME_PAIR_TIMEFRAME` × 128 against 222 packages: under continuous evaluation the
binding constraint was position concurrency, not signal scarcity. C1 is a **replay**, not a
controlled comparison.

**Instrumentation gap (still open):** 169 `CANDIDATE_REJECTED` events carry empty `diagnostics: {}`,
and `RULE_EVALUATED` events carry `decision: null`. A rule-level funnel is not reconstructable from
the ephemeral log. Part 2 shows the **durable** ledger *does* carry reason codes — so this gap is
specific to the pre-ledger Decision Event log.
