# MOGO-003 — Immutable Trade Ledger & Derived Account State

**Shipped:** v12.16.0 · **Schema:** `mogo.trade-ledger.v1`
**No trading-logic change. No replay change. Zero protected-function drift.**

---

## 1. The problem

Account totals are **stored and independently mutated**. `alexGCloseLivePosition` adds each trade's
P&L to `alexGAccount.balance`, and from that moment the balance is a number nobody can audit: it
cannot be recomputed, explained, or checked against anything.

INC-005 showed the consequence precisely. Once the seeded record was excluded from statistics, the
stored balance still carried its **+$200**. Statistics and balance disagreed — and only the balance
was authoritative.

## 2. The answer

Treat closed-trade records as an **append-only ledger** and **derive** every figure from it: balance,
realized P&L, win rate, expectancy, profit factor, R statistics and drawdown.

> A derived figure can be recomputed, explained and reconciled. A stored total cannot.

## 3. The deliberate boundary

This layer **does not** rewrite the stored balance and **does not** touch the protected close path.
`alexGCloseLivePosition` remains byte-identical and continues maintaining its own total. The ledger
derives truth *alongside* it and **reconciles** the two, so a divergence becomes a visible, explained
number instead of a silent one.

Replacing the stored total is a later, explicit step. This reconciliation is its prerequisite, and
doing it in this order keeps the milestone reversible.

## 4. Components

| Function | Role |
|---|---|
| `ledgerNormalizeEvent` | one closed trade → one canonical immutable event, adapter-mapped, with its integrity verdict attached |
| `ledgerBuildEvents` | deterministic ordering — `closedAt` ascending, tie-broken by `tradeId`, identical to the walk `alexGComputeEquityStats` already uses |
| `ledgerDeriveAccountState` | **the reconstruction**: starting balance + verified ledger + quarantined events (excluded, preserved) → the entire account |
| `ledgerReconcileBalance` | compares a stored total against the derived one and classifies the difference |

## 5. Reconciliation verdicts

| Status | Meaning |
|---|---|
| `MATCHES` | the stored total agrees with the ledger |
| `EXPLAINED_BY_EXCLUSIONS` | the difference is exactly the P&L of records excluded from the ledger (the INC-005 case) |
| `UNEXPLAINED_DELTA` | **the stored total moved for a reason the ledger cannot account for** |

The third verdict is the one worth acting on. It is reported, never absorbed.

## 6. One architecture for every strategy

Normalisation is adapter-based:

- **ALEX** uses the canonical field names (declared explicitly so the mapping is visible).
- **JVM** maps `id`→`tradeId`, `oPair`→`pair`, `dir`→`direction`, verbatim — nothing inferred.
- **Any strategy without an adapter** falls back to canonical names, so CRT, ICT and TJR work on day
  one without a code change here.

Derivation itself is entirely strategy-agnostic.

## 7. No second equity implementation

R-space reuses the shipped `alexGComputeEquityStats` rather than a second chronological walk. A
duplicate implementation is exactly the drift risk this milestone exists to remove, and fixture L8
asserts the call is real rather than re-derived.

## 8. Forensic history is complete

Quarantined and developer-test events are **never dropped** from the ledger. They are carried with
their exclusion reasons and their P&L — which is what allows the layer to say *"the stored balance is
$200 higher than the ledger, and here is the record that explains it."* Developer trades are excluded
from derived figures by default and can be opted back in for investigation.

## 9. Honest gaps

- **`pnlUnavailable` is counted, never filled in.** A record without a P&L contributes to no money
  figure and the count is reported.
- **Profit factor is `null` when there are no losses**, with `profitFactorBasis` stating why, rather
  than reporting infinity as a number.
- **Stored totals are still authoritative in the UI.** Derived state is not yet wired into any
  display; reconciliation must be observed against real accounts first, or a derivation bug becomes a
  wrong number on screen.

## 10. Guarantees

Read-only over the account: the layer contains no `localStorage`, `commitAlexGLedger`, `saveAlexG`,
`.splice(`, `delete` or `alexGAccount.balance=` path, and fixture L7 asserts source records are
byte-identical after derivation. No protected function references it, and deriving an account does not
alter an Evidence Package (L11).
