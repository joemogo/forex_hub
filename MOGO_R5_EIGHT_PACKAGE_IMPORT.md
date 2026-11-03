# MOGO R-5: eight-package forward import (B-1 fix + Route A)

Date: 2026-11-03. The branch is committed locally and bundled. **Nothing was pushed, merged or
deployed.** No trading setting, account, position, order or running instance was touched.
`forward_capture.sh` was not used. The live browser profile was not read; only the preserved
checkpoint copy was.

- **Worktree:** `.claude/worktrees/r5-forward-import`
- **Branch:** `claude/r5-forward-import-20261103`, based on `origin/mogo-main` = `1720f8765444f3cfdcbc9912ef7973c810bdb8a7` (re-checked with `git ls-remote`)
- **Commits:**
  - `6fcb05285`: B-1 test fix
  - `210b7afad`: R-5 import
  - a third commit for this report (see the bundle section)

Acceptance criteria came from `MOGO_R6_POST_PUSH_VERIFICATION.md` §8 (r6 worktree) and from
`MOGO-IMPORT-SCOPE-2026-10-20.md` §3, §4 and §8. Earlier investigations were not repeated.

## 1. Verdict: ACCEPTED. Every safeguard held.

| Acceptance criterion | Result |
|---|---|
| Total observations | **271** (263 + 8) |
| Identity manifest | **267 → 275**, 0 conflicts, diff +48/−0 (append-only). A re-run adds 0 |
| Original 263 files | **263/263 byte-identical**. Byte rollup `d929cfd7…` and canonical rollup `a00c9f75…` match the R-6 fingerprint exactly |
| 8 new records | all valid under the deployed validator. After-corpus is 0 invalid out of 271 |
| Duplicate identities | none: 8 unique observationIds, packageIds, contentHashes and sourceTradeIds. No collision with existing ids |
| Idempotent re-import | `convert_all` re-run converts **0**, skips 0 |
| Focused suites | all pass (§4) |
| R-6 mutation harness | **39/39 killed, PASS** |
| Full Python lane | **exactly the 3 pre-existing failures**, with 0 new (§5) |
| Booked P&L | unchanged. All 8 records' `pnl` and `exitPrice` equal their package outcomes. The originals are byte-identical |

## 2. Prior state verified (R-5 not already done)

- No R-5 branch or worktree existed before this run.
- The corpus at `origin/mogo-main` held 263 observations, and the manifest held 267.
- None of the 8 packageIds or contentHashes appeared anywhere under `docs/trader-intelligence/evidence/`.
- None of the 8 sourceTradeIds was in the manifest.

The Route A script checked all of this before any write.

## 3. B-1: test-only correction (`6fcb05285`)

`TestThePreservedCorpusIsUntouched` asserted that **no** corpus record carries an R-6 field. That
was a snapshot oracle. It now asserts the permanent relationship, through
`corpus_r6_violations(record)`:

- **No `executionProvenance`** (the pre-R-6 records): no R-6 field, and no R-6 field in `unknowns`.
- **With provenance:** `executionKind` must be SIMULATED or UNKNOWN, `brokerFill` NONE or UNKNOWN,
  and `executionVerified` exactly `False`. These are literal constants, so widening the validator
  constants cannot widen the test.
- **Every record** still passes `validate_observation`, so malformed provenance is still rejected.

Two tests were added:

- `test_an_R6_field_injected_into_a_pre_R6_record_is_caught`: a positive control, plus every R-6
  field injected into the record and into `unknowns`.
- `test_malformed_or_broker_provenance_is_still_caught`: a positive control on the real EUR/CHF
  gap record. It then sets BROKER kind, a FILLED fill, `verified=True` and a non-object
  provenance. Each must be flagged by the helper **and** refused by the validator.

A positive control also asserts that the pre-R-6 population is non-empty. The suite went from 51
to 53 tests, and the count was updated in `tests/expected_python_test_counts.tsv`.

**Hand mutation of the helper and test: 8/9 killed.** The one survivor removes
`validate_observation` from the corpus-wide loop. It is equivalent while every corpus record is
valid, which was equally true of the original test. Rejection of malformed provenance is pinned
directly by the third test.

No importer, validator or schema code changed. `git diff 1720f8765 HEAD -- scripts index.html
docs/trader-intelligence/evidence/schema` is empty.

## 4. Source verification and import (`210b7afad`)

**Checkpoint `~/MOGO-EVIDENCE-PRESERVED/20261014T115219Z`**

- The manifest says `status: VERIFIED`.
- `shasum -a 256 -c` over the 191 per-file entries gives **191/191 OK**, and there are 191 files
  on disk.
