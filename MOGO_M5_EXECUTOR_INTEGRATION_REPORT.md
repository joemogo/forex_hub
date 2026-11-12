# MOGO M5 — controlled integration of the OANDA practice executor

**Date:** 2026-11-09.
**Result:** the M1–M4 executor is integrated **locally** onto the mogo-main line, as merge commit **`5adfdfa96`** on the new branch **`claude/m5-oanda-executor-integration-20261109`**. This report is committed as the next commit on that branch.

**What was not done:**
- No push, remote merge or deployment.
- No broker contact of any kind: not even A2 reads.
- No credential changes, no new authorization, no change to any risk limit.

## 1. Initial pointers (verified, not assumed)

**Remote.** `git fetch origin` succeeded (the github.com egress was allowed for this command only).

| Ref | Commit | Note |
|---|---|---|
| `origin/mogo-main` | `1720f8765` | R-6 report, 2026-11-02. Unchanged after the fetch. This is the latest remote mogo-main |
| local `mogo-main` | — | **Does not exist.** Only the remote-tracking ref exists |
| `origin/main` | `abfc7634f` | 2026-07-16. Not the development line |
| `claude/m1-oanda-practice-executor-20261103` | `caeb1a021` | The executor. Its worktree was clean apart from 6 untracked reports |
| Main checkout (`Forex Hub/`) | `b61bd15e7` on `claude/v12.42.0-exit-fidelity` | **Not touched**, along with its untracked files |

**Ancestry.**
- `origin/mogo-main` **is an ancestor** of `caeb1a021`, with 12 executor commits on top and 0 commits behind.
- Every local branch was checked against `origin/mogo-main`. Only three contain it, and each has newer work on top:

| Branch | Ahead of mogo-main | Files | Overlap with the executor |
|---|---|---|---|
| `claude/r5-forward-import-20261103` (`031bd605e`) | 3 | 15 (R-5 evidence import) | **`tests/expected_python_test_counts.tsv` only** |
| `claude/first-paper-trade-readiness-20261103` (`1cbb6f7e6`) | 1 | `MOGO_FIRST_PAPER_TRADE_READINESS.md` | None |
| `claude/m1-oanda-practice-executor-20261103` | 12 | 44 | — |

- **None of those branches is integrated here.**
- All other local branches predate mogo-main and lack it.

## 2. What is integrated

**Method.** A `--no-ff` merge of `claude/m1-oanda-practice-executor-20261103` onto `origin/mogo-main`.
- It is the smallest safe method, because mogo-main is a direct ancestor.
- The merge was computed first in a temporary index (`read-tree -m`): **0 conflicts**, and the merged tree is **identical to `caeb1a021`'s tree** (`6ac875403…`).
- The commit was then made with `commit-tree`, and the branch advanced with a compare-and-swap `update-ref` (its old value checked against `1720f8765`).
- **No working tree was switched, reset or checked out** to create it (see §6, incident).

**Commits brought in** (oldest first):

| Commit | Content | Kind |
|---|---|---|
| `5217ef17f` | M1 offline executor core | code + tests |
| `93ea70ca0` | M1 report | report |
| `b67a98f05` | Register `tests/execution` in run_all.sh and the count gate | shared test infra |
| `a0e9069da` | M2 fills, protection, closing, accounting | code + tests |
| `a2e63c0d7` | Governance rule `MOGO Broker-Practice Execution` | governance |
| `da33723d8` | M2 report | report |
| `f393e3e46` | M3 prep: delta-only governance installer | script + tests |
| `8a8454788` | M3 read-only GET boundary and preflight | code + tests |
| `17e7dff7c` | M3 `--cafile`, rejection status, report | code + report |
| `b50c0d564` | M4 A3-gated write path | code + tests |
| `e1148f9a3` | M4 report hash | report |
| `caeb1a021` | M4 repair: closed-trade 404; approved absolute entry limit | code + tests + fixture |

**Files changed versus mogo-main: 44** (+8098 / −10).

