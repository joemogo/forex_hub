# ADR-011 — Market Data Completeness Contract

**Status:** Accepted · **Date:** 2026-08-01 · **Milestone:** MOGO-003
**Fixture:** `tests/v130_candle_completeness_regression_tests.js`
**Related:** [ADR-004](ADR-004-read-only-analytics-principle.md) · [ADR-010](ADR-010-evidence-package-persistence.md)

---

## Context

MOGO requests a fixed candle lookback and then evaluates signals and confluence over whatever
comes back. Until now, "whatever comes back" was a bare array with no indication of whether the
request had actually been satisfied.

Verified behaviour before this contract (measured, not assumed — see
[KNOWN_ISSUES.md](../KNOWN_ISSUES.md)):

| Path | Requested | Returned | Consumer could tell? |
|---|---|---|---|
| `fetchCandles()` + HTTP 429 | 220 | `null` | ✅ yes — `null` is unambiguous |
| `fetchCandles()` + HTTP 200 with 80 complete candles | 220 | 80-length array | ❌ **no** |
| `fetchCandlesRange()`, page 2 HTTP 429 | 220 | 80-length array after 2 pages | ❌ **no** |
| `scanPair()` on an 80-candle response | 220 | `signals=1`, `conf.total=20` | ❌ **no** |

The only protection was `if(!candles||candles.length<10)` inside `detectSignals()` and
`scoreConfluence()`. **That guard bounds the minimum usable length; it says nothing about whether
the requested lookback was satisfied.** Eighty candles clears it effortlessly, so a materially
truncated history scored confluence indistinguishably from a full one.

An initial audit attributed this to pagination failing on HTTP 429 inside `fetchCandles()`.
Test-first investigation disproved that specific mechanism. The lesson that shaped this ADR is
that **transport-level reasoning misidentified the defect**: consumers had been reasoning about
HTTP status when the actual risk arrived through a perfectly successful HTTP 200.

---

## Decision

### 1. One abstraction: `completenessState`

Every market-data producer classifies its result into exactly one of three states, and
**consumers depend on this value alone**:

| State | Meaning |
|---|---|
| **`COMPLETE`** | The requested lookback was fully satisfied. Safe for signal, AOI, swing-point and confluence evaluation. |
| **`PARTIAL`** | Some usable history was returned, but the request was **not** fully satisfied. Not safe for evaluation. |
| **`UNAVAILABLE`** | No usable history. Includes transport failure, empty responses, and results below the minimum usable length. |

```js
const MARKET_DATA_COMPLETENESS = Object.freeze({
  COMPLETE:'COMPLETE', PARTIAL:'PARTIAL', UNAVAILABLE:'UNAVAILABLE'
});
```

### 2. Consumers must never branch on transport details

`httpStatus`, `paginationTerminationReason`, `pagesRequested`, `pagesReceived`,
`fetchDurationMs` and `retryCount` are recorded **as diagnostics** — for forensics, Evidence
Packages and operator display. **No consumer may make an evaluation decision from them.**

This is the load-bearing rule. A consumer that branches on `httpStatus === 429` re-creates the
original defect, because the case that actually reached scoring was `httpStatus === 200`. New
transports (a different broker, a cache, a replay dataset) must be expressible as one of the three
states without any consumer changing.

### 3. `PARTIAL` does **not** assert that market data is missing

**`PARTIAL` means "the request was not fully satisfied." It never means "N candles are missing."**

MOGO cannot infer missing market candles by subtracting `receivedCount` from `requestedCount`:
session boundaries, weekends, holidays, instrument availability and thin liquidity all produce
legitimate gaps. A short response may mean the instrument genuinely has no more history.

**Therefore no `missingCandles` field exists, and none may be introduced.** MOGO records what it
asked for and what it observed, and draws no conclusion about the market from the difference.
`PARTIAL` is a statement about *the request*, not about *the market*.

### 4. Classification uses the RAW response size, never the post-filter size

