# Roadmap

This is a high-level map of where the project has been and what's explicitly planned next. For a
readable per-release summary, see [RELEASE_NOTES.md](RELEASE_NOTES.md). For the original,
unabridged text of every release, see `APP_VERSION_LOG` in `index.html` — that in-code log is the
verbatim source of record and is never rewritten by this documentation.

## Release phases

- **Phase 1 — Platform Foundation: COMPLETE (v12.0.0 – v12.1.1).** Established the repository
  itself (git init, `.gitignore`, `architecture/` docs, `CONTRIBUTING.md`, the canonical
  repository-owned test runner `tests/run_all.sh`) and the Strategy Registry/Manifest/Services
  framework the platform is built on (see [ADR-005](adr/ADR-005-strategy-framework.md)), then
  proved that framework by migrating both existing strategies into it — ALEX (v12.0.0) and JVM
  (v12.1.0) — with zero behavior drift confirmed at every step. v12.1.1 closed out the phase with
  a focused Diagnostics data-integrity fix (see [INC-003](INCIDENTS.md#inc-003--diagnostics-self-test-could-silently-persist-a-fake-trade-into-the-real-journal)),
  leaving the platform's foundation — versioning, testing, documentation, and the strategy
  boundary itself — reproducible from a fresh clone and sealed at tag `v12.1.1`.
- **Phase 2 — Strategy Expansion: begins with v12.2.0.** With the Strategy SDK contract now
  validated twice (once per strategy, with zero extensions needed for JVM's harder integration
  surface), this phase adds genuinely new strategies on top of the now-proven framework — TJR,
  ICT, Silver Bullet, and others named in [PRODUCT_VISION.md](PRODUCT_VISION.md) — each expected
  to require only its own state/storage/save-load pair and one new `STRATEGY_REGISTRY` entry, per
  ADR-005's stated consequence of the framework work. No Phase 2 release has started; this
  roadmap entry will be updated with real scope, not aspiration, once one does.

## Where the project has been

Grouped by era rather than every point release (there are 50+ entries in the full log):

| Era | Versions | What it established |
|---|---|---|
| Early paper trading & backtesting | v1.0 – v2.9 | Core JVM signal detection, AOI zones, confluence scoring, paper trading, backtesting, a security review pass (v2.6) |
| TRUE MTF Replay | v3.0 – v3.3 | A dedicated multi-timeframe replay/research mode for JVM |
| ALEX G S&R foundation | v3.4 – v4.0.1 | The independent ALEX strategy: rule spec, zone engine, setup qualification, trade construction, and a role-correction release |
| ALEX live paper trading | v4.2 – v4.2.2 | Connected ALEX to live OANDA data with its own auto-trading, exit monitoring, and reliability corrections |
| Developer tooling | v4.3 | Developer Mode and synthetic test-trade generation for both strategies, isolated from real logic |
| Unified journal | v5.0 | One normalized journal record set spanning both strategies, with a shared inline Trade Inspector |
| Charting | v6.0 – v6.1 | Full chart usability (fit/zoom/fullscreen), trade overlays, and manual drawing tools |
| MOGO rebrand & Dashboard | v7.0 | Product rebrand from "JVM Forex Hub" to MOGO, grouped navigation, a Dashboard landing page |
| Strategy Center, Academy, nav audit | v8.0 | Rebuilt Rules page into a real Strategy Center, added the Training Academy, honest "Coming Soon" pages for unbuilt nav items |
| Paper ledger integrity | v9.0 – v11.0.1 | A data-integrity audit and 3-option reset modal (v9.0), a dedicated Trade Inspector page (v10.0), and two releases root-causing and correctly fixing a real paper-account/journal desync defect (v11.0, v11.0.1 — see [INCIDENTS.md](INCIDENTS.md)) |
| Documentation | v11.0.1 follow-on | This documentation structure (README, docs/, ADRs, prompt archive) |
| Platform Foundation (Phase 1) | v12.0.0 – v12.1.1 | Git repository initialization, the Strategy Registry/Manifest/Services framework ([ADR-005](adr/ADR-005-strategy-framework.md)), migrating ALEX (v12.0.0) then JVM (v12.1.0) into it with zero behavior drift, the canonical repository-owned test runner, and a Diagnostics data-integrity fix (v12.1.1 — see [INC-003](INCIDENTS.md#inc-003--diagnostics-self-test-could-silently-persist-a-fake-trade-into-the-real-journal)) |

## What's explicitly planned but not yet built

These are named and scoped, not vague aspirations. They should not be treated as done, and a
future release picking one of these up should update this file when it ships.

- **v7.3 (tracked, not started)**: a visual/spacing redesign pass on Journal, Paper Trading, and
  the AI Assistant pages.
- **v7.4 (tracked, not started)**: a design-system pass and full responsive audit (targeted at
  1440p/ultrawide/laptop breakpoints).
- **Dedicated pages for the six current "Coming Soon" nav items**: Charts, Analytics, Reports,
  Market Outlook, Preferences, Developer. Each already has a named scope description in its
  Coming Soon panel — see [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
- **Remaining Academy content**: as of v11.4.0's School restructure (5 Tracks renamed to
  Schools, plus a new 6th School, Market Intelligence), the Academy has 55 total modules. 1 has
  the full premium lesson treatment (Forex Foundations, "How the Forex Market Works," written to
  the new rich schema) and 2 more have the original legacy-schema content from v8.0 (also Forex
  Foundations); the remaining 52 are real (titled, School-assigned, time-estimated) but not yet
  written, and honestly display "coming in a future release" rather than a fabricated lesson.
  Interactive Trading Drills are scoped but not built.
- **AI-assisted grading and coaching** in the Trade Inspector — explicitly deferred when the
  Trade Inspector foundation shipped (v10.0); the "AI Review" section there is a static
  placeholder today.

## What is not planned

Anything not listed above or in [PRODUCT_VISION.md](PRODUCT_VISION.md)'s "Planned functionality"
section is not a committed direction for this project — in particular, there is no plan to
connect MOGO to real order execution. It is a paper-trading research and journaling tool by
design (see [ADR-004](adr/ADR-004-read-only-analytics-principle.md)).