- The copy rollup **re-derives**, using the checkpoint script's own method:
  `91b04116ebee3fe2e9103db0d1996cc11ae4645e47048288e2fab69befcff4cf`.

**Extraction** used the deployed `mogo_evidence_leveldb_extract.js --store <leveldb> --packages
evidence/FWD-20261014T115219Z-PACKAGES.json`:

- 8 recovered, **8 verified, 0 mismatched**, 8 unique sourceTradeIds;
- rollup `3027f0b06a41…`;
- file sha256 **`f343e8b0da4a63648fba02280516ee998480bb9e823dea219769f033cfa5274a`**.

`evidence/` is gitignored, so the staged file is not committed. The source record cites it by
path and hash.

**Route A** ran from scratchpad `r5_route_a.py`. That script refuses any root other than this
worktree. Its order:

1. All checks run **before** the first write, and any inconsistency aborts the run. Nothing is
   skipped.
2. `convert_all` on the one file, then `write_sources`, then `write_observation` for each record,
   with no exception handler.
3. The identity-manifest update.

| | Before | After |
|---|---|---|
| Observations | 263 | 271 |
| Sources | 60 | 61 (`EVSRC\|MOGO\|20261103\|001`) |
| Identity manifest | 267 | 275 |
| Re-import converted | | 0 |
| Manifest re-run added | | 0 |

The new source record is `paper_trade` with `repositoryPath
evidence/FWD-20261014T115219Z-PACKAGES.json` and `contentHash f343e8b0…`. Its metadata holds
`packageCount 8`, `engineStrategyId alex_g_sr_v1`, one engine artifact (`887ac41f0ebc…`, 6
packages), `packagesWithoutEngineArtifact 2` and `strategyFamilyId null`. All of this matches
the scope report §3.

| observationId | Pair | Basis | Gap R | Booked R | Booked pnl | Provenance |
|---|---|---|---|---|---|---|
| `TOBS\|MOGO\|20260921\|001` | CAD/CHF | trigger_level | 0 | +2 | 200 | SIMULATED / NONE / false |
| `TOBS\|MOGO\|20260923\|001` | CAD/JPY | trigger_level | 0 | −1 | −102 | SIMULATED / NONE / false |
| `TOBS\|MOGO\|20261005\|001` | AUD/JPY | trigger_level | 0 | −1 | −100.98 | SIMULATED / NONE / false |
| `TOBS\|MOGO\|20261007\|001` | CAD/CHF | **candle_open_gap** | 0.2239 | −1 | −99.97 | SIMULATED / NONE / false |
| `TOBS\|MOGO\|20261008\|001` | USD/JPY | **UNKNOWN** | **UNKNOWN** | −1.043798 | −104.35 | SIMULATED / NONE / false |
| `TOBS\|MOGO\|20261012\|001` | CHF/JPY | trigger_level | 0 | −1 | −97.93 | SIMULATED / NONE / false |
| `TOBS\|MOGO\|20261014\|001` | AUD/JPY | trigger_level | 0 | −1 | −100.98 | SIMULATED / NONE / false |
| `TOBS\|MOGO\|20261014\|002` | EUR/CHF | **candle_open_gap** | 0.0526 | −1 | −96.95 | SIMULATED / NONE / false |

- **Gap trades.** On both, the modelled executable price differs from the booked `exitPrice`. The
  booking stays at the trigger, under fixed-R.
- **USD/JPY.** `exitPriceBasis`, `exitModeledExecutablePrice`, `exitGapR` and `exitGapPips` are
  listed in `unknowns`. None is defaulted to 0.
- **The other seven** have their exit quotes (bid/ask/spread) UNKNOWN.

## 5. Gates

The suites below ran with `__pycache__` cleared and `MOGO_R6_PACKAGES` set to the extracted file,
so the opt-in complete-package test **ran and was not skipped**.

| Suite | Result |
|---|---|
| `test_import_mogo_observations` | 124 OK |
| `test_balance_reconcile` | 21 OK |
| `test_population_fidelity` | 58 OK |
| `test_identity_manifest` | 41 OK |
| `test_trade_observation` | 48 OK |
| `test_r6_execution_evidence` | 53 OK, 0 skipped |
| `mutate_r6_execution_evidence.py` | 39/39 killed, PASS |
| Re-run after the assimilation write (the 7 suites above plus `test_research_assimilation` and `evidence.test_evidence`) | 770 run, 1 failure = the pre-existing `test_graph` coupling check |

**Reconciliation**

