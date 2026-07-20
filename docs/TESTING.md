# Testing

MOGO has no formal build/CI pipeline — it's a single static HTML file. Verification instead
relies on three independent layers, all of which should be run for any release that touches
application logic:

1. **Offline fixture suites** (JavaScript, run via `osascript -l JavaScript` / JXA on macOS)
2. **The durable regression baseline** (`regression-baseline-tools.py`)
3. **Live browser verification** for anything the offline harness cannot exercise

## 1. Offline fixture suites

Each release that adds behavior has added its own fixture file, named by version
(`v90_reset_tests.js`, `v100_trade_inspector_tests.js`, `v110_ledger_tests.js`,
`v111_ledger_transaction_tests.js`, `v112_chart_view_selfheal_tests.js`,
`v113_chart_history_policy_tests.js`, `v114_checklist_badge_tests.js`,
`v115_academy_lesson_engine_tests.js`, `v120_strategy_framework_tests.js`, etc.) plus a small
runner (`run_v90_tests.js`, ...) that:

- Extracts the app's `<script>` body out of `index.html`.
- Stubs `document`, `localStorage`, `fetch`, `alert`/`confirm`, timers, `ResizeObserver`, and the
  charting library.
- Wraps the app code + test code + a thin `g` object of exposed getters/setters in
  `new Function(...)` and executes it.
- Prints `PASS`/`FAIL` per fixture and a final summary line.

**Two categories exist, and it matters which one a suite is in:**

- **Repository-owned permanent suites** — live under [`tests/`](../tests/) in this repository,
  committed to git, reproducible from a fresh clone with no external dependency. As of v12.3.1
  there are **eight**: `tests/v120_strategy_framework_tests.js` (28 fixtures, ALEX registration,
  Release 1), `tests/v121_jvm_registration_tests.js` (30 fixtures, JVM registration, Release 2 —
  grew from 28 in v12.2.0, see below), `tests/v1211_diagnostics_integrity_tests.js` (13
  fixtures, Diagnostics data integrity), `tests/v1212_manual_review_and_replay_diagnostics_tests.js`
  (53 fixtures, TRUE MTF Replay Diagnostics + Manual Review Eligible),
  `tests/v1213_security_baseline_tests.js` (50 fixtures, Security Baseline — escaping fixes,
  Manual Lock, sensitive-action confirmation guards, and an explicit OANDA-never-persisted vs.
  Anthropic-persisted-by-design reconciliation pair), `tests/v122_multi_strategy_foundation_tests.js`
  (30 fixtures, Multi-Strategy Foundation / ADR-006 — strategyId identity, the 3-tier resolver,
  legacy-label and rename-resilience coverage, unknown/unregistered-record safe fallback, and a
  fixture-only synthetic third strategy proving genuine N-strategy support at all seven
  generalized seams), `tests/v123_tjr_phase1_session_zone_tests.js` (48 fixtures, TJR_SLR
  Phase 1 — Session and Zone Engine: registration, DST-aware session boundary resolution
  including the exact spring/autumn transition days, previous-completed-session predecessor
  cycling, no-lookahead M30 candle aggregation, malformed/duplicate-candle rejection, tied/unique
  extreme selection, all four mandatory zone-formula examples, deterministic/immutable zone
  objects, all three Phase 1 zone statuses, and a zero-mutation proof against JVM/ALEX state),
  and `tests/v1231_strategy_workspace_framework_tests.js` (31 fixtures, Strategy Workspace
  Framework & dedicated TJR workspace: registry metadata, registry-driven nav generation
  including a synthetic-4th-strategy proof that it isn't hardcoded, workspace routing via the
  existing showPanel() mechanism, all 12 header fields, all 7 tabs, Rules' three-category
  separation, Diagnostics against an intentionally incomplete dataset, Paper Trading's
  fully-disabled controls, Replay/Journal's exact placeholder text, Developer's no-credentials
  check, dedicated-chart isolation from the shared chart's own zone state, chart lifecycle
  cleanup, a Phase 5 source-inspection proof that the shared chart's auto-render call site was
  removed while the underlying function remains, ALEX/JVM registry compatibility, and a
  zero-mutation/zero-new-localStorage-key proof) — 283 fixtures total. Each has its own
  self-contained runner (`tests/run_v120_tests.js`, `tests/run_v121_tests.js`,
  `tests/run_v1211_tests.js`, `tests/run_v1212_tests.js`, `tests/run_v1213_tests.js`,
  `tests/run_v122_tests.js`, `tests/run_v123_tests.js`, `tests/run_v1231_tests.js`) that
  extracts `index.html`'s `<script>` body itself — no separate preprocessing step required.
  `tests/run_all.sh` discovers and runs all eight automatically via its `tests/run_*_tests.js`
  glob — adding a new suite under `tests/` never requires editing the runner.
  **v12.2.0 note:** two pre-existing `v121` fixtures (15, 18) asserted a per-id hardcoded
  fallback behavior that v12.2.0 deliberately replaced (see ADR-006) — updated, not weakened,
  to assert the new, correct, generalizable behavior; two new fixtures (15b, 18b) cover the
  still-supported "whole registry empty" fallback case, and one fixture's stale comment (22)
  was corrected.
  **v12.3.0 note:** one pre-existing `v121` fixture (1) asserted the registry's total size was
  exactly 2 — updated, not weakened, to assert JVM and ALEX are both present (`reg.length>=2`),
  since the exact count was only ever true before TJR_SLR's own registration and is now,
  correctly, obsolete.
