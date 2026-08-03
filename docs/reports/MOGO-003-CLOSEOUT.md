# MOGO-003 — Closeout

**Status:** ✅ **COMPLETE** · **Closed:** 2026-08-03 · **Tag:** `mogo-003-complete`
**Engine at closeout:** `APP_VERSION` 12.18.0 · **Head commit:** `6ea4538`
**Regression at closeout:** 943/943 across 17 suites · **Protected drift:** zero throughout

---

## 1. Final deliverables

Ten commits, `7b5e376` → `6ea4538`, spanning engine versions 12.10.0 → 12.18.0.

| # | Commit | Deliverable |
|---|---|---|
| 1 | `7b5e376` | Unit A + B — evidence capture and rule attribution |
| 2 | `a2d34d4` | Historical ALEX loss-forensics correction |
| 3 | `5c52e55` | Unit C1 — excursion timing |
| 4 | `856be73` | Unit C2-M1 — bounded market context + evidence lineage |
| 5 | `ea39b38` | Unit C2-M2 — higher-timeframe context |
| 6 | `c58a94e` | Trade Integrity & Quarantine |
| 7 | `acf955c` | Immutable Trade Ledger & Derived Account State |
| 8 | `dfa103a` | Ledger Reconciliation Diagnostics |
| 9 | `f7df671` | Final Validation & Transition Plan |
| 10 | `6ea4538` | Reporting Authority Transition |

### By capability

**Evidence capture.** Durable Evidence Packages (`mogo.evidence-package.v1`) with SHA-256 content
hashing, export verified by re-import (EXP-001), and IndexedDB persistence. **RUN-001** — the single
authorized EUR_USD 90-day ALEX replay — produced 24 packages, all hash-verified and export-verified,
recorded in `MOGO-003-VERIFIED-REPLAY-RECORD.md`.

**Attribution and context.** Specification/release version split · `realizedR` from the observed exit
· break and retest candle references · canonical setup naming · rule attribution with `ruleIds` and
`triggeredConditions` · excursion timing (`timeToMFE`/`timeToMAE`) · bounded own-timeframe market
context · higher-timeframe context anchored at entry with a **no-look-ahead guarantee enforced by
validation**.

**Integrity and accounting.** Rule-based trade quarantine (INC-005) · an append-only trade ledger with
deterministic account reconstruction · three-verdict reconciliation diagnostics · a reporting
authority flag, shipped OFF.

### Forensic outputs

INC-005 recorded · the ALEX loss-forensics document corrected and committed · the MOGO-002.8B sample
annotated as unverified Tier 1 · an ALEX rule-to-evidence join built (**paused, uncommitted**).

## 2. Deferred work

| Item | Why deferred |
|---|---|
| **Sizing authority** | requires editing protected trade construction; changes trading behaviour |
| **Enabling derived reporting** | needs parity observed on real accounts first |
| **JVM derived figures** | `paperAccount` declares no `startingBalance` |
| **Browser verification** | needs an authorized replay: IndexedDB persistence, in-browser `crypto.subtle`, a real run producing populated timing/context |
| **Condition-level rule joins** | RUN-001 predates Unit B and carries no `triggeredConditions` |
| **ALEX rule-to-evidence join** | paused mid-milestone by instruction; two untracked files intact |
| **Content-addressed candle store** | duplication accepted; the store is the economy that fixes it |
| **Untraded-candidate context** | not started |
| **Decision chains (CORR-5b)** | faithful capture needs protected-function emission |

## 3. Protected-code boundaries

**Zero drift across all ten commits** — 63 protected functions and 4 protected constants byte-identical
throughout, verified before and after every change.

The boundary held both ways: no protected function references any layer built here, and no layer here
writes state a protected function owns. Where fidelity mattered, mirrors are **pinned by differential
fixtures** rather than trusted — Unit B's evaluator mirror, C1's excursion loop, C2-M2's timeframe
ranking against `RULES_ALEXG.config.htfPriority`.

`alexGConstructLivePosition` reading the stored balance for sizing is what confined the final milestone
to reporting. The constraint set the scope.

## 4. Remaining technical debt

- **Candle duplication** — packages ~47.6 KB, a 24-trade run ~1.14 MB; overlapping trades each store
  their own candles.
- **Two balances coexist** — stored and derived, reconciled rather than merged. Deliberate: it is what
  makes rollback a flag flip.
- **`AGT|MANUAL-B|…` remains in storage** on origin `localhost:8899`, still inflating that stored
  balance to 10,200. Quarantined from every statistic; the stored number is uncorrected.
- **The B1 stale claim** persists in four documents, contradicted by RUN-001's own evidence (8
  validated never-broken resistance zones, 3 `upThroughResistance` breaks).
- **The join generator has no automated test.**
- **`docs/RELEASE_NOTES.md`** was not maintained across this milestone; the changelog in `index.html`
  is authoritative.

## 5. Validation status

| Claim | Status |
|---|---|
| Full regression | ✅ 943/943, 17 suites, 0 execution errors |
| Protected drift | ✅ zero, every commit |
| Evidence packages | ✅ 24/24 hash-verified, schema-valid, re-import verified; byte-identical since export |
| Replay determinism | ✅ `runId` recomputes; no look-ahead in captured context |
| Deterministic reconstruction | ✅ order-independent, repeatable |
| Quarantine correctness | ✅ on fixtures and the recovered INC-005 record; ⚠️ **not yet run against real history** |
| Reporting authority | ✅ off by default, byte-identical when off |
| Browser behaviour | ⚠️ **outstanding** — nothing since 12.9.0 has been exercised in a browser |
| Strategy validation | ❌ **no ALEX setup is validated.** RUN-001: RZR 16 trades −1.00R, B&R 8 trades −5.00R. Neither sample settles anything |

## 6. Future dependencies

1. **One page load** — Diagnostics → Ledger Reconciliation on the real accounts. Unblocks reporting
   enablement and the quarantine false-positive review.
2. **A JVM starting balance** — declared, not inferred.
3. **An authorized replay** — unblocks browser verification and condition-level attribution joins.
4. **Separate authorization** for anything touching protected trade construction.

---

**MOGO-003 delivered the infrastructure to make trade evidence trustworthy. It deliberately produced
no trading conclusions, and none should be drawn from it.** RZR remains suspended from paper and live
execution; no strategy is approved for live trading.
