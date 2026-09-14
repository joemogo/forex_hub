# Consolidation 2026-09-13 — what the merge found

Merging `claude/research-gates-holdout` into the exit-fidelity line required running the
canonical gate over a tree where both lines' work coexisted for the first time. That surfaced
four findings. Two are repaired here; two are blockers recorded for the operator.

The merge itself was clean: **zero textual conflicts**, zero files lost from either parent,
`index.html` byte-identical to the exit-fidelity parent, and **zero protected-function or
protected-constant drift** (64/64 and 4/4 byte-identical to the committed baseline).

---

## BLOCKER 1 — `aoi_close_v1` records a future-dependent `zoneTouchCount`, and it gates a criterion

**Status: unrepaired. Requires operator authorisation. This is the reason the gate is not green.**

The documented correction in `NEGATIVE_ACQUISITION_LOG.md` said lengthening v170's synthetic walk
from 9,000 to 18,000 bars makes all four starved fixtures pass. Applied, it fixes three:

| fixture | before | after | evidence |
|---|---|---|---|
| AOI-F1 | FAIL (4 trades, needs >=5) | **PASS** | real 7 trades, shifted control 8, ratio 1.14 — exactly the 7-and-8 the log predicted for 18,000 bars |
| AOI-C1 | FAIL (no trades to charge) | **PASS** | 7 trades, risk spread 8.6–12.7 pips, per-trade charge exact |
| AOI-1b | FAIL (no trades) | **PASS** | different bars -> different trades |
| AOI-1 | FAIL, **0 completed trades in the prefix** (vacuous) | **FAIL, 6 completed trades in the prefix** | `zoneTouchCount` differs |

**AOI-1 does not fail for the documented reason.** At 9,000 bars its filter was empty, so it was
failing vacuously — it never evaluated its own assertion. At 18,000 bars the filter holds 6
completed trades and the assertion runs for the first time, and it fails on exactly one field:

```
FIRST DIFF at trade index 0
   zoneTouchCount: full=15   trunc=11
```

Entry, stop, target, direction, exit, geometry and every other field are identical. Only
`zoneTouchCount` differs, because `aoiCloseFormZones` builds each zone's complete touch list
across the whole input series up front, so a trade that opened and closed early records a count
that includes touches occurring **after it closed**. Feed the walker a shorter series and the
same trade reports a different number. That is precisely the look-ahead AOI-1 exists to prove.

It is not cosmetic. `index.html:18067` gates on it:

```js
return {satisfied: r.zoneTouchCount >= 4, observed:{zoneTouchCount:r.zoneTouchCount, minimum:4},
        provenance:'OBSERVED'};
```

A threshold evaluated against a future-dependent value is a criterion that cannot be reproduced
from the data available at decision time.

**Why it was not repaired here.** The fix changes a threshold-bearing computation in a protected
production file, which this task's rules place outside scope and which CLAUDE.md puts behind an
operator governance boundary. The alternatives were all worse: weakening AOI-1 is forbidden and
would delete the look-ahead proof; reverting the walk to 9,000 would restore a *vacuous pass-by-
starvation* that hides a real defect. The fixture is therefore left **failing honestly**, with
its filter non-empty, which is the only state that keeps the finding visible.

`aoi_close_v1` is stood down and unreachable (no nav entry, no registry entry, nothing calls it),
so nothing trades on this today. It matters if the arm is ever revived.

---

## BLOCKER 2 — 25 Node suites never execute under the canonical runner (pre-existing on `mogo-main`)

**Status: unrepaired, deliberately out of scope for a merge commit. Bounded and mechanical.**

The gate reports **25 execution errors**, all one cause:

```
execution error: Error: ReferenceError: Can't find variable: require (-2700)
```

These suites are Node programs (`#!/usr/bin/env node`, `require`) with no
`// RUN_ALL_EXEC:` declaration, so `run_all.sh` falls back to `osascript -l JavaScript` and they
die before asserting anything. The runner catches this correctly — zero fixtures is an execution
error, not a pass — so the gate has been red rather than falsely green.

**This predates the consolidation.** `origin/mogo-main` (`482fb0623`) carries all 25 itself;
`run_v162_crt_tests.js` is byte-identical there. The merge neither caused nor worsened it.

Affected: v137, v138, v139, v140, v142, v143, v144, v145, v146, v147, v148, v149, v151, v154,
v155, v156, v157, v158, v159, v160, v161, v162, v163, v164, v165.

**Their assertions pass.** Sampled directly under `node`:

| suite | result |
|---|---|
| `run_v162_crt_tests.js` | 40 / 40 |
| `run_v144_baseline_trend_tests.js` | 39 / 39 |
| `run_v149_cost_model_tests.js` | 32 / 32 |
| `run_v165_byte_budget_tests.js` | 19 / 19 |

So roughly 700 real assertions exist and are green, but are not being run by the gate.

**The fix, per suite:** add `// RUN_ALL_EXEC: node tests/<file>` near the top; where the reporter
emits `  PASS  <id>` rather than the harness contract `PASS -- <id>`, conform it (about half
need this); then register the fixture count in `tests/expected_fixture_counts.tsv`. It is
test-harness-only and touches no assertion — the same repair applied to v170 in this commit.

It was kept out of this commit for two reasons: it is a separate pre-existing defect rather than
a consolidation concern, and a 25-file harness rewrite buried inside a merge commit is not
reviewable. It deserves its own commit. **It would not have made the gate green** — BLOCKER 1
holds that regardless.

---

## REPAIRED 1 — v170 integrated into the canonical gate (29 fixtures, all retained)

`run_v170_aoi_close_tests.js` was added by `cd10ea2e5`, a commit whose own message says
"WIP … blocked by the section 8 firing-rate gate". It was never wired into the gate:

