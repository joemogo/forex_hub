# ADR-004: Read-only analytics principle

## Status

Accepted (established informally from v1.0 onward; named and reinforced explicitly from v9.0's
data-integrity work through v11.0.1).

## Context

MOGO computes a large number of derived views over trading data: the unified journal, Strategy
Center performance stats, Trade Inspector compliance checks and decision timelines, the Paper
Ledger Integrity diagnostic, and chart trade overlays. Every one of these is tempting to make
"friendlier" by filling in a gap — showing an estimated figure instead of "insufficient sample,"
inferring a missing timeline event, or quietly reconstructing a missing account position from
journal data so a page looks complete.

MOGO also, by design, never executes a real trade against a brokerage account — everything it
opens or closes is a simulated paper position.

## Decision

1. **Analytics and derived views are strictly read-only and never fabricate missing data.** Every
   function that computes a display value from stored data must either compute it from data that
   genuinely exists, or honestly show that it can't be computed (`JOURNAL_NOT_RECORDED`, "Not
   Evaluated," "insufficient clean sample," an empty state) — never a placeholder, an estimate
   presented as fact, or a silently-invented timestamp/event.
2. **A derived view never becomes a second source of truth.** `getUnifiedJournalRecords()`,
   `classifyJvmJournalRecord()`, and `computePaperLedgerIntegrity()` all compute their output
   fresh from the real underlying stores every time they're called; none of them persist their
   own output as if it were independently authoritative data.
3. **Reconciling genuinely inconsistent data requires an explicit, user-confirmed action with an
   audit trail — never an automatic "helpful" rebuild.** When v11.0 needed a way to restore a
   provably orphaned trade into the paper account, it built a separate preview → explicit
   confirm → apply flow with its own audit trail (`paperReconciliationAudit`), specifically
   instead of having any diagnostic or classification function silently reconstruct
   `paperAccount` from `journalEntries` on its own.
4. **MOGO does not place real trades.** Every account it tracks (`paperAccount`, `alexGAccount`)
   is a simulation. No function anywhere calls an OANDA order-placement endpoint.

## Rationale

- A trading journal that quietly fills in gaps stops being trustworthy the moment a user notices
  one fabricated figure — the entire point of a journal is that its numbers are real.
- Two independent incidents ([INC-001](../INCIDENTS.md)) came directly from ambiguity about
  what a derived/reconciled value actually represented; a strict "never fabricate, always show
  the honest gap" rule removes that ambiguity by construction rather than by convention.
- Keeping analytics read-only means every one of these views can be recomputed, re-verified, or
  rebuilt entirely without any risk of also having to migrate or reconcile persisted "cached"
  output.
- Not executing real trades keeps MOGO's blast radius — even in the presence of a bug — limited
  to incorrect *display* of simulated data, never a real financial consequence. This is a
  deliberate, permanent product boundary, not a missing feature (see
  [KNOWN_ISSUES.md](../KNOWN_ISSUES.md#no-real-order-execution)).

## Consequences

- Any new statistic, chart annotation, or compliance check added in the future must follow the
  same honest-gap pattern rather than interpolating or estimating a missing input.
- Any future "fix up my data" tool (like the v11.0/v11.0.1 reconciliation flow) must be preview
  → explicit confirm → audited apply, matching the existing pattern, never automatic.
- If MOGO were ever to grow real order-execution capability, that would be a fundamental product
  change requiring its own explicit decision and almost certainly a new ADR — it is out of scope
  for this decision and not implied by anything in the current codebase.