- **Historical scratch-only suites** — the remaining 22 suites referenced in
  `regression-baseline-tools.py`'s `FIXTURE_COUNTS` dict (476 fixtures) live only in the
  ephemeral Claude Code scratchpad used during development, not in this repository, and are
  regenerated fresh each session from `index.html`'s current `<script>` contents when present.
  **This is a real, disclosed gap, not a design choice worth defending**: a fresh clone of this
  repository cannot reproduce any of these 22 suites. See
  [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the current state of that gap (3 of the 22 currently
  can't even execute in scratch due to missing companion source files, and 2 have proven
  fixture-count discrepancies against the committed baseline). New suites should be added under
  `tests/` going forward, following the `v120` pattern, rather than added to the scratch-only set.

### Canonical test command

```
tests/run_all.sh
```

Runs every repository-owned permanent suite (every `tests/run_*_tests.js`) plus the
protected-function/constant drift check, and prints a summary: suites run, fixtures run,
passed, failed, execution errors. Exits nonzero if any permanent suite fails, errors, or if
protected-function/constant drift is detected. Uses only files inside this repository — no
scratchpad path is ever read. Its output explicitly states that only repository-owned permanent
suites are being run, and that the historical scratch-only suites are not included. Run it from
anywhere; it resolves the repository root relative to its own location.

Current per-suite counts (including the 22 historical, scratch-only ones) are tracked in
`regression-baseline-tools.py`'s `FIXTURE_COUNTS` dict (also mirrored into the committed
`regression-baseline.json`) rather than restated here, so there is exactly one place to keep them
in sync.

### A known, permanent limitation of this harness

`osascript -l JavaScript` (JXA) runs JavaScriptCore without a real event loop. **It cannot
resolve a genuine `await` on a promise that settles asynchronously** (confirmed empirically: a
2-second `NSRunLoop` spin-wait around an immediately-rejecting `fetch()` never observed the
promise settle — and re-confirmed in v12.1.2, where the same `NSRunLoop` spin-wait technique was
tried again around `simulateTrueMTFReplay()`/an (at-the-time) `async approveManualReviewTrade()`
and again never observed the promise settle within a 5-second deadline). This means any function
with a real `await` inside it — `closePaperPosition()` (`await fetchBidAsk(...)`),
`checkAutoTrades()` (`await evaluateLiveTrigger(...)`), `simulateTrueMTFReplay()` (real
progress-reporting awaits for long replays), and similar ALEX live-polling functions — cannot be
driven to completion inside an offline fixture.

**The established pattern**: offline fixtures cover everything synchronously reachable (which is
most of the codebase, including `openPaperPosition`, all pure computation functions, and the
transaction/rollback contract of `commitPaperLedger()`). Anything that genuinely requires
completing a real async call is instead verified **live, in an actual browser**, against the
real function — never simulated by hand-reconstructing what the async function "would" do,
which would prove nothing about the real code path.

