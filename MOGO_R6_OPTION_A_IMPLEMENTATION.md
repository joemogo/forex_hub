# MOGO R-6 Option A — implementation report (2026-11-02)

**Status: IMPLEMENTED AND VERIFIED LOCALLY. NOT DEPLOYED. NOTHING IMPORTED.**

- Correction commit: `29f87dee9f721a6e18d72cecb8a7dd86829070c9`, on branch
  `claude/r6-execution-evidence-20261102`, parent `23d7b5b8f` (= `origin/mogo-main`).
  This report is committed on top of it.
- Isolated worktree: `.claude/worktrees/r6-execution-evidence`.
- Nothing was pushed, merged, deployed or imported. No trade, account, paper or live setting,
  checkpoint or `evidence/` file was touched.

Inputs read:
- `MOGO_R6_EXECUTION_EVIDENCE_REVIEW.md` (2026-11-02, session scratchpad).
- The 2026-10-29 R-5 report.
- `MOGO-IMPORT-SCOPE-2026-10-20.md`.

---

## 1. Starting state (verified)

| Check | Result |
|---|---|
| `git ls-remote origin mogo-main` | `23d7b5b8f411c59c86b740cb315d75b6eacb0f34`, unchanged |
| Worktree | new branch from `23d7b5b8f`; `git worktree list` showed no conflicting one |
| Main checkout | `b61bd15e7` on `claude/v12.42.0-exit-fidelity`, untracked set identical before and after |
| P2P86 worktree | `cd0fecd7f`, clean, untouched |
| Packages | the extraction re-verified in the R-6 review (8/8 verified, sha256 `f343e8b0…5274a`, checkpoint 191/191) |

## 2. What was implemented

| File | Change |
|---|---|
| `scripts/trader_intelligence/import_mogo_observations.py` (+217) | `EXECUTION_MAP`, `check_execution_evidence()`, `execution_provenance()` and `ExecutionEvidenceRefused`, wired into `observation_from_package()`. Docstring updated |
| `scripts/trader_intelligence/trade_observation.py` (+151) | 9 fields added to the `OBSERVABLE_FIELDS` whitelist; `FIELD_ROLES`; `_validate_execution_provenance()`, called from `validate_observation()`; `execution_verified_pnl()` |
| `docs/trader-intelligence/evidence/schema/trade-observation.schema.json` (+154) | the new fields, `executionProvenance`, and the missing R-3 fields `closedAtBasis` and `capturedAt` |
| `tests/trader_intelligence/test_r6_execution_evidence.py` (+867, new) | 51 tests |
| `tests/trader_intelligence/mutate_r6_execution_evidence.py` (+386, new) | 39-mutant gate plus a harness self-test |
| `tests/expected_python_test_counts.tsv` (+1) | registers the new suite (51) |

**Every change is an addition (0 deleted lines).** No existing mapping, test or record changed.

### 2.1 Fields. Values are copied unchanged; the only edit is one rename

