# MOGO M5: final integration onto R-5 `mogo-main`

Dates: 2026-11-10 (merge staged, gates run) and 2026-11-12 (resumed, verified, committed).
**Verdict: PASS, integrated locally.**

Nothing was pushed or deployed. No broker request, order, close, cancellation, credential change,
journal change or scheduler activation was made. The original M5 branch, the executor branch and
the R-5 branch were not modified.

## 1. Branch, base and integration

| Item | Value |
|---|---|
| Worktree | `.claude/worktrees/m5-on-r5` (new; created with `--no-track`, no upstream) |
| Branch | `claude/m5-on-r5-integration-20261110` |
| Base | `origin/mogo-main` = `031bd605e28b2f0155f1c8ba4efdee54cbd21496` (R-5). Re-checked with `ls-remote` on 11-10 and on 11-12 |
| Merged | `c33364e6435f5d9e7b1357b4183435ff2a3cf2ac`: M5 integration report, over merge `5adfdfa96` = `1720f8765` + executor `caeb1a021` |
| Merge commit | `e9d29632dbec7b7cbd3389414f8cc764ca4ba7e8` (parents `031bd605e`, `c33364e64`), tree `d2c4a4df…` |
| Release tip | the report commit on top of `e9d29632d` (§9) |

- **Method.** `git merge --no-ff c33364e64`. Both sides fork from `1720f8765`, so a true merge is the simplest history-preserving option: no rebase, no squash, no rewritten or duplicated commits.
- **Source branches unchanged on 11-12:** M5 `c33364e64`, executor `caeb1a021`, R-5 `031bd605e`.

## 2. Files and conflicts

There was exactly **one** conflict, in `tests/expected_python_test_counts.tsv`. Two adjacent rows clashed, and the resolution keeps both valid registrations:

| Row | R-5 | M5 | Resolved |
|---|---|---|---|
| `test_python_test_counts` | 12 | 13 | **13** |
| `test_r6_execution_evidence` | 53 | 51 | **53** |

Proof that nothing else moved:

