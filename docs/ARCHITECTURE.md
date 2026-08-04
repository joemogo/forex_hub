# Architecture

## Single-file application

The entire application — HTML structure, CSS, and JavaScript — lives in one file,
[`index.html`](../index.html) (~10,000 lines as of v11.0.1), inside a single `<script>` tag. There
is no bundler, no module system, and no backend. All application code shares one global JS scope.

Two other `.html` files exist in this directory (`forex_hub.html`, `trading_hub_v45.html`) as
historical artifacts predating the current baseline; they are not part of the running
application and are not maintained. A third file,
[`index-v2.9-KNOWN-GOOD.html`](../index-v2.9-KNOWN-GOOD.html), is a frozen, byte-for-byte
snapshot used as an integrity reference — see below.

## Panels and navigation

The UI is a set of top-level `<div class="panel" id="panel-X">` sections, exactly one of which is
visible at a time. `showPanel(name, btn)` toggles the active panel and runs that panel's own
init/refresh call (e.g. `renderPaper()`, `renderDashboard()`). Navigation is a set of grouped
dropdown buttons (`Dashboard`, `Trading`, `Strategy`, `Performance`, `Intelligence`, `Settings`)
added in v7.0; each real leaf button calls `showPanel('name', this)` directly.

Current real panels: `dashboard`, `scanner`/`scan`, `watchlist`, `paper`, `alexg`, `rules`
(Strategy Center), `truemtf` (TRUE MTF Replay), `backtest`, `journal`, `tradeinspector`, `ai`,
`academy`, `diagnostics`. A shared `comingsoon` panel (`comingSoonOpen(title, desc)`) is used by
nav items with no dedicated page yet — see [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

## JVM vs. ALEX: two isolated strategies

MOGO runs two independent trading strategies. They are isolated at every layer:

| | JVM (current strategy) | ALEX (`alex_g_sr_v1`) |
|---|---|---|
| Paper account variable | `paperAccount` | `alexGAccount` |
| Journal variable | `journalEntries` | `alexGJournalEntries` |
| Rule constants | `RULES`, `WEIGHTS`, `ALERT_THRESHOLD` | `RULES_ALEXG` |
| Function prefix | none (historical) | `alexG*` |
| Storage keys | `fxhub_paper`, `fxhub_journal`, `fxhub_auto`, ... | `fxhub_alexg_account`, `fxhub_alexg_journal`, `fxhub_alexg_auto`, `fxhub_alexg_zones`, `fxhub_alexg_setups` |

No function on one side reads or writes the other side's state. This isolation is not just
convention — it is mechanically verified by dedicated fixtures in every release that touches
either strategy (see [TESTING.md](TESTING.md)).

Both strategies' actual trading methodology (signal qualification, entry/stop/target
calculation, direction, exit logic) is treated as **frozen**: it may only be extended with new,
additive, clearly-disclosed fields or functions, never altered in place. See
[CODING_STANDARDS.md](CODING_STANDARDS.md).

## The unified journal

`getUnifiedJournalRecords()` merges `journalEntries` and `alexGJournalEntries` through a single
`normalizeJournalRecord(raw, storeStrategy)` function into one consistent shape (`strategyLabel`,
`tradeSource`, entry/stop/target/result/etc., plus strategy-specific fields left `null` where not
applicable). This is what the Journal tab, both mini-journals, the Dashboard, and the Trade
Inspector all read from — it is a read-side projection, not a third store; it never writes back
to either underlying journal.

## Paper Ledger Integrity (v9.0) and the classification layer

