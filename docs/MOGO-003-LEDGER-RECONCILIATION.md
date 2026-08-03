# MOGO-003 — Ledger Reconciliation Diagnostics

**Shipped:** v12.17.0 · **Schema:** `mogo.ledger-reconciliation.v1`
**Diagnostics only. Replaces no stored total. Writes nothing.**

---

## 1. Purpose

The immutable ledger (v12.16.0) derives account state; the stored totals still exist and are still
authoritative. This view puts the two side by side, field by field, and classifies every difference —
so a divergence becomes a visible, attributable number instead of a silent one.

## 2. Where it lives

Diagnostics → **Ledger Reconciliation**, refreshed when the panel opens and by its own Refresh
button. One table per strategy: ALEX and JVM today, and any strategy added later through
`ledgerReconciliationSources()`.

| Column | Meaning |
|---|---|
| Field | the account figure being reconciled |
| Stored | what the account says today |
| Derived | what the ledger derives |
| Difference | stored − derived |
| Verdict | `MATCHES` · `EXPLAINED_BY_EXCLUSIONS` · `UNEXPLAINED_DELTA` |
| Explanation | why, in words, plus the responsible trade IDs |

Eight fields are reconciled: `balance`, `realizedPnl`, `wins`, `losses`, `decided`, `winRate`,
`netR`, `maxDrawdownR`.

## 3. How a difference is classified

The ledger is derived **twice**:

1. **excluding** quarantined events — the authoritative view;
2. **including** them — the view the stored totals actually reflect.

If a field's stored value matches the all-inclusive derivation, the difference is *exactly* the
excluded records: `EXPLAINED_BY_EXCLUSIONS`, with those records named. If it matches neither, it is
`UNEXPLAINED_DELTA` — the stored value moved for a reason the ledger cannot account for. Otherwise
`MATCHES`. The vocabulary is a frozen three-value constant.

## 4. Worked example — INC-005

Against the account recovered from storage (stored balance 10,200; ledger 10,000):

| Field | Stored | Derived | Diff | Verdict |
|---|---|---|---|---|
| balance | 10200 | 10000 | 200 | EXPLAINED_BY_EXCLUSIONS |
| realizedPnl | 200 | 0 | 200 | EXPLAINED_BY_EXCLUSIONS |
| wins | 1 | 0 | 1 | EXPLAINED_BY_EXCLUSIONS |
| losses | 0 | 0 | 0 | MATCHES |
| decided | 1 | 0 | 1 | EXPLAINED_BY_EXCLUSIONS |
| winRate | 100 | null | — | EXPLAINED_BY_EXCLUSIONS |
| netR | 2 | 0 | 2 | EXPLAINED_BY_EXCLUSIONS |
| maxDrawdownR | 0 | 0 | 0 | MATCHES |

Drill-down on `balance` returns the single responsible event:
`AGT|MANUAL-B|1785634676564 · pnl 200 · TI_WIN_REQUIRES_FAVOURABLE_EXCURSION,
TI_NONZERO_LIFETIME, TI_TRADE_ID_ENGINE_MINTED`.

`winRate` derives as `null` rather than `0%` — zero decided trades has no win rate, and inventing one
would be a fabricated figure.

## 5. Drill-down

`ledgerReconciliationDrillDown(report, field)` returns the field's verdict, its explanation and the
full ledger events behind it — each with its result, P&L and the integrity rules it violated. The
card also lists every excluded event beneath each table, stating plainly that they are preserved and
never deleted.

## 6. Read-only guarantees

The layer contains no `localStorage`, `commitAlexGLedger`, `saveAlexG`, balance-assignment, `splice`
or `delete` path; accounts are byte-identical after reconciliation (fixture R7); the report carries
`readOnly: true`; and the card states on screen that it replaces nothing.

## 7. Deliberate limitation

**Nothing is corrected.** The stored balance still reads what it reads. This milestone makes the
divergence visible and attributable; changing it is a separate explicit act, addressed by the
transition plan.