**A useful corollary, found in v12.1.2**: if a function is declared `async` but contains no
*genuine* `await` (no real pending I/O — every call inside it is already synchronous), the
`async` keyword itself is doing nothing except making the function untestable in this harness.
`approveManualReviewTrade()` was exactly this case (`openPaperPosition()`/`commitPaperLedger()`
are both synchronous) and was changed to a plain function — a real simplification, not a
workaround, since real callers awaiting a non-Promise value works unchanged in an actual browser.
Before writing offline fixtures for a new async-looking function, check whether it actually
awaits anything real; if not, removing `async` is often the correct fix, not a harness workaround.

### A second known limitation, found during v12.2.0, resolved in v12.3.0: real-wall-clock-dependent fixtures

Some fixtures in `tests/v1212_manual_review_and_replay_diagnostics_tests.js` (Fixtures 39, 40,
47, 48) call `approveManualReviewTrade()`, which gates on `getSession().active` using the real
system clock rather than the setup's own `decisionTs` — a genuine, pre-existing production
behavior (confirmed identical on unmodified `v12.1.3` via `git stash`), not a bug in the function
under test. Because of it, these specific fixtures failed with `"Outside approved session."`
whenever `tests/run_all.sh` happened to run during the real, documented 00:00–08:00 UTC
off-hours window — first disclosed as a tracked, unfixed follow-up in v12.2.0.