`classifyJvmJournalRecord(r)` is a pure, read-only function that answers "what is this JVM
journal row's actual relationship to the current `paperAccount`?" — `Active position`, `Closed
account trade`, `Journal only`, `Account reset history`, `Manual entry`, `Legacy/imported`, or
`Developer test`. It never mutates state and never fabricates a missing position.
`computePaperLedgerIntegrity()` (v11.0) builds on it to surface orphans, duplicates, and balance
mismatches live on the Diagnostics page.

## The paper-ledger transaction model (v11.0.1)

This is the most important persistence rule in the codebase, and the one most likely to be
violated by an unaware future change — see [ADR-003](adr/ADR-003-paper-ledger-transaction-model.md)
for the full reasoning and the incident that motivated it.

- **General `save()` does not persist `paperAccount`.** It persists every other piece of app
  state (`scanData`, `journalEntries`, `checklistState`, `alertLog`, `autoTrading`, `autoScan`,
  `paperResetHistory`, `tradeNotes`, `paperReconciliationAudit`) but never touches
  `fxhub_paper` or `fxhub_paper_version`. It is safe to call `save()` from anywhere, at any
  frequency, without it affecting the paper ledger.
- **`commitPaperLedger()` is the only function allowed to persist `paperAccount`.** It attempts a
  version-guarded write (`savePaperAccountGuarded()`) first; only if that succeeds does it call
  `save()` to persist everything else the transaction touched (the linked journal mutation,
  `autoTrading.tradedToday`/log, reset history, the reconciliation audit trail).
- **Linked state commits together, or not at all.** Every call site that mutates `paperAccount`
  (`openPaperPosition`, `closePaperPosition`, `setPaperBalance`, both reset confirmations,
  `clearTestTradesPaper`, the developer TEST-trade tagger, `applyPaperReconciliation`) snapshots
  `paperAccount` and any linked `journalEntries`/`autoTrading` state *before* mutating, and rolls
  both back to that snapshot in memory if `commitPaperLedger()` reports rejection.
  `checkAutoTrades()` relies on this: its post-open side effects (`tradedToday`, the auto-trade
  log, notifications) are gated behind `openPaperPosition`'s own success/failure result, so a
  rejected commit can never mark a pair as traded or log a trade that didn't actually persist.
- **A rejected commit is a visible failure, not a silent no-op.** `commitPaperLedger()` sets a
  session-global `paperLedgerBlockingError` message, which renders as a red banner at the top of
  the Paper Trading page (not gated behind Developer Mode) with a Reload Now action, whenever any
  paper-ledger mutation is blocked — most commonly a genuine two-tab/two-session write conflict.

## The durable regression baseline

[`regression-baseline-tools.py`](../regression-baseline-tools.py) extracts and SHA-1 hashes the
exact source of every function and constant considered frozen trading methodology (see
`PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS` in that file — 63 functions, 4 constants as of
v11.0.1) directly out of `index.html`, plus the SHA-1 hash of the frozen
`index-v2.9-KNOWN-GOOD.html` reference file and the current fixture counts. It writes/compares
against the committed [`regression-baseline.json`](../regression-baseline.json). This exists
specifically so an accidental change to trading logic is caught mechanically, even if it's
buried inside an otherwise-unrelated release. See [TESTING.md](TESTING.md) for usage.

## Security baseline (v12.1.3)

Credential handling, XSS/escaping policy, the Manual Lock privacy barrier, CSP status, and the
external-dependency inventory are all documented in [SECURITY.md](SECURITY.md) rather than
duplicated here. In brief: the OANDA token is memory-only (never persisted); the Anthropic key is
persisted client-side by explicit user action and documented as a temporary design pending a
future backend boundary; Manual Lock is a client-side visibility/interaction gate (`mogoLock`,
`fxhub_lock`), not authentication, that conceals the app and blocks sensitive actions while
leaving Scanner polling, chart updates, paper-position monitoring, and already-running automation
untouched.

## Supporting subsystems (brief)

- **Chart**: TradingView Lightweight Charts (v4.1.3, via CDN). `loadChart()`/`destroyChart()`
  manage the chart instance; trade overlays and manual drawings (`chartDrawings`, its own
  `fxhub_chart_drawings` key) are display-only layers driven entirely by already-stored data.
- **AI Assistant**: a chat interface against the Anthropic API using a user-supplied API key
  (stored client-side only — see [STORAGE_KEYS.md](STORAGE_KEYS.md)). It can read live app state
  to answer questions but has no write access to any trading state.
- **Academy** (MOGO Academy, `academy` panel): an isolated learning-content and
  progress-tracking subsystem (`academyProgress`, its own `mogo_academy_progress` key) that
  never reads or writes any trading state. Content is organized into 6 Schools
  (`ACADEMY_SCHOOLS` — `foundations`/`technical`/`mogo`/`platform`/`development`/`intelligence`;
  the first 5 ids are the pre-v11.4.0 "Track" ids, kept byte-identical during the v11.4.0
  Track→School rename since `academyLessonId(schoolId,idx)` derives every persisted lesson id
  from schoolId+index), 55 modules total. Lesson content lives in two separate stores: the
  original `ACADEMY_LESSONS` (legacy, simple `{title,body,keyTakeaway,quiz:[...]}` shape,
  untouched since v8.0) and `ACADEMY_LESSON_LIBRARY` (v11.4.0+, a richer schema —
  `contentSections`, `examples`, `commonMistakes`, `professionalTips`, `interactiveExercise`,
  scored `quiz`, `homework`, `glossaryTerms`, cross-links to real platform pages). A pure,
  read-only `academyGetLesson(lessonId)` is a 3-tier lookup (rich library → legacy store → null)
  — this is the compatibility layer that lets the two schemas coexist indefinitely without a
  migration: a lesson with no rich content yet still renders an honest "coming in a future
  release" stub rather than erroring or fabricating content. Progress
  (`academyProgressDefaultShape()`) is additive — `loadAcademyProgressSaved()` merges saved data
  onto the current default shape via `Object.assign`, so new fields (`quizScores`,
  `homeworkAcknowledged`, `homeworkNotes`, `lessonNotes`, `recentLessonIds`, added in v11.4.0)
  appear automatically for existing users without a migration step or lost data. Progress
  percentages (`academyComputeSchoolProgress`/`academyComputeOverallProgress`) are always
  computed on demand from `completedLessonIds`, never separately cached — the same read-only
  derived-value principle as [ADR-004](adr/ADR-004-read-only-analytics-principle.md).

## Trader Intelligence (research subsystem, outside the application)

`docs/trader-intelligence/` plus `scripts/trader_intelligence/` form a research system that turns
trader material (transcripts, and later replay and paper-trading results) into structured,
provenance-tracked, confidence-rated data. **It is not part of the application.** It never runs in
the browser, is never loaded by `index.html`, has no localStorage key, and cannot place, modify, or
close a trade. Every module is pure Python standard library with no network capability and no LLM
call — both properties are enforced structurally by tests, not merely by convention.

The boundary is deliberate and one-directional: the research subsystem may read `index.html` (the
regression baseline tooling does), but nothing in the application reads the research subsystem. A
`StrategyRule` becoming well-evidenced there authorizes no code change by itself — promotion runs
through an 18-stage `PromotionState` gate (`graph/schema/promotion-state.schema.json`) where every
transition past `DISCOVERED` requires a traceable `OwnerDecision`, and the final step from an
approved rule candidate to real execution logic is deliberately outside all automation
([ADR-008](adr/ADR-008-evidence-intelligence-engine.md) §9–10).

Three layers: **acquisition** (what to ingest next), **evidence** (what we know and how well —
intake manifests, transcript segments, annotations, evidence items, claims, links, contradictions,
questions, trader profiles, draft blueprints, knowledge gaps, hypotheses), and the **Knowledge
Graph** (a deterministic build over every authoritative record, with integrity validation). Claim
confidence is always computed from stored evidence links, never authored — and because independence
groups key on source, a single source structurally cannot corroborate itself into a promotable rule.

Start at [`docs/trader-intelligence/README.md`](trader-intelligence/README.md); the ingestion
runbook is [`OPERATOR-PLAYBOOK.md`](trader-intelligence/OPERATOR-PLAYBOOK.md). Testing is covered by
[TESTING.md](TESTING.md) §4.

## Evidence Platform (v12.8.0, MOGO-003 Phase 1)

MOGO now has **two browser storage media, not one**. `localStorage` is a bounded **working buffer**;
a new IndexedDB database (`mogo_evidence`) is the **automatic evidence store**, written with no user
action on every ALEX trade close; and a **successfully completed file export** is the only tier
intended to survive clearing site data. See
[ADR-010](adr/ADR-010-evidence-package-persistence.md) and [STORAGE_KEYS.md](STORAGE_KEYS.md).

⚠️ **IndexedDB is not a backup.** Clearing site data destroys `localStorage` and IndexedDB together,
and an exported file still lives on the same disk as the browser profile. The application states
both limits in the Diagnostics card and the standing banner rather than implying durability it does
not have.

**The defect this closes.** `saveAlexGRest()` and `save()` were both `try{…}catch(e){}` — a
quota-exceeded write failed and nothing anywhere reported it, which made *silent* evidence loss the
default. Both now classify the error, record it to the existing engine-error channel, emit a
`DATA_UNAVAILABLE` decision event and raise a persistent banner. **Both still never throw**:
`commitAlexGLedger()`/`commitPaperLedger()` call them *after* their guarded units have already
succeeded, so their best-effort semantics are load-bearing and are preserved exactly.

**Integrity, scoped honestly.** Each package carries a SHA-256 `contentHash` over a deterministic
canonical form (`mogo.evidence-canon.v1`) that excludes the integrity fields and the `export` block,
so marking a package exported can never change its hash. This detects **alteration**. It is not
authenticity, not identity verification, and not a signature — anyone able to modify a package can
recompute its hash. `alexGStableHash` is a 64-bit FNV variant and is deliberately not used here.

**The capture seam.** `alexGCloseLivePosition` is protected and untouched. Capture is installed at
the non-protected caller, **after** the `alexGCheckLivePositions` loop and next to the existing
save, in its own try/catch — the same seam pattern used by MOGO-002.5 provenance stamping, the v1.1
entry-day gate and the 002.8B suspension gate. It is fire-and-forget and structurally cannot
prevent, repeat, delay or alter a close.

**The boundary with the ledger.** The evidence layer reads trading state and never writes it. Buffer
caps apply only to `fxhub_alexg_setups` (1,000) and `fxhub_alexg_zones` (200 per pair) — the two
genuinely unbounded stores. **The guarded journal/ledger path is never capped, evicted, rewritten or
bypassed** ([ADR-003](adr/ADR-003-paper-ledger-transaction-model.md) is reinforced, not relaxed).
No tier-(a) record is evicted until its evidence is committed to tier (b), and tier-(b) packages are
never automatically deleted.