Candle arrays are filtered to `complete: true` before use, and the most recent candle is almost
always still forming. Comparing the **filtered** length against the requested count would classify
essentially every healthy scan as `PARTIAL`.

**Classification therefore compares the raw response size against the requested count.** This trap
was already discovered once in this codebase — `fetchCandlesRange()` carries a comment describing
the identical mistake and its fix. This ADR makes the rule explicit so it is not rediscovered a
third time.

### 5. Producers attach state without changing their return type

`fetchCandles()` has twelve call sites and `fetchCandlesRange()` has nine. Changing either to
return a wrapper object would touch every one of them for no safety gain.

**State is attached to the returned array as non-enumerable properties.** Existing consumers are
byte-for-byte unaffected — iteration, `.length`, `JSON.stringify` and `for...in` all behave exactly
as before — while completeness-aware consumers read `completenessState` directly. `null` continues
to mean `UNAVAILABLE` and needs no attachment.

### 5a. Attachment durability — measured, not assumed

**`completenessState` does not survive copying or transformation.** Non-enumerable properties are
not carried over by any array-producing operation. Measured, and pinned by fixture `CONTRACT-1`:

| Operation | State |
|---|---|
| direct producer return | ✅ preserved |
| `.slice()` · `.map()` · `.filter()` · `.concat()` · spread · `Array.from()` · JSON round-trip | ❌ **lost** |

**This is acceptable for the current call paths, and that is verified rather than asserted:**

- The **only** reader is `scanPair()`, which classifies `fetchCandles()`' return value directly,
  with no intervening copy (`CONTRACT-2`, enforced in both source and behaviour).
- `pairData` is session-only and never persisted.
- `scanPair()` immediately copies the state into `pairData[pair].completenessState` as a **plain
  enumerable field**, which *does* survive serialization (`CONTRACT-3`). The fragile form exists
  only on the producer→consumer hop; everything downstream reads the durable copy.

**`marketDataCompletenessOf()` fails closed:** an array with no classification returns
`UNAVAILABLE`, never an optimistic `COMPLETE`. So even if a future consumer *did* classify a copy,
the result is over-suppression — visible and safe — rather than a truncated history being scored.

**Rule for future consumers:** read `pairData[pair].completenessState`, or classify the producer's
return value directly. **Never re-derive completeness from a transformed array, and never assume
`COMPLETE` from its absence.** If a transform-surviving carrier is ever genuinely needed, change
the producer's return type deliberately — do not sprinkle re-classification at call sites.

### 6. Producers classify; consumers gate

A producer never decides what a consumer should do. `scanPair()` gates evaluation by passing
`null` into the protected evaluators when the state is not `COMPLETE` — relying on the guards those
functions **already** have, so no protected function is modified.

---

## Consequences

**Gained**

- A truncated history can no longer produce a signal or a confluence score that is
  indistinguishable from a full-lookback one.
- The completeness question is answered once, by the producer, instead of being re-derived
  (or ignored) by each of twenty-one call sites.
- Future transports slot in behind the same three states.

**Accepted**

- **An instrument whose genuine history is shorter than the requested lookback will be classified
  `PARTIAL` and will not be scanned.** MOGO cannot distinguish "truncated response" from "this
  instrument only has this much history", and this ADR deliberately chooses the conservative
  reading. If a legitimately short-history instrument is ever needed, the fix is a per-request
  lookback that the instrument can satisfy — **not** a relaxation of this contract.
- Suppression is silent to the trading path by design. It must **not** be silent to the operator:
  the state belongs in Diagnostics and any evidence record.
- Non-enumerable properties are invisible to `JSON.stringify`. Anything persisting completeness
  into an Evidence Package must copy the value explicitly.

**Rejected**

- **A `missingCandles` count** — unsound (§3).
- **Branching on `httpStatus` at consumers** — this is precisely what misdiagnosed the original
  defect (§2).
- **Relaxing the length guards instead** — they bound minimum usability, a different question.
- **Changing the producers' return type** — twenty-one call sites, no safety gain (§5).