| Group | Files |
|---|---|
| Executor code | `execution/oanda_practice/` (13), `execution/oanda_practice_m3/` (3), `execution/oanda_practice_m4/` (2), `execution/mogo_practice_{executor,preflight,trade}.py` |
| Tests | `tests/execution/`: 4 suites, 3 mutation gates, fake broker, 2 demos, 2 fixtures |
| Shared test infrastructure | `tests/run_all.sh`, `tests/count_python_tests.py`, `tests/expected_python_test_counts.tsv`, `tests/trader_intelligence/test_python_test_counts.py` |
| Governance | `scripts/auto_mode/mogo_rules.json` (one soft_deny rule **added**, one posture sentence added); `scripts/auto_mode/install_mogo_delta_only.py`; `CLAUDE.md` (one paragraph) |
| Reports (already committed on the branch) | `MOGO_M1_…`, `MOGO_M2_…`, `MOGO_M3_PREPARATION.md`, `MOGO_M3_READ_ONLY_CONNECTION_REPORT.md`, `MOGO_M4_FIRST_PRACTICE_TRADE_PREPARATION.md` |

**Not integrated, deliberately:**
- **Six untracked trade-day reports** stay untracked in the executor worktree for the operator to decide on:
  - `MOGO_M3_REDIRECT_DIAGNOSIS.md`
  - `MOGO_M4_FIRST_PRACTICE_TRADE_STATUS.md`
  - `MOGO_M4_FIRST_FILL_VERIFICATION.md`
  - `MOGO_M4_FIRST_PRACTICE_CLOSE_STATUS.md`
  - `MOGO_M4_FIRST_TRADE_RECONCILIATION.md`
  - `MOGO_M4_EXECUTION_INTEGRITY_REPAIR.md`

  They were scanned and contain no account ID or token.
- **Never in git:**
  - `~/.mogo/oanda_practice.json` (credentials);
  - `order-0003.json`, `close-0001.json`;
  - `journal.sqlite3`;
  - scratchpad files.
- **`index.html`, `scripts/trader_intelligence/` and `docs/`:** not modified by the integration.

## 3. Sensitive-material checks

| Check | Result |
|---|---|
| Real practice account ID, its unique middle segment, or the token, in any of the 44 integrated files | **0 hits.** Compared in memory against `~/.mogo/oanda_practice.json`; nothing was printed |
| The same check over **every new blob in all 12 commits** (94 blobs) and all 12 commit messages | **0 hits** |
| Account-ID-shaped strings that are present | Only the synthetic test placeholder (`101-004-…-001`), whose fingerprint differs from the real account |
| Tracked files named like sqlite, credentials, tokens, `.env`, `order-0*` or `close-0*` | None |
| Observed-trade fixture keys | No `accountID`, `userID`, `requestID`, `batchID`, `bids` or `asks` |

## 4. Safety properties retained (requirement 5)

Each property was checked in the integrated tree. Each guard is backed by a mutation gate that kills its deletion (§5).

| Property | Where |
|---|---|
| Practice host only; no live host; no environment selector | `config.PRACTICE_HOST = "api-fxpractice.oanda.com"`. `fxtrade` appears nowhere in `execution/`. `_FORBIDDEN_KEYS` refuses `host`, `url`, `baseUrl`, `environment`, `env` and `live` |
| No network code except the A2 read-only module | `transport.py` imports `urllib.parse` only. Only `oanda_practice_m3/readonly.py` imports `http.client` and `ssl` (M1 import-ban exemption) |
| A2 GET-only, separated from writes | `readonly.py` and `transport.py` GET allow-lists; gate M3 21/21 |
| Explicit A3 entry and separate close authorization | `a3.py`: `A3WriteOpener`, `EntryGrant`, `CloseGrant` |
| Absolute entry limit (`maxEntryPrice` / `minEntryPrice`) | `authorization.ENTRY_LIMIT_FIELD`; `risk.PRICE_BOUND_BEYOND_APPROVED_ENTRY_LIMIT`; `EntryGrant.check` |
| Duplicate-order protection, journal write-ahead | journal intents with `clientExtensions.id` (gates M1/M2) |
| Fail-closed reconciliation, including closed-trade 404 | `executor._reconcile_position` (gate M4 RA1–RA5) |
| Stale-data and spread limits; $5 cap; mandatory stop | `risk.py` (`STALE`, `SPREAD_TOO_WIDE`, `MAX_LOSS`); `stopLossOnFill` |
| Kill switch and halts | `kill.py`; executor KILL checks; append-only halt/clear |
| Mode separation | `mode: BROKER_PRACTICE`; records stay out of the research corpus; the PAPER posture in `mogo_rules.json` is unchanged |

