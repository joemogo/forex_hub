# MOGO-003 — Final Validation & Transition Plan

**Date:** 2026-08-03 · **Status:** APPROVED — scope reduced to the Reporting Authority Transition
**Analysis only. No code changed by this document.**

---

## 0. The finding that shapes everything

**The stored balance is not only displayed — it is an input to position sizing.**

| Site | Use |
|---|---|
| `index.html:4390` | `alexGConstructLivePosition(setup, datasets, ba, cfg, alexGAccount.balance, evalMeta)` — risk amount = balance × riskPercent |
| `:8800` | JVM: `riskAmount = paperAccount.balance * 0.01` |
| `:5020` | developer-test sizing |

`alexGConstructLivePosition` is **protected**. So "make derived values authoritative" is two
separable changes:

- **Reporting authority** — what every surface *displays*. Achievable with **zero protected changes**.
- **Sizing authority** — what the next trade risks. Touches protected trade construction and
  **changes trading behaviour**.

MOGO-003 completes the first and deliberately defers the second.

## 1. What remains before derived values become authoritative (reporting)

1. **Parity evidence on real accounts** — reconciliation must report `MATCHES` (or an explained
   delta) against the real ALEX and JVM accounts. To date it has run only on fixtures and the
   reconstructed INC-005 account.
2. **A declared starting balance for JVM.** ALEX stores `startingBalance: 10000`; `paperAccount` is
   `{balance, openPositions, closedPositions}` with no starting balance, and a manual override at
   `:15189` can overwrite the balance. Without a declared start, a JVM derived balance is a guess.
   **This is the one genuine data gap.**
3. **`pnlUnavailable` must be zero or explained** — a closed record without `pnl` contributes to no
   derived money figure.
4. **A quarantine false-positive review** over full real history. Excluding a *genuine* trade is now
   the highest-consequence failure mode.
5. **The display switch itself**, behind a flag.

## 2. Technical dependencies

`ledgerDeriveAccountState` / `ledgerBuildEvents` / adapters (shipped) · `evaluateTradeIntegrity`
(shipped; quarantine correctness is load-bearing for money figures) · `alexGComputeEquityStats`,
`alexGRealizedR`, `alexGStartingBalance`, `computeCanonicalPerformance` (**none protected**) ·
display seams in the ALEX live panel, dashboard tiles, journal summary and strategy analytics (**none
protected**).

**INC-001 interaction:** journal-only records with no account position are invisible to a ledger built
from `closedPositions`. The Paper Ledger Integrity card detects them; the two views must agree.

## 3. Replay dependencies

**None block the reporting switch.** Replay statistics come from `alexGComputeReplayStats`
(protected, untouched) over replay trades, which never enter a live account ledger. RUN-001 and the
24 packages are unaffected.

Independent of this transition, two replay items remain outstanding: **browser verification** of
timing- and context-bearing packages, and the fact that **RUN-001 predates Unit B**, so condition-level
rule attribution can only be joined against a future run.

## 4. Protected-function dependencies

| Function | Relationship | Needed for the reporting switch? |
|---|---|---|
| `alexGCloseLivePosition` | writes `alexGAccount.balance` | **No** — it may keep writing; the ledger stops being read from it |
| `alexGConstructLivePosition` | reads balance for sizing | **No** for reporting; yes for sizing authority |
| `alexGUpdatePositionExcursionAndCheckExit` | produces the excursions the integrity rules test | correctness dependency only |
| `alexGComputeReplayStats` | replay only | No |

**The reporting transition requires no protected-function change at all.**

## 5. Reversible migration strategy

One flag, no data migration.

1. `LEDGER_REPORTING_AUTHORITY`, default **OFF**. Display seams read derived when enabled, stored
   otherwise.
2. **Nothing is written, ever.** Stored balances continue to exist and continue to be maintained by
   the protected close path. **Sizing continues to read the stored balance regardless of the flag.**
3. **Rollback = flip the flag back.** No data restoration, no migration reversal — because no stored
   value was ever altered.
4. Ship off, verify on real accounts, enable per strategy (ALEX first; JVM after its starting balance
   is declared).
5. The Diagnostics card stays permanently: after the switch it reconciles derived-displayed against
   stored-legacy, which is the long-term drift detector.

## 6. Risks, rollback, regression requirements

| Risk | Severity | Mitigation |
|---|---|---|
| Quarantine false positive removes a genuine trade from all figures | **High** | full-history review before enabling; the record is preserved and named in Diagnostics |
| Derivation bug displays a wrong balance | High | flag defaults off; parity observed on real accounts first |
| JVM starting balance unknown | **High (JVM only)** | do not enable for JVM until declared |
| `pnlUnavailable` understates derived balance | Medium | counted and surfaced; must be zero or explained |
| INC-001 orphans absent from the ledger | Medium | cross-check against Paper Ledger Integrity |
| Displayed balance diverges from sizing balance | Medium | label the figure as ledger-derived; keep reconciliation visible |

**Rollback:** set the flag false. Because the layer never writes, that fully restores prior behaviour
with no data operation.

**Regression requirements before enabling:** parity fixtures (derived equals current displayed values
for a clean account) · real-history quarantine review with zero unexpected exclusions · JVM starting
balance including the manual-override path · `pnlUnavailable` behaviour · **flag-off output
byte-identical to today** · zero protected drift · browser verification of the Diagnostics card.

## 7. Recommendation

**MOGO-003 is not complete; one final milestone is required — the Reporting Authority Transition.**

Done: durable evidence capture, export verification, rule attribution, excursion timing, market and
higher-timeframe context, integrity quarantine, the immutable ledger, reconciliation diagnostics.
Missing: the switch, and the evidence to justify flipping it.

**Explicitly deferred beyond MOGO-003: sizing authority.** Making the next trade's risk derive from
the ledger changes trading behaviour and requires editing protected trade construction — a separate
authorization and a separate milestone.
