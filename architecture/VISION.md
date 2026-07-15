# Vision

## Product identity

**MOGO — A Forex Trading OS.**

MOGO began as a single trading application built around one strategy (internally identified as
`JVM`, a naming holdover from before the MOGO rebrand — see
[ADR-001](../docs/adr/ADR-001-product-name-vs-strategy-identifier.md)). It grew a second,
fully independent strategy (Alex G Support & Resistance, `alex_g_sr_v1`) built in parallel. As of
v12.0.0, MOGO is deliberately repositioning from "an app with two strategies" to **an operating
system that hosts multiple trading strategies** as first-class, pluggable modules — with paper
trading, journaling, statistics, charting, an Academy, and (eventually) AI coaching as shared
services every strategy gets for free.

## Where MOGO is going

The explicit, approved direction (established across a full architecture audit and a Strategy SDK
design pass before any framework code was written — see
[ADR-005](../docs/adr/ADR-005-strategy-framework.md)) is a platform that can eventually host:

- The existing strategies: **JVM** and **Alex G S&R**.
- Named future strategies: **TJR, ICT, Silver Bullet**.
- Further MOGO-authored strategies not yet named.
- Eventually, community-contributed strategies.

Every one of these should be able to plug into MOGO **without requiring changes to the core
application** — the Dashboard, the unified Journal, Charts, Statistics, the Scanner shell, and
(eventually) AI coaching should all work generically over however many strategies are installed,
not be hand-edited per strategy.

## What MOGO is not

- **Not a real-money trading platform.** MOGO never places a real order. `paperAccount` and every
  strategy's own account (`alexGAccount`, and any future strategy's account) are simulations only
  — no function anywhere calls a real brokerage order-placement endpoint. This is a deliberate,
  permanent product boundary (see
  [ADR-004](../docs/adr/ADR-004-read-only-analytics-principle.md)), not a missing feature.
- **Not an enterprise platform for its own sake.** Every architectural decision in this project
  has been evaluated against "does this make it easier to add the next strategy without touching
  the core engine again" — not against a generic notion of scalability. Abstraction is added only
  when a real, current seam demands it (see [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)).

## Guiding philosophy

Two principles have held since the project's earliest releases and now govern the multi-strategy
framework explicitly:

1. **Zero behavior drift.** A structural or architectural change must never alter what a strategy
   actually does — its scanning, qualification, entry timing, stop/target placement, sizing,
   polling, or journaling. Every release proves this mechanically against a frozen baseline of
   protected functions and constants (see [docs/TESTING.md](../docs/TESTING.md)).
2. **Read-only, honest analytics.** Derived data (statistics, progress, DNA) is always computed
   fresh from real stored data, never fabricated and never cached as a second source of truth
   (see [ADR-004](../docs/adr/ADR-004-read-only-analytics-principle.md)).

These two principles are why a multi-strategy framework was judged feasible with low risk: the
existing strategies were already isolated enough, and the project's own testing discipline already
provided the mechanism to prove any refactor doesn't quietly change trading behavior.