**Governance diff.** It **adds** `MOGO Broker-Practice Execution` as a soft_deny entry, and adds one sentence to the posture entry stating that this executor never clears Live-Money Capability. Nothing is removed or loosened.

**Not installed.** The rule is in the repo file only. Installation stays the operator's step, via `install_mogo_delta_only.py`.

## 5. Tests and mutation gates

Run in the executor worktree, whose tracked content is byte-identical to the merge tree. `__pycache__` was cleared before each run.

| Gate | Result |
|---|---|
| Execution suites (M1 53, M2 37, M3 30, M4 50) | **170 tests, OK.** No network attempt |
| `demo_offline_lifecycle.py`, `demo_m4_practice_trade.py` | exit 0 / exit 0 |
| `mutate_oanda_practice.py` (M1/M2) | **107/107 killed**, 0 unapplied, sources restored |
| `mutate_oanda_practice_m3.py` | **21/21 killed** |
| `mutate_oanda_practice_m4.py` | **52/52 killed**, including RA1–RA5 (404 reconciliation) and RB1–RB11 (entry limit) |
| Full Python lane (`tests/trader_intelligence` + `tests/execution`, 40 modules, as run_all.sh runs it) | 1944 tests: **3 failures, 1 skip.** All 3 also fail on mogo-main (below) |
| `count_python_tests.py --check` | exit 1, **pre-existing**: `test_engine_provenance` is unregistered. Identical on mogo-main. The four execution rows match |

**Baseline comparison.** `origin/mogo-main` was extracted with `git archive` into scratch and the same tests run. **The same three tests fail there:**
- `test_python_test_counts.…test_POSITIVE_CONTROL_the_real_manifest_is_in_sync`
- `test_python_test_counts.…test_the_script_runs_as_a_subprocess_and_reports_its_verdict`

  Both follow from the unregistered `test_engine_provenance` row.
- `test_graph.TestNoRuntimeCoupling.test_index_html_never_references_trader_intelligence`

  This is about `index.html`, which the integration does not change.

**The integration introduces no new failure.** The line "expected_python_test_counts.tsv is missing or empty" in the log is output a fixture test prints deliberately, not a failure.

**Not run:** the JS/node lanes of `run_all.sh`. The integration changes no JS, no `index.html` and no JS test. The only `run_all.sh` change adds the three Python mutation gates and a find root, both exercised above.

**Specific verifications (requirement 9):**
- **Sanitized first-trade fixture:** `oanda_practice_observed_first_trade_20261109.json`. `TestTheObservedFirstTradeReplay` reaches RECONCILED (entry 1.12032, exit 1.11911, net −0.0012, balance 99999.9988), and its five negative variants halt.
- **Closed-trade 404:** the fake broker answers 404 for closed trades by default. `TestAClosedTrade404ReconcilesOnlyFromCloseEvidence` passes, and mutants RA1–RA5 are killed.
- **Absolute entry limit:** `TestTheApprovedEntryLimitIsEnforced` passes, including the first trade replayed under 1.11980 being refused with 0 POSTs. Mutants RB1–RB11 are killed.

## 6. Operator journal and evidence (checked, not modified)

The journal was read from a **copy** opened `mode=ro`. `status` was run against a second copy.

| Item | Value |
|---|---|
| Position, trade 5 | **RECONCILED / FILLS_STREAM_AND_BALANCE_AGREE**: entry fill 5 at 1.12032, close fill 8 at 1.11911, realized −0.0012, financing 0, commission 0, fees 0, **net −0.0012**, balance_after 99999.9988 (reconciled 17:11:07Z) |
| Events | 7, ending CLOSED → RECONCILED |
| `status` | `activeHalts: []`, killSwitch false, mode BROKER_PRACTICE |
| Halts table | seq 1 HALT `TRADE_MISSING_AT_BROKER 5`; **seq 2 and seq 3 are both CLEAR of halt 1** (17:14:06Z and 17:14:11Z), by the operator. See below |
| Integrity | `pragma integrity_check` ok; refusals 0; broker_transactions 6 (ids 4–9) |
| `journal.sqlite3` sha256 | `023f7e9b967c6181…`. It differs from the earlier `88874bb1…` **because of the operator's own reconcile and clear-halt**. It is unchanged by this task (re-checked at the end) |
| `order-0003.json` / `close-0001.json` | `ab566751…` / `c6dca47c…`, unchanged |