**Resolved in v12.3.0, in the test harness only, per explicit instruction not to alter protected
production behavior merely to make fixtures pass:** `tests/run_v1212_tests.js` now exposes
`g.forceActiveSession()` / `g.restoreSession()`, which reassign that offline test realm's
in-memory `getSession` reference (never `index.html`'s actual, protected `getSession()`) to a
fixed, always-active session for exactly the fixtures that call `approveManualReviewTrade()`
(39–49), restoring the real reference immediately after. `tests/run_all.sh` now produces the
identical 252/252-passing result regardless of what time it's run — confirmed by re-running it
repeatedly, including inside the previously-failing 00:00–08:00 UTC window. If a *future* release
adds a new fixture that calls `approveManualReviewTrade()` (or any other function gating on the
real `getSession()`), bracket it with the same `g.forceActiveSession()`/`g.restoreSession()` pair
rather than reintroducing a real-clock dependency.

## 2. Live browser verification

For UI changes and for anything the offline harness can't reach (see above), verification is
done against a real browser instance pointed at a locally-served copy of `index.html`
(`python3 -m http.server` + a browser automation tool). The established pattern:

1. Bypass the OANDA connect screen by directly toggling `#setupScreen`/`#mainApp` visibility.
2. Seed whatever `pairData`/`journalEntries`/`paperAccount`/etc. state a scenario needs.
3. Call the real, unmodified application function(s) directly via the browser's JS console/eval
   (e.g. `await closePaperPosition(id, false, 'Win')`), or drive it through the actual UI.
4. Assert on the resulting real state and, where relevant, screenshot the rendered UI.

This is how, for example, v11.0's stale-save race and v11.0.1's split-transaction rollback were
both actually reproduced and later confirmed fixed — through the real engine, not a mock of it.
Live browser verification is always subject to the Browser Testing Policy below.

**A known screenshot-capture limitation at large viewport sizes**: the browser automation
tooling used for live verification was found (during v11.4.0 responsive testing) to render an
inaccurate screenshot at very large viewport sizes (confirmed at 2560×1440) — the captured image
showed page content confined to a small corner of the frame. Direct DOM measurement
(`getBoundingClientRect()`, `scrollWidth`/`clientWidth`) at the same viewport size confirmed the
actual layout was correct and full-width with zero overflow, proving the discrepancy was in the
screenshot capture step, not the application. When a screenshot at a large viewport looks wrong,
verify with direct DOM measurement before treating it as a real layout bug.

## Browser Testing Policy

**Permanent rule.** Developer browser testing must never contaminate the user's real
paper-trading data. This was written after live verification of the v11.0/v11.0.1 paper-ledger
fix itself left real, untagged trades behind in production `journalEntries`/`paperAccount` —
including one that later surfaced as a false `JOURNAL_ONLY` data-integrity report and required a
full forensic investigation to trace back to test contamination rather than a real defect. See
[INCIDENTS.md](INCIDENTS.md#inc-001).

**Preferred verification order** — always prefer the earliest option on this list that can
actually prove what you're checking:

1. **Unit fixtures** — the offline JXA suites described above.
2. **Regression fixtures** — a new fixture added to an existing suite, not a one-off script.
3. **Mock data** — hand-constructed trade/journal objects passed to pure functions
   (`computePaperLedgerIntegrity()`, `classifyJvmJournalRecord()`, `normalizeJournalRecord()`,
   etc.), never routed through `commitPaperLedger()`.
4. **Temporary in-memory state** — reassigning app variables in a live tab for a check that
   provably never calls `save()`/`commitPaperLedger()`.
5. **Real paper trades** — only when explicitly authorized for that specific instance, and only
   when nothing above can prove the thing being verified (e.g. the real async open→close engine,
   a real `commitPaperLedger()` rejection/rollback).

**If a real paper trade is created during testing** (option 5), it must:

- Be tagged as a Developer Test — set `isDeveloperTrade:true` / `tradeSource:'TEST'`, reusing the
  existing v4.3 Developer Test Mode fields and `generateTestPaperTrade()`'s tagging pattern rather
  than inventing a new mechanism.
- Be excluded from analytics and performance statistics by default (Strategy Center's
  `computeMogoStrategyPerformance()` already reads only non-test closed positions — confirm this
  still holds for whatever path was used).
- Be removable through the existing Diagnostics cleanup tool (`clearTestTradesPaper()`), not left
  for the user to clean up manually.
- Be disclosed to the user *before* it's created, clearly labeled as a developer verification
  trade — not reported after the fact.

**Default assumption:** browser verification leaves the user's paper-trading history completely
unchanged. Any deviation from that is the exception, requires explicit authorization for that
specific instance, and must satisfy every bullet above.

## 3. The durable regression baseline

[`regression-baseline-tools.py`](../regression-baseline-tools.py) exists specifically to catch an
accidental change to frozen trading methodology, even one buried inside an otherwise-unrelated
release. It extracts the exact source text of every function/constant in `PROTECTED_FUNCTIONS`
(63 as of v11.0.1: 15 JVM + 48 `alexG*`) and `PROTECTED_CONSTANTS` (`WEIGHTS`, `ALERT_THRESHOLD`,
`RULES`, `RULES_ALEXG`) directly out of the current `index.html`, SHA-1 hashes each one, and also
hashes the frozen `index-v2.9-KNOWN-GOOD.html` reference file.

```bash
# Compare current index.html against the committed baseline (exit 1 on any drift):
python3 regression-baseline-tools.py

# Deliberately redefine "known good" -- only after a release's drift has been
# reviewed and is understood to be safe (e.g. added logging inside a protected
# function, math otherwise untouched):
python3 regression-baseline-tools.py --update
```

A non-zero exit / reported drift is not automatically a bug — some releases legitimately touch a
protected function (e.g. v11.0 and v11.0.1 both added logging/transaction-commit code inside
`openPaperPosition`/`closePaperPosition`). What matters is that the drift is **expected,
disclosed, and reviewed** before `--update` is run — never run `--update` reflexively just to
make the tool pass.

### Updating fixture counts

`FIXTURE_COUNTS` inside `regression-baseline-tools.py` is itself part of the baseline. Any
release that adds a new fixture suite, or adds fixtures to an existing suite, must update the
corresponding entry (or add a new one) **before** running `--update`, so the committed baseline's
`totalFixtureCount` always matches what a full regression run should actually reproduce.

## What a release should run before shipping

0. `tests/run_all.sh` — the canonical command for every repository-owned permanent suite plus the
   protected-function/constant drift check, in one step. Zero failures, zero execution errors,
   zero drift.
1. All existing fixture suites, including any historical scratch-only ones present this session
   (regenerate the extracted script from the current `index.html` first) — zero failures.
2. Any new fixture suite the release added — zero failures.
3. `python3 regression-baseline-tools.py` (no flag) — review the reported drift, if any, and
   confirm it's limited to what the release actually disclosed changing.
4. A syntax check (the same script-extraction step, wrapped in `new Function(...)`, must not
   throw).
5. Live browser verification for anything UI-facing or anything the offline harness cannot
   exercise (see above) — governed by the Browser Testing Policy: prefer fixtures/mocks/in-memory
   state first, and if a real paper trade is genuinely unavoidable, tag/exclude/make it
   cleanable exactly as that policy requires.
6. Only then: `regression-baseline-tools.py --update`, version bump, and changelog entry.

**Rule for future releases:** update this file whenever the testing process itself changes —
a new suite naming convention, a new verification pattern, or a change to what the offline
harness can or can't do.
