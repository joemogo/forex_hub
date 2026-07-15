# ADR-003: Paper-ledger transaction model

## Status

Accepted (established v11.0.1, correcting an incomplete v11.0 fix).

## Context

`paperAccount` (JVM's simulated trading account) and `journalEntries` (the JVM trade journal) are
deliberately separate stores (see [ADR-002](ADR-002-isolated-strategy-and-feature-storage.md)),
but a single trade event — opening or closing a position — must update both together: the
account gets a new/updated position and balance, and the journal gets a matching record.

Through v11.0, both were persisted by one general-purpose `save()` function, called after both
in-memory mutations were already made. `save()` wrote `fxhub_journal` unconditionally, then
attempted a version-guarded write of `fxhub_paper`. Two real problems followed from this (see
[INC-001](../INCIDENTS.md#inc-001--completed-paper-trades-appearing-as-journal-only-after-a-reset)
for the full incident):

1. If the guarded `paperAccount` write was rejected (a genuine two-tab conflict), the journal
   write had *already happened* — an incomplete, split transaction that left a real orphaned
   journal record with no matching account position.
2. Because `save()` is called from dozens of places with no relationship to the paper ledger
   (scanner renders, alerts, checklist edits, Academy progress...), the paper-account version
   guard was being exercised — and could reject a real trade — based on completely unrelated
   activity in another tab.

## Decision

Treat every paper-ledger-affecting action as an explicit, atomic-from-the-application's-perspective
transaction, structurally separate from general app-state persistence:

1. **General `save()` never touches `paperAccount`.** It persists every other piece of app state,
   but never `fxhub_paper` or `fxhub_paper_version`.
2. **`commitPaperLedger()` is the only function allowed to persist `paperAccount`.** It attempts
   the version-guarded paper-account write first; only if that succeeds does it call `save()` to
   persist everything else the same transaction touched (the linked journal mutation,
   `autoTrading.tradedToday`/log, reset history, the reconciliation audit trail).
3. **Every call site owns its own snapshot and rollback.** `openPaperPosition`,
   `closePaperPosition`, `setPaperBalance`, both reset confirmations, `clearTestTradesPaper`, the
   developer TEST-trade tagger, and `applyPaperReconciliation` each snapshot `paperAccount` (and
   any linked `journalEntries`/`autoTrading` state) before mutating, and restore that snapshot in
   memory if `commitPaperLedger()` reports rejection. `commitPaperLedger()` itself has no
   knowledge of what a given caller changed and performs no rollback on its own — that
   responsibility is deliberately kept at the call site, next to the mutation it corresponds to.
4. **A rejected commit is a visible, actionable failure.** It sets a session-global
   `paperLedgerBlockingError` message, rendered as a persistent red banner on Paper Trading
   (never gated behind Developer Mode) with a Reload Now action, and is recorded via
   `recordPaperEngineError()` for the Diagnostics-side Paper Ledger Integrity view.

## Rationale

- A version guard alone (v11.0's fix) prevents a *stale overwrite*, but does not prevent a
  *partial write* — those are different failure modes and need different fixes. Framing this as
  a transaction problem (what commits together, atomically, versus what's allowed to fail
  independently) addresses both.
- Scoping the guarded write to only genuine paper-ledger mutations (rather than every `save()`
  call) eliminates false-positive rejections from unrelated activity, without weakening the
  guard's actual protection against a real two-tab conflict.
- Putting rollback responsibility at each call site (rather than trying to make
  `commitPaperLedger()` generic enough to undo arbitrary mutations) keeps the transaction
  boundary explicit and readable at the exact place a future change is most likely to need to
  understand it.

## Consequences

- Any new code that mutates `paperAccount` must go through this same
  snapshot → mutate → `commitPaperLedger()` → rollback-on-rejection pattern. See
  [CODING_STANDARDS.md](../CODING_STANDARDS.md) rule 5 and
  [ARCHITECTURE.md](../ARCHITECTURE.md#the-paper-ledger-transaction-model-v1101).
- `checkAutoTrades()` required no structural change under this model — its existing
  `if(pos.error){return;}` guard, positioned before any `tradedToday`/log/notification side
  effect, was already correctly placed to depend on `openPaperPosition`'s success/failure result.
- This pattern is currently scoped to `paperAccount` only (the store actually proven to lose
  data). ALEX's equivalent store (`alexGAccount`) does not yet have an analogous guarded commit
  path — if ALEX's live auto-trading is ever found to have the same class of exposure, the same
  model should be applied there rather than inventing a different one.
