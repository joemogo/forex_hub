# PROPOSAL-001 — Instrument Abstraction

**Status:** Proposal only. **Nothing in this document has been implemented.**
**Requires:** an `OwnerDecision` with `decisionType: architectural` before any code is written.
**Prerequisite for:** any modeling, replay, or execution work on a non-FX strategy.

---

## 1. Problem

MOGO models market concepts in terms of **forex**, not in terms of markets. This was invisible
while every strategy was an FX strategy. The first real knowledge intake — a US index strategy —
made it structural.

**Evidence from the codebase (verified, not assumed):**

| Fact | Detail |
|---|---|
| Risk math is pip-denominated | `pipSize` (42 references), `pipValue` (52), `pips` (35) in `index.html` |
| The domain noun is "pair" | Call sites read `pipSize(pos.oPair)`, `pipSize(setup.pair)`, `pipSize(pos.pair)` |
| Both sizing utilities are protected | `pipSize` and `pipValuePerLot` are 2 of the 63 protected functions, covered by the shared `riskFingerprint` that JVM **and** ALEX depend on |

**Evidence from the intake:**

| Fact | Detail |
|---|---|
| The strategy is index-based | *"I am trading US indexes such as the S&P 500 and NASDAQ"* — zero currency pairs in 397 lines |
| The data model already knows | `BLUEPRINT\|TJR\|20260727\|001.scope.instruments = ["NASDAQ", "S&P 500"]` |
| The trader record disagrees | `traders/tjr/profile.json` says `"markets": ["forex"]`, carried into the profile as `confirmed` with **zero evidence** (defect D1) |

Index futures are quoted in **points and ticks with a contract multiplier** (ES ≈ $50/point,
NQ ≈ $20/point), not pips and lots. **There is currently no way to express an index strategy's risk
in MOGO's risk model at all.** This is a missing domain concept, not a mislabeled file.

## 2. Goals

1. Model market concepts (quotation, tick value, sizing, sessions) **independently of asset class**.
2. Let a `StrategyRule`, `StrategyBlueprint`, or scanner be scoped to instruments and behave
   correctly for each.
3. Detect, rather than silently accept, an unevidenced trader/market classification (defect D1).
4. **Change zero existing trading behavior.** JVM and ALEX must produce byte-identical decisions.

## 3. Non-goals

- Not adding index execution, a broker connector, or market data for any new asset class.
- Not porting TJR's strategy to forex. SMT divergence compares two correlated indices; an FX
  analogue would be **a different rule requiring its own evidence**, not a reinterpretation.
- Not modifying `pipSize` or `pipValuePerLot`. They stay byte-identical (see §5).
- Not changing any UI in this proposal.

## 4. Proposed model

### 4.1 `Instrument` record

A new registry under `docs/trader-intelligence/instruments/`, one JSON per instrument, following the
existing deterministic-ID and atomic-write conventions.

| Field | Notes |
|---|---|
| `instrumentId` | `INSTR\|{SYMBOL}` e.g. `INSTR\|ES`, `INSTR\|EURUSD` |
| `symbol`, `displayName`, `aliases` | `aliases` lets evidence text ("S&P 500", "ES", "SPX") resolve to one instrument |
| `assetClass` | `fx` \| `index_future` \| `index_cfd` \| `metal` \| `crypto` \| `equity` \| `other` |
| `quoteUnit` | `pip` \| `point` \| `tick` — **the key discriminator** |
| `tickSize`, `tickValue`, `contractMultiplier` | Nullable where not applicable |
| `quoteCurrency`, `pricePrecision` | |
| `sessionCalendarId` | Points at a session definition; index and FX session boundaries differ |
| `dataAvailability` | `none` \| `replay_only` \| `live` — honest about what MOGO can actually get |
| `provenance`, `schemaVersion`, `createdAt` | Matches existing record conventions |

Seeded initially with the FX pairs MOGO already trades (`quoteUnit: pip`, values read from the
existing frozen functions so nothing changes) plus `ES` and `NQ` as `dataAvailability: none`.

### 4.2 Risk sizing dispatch — additive only

Introduce a **new** entry point, e.g. `instrumentRiskPerUnit(instrumentId, ...)`, that:

- for `quoteUnit: pip` → **delegates to the existing `pipSize`/`pipValuePerLot`, unchanged**;
- for `quoteUnit: point`/`tick` → computes from `tickSize`/`tickValue`/`contractMultiplier`.

