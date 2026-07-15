# Contributing to MOGO Trading OS

This document explains how work actually gets done in this project. It reflects practices
established over the project's history, not aspirational process — if something here stops
matching reality, fix the doc, don't just ignore it.

## Coding philosophy

- **MOGO is a single static file** (`index.html`) with no build step. Keep it that way unless a
  change to that constraint is itself an explicit, discussed decision — don't introduce a bundler,
  framework, or package manager as a side effect of an unrelated task.
- **Reuse before you rewrite.** If existing code already does most of what's needed, wrap or
  extend it — don't rewrite working logic to make it "cleaner." See the Strategy Framework
  (`architecture/STRATEGY_SDK.md`) for the concrete pattern: it wraps ALEX's existing engine
  through Manifest/Services references without rewriting a single line of it.
- **Don't invent abstraction ahead of a real need.** The Strategy SDK deliberately does not
  standardize strategy-internal pipelines (scanning, qualification, trade construction) because
  no current seam needs that uniformity — see `architecture/SYSTEM_ARCHITECTURE.md`. If you find
  yourself designing an interface "for the future," stop and ask whether a concrete, current
  requirement actually demands it yet.
- **Read-only, honest analytics, always.** Any derived/computed value (statistics, progress, DNA)
  must be computed fresh from real data or honestly show it can't be computed — never fabricated,
  never estimated and presented as fact, never cached as a second source of truth. See
  [docs/adr/ADR-004-read-only-analytics-principle.md](docs/adr/ADR-004-read-only-analytics-principle.md).

## Architecture principles

- **Isolation by construction.** Each strategy owns its own state tree, its own `localStorage`
  keys, and its own save/load pair. Never merge two strategies' storage, and never let one
  strategy's code read or write another's state directly. See
  [docs/adr/ADR-002-isolated-strategy-and-feature-storage.md](docs/adr/ADR-002-isolated-strategy-and-feature-storage.md).
- **The Strategy SDK boundary is the only sanctioned way the core app touches a strategy.**
  Read `architecture/STRATEGY_SDK.md` and `architecture/STRATEGY_REGISTRY.md` before touching
  any of the shared seam functions (`getUnifiedJournalRecords`, `renderDashboard`, `showPanel`,
  `applyDeveloperModeVisibility`, `runDiagnostics`, `renderMiniJournal`).
- **A missing optional capability must fail safely**, falling back to prior behavior — never throw,
  never silently no-op in a way that looks like success. Every new optional SDK hook needs a
  fixture proving this.
- **MOGO never places a real trade.** Every account (`paperAccount`, and every strategy's own
  account) is a simulation. This is a permanent product boundary, not a missing feature — don't
  add real order execution without an explicit, separate decision and a new ADR.

## Zero behavior drift policy

This is the single most important rule in the project. A structural, architectural, or refactoring
change must never alter what a strategy actually does — its scanning, qualification, entry timing,
stop/target placement, position sizing, polling cadence, or journaling.

- `regression-baseline-tools.py` hashes the exact source text of every function/constant in
  `PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS` and compares against a committed
  `regression-baseline.json`. Run it (no flag) before and after every change:
  ```
  python3 regression-baseline-tools.py
  ```
  A non-zero exit or reported drift is not automatically wrong — some releases legitimately touch
  a protected function. What's required is that the drift is **expected, disclosed, and reviewed**
  before you ever run `--update`.
- If your change is purely structural (a refactor, a new integration seam, a framework), you
  should be able to prove **zero** drift. If you can't, the change has touched trading logic and
  needs to be re-scoped or explicitly re-framed as a behavior change with its own justification.
- Never run `--update` reflexively just to make the tool pass.

## Testing requirements

Full model: [docs/TESTING.md](docs/TESTING.md). In short, before any release:

1. Regenerate/extract the app's script body from `index.html` and run a syntax check (must not
   throw when wrapped in `new Function(...)`).
2. Run every fixture suite you can (see below on scratch vs. `tests/`) — zero failures.
3. Add focused fixtures for whatever you changed, following the existing per-release-suite naming
   convention (`vNNN_<topic>_tests.js` + `run_vNNN_tests.js`).
