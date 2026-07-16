# Release Notes

This is a readable, maintained summary of every MOGO release. It is deliberately condensed —
the original, complete, as-shipped text for every release (including full verification detail,
fixture counts, and forensic detail for reliability releases) remains in-code as
`APP_VERSION_LOG` in `index.html` and is never rewritten here. If a summary below and the
in-code log ever appear to disagree, the in-code log is the source of record.

**Rule for future releases:** every release that changes behavior must add an entry here (in
addition to its own `APP_VERSION_LOG` entry), and must update [TESTING.md](TESTING.md) and
[KNOWN_ISSUES.md](KNOWN_ISSUES.md), plus any ADR or [ARCHITECTURE.md](ARCHITECTURE.md) section
its change actually affects.

---

## v12.1.1 — Diagnostics data integrity
A focused data-integrity patch to the Diagnostics subsystem only — no new features, no Strategy
SDK/Registry work, no UI redesign. Fixed a silent journal-only-orphan leak in the "Paper trading
engine" self-test: it restored `pairData`/`paperAccount`/`activePair`/`fetchBidAsk`/the R:R
Calculator's fields, but never `journalEntries` — so a successful, green self-test run could
silently persist the simulation's own leftover journal record into the real `fxhub_journal` as an
untagged orphan, discovered during v12.1.0's live verification and disclosed but not fixed then.
Added a small, Diagnostics-only, unexported helper pair, `diagSnapshot()`/`diagRestore()`
(generalizing the existing save/restore pattern already used by `alexGIsolationCheck()` and
`openPaperPosition()`'s own snapshot fields — not a new architecture), and applied it to all three
self-tests that mutate real state, including `journalEntries`. A second, subtler defect was caught
by the new fixtures (not by code review) before shipping: `paperAccount` is isolated by reassigning
it to a fresh synthetic object before the simulation runs, so the real object is never touched —
but `journalEntries` was left pointing at the real, live array, and `openPaperPosition()` mutates
that array **in place** (`.unshift()`) rather than reassigning it, so merely restoring the
reference afterward was a no-op. Fixed by isolating `journalEntries` the same way `paperAccount`
already is. 13 new fixtures ship in `tests/v1211_diagnostics_integrity_tests.js`; zero drift across
all 63 protected functions and 4 protected constants; live verification confirmed `fxhub_journal`,
`fxhub_paper`'s content, and both ALEX storage keys are byte-identical before and after running the
real "Run Diagnostics" button (the one key that legitimately changes, `fxhub_paper_version`, is the
pre-existing v11.0.1 monotonic save counter, unrelated to this fix). See
[INCIDENTS.md](INCIDENTS.md) and the full `APP_VERSION_LOG` entry in `index.html` for complete
detail.

## v12.1.0 — Strategy Framework, Release 2: JVM registration
Registered JVM as the framework's second strategy, following the exact Manifest/Services
pattern ALEX used in v12.0.0. This was treated as the real validation of the SDK contract
(not a mechanical copy): a deliberate pre-implementation audit checked every Manifest field
and Service method JVM needs against the existing Release-1 contract, field by field. Verdict —
zero SDK extensions required. `computePerformance()`, reserved in the original design but never
exercised (ALEX has no live-performance function), is JVM's first real use of that slot, since
JVM has `computeMogoStrategyPerformance()`. `JVM_MANIFEST` reads `version`/`fullName`/`status`
directly from the existing `MOGO_STRATEGY_META` constant rather than restating them, and
`academySchoolId:'mogo'` is a real, verified link (`ACADEMY_SCHOOLS` already has that id).
4 of 8 previously-hardcoded seams needed a JVM-specific change (`getUnifiedJournalRecords`,
`renderDashboard`, `showPanel`, `applyDeveloperModeVisibility`); 3 more were reviewed and
deliberately left untouched with the reason disclosed — most notably, `renderMiniJournal()`'s
JVM branch is confirmed dead code, and Strategy Center's 2-strategy hardcoding is the optional
Release 3 scope named in [ADR-005](adr/ADR-005-strategy-framework.md), not required for this
release. Zero behavior drift: all 63 protected functions and 4 protected constants remain
byte-identical, all 28 pre-existing ALEX fixtures still pass, no `localStorage` key changed.
28 new fixtures ship in `tests/v121_jvm_registration_tests.js`, auto-discovered by
`tests/run_all.sh` with no runner changes needed.

## v12.0.0 — Strategy Framework Foundation, Release 1: ALEX registration
The first step of a multi-strategy architecture migration, approved via a two-pass architecture
design exercise before any code was written (see [ADR-005](adr/ADR-005-strategy-framework.md)).
Introduced a minimal Strategy Registry/Manifest/Services boundary and registered ALEX as its
first entry — without rewriting a single line of ALEX's existing engine. The Manifest is static,
lightweight, computed-performance-free metadata (identity, capabilities, dependencies, declared
DNA, routing ids); Services exposes thin references to ALEX's existing account/journal state and
functions (`getAccount`, `getJournal`, `normalize`, `onOpen`, `isolationCheck`, plus a reserved
`health` accessor) — only what this release's target seams actually need. Six of eight listed
seam functions were edited (`getUnifiedJournalRecords`, `renderDashboard`, `showPanel`,
`applyDeveloperModeVisibility`, `runDiagnostics`, `renderMiniJournal`), each a one-line-scoped
change with a safe fallback to the pre-v12.0.0 hardcoded behavior; the other two
(`toggleDeveloperMode`, `getFilteredJournalRecords`) needed no change, disclosed with why. JVM is
**not** registered this release — every JVM-specific code path is untouched. Zero behavior
change: all 63 protected functions and 4 protected constants remain byte-identical to v11.4.0, no
localStorage key was added/removed/renamed, and existing saved data loads with zero migration.
28 new fixtures plus the complete pre-existing suite pass. Live verification confirmed Dashboard,
Journal, the ALEX panel, Strategy Center, Developer Tools, and Diagnostics all render identically
to v11.4.0. A pre-existing, unrelated Diagnostics self-test failure ("Paper trading engine (sizing
+ auto-close)") was discovered during verification and deliberately not fixed — see
[KNOWN_ISSUES.md](KNOWN_ISSUES.md).

## v11.4.0 — MOGO Academy lesson engine foundation
Built a reusable Academy lesson engine and one complete gold-standard lesson rather than many
shallow ones. Renamed the five existing Tracks to Schools (ids kept byte-identical for backward
compatibility) and added a sixth, Market Intelligence, bringing the module count from 49 to 55.
Added a new rich lesson schema (`ACADEMY_LESSON_LIBRARY`) alongside the untouched legacy
`ACADEMY_LESSONS` store, with a pure 3-tier lookup (`academyGetLesson()`) so lessons without
written content still render an honest "coming in a future release" stub. Built a full premium
lesson template — hero, objectives, sectioned content with callouts, key takeaways, common
mistakes, professional tips, an interactive classification exercise, a scored knowledge-check
quiz with retry and a persisted best score, homework, personal notes, and gated Mark Complete —
and wrote Forex Foundations Module 1, "How the Forex Market Works," to the full spec. Extended
Academy progress (quiz scores, homework, notes, recently opened) additively, with existing
`mogo_academy_progress` data migrating forward automatically. Added Academy-wide search and a
richer Academy Home. Zero Scanner/signal/paper-trading/journal/JVM/ALEX/chart code touched,
confirmed by zero drift in the regression baseline. See [INCIDENTS.md](INCIDENTS.md) if a future
Academy-related defect needs tracing back to this restructure.

## v11.3.0 — Pre-Trade Checklist badge text + future-state prep
UI-only change to the Strategy Center's Section H Pre-Trade Checklist. Replaced the "NOT
CONNECTED" badge text with "OFF MARKET • NO SCAN" (text only — the existing gray color/size/
spacing is unchanged) and updated the informational lede to explain that the checklist will
populate automatically from the live Scanner during market hours. Added a `SC_CHECKLIST_BADGE_STATES`
config and `renderScChecklistBadge()` helper so a future release can swap which of five states
(off market/waiting/scanning/complete/attention — gray/blue/gold/green/red) a row displays
without touching markup — no state logic was implemented, every row still hardcodes the
off-market state today. The separate, already-interactive Sunday Scan checklist is untouched.