- **Against `031bd605e`** (M5's side): the merge changes 45 files (+8313/−10). That is exactly M5's own file set against `1720f8765`.
- **Against `c33364e64`** (R-5's side): it changes 15 files (+1238/−16). That is exactly R-5's file set.
- **Every other file** is blob-identical to the side that introduced it. Only the TSV differs from both sides.
- **R-5 paths:** `docs/trader-intelligence/` is identical to `mogo-main`.

## 3. Tests and mutation gates

All gates ran on a `checkout-index` export of the staged tree, with `__pycache__` cleared, `HOME` pointed at an empty directory and network egress denied by the sandbox.

On 11-12, `diff -rq` showed that export to be **byte-identical** to the staged tree, and the committed tree hash equals it. So these results apply to `e9d29632d`, and none of them was re-run.

| Gate | Result |
|---|---|
| `test_oanda_practice` / `_m2` / `_m3` / `_m4` | 53 / 37 / 30 / 50 = **170, all OK** |
| `demo_offline_lifecycle.py`, `demo_m4_practice_trade.py` | exit 0, exit 0 |
| `mutate_oanda_practice.py` | **107/107 killed**, sources restored |
| `mutate_oanda_practice_m3.py` | **21/21 killed** |
| `mutate_oanda_practice_m4.py` | **52/52 killed** (including RB11) |
| `test_r6_execution_evidence` (B-1) | 53 OK, 1 skip (see below) |
| `test_identity_manifest` | 41 OK |
| `count_python_tests.py --check` | exit 1. The only drift is `test_engine_provenance is not registered`, which is pre-existing |
| Full Python lane (40 modules, as `run_all.sh` enumerates them) | **1946 tests: 3 failures, 1 skip** |

- **The 1 skip** is the opt-in complete-package test. It needs `evidence/`, which this sandbox cannot read. It passed on 11-03.
- **Lane arithmetic:** 1946 = M5's 1944 + R-5's 2 B-1 tests.
- **The 3 failures are the established baseline**, not regressions:
  - `test_graph…index_html_never_references_trader_intelligence`;
  - `test_python_test_counts…POSITIVE_CONTROL_the_real_manifest_is_in_sync`;
  - `test_python_test_counts…the_script_runs_as_a_subprocess…`.
- **The fourth `FAIL:` line** in the log ("tsv is missing or empty") is the count gate's own negative-fixture subTest message. It is not a fourth failure.
- **Not run:** the JS/node lanes of `run_all.sh`. The merge changes no JS and no `index.html`.

## 4. R-5 preservation (merged tree)

| Check | Result |
|---|---|
| Observations | 271; 0 duplicate `observationId` / `sourceContentHash` |
| Identity manifest | 275; 0 duplicate tradeIds |
| R-6 provenance | 8 records, all `SIMULATED / NONE / executionVerified=false` |
| Graph reconcile | RECONCILED: HISTORICAL 221 / FORWARD 41 / RECONSTRUCTED 9, sources 61, provenanceMissing 0, deterministic rebuild |

These figures are identical to the 11-10 post-deployment verification of `mogo-main`.

## 5. Practice-only safeguards (targeted source inspection)

| Safeguard | Evidence in the merged tree |
|---|---|
| Practice host only | `PRACTICE_HOST = "api-fxpractice.oanda.com"`; `fxtrade` occurs 0 times in `execution/` |
| No host or environment override | `_FORBIDDEN_KEYS = ("host","url","baseUrl","environment","env","live")` |
| Network code confined | only `oanda_practice_m3/readonly.py` imports a network module (A2 GET-only) |
| Separate A3 entry and close authorization | `A3WriteOpener`, `EntryGrant`, `CloseGrant` |
| Absolute entry-price limit | `ENTRY_LIMIT_FIELD = {"BUY": "maxEntryPrice", "SELL": "minEntryPrice"}`; `PRICE_BOUND_BEYOND_APPROVED_ENTRY_LIMIT` |
| Duplicate-order protection, write-ahead journal | `clientExtensions` in 3 files; journal intents |
| Stop confirmation | `stopLossOnFill` |
| Stale price, spread and risk cap | `QUOTE_STALE`, `SPREAD_TOO_WIDE`, `LOSS_AT_STOP_EXCEEDS_MAX_LOSS` |
| Fail-closed reconciliation | `_reconcile_position` with closed-trade 404 handling (mutations RA1–RA5) |
| Kill switch | `kill.py`, plus executor KILL checks |
| No autonomy | 0 `while True` / sched / cron / Timer / asyncio in `execution/` |

Every one of these guards is pinned by the mutation gates in §3.

**Governance (`mogo_rules.json`).** The change only adds:

- 42 → 43 leaves;
- the one changed leaf, the PAPER posture, keeps its old text as an exact prefix and appends one sentence;
- the added rule is `MOGO Broker-Practice Execution`.

**`CLAUDE.md`** gains a broker-practice paragraph and loses nothing.

The governance rule is **not installed**. Installation stays an operator step.

## 6. Security scan

| Check | Result |
|---|---|
| Real token, account ID and its middle segment | read in memory from `~/.mogo/oanda_practice.json`, never printed. **0 hits** in the full merge diff, and 0 in the commit messages. A positive control passed |
| Generic patterns | 14 hits, all benign: the synthetic placeholder accounts `101-004-1234567-001` and `101-004-7654321-001` in tests, demos and fixtures, and the bare `Bearer ` header prefix with no token |
| Binary files | none |
| Suspicious added paths | only `execution/oanda_practice/journal.py`, which is source code, not a journal. No sqlite, db, env, order, close or authorization files |

## 7. Operator state (read-only hashes; nothing opened for writing)

| File | sha256 prefix | Matches the 11-09/11-10 record |
|---|---|---|
| `~/.mogo/practice_state/journal.sqlite3` | `023f7e9b967c6181` | yes (no -wal or -shm present) |
| `~/.mogo/oanda_practice.json` | `3d7ef28eae9091cf` | yes |
| `~/.mogo/order-0003.json` | `ab566751f923b9a7` | yes |
| `~/.mogo/close-0001.json` | `c6dca47c6b799871` | yes |

## 8. Remaining blockers and uncertainties

- **P3, pre-existing:**
  - `test_engine_provenance` is unregistered, which keeps the count gate red on `mogo-main` and here alike;
  - the `test_graph` index.html coupling check.

  Neither is fixed here. Changing unrelated tests to go green is out of scope.
- **P3:** `clear-halt` accepts a second CLEAR of an already-cleared halt. It is cosmetic, and recorded in the M5 report.
- **The opt-in R-6 package test** was not runnable here, because of the sandbox restriction on `evidence/`.
- **Governance:** deploying this puts a broker-practice executor on the branch the live instance serves. The executor is inert unless invoked, and every broker contact stays separately operator-authorised. The `mogo_rules.json` rule also still needs installing by the operator, via `install_mogo_delta_only.py`.

## 9. Release and deployment (prepared, NOT executed)

| Item | Value |
|---|---|
| Release tip | in the final response of this session (the report commit over `e9d29632d`) |
| Bundle | `~/Desktop/Forex Hub/.scratch/m5-on-r5-integration-20261110.bundle`, based on `031bd605e` |

**Pre-check.** It must print `031bd605e28b2f0155f1c8ba4efdee54cbd21496`. If it prints anything else, STOP and re-derive the bundle.

```
cd ~/Desktop/"Forex Hub" && git ls-remote origin mogo-main
```

**Deploy.** Temp ref, no `+`, working branch untouched.

```
cd ~/Desktop/"Forex Hub" \
  && git bundle verify .scratch/m5-on-r5-integration-20261110.bundle \
  && git fetch .scratch/m5-on-r5-integration-20261110.bundle refs/heads/claude/m5-on-r5-integration-20261110:refs/temp/m5-on-r5-integration-20261110 \
  && git push origin refs/temp/m5-on-r5-integration-20261110:mogo-main \
  && echo "=== DEPLOYED OK ==="
```

**Post-deploy checks** (read-only):

- `git ls-remote origin mogo-main` equals the release tip;
- `git diff --stat 031bd605e origin/mogo-main` shows 46 files: M5's 45 plus this report;
- on a clean export, `observation_graph_reconcile.py` reports RECONCILED with 271 observations.

## 10. Operator action

Review this report, then decide whether to deploy. If you approve, run the §9 pre-check and then the deploy command.