- **`observation_graph_reconcile.py`:** RECONCILED (structure only). 271 preserved, 271 with
  provenance, 0 missing, populations HISTORICAL 221 / FORWARD 41 / RECONSTRUCTED 9, and a
  deterministic rebuild.
- **Population fidelity, base vs after:**
  - FORWARD went from n=31 (7 W / 24 L) to **n=39 (8 W / 31 L)**.
  - One new off-lattice R appeared, −1.0438 (USD/JPY's snapshot exit).
  - The forward period now ends at 2026-10-14T07:22Z.
  - Replay is unchanged, so no forward record leaked into replay.
  - The findings set is unchanged.
- **Accounting (`balance_reconcile.reconcile` over paper_trade records with balances):**
  - checked 28 → 36, with **0 failures** both before and after;
  - 2 ambiguous contributions appear. These are the bounded `[closedAt, capturedAt]` windows of
    v12.42 D4 records, resolved under the operator-accepted G-3 rule.

**Full Python lane** ran on the same machine, in parallel, against a clean archive of
`1720f8765` and against this branch:

| | Tests | Failures |
|---|---|---|
| base `1720f8765` | 1773 | 3 |
| this branch | 1775 (+2 B-1 tests) | **3, the identical set** |

The three failures:

- `test_graph…test_index_html_never_references_trader_intelligence`;
- `test_python_test_counts…POSITIVE_CONTROL_the_real_manifest_is_in_sync`;
- `test_python_test_counts…the_script_runs_as_a_subprocess…`.

`count_python_tests.py --check` output is identical on both: the only drift is
`test_engine_provenance is not registered`, which is pre-existing. The `missing or empty` line is
a subTest message from the gate's own negative fixture.

## 6. Research assimilation (run once, after the gates)

The dry run, then `--write`, produced `LEARN_20261103_a8e46e73e9ec.json` and updated
`current-state.json`. A re-run reports `corpus changed: False`.

The delta matches the scope report §4 leaf for leaf:

- observationTotal 263→271;
- FORWARD n 33→41, Win/Loss 8/25 → 9/32;
- meanR −0.278437 → −0.347128;
- winShare 0.242424 → 0.219512;
- marketExitAt unknown 9→10;
- `alex_g_sr_v1|FORWARD` 31→39.

There are two differences from §4, and both are explained:

- **The R-6 unknown counts are new.** `exitPriceBasis`, `exitModeledExecutablePrice`, `exitGapR`
  and `exitGapPips` are each 1 (USD/JPY). The three exit-quote fields are each 7. §4 was written
  before R-6.
- **Learning kind G is absent.** The kinds are A, B, I, H and F. G fires only when a fidelity
  finding changes. In §4 that change was `REPLAY_IS_BAR_QUANTIZED` disappearing, and R-3 has
  since removed that artifact at source. §8 step 5 predicted exactly this.

No hypothesis verdict or blocker changed.

## 7. Population and interpretation discipline

- The 8 are **FORWARD** (paper_trade source). The population is derived from the source and is
  never denormalised onto the record.
- They are `alex_g_sr_v1` implementation evidence. They are **not** evidence about the trader
  ALEX_G.
- No P&L here is execution-verified: MOGO places no broker orders, and
  `execution_verified_pnl()` refuses to aggregate.
- **Coverage caveat (B-22):** every forward figure above describes the PRESERVED subset, not the
  account.

## 8. Delivery (not executed)

The bundle is `~/Desktop/Forex Hub/.scratch/r5-forward-import-20261103.bundle`. It is based on
`1720f8765` (`origin/mogo-main`) and carries `claude/r5-forward-import-20261103`. Its verification
is recorded in the final response of this session.

**Next action (operator):** review this report and the two content commits. If approved:

1. Re-check that `origin/mogo-main` is still `1720f8765`.
2. Apply with the temp-ref form only:

```
cd ~/Desktop/"Forex Hub" \
  && git fetch .scratch/r5-forward-import-20261103.bundle refs/heads/claude/r5-forward-import-20261103:refs/temp/r5-forward-import-20261103 \
  && git push origin refs/temp/r5-forward-import-20261103:mogo-main \
  && echo "=== DEPLOYED OK ==="
```

If `mogo-main` has moved, re-derive the bundle. Do not resend this command.

## 9. Open, not blocking

- The 3 pre-existing full-lane failures. Registering `test_engine_provenance` in the counts file
  is part of that; the other is the index.html coupling string.
- Extractor defect T-1 (`--out`). It was avoided by using `--packages`.
- The global-halt cost of the fail-closed import.
