# ADR-005: Strategy Registry / Manifest / Services framework

## Status

Accepted. Approved through a two-pass architecture design exercise (a full codebase audit,
followed by a Strategy SDK design pass) before any code was written. Release 1 (ALEX
registration, v12.0.0) is the first implementation step.

## Context

MOGO contains two fully-implemented, independently-running trading strategies (JVM and Alex G
S&R) built with a deliberately isolated pattern from the start: each has its own state tree, its
own `localStorage` namespace, its own save/load pair, and its own function-name prefix (`alexG*`
for Alex). A full architecture audit confirmed the strategies' *internal engines* were already
well isolated — the real coupling was confined to a small set of places where the surrounding
app (Dashboard, the unified Journal, the panel router, the Developer Mode toggle, Diagnostics,
Strategy Center) hardcodes both strategies by name. As MOGO moves toward supporting additional
strategies (TJR, ICT, Silver Bullet, and others) as an operating-system-style platform, adding
each one by hand-editing the same handful of hardcoded seam functions again would not scale, and
risks introducing exactly the kind of accidental behavior drift the project's regression-baseline
tooling exists to catch.

## Decision

1. **Separate "what strategies exist" from "what every strategy must provide."** A `STRATEGY_REGISTRY`
   is a small, boring directory (one entry per strategy: a `manifest` + a `services` object) —
   it holds references, never logic or computed data. A Strategy **Manifest** is static,
   lightweight, computed-performance-free metadata (identity, capabilities, dependencies,
   declared DNA, routing ids). Strategy **Services** exposes dynamic behavior as thin references
   to the strategy's own existing functions/state — never new trading logic, never a rewrite.
2. **Do not standardize a strategy's internal pipeline.** Scanning, qualification, trade
   construction, risk, and trade management stay strategy-internal, in whatever shape actually
   fits that strategy's logic (JVM's numeric confluence score vs. Alex's categorical zone/touch
   state machine are legitimately different, not two implementations of one abstract idea).
   Only the boundary the *core app* actually needs to call generically is standardized.
3. **Every registered capability that isn't wired this release is honestly absent, not stubbed.**
   A missing optional Service (e.g. `computePerformance`, `start`/`stop`, AI hooks) must cause
   graceful, tested fallback to prior hardcoded behavior — never a fabricated value, and never a
   silent no-op that looks like success.
4. **Migrate the least-risk strategy into an unproven contract first.** Release 1 registers ALEX
   only; JVM is migrated in a later release, explicitly treated as the harder validation of the
   contract (JVM has the larger seam surface), not a routine repeat of Release 1.
5. **Zero behavior drift is the release gate, not an afterthought.** Every release under this ADR
   must show zero drift across all `PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS`
   (`regression-baseline-tools.py`) before and after, since a Registry/Services refactor should
   never need to touch a protected trading function's body at all.

## Rationale

- The existing isolation discipline (ADR-002) already did the hard work of keeping the two
  strategies' internals apart; this ADR only formalizes the seam between them and the app, which
  is where the actual duplication and hardcoding lived.
- None of the seam functions targeted by this framework are on `PROTECTED_FUNCTIONS` — meaning
  the existing regression-baseline tool can mechanically prove zero trading-behavior drift for
  this entire migration line with no changes to the tool itself.
- Forcing a common interface onto strategies' internal pipelines would trade real accuracy
  (JVM and Alex's genuinely different qualification models) for a uniformity the core app does
  not actually need — exactly the "enterprise-style architecture" this project's own operating
  philosophy warns against.

## Consequences

- Adding a future strategy (TJR, ICT, Silver Bullet, or otherwise) should require only: its own
  state/storage/save-load pair (following the existing Alex pattern), its own engine functions
  added to `PROTECTED_FUNCTIONS` once frozen, and one new `STRATEGY_REGISTRY` entry — not further
  edits to Dashboard, the Journal, the panel router, Developer Mode, or Diagnostics.
- `regression-baseline-tools.py`'s `PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS` remain a
  deliberately hand-curated, reviewed list per strategy — not auto-generated from the registry —
  to preserve the reviewed-before-frozen property that makes the baseline trustworthy.
- Any future release that wires a new optional Service (statistics, settings, AI hooks, etc.)
  must ship its own disclosed capability change and its own fixtures proving graceful fallback
  when that Service is absent for a strategy that hasn't implemented it yet.
