# MOGO-002.5 — Repository-Truth Audit (Phase 1)

**Milestone:** Strategy Fidelity Audit · **Date:** 2026-07-29 · **Scope:** ALEX paper-trading implementation.
**Nothing in this document is an assumption.** Every claim cites a file and symbol that was read.

---

## 1. The reconstructed ALEX strategy artifact — IDENTIFIED

`RULES_ALEXG` (`index.html`, resolved live by symbol) is the reconstructed strategy artifact, and it
is a **PROTECTED CONSTANT** in `regression-baseline.json`. It already separates the two evidence
classes this milestone requires be kept apart:

| Field | Count | Meaning |
|---|---|---|
| `ruleVersion` | — | `alex_g_sr_v1` |
| `originalAlexConcepts` | **13** | What the SOURCE states → **the specification** |
| `hubTestStandardizations` | **15** | What MOGO CHOSE → **extra implementation rules** |
| `config` | 20 keys | The parameters actually traded |
| `experimentalParams` | 1 | Explicitly untuned |

**That separation already existed.** MOGO-002.5 did not invent it; it made it machine-readable.
The stop condition "the reconstructed Alex strategy artifact cannot be identified" does **not** apply.

## 2. ⚠️ There are TWO Alex strategies in the repository

| | `alex_g_sr_v1` | `ALEX_SCORE_V2` |
|---|---|---|
| Symbol | `RULES_ALEXG`, `ALEX_MANIFEST` | `ALEX_V2_META` |
| Version | `alex_g_sr_v1` | `1.0.0-research` |
| Method | Support/resistance zone-reaction | Weighted score: HTF trend → AOI → price-action confirmation → 50 EMA |
| **Paper trades?** | **YES — live automatic paper trading** | **NO** — `alexV2AutoTrading.enabled` is `false` and nothing flips it |
| State | `alexGAccount`, `fxhub_alexg_*` | `alexV2Account`, `fxhub_alexv2_*` (fully isolated) |

**The milestone's subject is `alex_g_sr_v1`**, because that is the one that paper-trades.
`ALEX_SCORE_V2` is recorded as extra implementation rule `ALEX_X_008` — a second implementation
claiming the Alex name, in shadow mode, out of scope for this comparison.

## 3. ⚠️ There is a THIRD body of "Alex" knowledge, and it must not be merged

`docs/trader-intelligence/` holds **195 `ALEX_G` claims** from the YouTube educator, all at
`emerging` confidence with **zero rule candidates**.

**It is not this engine's specification, and the repository says so explicitly:**

- `DECISION|MOGO|20260727|004` — JVM's and ALEX's constants describe *what MOGO built*, not what any
  trader teaches.
- `docs/trader-intelligence/traders/alex-g/profile.json` — "ALEX G's rules today are fully specified
  by MOGO's own implementation and documentation … not derived from an external trader's research."

Using those 195 claims as the fidelity baseline would fabricate a lineage the repository denies.
Recorded as knowledge gap **GAP-PROV-001** with an Engineering Authority decision path.

## 4. The central engineering constraint: 48 of 63 protected functions are ALEX

`regression-baseline.json` protects **63 functions and 4 constants**. **48 of the functions are
`alexG*`**, including every rule evaluator that matters:

`alexGConstructLivePosition` · `alexGRunSetupEngine` · `alexGEvaluateBreakRetest` ·
`alexGEvaluateRepeatedReaction` · `alexGClassifyTouch` · `alexGCreateSetupRecord` ·
`alexGDetermineTradeDirection` · `alexGAcceptReaction` · `alexGCorrectedQuality` …

Protected constants: `WEIGHTS`, `ALERT_THRESHOLD`, `RULES`, **`RULES_ALEXG`**.

**Consequences, both of which shaped this milestone's design:**

1. The fidelity toolchain lives in `scripts/strategy_fidelity/` as an **offline audit tool**. It
   reads the repository as data and writes reports; it is never imported by trading code, so it
   cannot alter ALEX behaviour by construction.