4. Run `regression-baseline-tools.py` (no flag) and review any drift.
5. For anything the offline JXA harness can't reach (real `await` chains — the harness cannot
   resolve a genuine asynchronous promise), verify live in a real browser instead, governed by the
   Browser Testing Policy below.
6. Only then: `regression-baseline-tools.py --update`, version bump, changelog entry.

**Where test files live.** Historically, every fixture suite lived only in the ephemeral Claude
Code scratchpad, not in this repository — a real, disclosed gap (see
[docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)). Starting with `tests/v120_strategy_framework_tests.js`,
new suites should be added directly under `tests/` in the repository, with a self-contained runner
that reads `index.html` directly (no separate preprocessing step) and depends on nothing outside
the repo. Prefer this pattern for any new suite going forward.

**Browser Testing Policy** (permanent rule): developer browser testing must never contaminate real
paper-trading data.
1. Unit fixtures first.
2. Regression fixtures added to an existing suite next.
3. Mock data passed to pure functions next.
4. Temporary in-memory state (reassigning app variables in a live tab) next — only for checks that
   provably never call `save()`/`commitPaperLedger()`.
5. Real paper trades **only** when explicitly authorized for that specific instance, tagged
   `isDeveloperTrade`/`tradeSource:'TEST'`, excluded from analytics, and disclosed to the user
   *before* creation.

Default assumption: browser verification leaves the user's paper-trading history completely
unchanged. This was written after a real incident — see
[docs/INCIDENTS.md](docs/INCIDENTS.md).

## Documentation requirements

Every release that changes behavior must:

- Add an entry to [docs/RELEASE_NOTES.md](docs/RELEASE_NOTES.md) (condensed summary) **and** the
  full, detailed entry stays in-code as `APP_VERSION_LOG` in `index.html` — the in-code log is the
  source of record if the two ever disagree.
- Update [docs/TESTING.md](docs/TESTING.md) if the testing process itself changed (new suite
  naming, new pattern, new harness limitation discovered).
- Update [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) if the release closes a documented gap or
  discovers a new one worth disclosing (found-but-not-fixed defects belong here, clearly labeled
  as defects, not as intentional limitations).
- Update any `architecture/` document or ADR the change actually affects. A structural change that
  isn't reflected in `architecture/` didn't really happen from a documentation standpoint.
- When a defect is found but deliberately not fixed in the current release, disclose it explicitly
  in the release report and in `docs/KNOWN_ISSUES.md` — never fix it silently while working on
  something else, and never leave it undisclosed either.

## Release process

1. Confirm the current regression baseline is clean before you start.
2. Identify the exact functions/files that will change; state this up front.
3. Implement, scoped tightly to what was actually asked — don't fold in unrelated cleanup.
4. Run the full testing sequence above.
5. Live-verify anything UI-facing or async, per the Browser Testing Policy.
6. Bump `APP_VERSION` in `index.html` and write the full `APP_VERSION_LOG` entry (root cause if
   applicable, every function touched, fixture counts, verification results).
7. Update documentation per the section above.
8. Report back: what changed, why each changed file/function needed to change, test results,
   protected-function drift results, live verification results, known limitations left
   deliberately untouched, and rollback instructions.

Do not begin work on a subsequent release until the current one has been reviewed and approved —
this project's history includes several instances of a release being explicitly paused for
verification before the next one starts; treat that as the default, not the exception.

## Regression requirements

- **Zero drift on `PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS`** is the release gate for any change
  that isn't an intentional, disclosed methodology change. See "Zero behavior drift policy" above.
- **All fixtures that can run, must run and pass** before a release ships. If a fixture suite
  cannot execute (missing source, environment issue), that is itself a finding to disclose, not a
  suite to silently skip.
- **A new optional SDK capability needs a "fails safely when absent" fixture**, not just a
  "works when present" fixture.
- **Never silently correct an unrelated pre-existing discrepancy** (a wrong fixture count, a
  failing unrelated Diagnostics check, etc.) while working on something else — flag it, document
  it, and if it's real follow-up work, spin it off as its own separately-scoped task.