**Observation (P3, not repaired).** `clear-halt` accepted a second CLEAR of an already-cleared halt, which produced the duplicate seq 3.
- It is harmless: it is append-only and the halt is cleared either way.
- But it is noise in an audit trail. A guard that refuses to re-clear an inactive halt would be a small offline change. Not done here, being outside scope.

### Incident during integration (recovered; no data lost)

1. **The attempt.** I first tried `git switch -c claude/m5-… origin/mogo-main` in the executor worktree. It **failed partway**:
   - the branch ref was created at `1720f8765`;
   - the index and working tree were moved to mogo-main's tree;
   - but HEAD stayed on the executor branch.

   The likely cause: setting the branch's upstream failed (no upstream was recorded, and git printed only the set-upstream hint). That is unconfirmed.
2. **Effect.** For a few minutes, the worktree showed the executor's 44 files as deleted.
3. **Why nothing was lost:**
   - every one of those files is committed in `caeb1a021`;
   - the worktree had **0 uncommitted tracked changes** before the attempt;
   - the six untracked reports were never touched.
4. **Recovery.** `git read-tree HEAD`, then `git restore --worktree -- .`. Verified: 0 tracked differences from `caeb1a021`, and all 11 report files present.
5. **Then:** the merge was built with plumbing, without touching any working tree. The main checkout was never involved.

## 7. Final state

| Item | Value |
|---|---|
| Integration branch | `claude/m5-oanda-executor-integration-20261109` (local only, no upstream) |
| Merge commit | **`5adfdfa96`**, with parents `1720f8765` (mogo-main) and `caeb1a021` (executor) |
| Report commit | The child of `5adfdfa96`, adding only this file |
| Executor branch | `claude/m1-oanda-practice-executor-20261103` still at `caeb1a021`; its worktree is still on that branch |
| `origin/mogo-main` | `1720f8765`, untouched. Nothing pushed |

## 8. Unresolved blockers and uncertainties

| Item | Severity | Note |
|---|---|---|
| R-5 (`031bd605e`) and this integration both edit `tests/expected_python_test_counts.tsv` | P2 | A textual conflict is likely when both reach mogo-main. Resolve by regenerating the TSV, not by hand-picking rows |
| `test_engine_provenance` unregistered (count gate red) | P3, pre-existing | It makes run_all.sh exit non-zero on mogo-main and here alike |
| `test_index_html_never_references_trader_intelligence` | P3, pre-existing | Unrelated to the executor |
| Duplicate CLEAR accepted by `clear-halt` | P3 | §6 |
| A9 mutant now killed by `TypeError` | P3 | Carried over from M4 |
| Six trade-day reports untracked | Operator decision | Scanned clean, so they could be committed if wanted |
| `MOGO Broker-Practice Execution` rule not installed in `~/.claude/settings.json` | Operator step | Use `install_mogo_delta_only.py`, **never** `build_auto_mode_config.py --write` |
| Cause of the partial `git switch` failure | Unconfirmed | Recovered; does not affect the result |
| No further entry is authorized | By design | Any future A3 must quote an absolute `maxEntryPrice` or `minEntryPrice` |

## 9. Next action

**The operator must act.** Review this integration and decide whether to publish `claude/m5-oanda-executor-integration-20261109` to `mogo-main`. The sandbox cannot push (403), so it would go out as a bundle with the temp-ref deploy command from CLAUDE.md. Before that command is quoted:
- `git fetch origin` and re-verify that `origin/mogo-main` is still `1720f8765`;
- decide the order relative to R-5, which is still awaiting deploy and overlaps on the counts TSV.

**Executor safety on deploy.** Deploying is safe, because nothing here runs automatically. The executor only acts when the operator runs its CLI with credentials and an authorization. But publishing it is still the operator's governance decision.