2. Trade provenance (Phase 5) is stamped in the **non-protected caller**
   `alexGAttemptOpenLivePosition`, on the object the protected constructor already returned — the
   same additive pattern v12.6.0 used. **Zero drift, verified.**

## 5. Existing infrastructure that already satisfies parts of the brief

**Do not duplicate these.**

| Requirement | Already exists | Evidence |
|---|---|---|
| Rule-level decision tracing | **`mogo.decision-event.v1`** — `RULE_EVALUATED` events carry `ruleId`, `ruleVersion`, `ruleResult`, `reasonCode`, `evidenceCompleteness` | `docs/DECISION_EVENT_ARCHITECTURE.md`; 17 ALEX emit sites |
| ALEX rule IDs in traces | `ALEX_ACTIVATION_CUTOFF`, `ALEX_SIGNAL_STALENESS` | mapped to `ALEX_X_004`, `ALEX_X_003` |
| Candidate lifecycle | `CANDIDATE_CREATED → RULE_EVALUATED → CANDIDATE_APPROVED/REJECTED → TRADE_OPEN_REQUESTED → TRADE_OPENED/FAILED` | v12.6.0 |
| Config snapshot per trade | `configurationSnapshot` (from `snapshotAlexGConfig()`) + `createdByEngineVersion` | on every ALEX position |
| Deterministic JSON / hashing | `graph_common.py` — `canonical_json_bytes`, `content_hash_of`, `atomic_write_text` | reused, not reimplemented |

**Structural limitation, documented not worked around:** `alexGEvaluateBreakRetest` and
`alexGEvaluateRepeatedReaction` are protected AND their `{qualifies:false}` return contract discards
*which* condition failed. Per-condition tracing for the core setup rules is therefore **not
reachable** without a protected-function edit, which governance forbids. Already disclosed in the
v12.6.0 release notes as out of scope; this audit confirms it independently.

## 6. Test coverage of ALEX before this milestone

12 permanent suites, 530 fixtures. ALEX-referencing: `v_paper_trading_audit_tests.js` (376
mentions), `v126_phase2c_wave1_tests.js` (134), `v120_strategy_framework_tests.js` (87),
`v121_jvm_registration_tests.js` (52). **No suite existed for strategy fidelity or trade
provenance** — that gap is closed by `v1027_strategy_fidelity_provenance_tests.js` (61 fixtures).

## 7. Mismatches between roadmap intent and repository implementation

| # | Discrepancy | Evidence | Impact |
|---|---|---|---|
| **FIDELITY-DISC-001** | `RULES_ALEXG.config.zoneTimeframes` is declared but **never read**. All three real loops hardcode `['H1','H4','D','W']`. | `alexGEnsureZoneState`, `alexGRunZoneEngine`, `alexGRunSetupEngine` | Behaviour is correct today, but the config key is dead — a future edit to it would silently have no effect. |
| **FIDELITY-DISC-002** | The specification contains **zero risk rules**, yet the engine trades a full risk model. | `hubTestStandardizations`: the stop/TP/risk/R:R mechanism is "100% unaddressed by the source" | Every stop, target and position size has no source authority. Risk fidelity is **undefined**, not merely unverified. |
| **FIDELITY-DISC-003** | The specification contains **zero trade-management rules**. | no `originalAlexConcepts` entry addresses an open position | Exit behaviour is entirely unspecified. |
| **FIDELITY-DISC-004** | "MOGO-002.5" appears nowhere in `docs/ROADMAP.md` or any ADR. | `grep` returned no match | This milestone has no approved ADR. Its artifacts are additive and non-behavioural, but **Engineering Authority may wish to record an ADR** before the model is depended upon. |
| **FIDELITY-DISC-005** | Two strategies claim the Alex name; one paper-trades, one does not. | §2 above | Any report saying "ALEX fidelity" must state which. |

## 8. Audit conclusion

The reconstructed artifact exists, is protected, and already distinguishes source concepts from
MOGO's own standardizations. **No stop condition was triggered.** The milestone proceeded through
all eight phases without altering trading behaviour: 591/591 fixtures pass and all 63 protected
functions and 4 protected constants remain byte-identical to the committed baseline.
