# Product Vision

## What MOGO is

MOGO is a browser-based forex trading research tool. It connects to a real OANDA account for
live market data, evaluates two independent, rules-based trading strategies against that data,
simulates trades in a paper (not real-money) account, and gives the user tools to review,
journal, and study the results.

It is a research and journaling tool, not an order-execution platform: no function anywhere in
the codebase places a real order against an OANDA (or any) brokerage account. Every "trade" MOGO
opens or closes is a paper position tracked entirely in the browser's own state.

## Naming: MOGO vs. JVM vs. ALEX

These three names mean three different things, and the distinction is deliberate and preserved
throughout the codebase (see
[ADR-001](adr/ADR-001-product-name-vs-strategy-identifier.md)):

| Name | What it is | Where it appears |
|---|---|---|
| **MOGO** | The product itself — the application's brand name. | `<title>`, the top-nav wordmark, the Trade Inspector header, desktop notification titles, the AI Assistant's own self-description. |
| **JVM** | The internal identifier for the app's original ("current") strategy. | `strategyLabel:'JVM'` on journal records, the Journal tab's strategy filter, function names like `journalNoteOpenJVM`, `buildJVMJournalOpenRecord`, `computeJVMExplanations`. |
| **ALEX** | The internal identifier for the second, independently-specified strategy, `alex_g_sr_v1` internally. | `strategyLabel:'ALEX'` on journal records, every `alexG*`-prefixed function, `alexGAccount`, `alexGJournalEntries`. |

MOGO was previously named "JVM Forex Hub" / "Forex Trading Hub"; the rebrand to MOGO (v7.0)
changed display text only. It deliberately did **not** rename the `JVM` strategy identifier
anywhere it is a stored value or code identifier, because doing so would have broken backward
compatibility with every already-stored journal record. "JVM" today reads as that strategy's own
internal label, distinct from the MOGO product name — not a leftover of the old product name.

## Current functionality

As of v11.0.1, the following are real, working features — not placeholders:

- **Live market data** from a connected OANDA account (practice or live environment).
- **JVM strategy**: automated signal detection, confluence scoring, and paper-trade execution
  (manual and automatic) against the frozen JVM rule set.
- **ALEX strategy**: an independent support/resistance-based strategy with its own zone
  detection, setup engine, live polling, and paper-trade execution — fully isolated from JVM in
  both code and storage.
- **Paper Trading**: a simulated account per strategy (`paperAccount` for JVM, `alexGAccount` for
  ALEX) with real position sizing, balance tracking, and win/loss history.
- **Unified Journal**: every trade from either strategy, normalized into one browsable,
  filterable record set, with a dedicated Trade Inspector for per-trade detail (summary,
  compliance checks computed from real stored data, decision timeline, performance metrics,
  chart replay, manual notes).
- **Paper Ledger Integrity diagnostic**: a live, read-only reconciliation between the journal and
  the paper account, plus an explicit-confirmation-gated tool to restore any genuinely orphaned
  trade.
- **Charting**: a full-featured candlestick chart (TradingView Lightweight Charts) with trade
  overlays, saved per-pair/timeframe views, and manual drawing tools.
- **Strategy Center**: a rules/methodology reference page for JVM (hero, entry model,
  disqualifiers, risk framework, real performance stats) with ALEX shown as a documented "Coming
  Soon" tab.
- **MOGO Academy**: a learning-content section with 55 named modules across 6 Schools; 1 module
  has the full premium lesson treatment (structured content, an interactive exercise, a scored
  knowledge check, homework), 2 more have earlier-generation written content and a simple quiz,
  and the rest are real-but-unwritten placeholders that say so honestly (see
  [KNOWN_ISSUES.md](KNOWN_ISSUES.md)).
- **AI Assistant**: an optional chat interface (bring-your-own Anthropic API key) that can see
  the user's live watchlist, open positions, and journal stats.
- **Diagnostics**: a self-test suite, a live historical-data pagination diagnostic, and the Paper
  Ledger Integrity card, all runnable from inside the app.

## Planned functionality

The following are named, scoped, and explicitly not yet built. They are represented in the UI
today (where applicable) as an honest "Coming Soon" panel rather than a broken or fabricated
page — see [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the full current list. High-level:

- A dedicated Charts workspace separate from the Scanner page.
- Deeper Analytics (equity curves, R-multiple distribution, setup-type breakdowns) beyond the
  Journal's own filters.
- Exportable Reports.
- A dedicated Market Outlook (macro/news/calendar) view.
- A dedicated Preferences page (today's toggles live on Diagnostics).
- A dedicated Developer console (today's Developer Mode lives on Diagnostics).
- The remaining 52 of 55 Academy modules' written content, and interactive Academy Trading
  Drills.
- AI-assisted grading and coaching in the Trade Inspector (explicitly deferred when the Trade
  Inspector foundation shipped in v10.0).
- A visual/spacing redesign pass on Journal, Paper Trading, and the AI Assistant, plus a
  responsive audit (tracked internally, not yet started — see [ROADMAP.md](ROADMAP.md)).

## Known limitations

Documented in full in [KNOWN_ISSUES.md](KNOWN_ISSUES.md). Do not treat an item there as a defect
to silently patch around — it is either an intentional scope boundary or a documented constraint
of the tooling used to build this app.
