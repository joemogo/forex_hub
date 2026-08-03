# MOGO-003 — Reporting Authority Transition

**Shipped:** v12.18.0 · **Flag:** `LEDGER_REPORTING_AUTHORITY` · **Default: OFF for every strategy**
**Reporting only. No sizing change. No replay change. No evidence change. Zero protected drift.**

---

## 1. What this switches

When enabled for a strategy, the figures that strategy **displays** come from the immutable ledger
instead of its stored totals. That is the entire scope.

## 2. What it pointedly does not switch

**Position sizing still reads the stored balance.** `alexGConstructLivePosition` is protected and
untouched, and the call site still passes `alexGAccount.balance`, so the next trade risks exactly
what it would have risked before. **This flag cannot alter a trade** — fixture A6 asserts the
protected constructor contains no reference to the reporting layer, and the reporting layer contains
no reference to `riskAmount`, `positionSize` or any open path.

The stored balance also continues to be written by the protected close path. The ledger simply stops
being *read from* it for display.

## 3. Two switches, both off

```
LEDGER_REPORTING_AUTHORITY = {
  enabled: false,                        // master
  byStrategy: { alex_g_sr_v1: false, current_strategy: false },
  blockers:   { current_strategy: 'paperAccount declares no startingBalance; a derived
                                    balance would be a guess' }
}
```

Both the master switch and the per-strategy switch must be true. The master switch alone enables
nothing (fixture A4). JVM records **why** it is not merely un-enabled but not yet *eligible*.

## 4. Off means byte-identical

With the flag off, `ledgerReportingFigures` returns the stored value and performs no derivation at
all. Every surface computes exactly what it computed in v12.17.0 — asserted, not assumed (A2).

## 5. Fails to the stored value

Any doubt resolves to the stored figure: an exception in the enablement check returns `false`, and a
derivation failure returns `source: 'STORED_DERIVATION_FAILED'` with the stored balance. A figure is
always produced; the display is never blanked (A5).

## 6. Disclosure

When a figure is derived, the ALEX panel labels it **"Alex balance (ledger-derived)"**, so the
operator can always tell which authority produced the number on screen.

## 7. Diagnostics remain permanent

The Ledger Reconciliation card is unaffected by the flag and keeps reconciling derived against stored
in both modes — after a switch it becomes the long-term drift detector between the displayed figure
and the legacy stored one. Fixture A9 asserts the flag does not change what reconciliation reports.

## 8. Rollback

Set the flag false. Because this layer never writes, that fully restores prior behaviour with no data
operation of any kind.

## 9. Before enabling on real data

Unchanged from the transition plan: parity observed on the real accounts, JVM starting balance
declared, `pnlUnavailable` zero or explained, and a full-history quarantine review with zero
unexpected exclusions.