No existing call site changes in this phase. JVM and ALEX continue calling `pipSize` directly, so
the shared `riskFingerprint` is untouched and drift stays zero. Migrating call sites is a separate,
later, individually-gated step — explicitly **not** part of this proposal.

### 4.3 Scoping records by instrument

The data model is largely ready: `StrategyRule.supportedMarkets` and
`StrategyBlueprint.scope.instruments` already exist. Proposed additions:

- `Instrument.instrumentId` referenced from `StrategyRule` (new optional `supportedInstrumentIds`).
- `traders/{id}/profile.json` gains `instruments` alongside `markets`, and `markets` becomes
  derivable rather than hand-asserted.
- New graph node type `INSTRUMENT` and edge types `RULE_APPLIES_TO_INSTRUMENT`,
  `EVIDENCE_MENTIONS_INSTRUMENT` — additive, mirroring how Phase 7A added its four node types.

### 4.4 Defect D1 — evidence must be able to contradict a baseline

`trader_profile.py:141-143` copies Wave-1 `markets`/`sessions` then overrides status to
`"confirmed"`, so `markets: [forex]` is asserted confidently with `evidenceIds: []`. Proposed:

- Status becomes `"unevidenced"` (new `PROFILE_CONCEPT_STATUSES` value) when `evidenceIds` is empty,
  instead of `"confirmed"`.
- New integrity check `BASELINE_CONTRADICTED_BY_EVIDENCE` (severity `WARNING`) firing when a
  baseline `markets`/`instruments` value has no evidence *and* the evidenced instruments resolve to
  a different `assetClass`. On current data this fires immediately for TJR — which is the point.

## 5. Safety and risk

| Risk | Mitigation |
|---|---|
| Protected-function drift | Nothing touches `pipSize`/`pipValuePerLot`. `regression-baseline-tools.py` must report zero drift as an acceptance gate. |
| JVM/ALEX behavior change | No existing call site is modified. Acceptance gate: 530/530 JS fixtures pass and the baseline registry reports MATCH for JVM, ALEX, and shared-risk. |
| Integrity report stops being clean | `BASELINE_CONTRADICTED_BY_EVIDENCE` will fire on TJR. Intended. Land it as `WARNING`, not `ERROR`, so it does not block. |
| Schema churn | All additions are optional/additive; `schemaVersion` bump with backward-compatible `or {}` defaults, exactly as Phase 7A extended `query_evidence`. |
| Scope creep into execution | `dataAvailability: none` for ES/NQ makes it structurally impossible to trade an instrument MOGO has no data for. |

## 6. Suggested phasing

| Phase | Content | Gate |
|---|---|---|
| **A** | `Instrument` schema + registry + FX seed records mirroring current values. No behavior change anywhere. | Zero drift; all suites green |
| **B** | `instrumentRiskPerUnit()` dispatch layer (unused by JVM/ALEX). Unit tests proving FX path is numerically identical to `pipSize`/`pipValuePerLot`. | Byte-identical FX results |
| **C** | Graph node/edge types; blueprint and trader-profile instrument scoping; defect D1 fix + `BASELINE_CONTRADICTED_BY_EVIDENCE`. | Graph integrity has no new ERROR/FATAL |
| **D** *(separate milestone, not authorized here)* | Migrate JVM/ALEX call sites to the dispatch layer. | Requires its own OwnerDecision |

## 7. Open questions for the owner

1. **Is MOGO an FX product that studies other markets, or a multi-asset product?** Phase D only
   makes sense under the latter. Phases A–C are worth doing either way, because they fix D1 and let
   research be scoped honestly.
2. Should `Instrument` live under `docs/trader-intelligence/` (research data) or somewhere shared,
   given it will eventually be consumed by runtime code?
3. Do ES/NQ enter as futures contracts, CFDs, or both? It changes `contractMultiplier` handling and
   the session calendar.
4. Should `traders/{id}/profile.json.markets` be corrected for TJR now (to US indices), or left
   until the D1 check exists so the correction is evidence-driven rather than manual?

## 8. Relationship to other work

- **Blocks:** all replay-validation items in `BACKLOG-001` that require P&L or position sizing.
- **Blocked by:** nothing technical. Question 1 above is the only real gate.
- **Related defects:** D1 (fixed here), D2/D4 (independent, see the pre-commit report §13).