1. **No `RUN_ALL_EXEC`** — same defect as BLOCKER 2, so it produced 0 fixtures. Declaration added.
2. **Reporter emitted `  PASS  <id>`**, matching neither counting pattern, so every fixture was
   invisible to `run_all.sh`. Conformed to `PASS -- <id>`. No assertion, id or description changed.
3. **Unregistered** in `expected_fixture_counts.tsv`, which the runner treats as a failure.
   Registered at **29**.
4. **Synthetic walk lengthened 9,000 -> 18,000** (and the AOI-1/AOI-1b walk 6,000 -> 18,000 with
   its prefix `K` 4,000 -> 12,000, holding the 2/3 ratio). `walkH1` is a self-contained LCG local
   to the test file: no production import, no candle requirement, no ALEX or AOI rule, no firing
   threshold, no spread calculation, no runtime evaluation path. Synthetic test data only.

All **29 fixtures retained**. AOI-1, AOI-1b, AOI-F1 and AOI-C1 are all present; the retracted
proposal to delete them and register at 25 was **not** implemented. Result: **28 / 29**, with
AOI-1 failing per BLOCKER 1.

## REPAIRED 2 — the runtime-coupling test was a false positive

`TestNoRuntimeCoupling.test_index_html_never_references_trader_intelligence` asserted
`assertNotIn("trader-intelligence", content)` over the whole 2.4 MB file. That is not the
invariant. All six occurrences in `index.html` are documentation:

| line | kind |
|---|---|
| 2272 | release-note string (`'12.65.0 - …'`) |
| 23762, 23766, 24298, 25315 | `//` line comments |
| 25165 | `replayDisclosures.preregistration` provenance string |

**No executable coupling exists** — nothing `fetch`es, `import`s, `require`s or points a `src`
at a corpus path. The test was failing on comments.

Rewritten to detect real coupling: comments are stripped (a commented-out `fetch` cannot
execute), then loader constructs whose argument names a corpus path are matched. It ships with a
**positive control** (6 genuine coupling forms must be caught), a **negative control**
(documentation must not trip it), a **non-vacuity guard** (the stripper must not return an empty
file), and a test asserting the provenance citations still exist so they cannot be deleted to
make a blunt check pass.

Mutation-verified — each mutant fails the suite:

| mutation | caught by |
|---|---|
| detector regex matches nothing | positive control (6 subtests fail) |
| comment stripper made a no-op | negative control |
| empty input fed to the check | non-vacuity guard |

`tests/expected_python_test_counts.tsv` updated 66 -> 69 for that module (1 test became 4); the
Python lane is back in sync at 33 modules / 1669 tests.

---

## REPAIRED 3 — `run_v124_baseline_registry_tests.js` registration drift

The gate reported `FIXTURE COUNT MISMATCH for run_v124_baseline_registry_tests.js: expected 34,
got 35 … ran LONG`. A fixture had been added without updating the manifest. Verified the extra
one is real and not a duplicate — 35 emitted lines, **35 distinct**, 0 FAIL — and registered at
35. Pre-existing: `origin/mogo-main` also records 34 against a suite that emits 35. Same class of
one-line registration fix as v170, so it was taken here rather than deferred.

---

## Also observed, not repaired

**The evidence-checkpoint selftest fails in this sandbox, environmentally.**
`scripts/mogo_evidence_checkpoint.sh --selftest` reports `FAIL -- a clean checkpoint VERIFIES`,
with `ls: .mogo-ckpt-selftest-<pid>: No such file or directory` — its scratch root is never
created under this sandbox's write policy. Pre-existing (identical in the pre-change run) and not
a repository defect; it is expected to pass on the operator's machine. Per CLAUDE.md, a check
that reports what it cannot do is behaving correctly and must not be suppressed or downgraded,
so it is left exactly as it is.

**Auto-mode governance config drift.** The gate reports the installed `~/.claude/settings.json`
`autoMode` block is behind what this repository generates (`environment` 27 vs 28, `soft_deny`
75 vs 77). This is CLAUDE.md's documented staleness after a Claude Code upgrade. Fixing it means
`build_auto_mode_config.py --write` against the operator's own settings — a governance-perimeter
change, so it is the operator's to run. It contributes to the red exit code.

**An orphaned comment, fixed in passing.** Inserting the research-gate blocks into `run_all.sh`
separated the MOGO-023 comment from the platform-health selftest it documents, leaving it
attached to the holdout gate. Moved back.

**Double execution, fixed.** The merged runner invoked `holdout_gate.py --selftest`,
`candidate_power.py --selftest` and `tests/mutate_holdout_gate.py` twice each — once standalone
and once via the loops that supersede them. The three standalone blocks were removed; all seven
gates and all five mutation harnesses now run exactly once.

---

## Research gates, as consolidated

Seven selftests, all exit 0: `candidate_power`, `candidate_frequency`, `holdout_gate`,
`month_end_test`, `bond_carry_test`, `venue_recost`, `portfolio_combine`.

Five mutation harnesses, all PASS, **59 mutations caught, 0 survivors**
(`__pycache__` cleared first, per CLAUDE.md, so no stale-bytecode false survivors):

| harness | caught | survived |
|---|---|---|
| `mutate_holdout_gate.py` | 8 | 0 |
| `mutate_candidate_frequency.py` | 8 | 0 |
| `mutate_month_end_test.py` | 18 | 0 |
| `mutate_bond_carry_test.py` | 14 | 0 |
| `mutate_portfolio_combine.py` | 11 | 0 |

UNKNOWN stays UNKNOWN rather than collapsing to zero — `candidate_power.py` with no sample
reports `detection floor unknown` and `POWER: sigma or n missing, so detectability is unknown --
not zero`.

No candidate was promoted. No strategy was enabled. PAPER only.