## v11.2.0 — Timeframe-aware chart display history
A follow-on to v11.1.0: most Scanner charts only showed roughly one to two trading days of
history because `loadChart()` always requested a fixed 200 candles regardless of timeframe — on
M15 that's only ~50 market hours. Added a single pure helper, `getChartCandleCount(timeframe)`,
returning a sensible display count per timeframe (M15/H1: 500, H4: 400, D: 365, W: 260, M: 180),
used *only* inside `loadChart()`'s own chart fetch. Every other candle fetch in the app —
`evaluateLiveTrigger()`'s entry-timing window, `scanPair()`'s confluence/signal fetch,
`getStructuralAOI()`, `runAutoTopDownScan()`, and Replay/Backtest's paginated fetch — keeps its
own independent, unchanged count; none of them feed the visible chart's history. Falls back to
the previous fixed count if the larger request fails, and shows a loading state while the
primary fetch is in flight. A direct usability improvement rather than a defect — see
[INCIDENTS.md](INCIDENTS.md#inc-002) for the related saved-view bug (v11.1.0) this follows.

## v11.1.0 — Chart saved-view self-heal
A user-reported chart bug (a small cluster of real candles crammed against one edge with a large
blank area everywhere else) was traced to `saveChartView()` persisting raw logical-index
positions with no record of how many candles existed when the view was saved — a later reload
with a substantially different candle count (e.g. an off-hours/weekend gap) applied a now-stale
range unconditionally. Fixed with a new `isSavedChartViewValid()` check: a saved view is only
restored if it still overlaps real, current data closely enough; otherwise it's discarded and the
chart self-heals via the same `fitContent()` path already used when no saved view exists, with no
user action required. Chart-viewport subsystem only — zero trading functions touched, confirmed
by zero drift in the regression baseline. See [INCIDENTS.md](INCIDENTS.md#inc-002).

## v11.0.1 — Paper ledger transaction correction
An independent code review found a more precise defect than v11.0's own fix addressed: `save()`
could persist a journal record even when the linked paper-account write was rejected (a split
transaction), and the paper-account version guard was being triggered by totally unrelated
saves. Fixed by making paper-account persistence its own dedicated, atomic commit path,
completely separate from general app state saving. See [INCIDENTS.md](INCIDENTS.md) for the full
incident writeup.

## v11.0 — Paper Ledger Integrity: stale-save race root-cause fix
Root-caused and fixed a real defect where completed paper trades could show as "Journal only" in
the unified journal while the Paper Trading page showed a fully-reset account. Added a version
guard on the paper-account store, a Paper Ledger Integrity diagnostic, and a
confirmation-gated reconciliation tool. (Superseded in part by v11.0.1 above — see
[INCIDENTS.md](INCIDENTS.md).)

## v10.0 — Trade Intelligence Foundation
Added a dedicated, nav-reachable Trade Inspector page (summary, real compliance checks computed
from stored data, decision timeline, performance metrics, chart replay, manual notes, and a
placeholder AI Review section) on top of the existing inline Trade Inspector component from v5.0,
which remains unchanged.

## v9.0 — Paper trading data-integrity audit + durable regression baseline
Investigated and explained why Paper Trading and the Strategy Journal could disagree (they are
two independent stores; account reset never touched the journal by design). Added a read-only
classification layer for every journal record, replaced the single ambiguous "Reset Account"
confirmation with a 3-option modal, and created the durable, committed regression-baseline tool
(`regression-baseline-tools.py` / `regression-baseline.json`).

## v8.0 — Scanner layout fix, Strategy Center, nav audit, Training Academy
Fixed a real chart/panel layout clipping bug. Rebuilt the plain Rules page into a full Strategy
Center (hero, entry model, disqualifiers, risk framework, real performance stats). Audited every
navigation item and replaced silent misrouting with honest "Coming Soon" pages. Added the MOGO
Training Academy (5 tracks, 49 named modules, 3 fully written with quizzes).

## v7.0 — Rebrand + grouped navigation + Dashboard
Rebranded the app's display name from "JVM Forex Hub"/"Forex Trading Hub" to MOGO (cosmetic
strings only — the `JVM` strategy identifier in stored data and code was deliberately left
unchanged). Replaced the flat top-nav with grouped dropdown navigation. Added a Dashboard landing
page built from data the app already computes elsewhere.

## v6.1 — Manual chart drawing tools
Built the interactive drawing toolbar on top of the v6.0 data-model foundation: horizontal
lines, rectangles, trendlines, and text notes, with hit-testing, selection, undo/redo, a Drawing
Inspector, and per-pair/timeframe persistence — fully isolated from trading state.

## v6.0 — Chart usability and visual trade overlay
Fixed a flat-line/tiny-candle chart bug (an autoscale conflict between AOI reference lines and
candlesticks). Added Fit Visible/Fit All/Reset View, saved per-pair/timeframe chart views, a
full trade overlay (entry/stop/target lines, markers, risk/reward shading) driven only by stored
trade data, and the underlying (non-interactive yet) drawing data model.

## v5.0 — Unified trade experience
Unified the JVM and ALEX journals into one normalized, filterable record set with a shared inline
Trade Inspector, standardized page layout, and reorganized navigation.

## v4.3 — Developer Test Mode
Added a hidden-by-default "Developer Test Tools" section (revealed by a session-only Developer
Mode toggle) that generates synthetic BUY/SELL/WIN/LOSS trades through the same real, frozen
open/close functions a live trade uses, tagged and filterable as TEST trades.

## v4.2 – v4.2.2 — ALEX live paper trading
Connected the validated ALEX zone/setup/trade-construction pipeline to live OANDA data so it can
detect real setups and open/close simulated ALEX paper trades automatically. v4.2.1 corrected a
real exit-monitoring gap (comparing a position's stop/target against a single bid/ask instead of
walking the full historical candle range since the last check). v4.2.2 was a UI/reliability
reporting release for the exit-detection metadata v4.2.1 introduced.

## v4.0 – v4.0.1 — ALEX trade construction, replay & role correction
v4.0 converted qualified ALEX setups into complete hypothetical trades and walked them through
historical candles to a result, adding a historical replay engine and stats. v4.0.1 was a narrow
correction release fixing a zone-role initialization defect the v4.0 report itself had disclosed.

## v3.4 – v3.6.1 — ALEX G S&R foundation
Introduced the ALEX strategy from scratch as a fully independent module: the frozen rule
specification (v3.4), an independent zone-detection engine (v3.5), deterministic setup
qualification (v3.6), and a narrow correction release (v3.6.1) fixing two setup-metadata defects
found in a follow-up audit — none of which changed ALEX's actual trading methodology.

## v3.0 – v3.3 — TRUE MTF Replay
Added a dedicated multi-timeframe replay/research engine for validating the JVM strategy against
real historical data, plus three correction releases (v3.1–v3.3) fixing confluence-scoring,
statistics-display, and lookahead-timing defects the replay engine itself surfaced.

## v1.0 – v2.9 — Core JVM strategy and early hardening
The original build: paper trading, auto paper trading, the AI Assistant, Diagnostics, automatic
top-down scanning, and bias-filtered chart markers (v1.0), followed by a long series of
targeted fixes and additions — notification/UX polish, AOI zone-detection rebuilds and rendering
fixes, a Backtest tab with funnel/optimizer views, additional chart timeframes, a security pass
(v2.6 — fixed a real stored-XSS vulnerability in AI chat/journal/scan notes), bid/ask-aware paper
trading fills (v2.7), and a historical-data pagination fix (v2.9).