| Record field | Package field | Role (`executionProvenance.fieldRoles`) |
|---|---|---|
| `exitPrice`, `pnl`, `rMultiple`, `accountBalanceAfter` (existing, unchanged) | as before | `SIMULATOR_BOOKED` |
| `recordedResultR` | `recordedResultR` | `SIMULATOR_BOOKED` (the ledger's fixed-R label) |
| `exitPriceBasis` | `exitPriceBasis` | (statement of the case: `trigger_level` / `candle_open_gap`) |
| `exitTriggerLevel` | `exitTriggerLevel` | `ENGINE_TRIGGER_LEVEL` |
| **`exitModeledExecutablePrice`** | `exitExecutablePrice` | `ENGINE_MODELED_NOT_A_FILL`. Renamed so it can never be read as an executed price |
| `exitGapPips`, `exitGapR` | same | `ENGINE_MODELED_NOT_A_FILL` |
| `exitQuoteBid`, `exitQuoteAsk`, `exitQuoteSpreadPips` | `exitBid`, `exitAsk`, `exitSpreadPips` | `OBSERVED_QUOTE` |

- Any absent value goes into `unknowns`. It is never defaulted to 0 or to `trigger_level`.
- `fieldClassification` is `DIRECTLY_OBSERVED`, in the importer's one existing sense: copied from
  MOGO's own record. What the value **means** is carried by the fixed role table, not by that
  label. This avoided adding a new classification value, which would have been a vocabulary
  change outside R-6.

### 2.2 `executionProvenance` (record-level, on every newly minted MOGO record)

```json
{"executionKind": "SIMULATED", "brokerFill": "NONE", "executionVerified": false,
 "outcomeBasis": "SIMULATOR_BOOKED", "packageMode": "LIVE_PAPER",
 "fieldRoles": {...}, "basis": "identity.mode=LIVE_PAPER; MOGO places no broker orders (...)"}
```

- The kind comes from the package's own `identity.mode`, not from a default.
  - `LIVE_PAPER` or `REPLAY` (the engine's only two modes) → `SIMULATED`.
  - No mode stated → `UNKNOWN` / `UNKNOWN` / `UNKNOWN`, with empty roles. The package is not
    assumed to be simulated.
  - Any other mode → **refused**, because it could be a future real execution path.
- **Prohibitions** (requirement 9), enforced by `validate_observation`:
  - no broker-named top-level key on a MOGO record;
  - `brokerFill` only `NONE` (SIMULATED) or `UNKNOWN`;
  - `executionVerified` only `false`;
  - `outcomeBasis` only `SIMULATOR_BOOKED` or `UNKNOWN`;
  - field roles fixed, never caller-chosen;
  - every recorded booked, modelled or quoted value must have its role;
  - an UNKNOWN kind cannot assign roles;
  - `executionProvenance` is not permitted on HUMAN records.
- `execution_verified_pnl()` always refuses. It is the explicit answer to
  "execution-verified P&L", where otherwise a caller might sum `pnl`.

### 2.3 The seven checks, which fail closed and halt the whole run

`check_execution_evidence()` reads the package, so it checks exactly what the engine stated. It
raises `ExecutionEvidenceRefused`. That is deliberately not an `ObservationRefused`, so `main()`'s
per-record write handler cannot swallow it. `convert_all()` has written nothing at that point, so
a refusal leaves the corpus untouched, and `forward_capture.sh:221-225` exits `FAIL: import step
failed`.

| # | Refused when |
|---|---|
| 1 | `exitPriceBasis` is present but unsupported; or gap evidence is present with no basis |
| 2 | Any of executable, gap pips, gap R or trigger is missing, non-numeric or non-finite; or `candle_open_gap` has a non-positive gap |
| 3 | The modelled price is on the wrong side of the trigger: a **stop** modelled in the position's favour, or a **target** modelled short of the target; or the trigger matches neither stop nor target |
| 4 | `trigger_level` with a non-zero gap, or with a modelled price that is not the trigger |
| 5 | The stated gap disagrees with \|executable − trigger\|/pip or /riskPips (relative 1e-6). The pip rule mirrors `index.html` `pipSize()`, and risk uses `currentStop` as the engine does |
| 6 | A basis on a non-`historical_candle` exit |
| 7 | Booked `exitPrice` ≠ `exitTriggerLevel` (would catch an engine that silently started booking the model) |
| MODE | `identity.mode` present but not `LIVE_PAPER` / `REPLAY` |

**Correction to the R-6 review, check 3.**
- The review said to refuse any executable price "favourable to the position".
- That is wrong for targets. The engine clamps a target exit with `max(open, target)` on a buy
  (`index.html:6812`), so a gap *through* a target is legitimately in the position's favour.
- The naive rule would have refused real winning gap exits. The implemented rule is
  side-correct, and mutant C3b (the naive rule) is killed by
  `test_rule3_a_target_gap_in_the_positions_favour_is_ACCEPTED`.

## 3. Verification. All of it was actually run; counts are exact

### 3.1 The four regression suites, plus the observation validator

| Suite | `23d7b5b8f` baseline | After `29f87dee9` |
|---|---|---|
| `test_import_mogo_observations` | 124 OK | 124 OK |
| `test_balance_reconcile` | 21 OK | 21 OK |
| `test_population_fidelity` | 58 OK | 58 OK |
| `test_identity_manifest` | 41 OK | 41 OK |
| `test_trade_observation` | 48 OK | 48 OK |
| `test_r6_execution_evidence` (new) | n/a | 51 OK (0 skipped, with `MOGO_R6_PACKAGES` set to the extracted originals) |

### 3.2 Full Python lane: every registered suite

The baseline was run in a clean detached worktree at `23d7b5b8f`, created for that run and
removed afterwards.

| | Tests | Failures | Failure set |
|---|---|---|---|
| Baseline `23d7b5b8f` | 1722 | 3 | — |
| After `29f87dee9` | 1773 (+51 = the new suite) | 3 | **identical** (`diff` empty) |

**The 3 failures all predate this change, and they are not hidden:**

1. `test_python_test_counts` …`test_POSITIVE_CONTROL_the_real_manifest_is_in_sync` and
2. …`test_the_script_runs_as_a_subprocess_and_reports_its_verdict` (one subTest message
   line is reported with them): `tests.trader_intelligence.test_engine_provenance` (17 tests) is
   not registered in `expected_python_test_counts.tsv` at `23d7b5b8f`. I registered only my own
   suite. Regenerating the file would have silently registered that one too, and hidden this
   drift.
3. `test_graph` …`test_index_html_never_references_trader_intelligence`: `index.html` contains
   the string `trader-intelligence` at `23d7b5b8f`. `index.html` was not touched here.

### 3.3 The existing 263 observations

| | Before | After |
|---|---|---|
| Count | 263 | 263 |
| Byte rollup (sha256 of name + file sha256, sorted) | `d929cfd77ab213e03f91238fdc1874be0aa6b0b4a5b60fdd8b891fe7067ac9fe` | **identical** |
| Canonical rollup (`json.dumps(sort_keys, compact)`) | `a00c9f75dd3be694d6b1fa621dacaab988d5a4abb5b62ebbed06119e6994577b` | **identical** |
| Per-file byte hashes | — | 263/263 identical |
| Invalid under the NEW validator | 0 | 0 |
| `git diff 23d7b5b8f -- docs/trader-intelligence/evidence/observations sources` | — | empty |

No preserved record carries any R-6 field or `executionProvenance`. The suite asserts this as a
relationship over the real corpus, with no pinned count. The widening backfill cannot add the new
fields (`TestNothingIsRetroactive`, mutant F1).

### 3.4 The eight candidate packages: in memory only, nothing persisted

All 8 were mapped twice: by the importer at `23d7b5b8f` and by this one, both from
`f343e8b0…5274a`.

- **For every package, every pre-existing field and classification is identical.** No unknown
  was lost. Only the new fields and `executionProvenance` were added.
- The test suite repeats this hermetically over verbatim excerpts (§3.6). It also checks the
  untrimmed originals: `TestTheCompleteOriginalPackages` passes, and the originals map identically
  to the excerpts.

| Package | Basis on record | Modelled | Gap R | Quotes | Booked R / pnl (unchanged) |
|---|---|---|---|---|---|
| `PKG\|alex_g_sr_v1\|20261014\|2` EUR/CHF | `candle_open_gap` | 0.93353 | 0.052647 | UNKNOWN | −1 / −96.95 |
| `PKG\|alex_g_sr_v1\|20261007\|1` CAD/CHF | `candle_open_gap` | 0.58313 | 0.223886 | UNKNOWN | −1 / −99.97 |
| `PKG\|alex_g_sr_v1\|20261014\|1` AUD/JPY | `trigger_level` | = trigger | 0 (measured) | UNKNOWN | −1 / −100.98 |
| `PKG\|alex_g_sr_v1\|20260921\|1` CAD/CHF | `trigger_level` | = target | 0 | UNKNOWN | +2 / +200.00 |
| `PKG\|alex_g_sr_v1\|20260923\|1` CAD/JPY | `trigger_level` | = trigger | 0 | UNKNOWN | −1 / −102.00 |
| `PKG\|alex_g_sr_v1\|20261005\|1` AUD/JPY | `trigger_level` | = trigger | 0 | UNKNOWN | −1 / −100.98 |
| `PKG\|alex_g_sr_v1\|20261012\|1` CHF/JPY | `trigger_level` | = trigger | 0 | UNKNOWN | −1 / −97.93 |
| `PKG\|alex_g_sr_v1\|20261008\|1` USD/JPY | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** | bid 157.619 / ask 157.638 / 1.9 pips | −1.043798 / −104.35; `recordedResultR` −1 |

All 8 are `SIMULATED` / `brokerFill NONE` / `executionVerified false`. The booked total is
unchanged at −503.16 (−5.0438R). No figure was re-priced.

### 3.5 Schema coverage

No JSON-schema validator is installed, so I checked the `additionalProperties: false` contract
directly:
- every key of all 263 existing records and of all 8 newly minted records is a schema property.
- Before the schema edit, `closedAtBasis` and `capturedAt`, minted since R-3, were missing from
  the schema. That is pre-existing documentation drift, now closed.
- A test pins the schema enums to the validator's constants.

### 3.6 Focused tests (51)

The fixtures are verbatim **excerpts** of the 8 real packages: only the fields the importer
reads, with every value unchanged. The complete packages are OANDA-derived capture data and stay
out of the repository, like `evidence/`.

| Class | Covers |
|---|---|
| `TestTheFixturesAreTheRealPackages` (2) | 8 packages, 8 hashes; exactly A and B gapped |
| `TestTheGapExitsCarryTheirEvidence` (5) | each field from its package field (an independent table); model beside booking; booking ≠ model; model never named "executable"; SIMULATED/NONE |
| `TestTheControlsKeepTheirClassification` (5) | measured zero gap; none of the 5 trigger exits acquires a gap; snapshot keeps UNKNOWN basis with quotes carried; old format → all 9 UNKNOWN, never 0; no mode → not assumed simulated |
| `TestEveryRealPackageKeepsItsBookedValues` (2) | every OUTCOME/POSITION field = package, on all 8; booked totals = ledger totals |
| `TestInconsistentExecutionEvidenceIsRefused` (17) | each of rules 1–7 and MODE (rule 1 ×2, rule 2 ×4, rule 3 ×3, rule 4 ×2, rule 5 ×2, rules 6, 7 and MODE ×1), plus the favourable-target-gap acceptance. **Each first proves its unmodified package is accepted**, and each asserts *which* rule refused it |
| `TestARefusalHaltsTheWholeRun` (2) | one bad package halts `convert_all` and nothing is written (positive control: the good set converts); not swallowable |
| `TestNoBrokerClaimCanBeRecorded` (12) | CONFIRMED fill, verified execution, broker kind, realized basis, booked→fill relabel, model→quote relabel, missing role, UNKNOWN with roles, broker-named field, extra provenance key, HUMAN provenance; `execution_verified_pnl` refuses. Each asserts its refusal message |
| `TestNothingIsRetroactive` (2) | EXECUTION_MAP ∩ OUTCOME_MAP = ∅; the backfill adds no R-6 field (positive control: it does add `pnl`) |
| `TestThePreservedCorpusIsUntouched` (1) | real corpus, non-empty: no R-6 field, all valid |
| `TestTheSchemaDocumentsTheRecord` (2) | minted keys ⊆ schema; enums = constants |
| `TestTheCompleteOriginalPackages` (1, opt-in) | untrimmed originals map identically to the excerpts |

### 3.7 Mutation testing: `python3 tests/trader_intelligence/mutate_r6_execution_evidence.py`

- The harness self-test passes **9/9**. It refuses to score each of: missing anchor, ambiguous
  anchor, no-op, syntax-invalid, loader-failure, wrong-count and wrong-discriminator mutants;
  recognises a true kill; and rejects the real repo as a mirror.
- The `__pycache__` was cleared before the run. The baseline mirror passes **47/47**.
- **Result: 39/39 KILLED, each by its named discriminator.** Guarded files did not move.

| Group | Mutants |
|---|---|
| Missing evidence | D1–D9 (drop each map entry), U1 (absent→0), U2 (absent basis→`trigger_level`), U3 (no mode→`LIVE_PAPER`), U4 (crossed bid/ask) |
| Invalid gap values / checks | C1, C1b, C2, C2b, C3, C3b (naive rule 3), C4, C5, C6, C7, C8 (unknown mode), H1 (refusal downgraded to a skip) |
| Accidental re-pricing | R1 (exitPrice→model), R2 (pnl and rMultiple scaled by the gap) |
| False broker-fill classification | B1 (importer stamps CONFIRMED), B2–B8 (each validator guard removed), B9 (`execution_verified_pnl` sums), B10 (provenance validation never called) |
| Whitelist / backfill | W1 (whitelist loses the fields), F1 (EXECUTION_MAP joins the backfill) |

## 4. Stop-condition assessment

**Not triggered.** Distinguishing simulation from execution needed:
- **no engine change**, since `index.html` is untouched;
- **no change to existing records**;
- **no new `fieldClassification` value**;
- only additive fields, a validated record-level block, and documentation in the schema.

All of that falls within the reviewed R-6 scope: the importer, the whitelist and the schema.

## 5. Remaining risks and open points

1. **Halting is global.** One future package with inconsistent execution evidence will stop
   *every* import, including through `forward_capture.sh --write`, until someone examines it.
   That is the specified fail-closed behaviour. The cost is that forward evidence waits in
   `evidence/` and in the checkpoint. It is preserved, but not imported, while the halt stands.
2. **The modelled price is unverifiable offline.** The exit candles were not preserved, so the
   0.93353 and 0.58313 figures are carried as the engine stated them. The likeliest driver is the
   21:04 UTC rollover spread, but that is unverified.
3. **Mixed booking conventions remain.** Snapshot exits book the observed quote (slippage in
   `rMultiple`); candle exits book the trigger (gap beside it). This is now visible per record
   through `exitPriceBasis` and the roles, but not reconciled. It is an engine-methodology
   question for the operator.
4. **The pre-R-6 corpus stays implicit.** The 263 existing records do not carry
   `executionProvenance`, so their absence must be read as UNKNOWN. Widening them is an
   operator decision, deliberately not taken here.
5. **Pre-existing red gates (§3.2):** the unregistered `test_engine_provenance` count, and the
   `test_graph` coupling check. Both are untouched, both outside scope (P2/P3).
6. R-1d (`validate_evidence` package witnesses for the new fields) was not added. The import's
   gates do not need it. It is recorded here.

## 6. Delivery (prepared, NOT applied)

- Bundle: `~/Desktop/Forex Hub/.scratch/r6-execution-evidence-20261102.bundle`, covering
  `23d7b5b8f..claude/r6-execution-evidence-20261102`. Its verification is recorded in the final
  session report.
- **Deploying is the operator's decision.** It changes only Python tooling and documentation
  (`index.html` is untouched), so the live PAPER instance is unaffected. Before any deploy
  command is used, `git fetch origin` and confirm `mogo-main` is still `23d7b5b8f`. Then use the
  temp-ref form from CLAUDE.md, never a `+` force-fetch into a working branch.

## 7. Next required action

1. **Operator:** review this branch and bundle, then approve or reject deploying it to `mogo-main`.
2. After it is deployed: run the approved R-5 import plan unchanged (Route A, a fresh worktree
   from the new `mogo-main`, re-extract and require sha256 `f343e8b0…`). Its acceptance criteria
   now also require:
   - `executionProvenance` and the R-6 fields on all 8 records;
   - `candle_open_gap` on exactly the two named packages;
   - UNKNOWN basis on USD/JPY;
   - the 263 preserved records byte-identical.
