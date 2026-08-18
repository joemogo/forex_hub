# MOGO-022 — Operator decision packages: B-21 and B-22

**Status: investigation complete, nothing implemented.** Both items are governance-bound
and await an operator decision. No repository file was edited to produce this, no evidence
record touched, no protected function changed. All out-of-repo work was read-only: browser
storage was copied out and parsed in scratch, with no lock taken and no browser driven.

Independently verified: a second pass reached every count by a different route
(package-side extraction joined on `sourceTradeId`, versus ledger-side extraction) and
agreed exactly.

---

# B-21 — Per-tick exit-monitoring state is never persisted

## 1. What is actually wrong

Every 60 seconds the ALEX exit monitor checks each open trade against new price data, records
how far the trade went against you and in your favour, and remembers how far ahead it has
checked. **None of that is written to disk.** It reaches disk only as a side effect, when some
*other* ALEX trade opens or closes. So the saved data for a healthy open position can look as
though the monitor has never run, and after a page reload the monitor starts its check over
from the moment the trade opened.

## 2. Why

A v12.3.2 split: the account and journal moved into a guarded atomic unit
(`commitAlexGLedger`), and `saveAlexG` was narrowed to the non-ledger remainder. The exit
monitor's `saveAlexG()` call stayed where it was and silently stopped covering the state the
monitor mutates.

| Fact | file:line |
|---|---|
| Exit cursor mutated in memory | `index.html:5470` |
| MAE/MFE mutated in memory | `index.html:5354-5358`, `5389-5393` |
| Loop calls `saveAlexG()` | `index.html:5507` |
| …which writes 3 keys, none of them the account | `index.html:3317-3334` |
| Only account write site | `index.html:3256`, reachable only from `commitAlexGLedger()` |
| Its call sites | open, close, reset, TEST trade, migration — **nothing on a monitoring tick** |

The account is serialised whole (`index.html:3234`), so cursor and extremes *are* persisted
atomically whenever any position opens or closes. They can never disagree on disk. The gap is
that no commit happens on a tick, so between commits the disk copy is arbitrarily stale.

## 3. Evidence (OBSERVED 2026-08-18, read-only)

The single open position, from the live `fxhub_alexg_account` blob written ≈15:06Z:

```
GBP_JPY  openedAt 2026-08-18T01:00:29.165Z
         lastExitCheckTimestamp = 1787014829165
         maePips = 0   mfePips = 0
```

`Date.parse('2026-08-18T01:00:29.165Z') === 1787014829165` — the persisted cursor is
byte-exactly `openedAt`, extremes exactly the construction defaults. **Frozen for ≈14 hours.**

**The monitor was alive throughout.** The observation ledger runs continuously
2026-08-17T12:56:04.644Z → 2026-08-18T15:01:02.678Z, carries a PIPELINE `OPENED` for this
tradeId, and no `CLOSED`. The frozen cursor is not a dead poll loop.

**A reload cannot MISS an exit.** The cursor advances only to the end of a candle actually
walked (`:5395`); the fetch is fail-closed on `!r.ok`, on a 200 with no candles, and on any
throw (`:5419-5443`), with the caller deliberately doing nothing (`:5464-5467`). So intervals
walked and intervals covered are the same set, and a stale cursor re-walks a **superset**.
Pinned by `ALEXEXEC.2`/`ALEXEXEC.7`.

**It cannot DOUBLE-COUNT** (`:5551-5553`, closed positions are never iterated) and **cannot
produce a wrong booked P&L**: a candle-detected exit closes at `pos.stop`/`pos.target` exactly
(`:5471-5475`), and those are never reassigned anywhere — consistent with frozen rule
`ALEX_X_010` "no break-even / trailing / partials / scaling".

**MAE/MFE gate no decision.** Full consumer list is journal, stats, renders, chart overlay,
evidence package, and two trade-integrity rules. None gate entry, sizing, stop/target or exit.
Nothing reads `lastExitCheckTimestamp` except `:5461`.

**MAE/MFE on closed trades are correct today *because* the cursor reverts** — a re-walk from
`openedAt` recomputes full-life extremes before reaching the exit candle.

## 4-7. Choices, consequences, reversibility, effects

| | A — do nothing | **B — observability mirror** | C — durable ledger row | D — persist account per tick |
|---|---|---|---|---|
| What | accept staleness | new write-only `localStorage` key, never read back | new `PIPELINE` stage per tick | call `commitAlexGLedger()` from the monitor |
| Frozen semantics | none | none (function not among the 63 protected) | none | none in code, but changes engine input |
| Self-heal on reload | preserved | **preserved** | preserved | **lost** |
| PAPER cost | none | 1 bounded write/tick | ~1,440 IDB rows/day/position | cross-tab `STALE_VERSION` storms |
| Reversibility | n/a | **full** — delete writer and key | code only; rows persist | **not reversible in data** |
| Residual hole | a silently non-advancing monitor leaves no trace | closed | closed | closed, at high cost |

D also lets a read-only monitoring loop raise operator-visible ledger-failure banners, and
permanently persists an over-advanced cursor — meaning a skipped minute becomes missed across
sessions rather than until reload.

## 8. Recommendation — **B**

The backlog frames "persist the cursor" as the remaining item, and **that framing is wrong.**
The cursor's value to the engine is fine where it is: it self-heals, cannot miss an exit, and
cannot change a booked number. What is missing is a **report**, not a **record**. B supplies
the report and leaves the record alone. If a queryable version is ever wanted, B-then-C is
strictly safer than C alone, because B establishes the field set against real forward
operation before it is committed to an evidence schema.

> **What you are approving:** a new write-only `localStorage` key mirroring each open
> position's exit cursor and MAE/MFE, on the explicit condition that the engine never reads it
> back — and **not** approving any change to what a reload re-walks.

## 9. Required before implementing

One addition inside `alexGCheckLivePositions` (unprotected), via `persistStorageKey`.
`saveAlexGRest` must **not** be extended — that preserves its never-throw contract.

Seven fixtures, each mutation-verified. The load-bearing one: **engine-input isolation** — with
a mirror on disk holding a cursor *ahead* of the account's, a reload must re-walk from the
**account's** cursor; mutating `sinceMs` to read the mirror must fail. Without it, B silently
becomes D. Explicitly **must not** be added: any fixture asserting the account's cursor
survives a reload advanced — that is D, and would ratify it by the back door.

---

# B-22 — Oldest closed ALEX trades have no evidence package

## 1. What is actually wrong

The browser database holding MOGO's evidence packages was wiped and rebuilt on the morning of
2026-08-17. Everything in it was lost, and the automatic repair only reaches the **25 most
recent** closed trades — so the **nine oldest real ALEX trades**, an unbroken block from 13 to
17 July, have no evidence package and no research record. Everything after that block is
captured, so nothing is being missed as trades close now. The nine trades are still fully
intact in the account's own saved records, so they remain recoverable — but the account has now
outgrown what an automatic repair can restore.

## 2. Why — the backlog names only half of it

**Trigger:** the evidence IndexedDB logged `Creating DB … since it was missing` at 12:56:04Z on
2026-08-17. Every prior package was destroyed.

**Shape:** `evidenceCaptureClosedTrades()` reads `alexGAccount.closedPositions.slice(0,25)`
(`index.html:15951`), and the array is newest-first. At that pass the account held 38 closes;
the newest 25 are exactly the 25 re-minted. Rows 25–37 were never *eligible* for capture, at
that pass or any other.

**The wipe explains why re-minting was needed; the 25-record window explains which trades were
lost and why the loss is a clean contiguous block.** That window is backlog **B-17**'s unpinned
N-1 boundary. **B-17, B-22 and B-25 are one defect seen from three angles.**

The packages were unrecoverable because `evidence/` is gitignored by design (MOGO-005 B-3) and
the capture-and-preserve pipeline was built *after* the loss. The trades survived because
`alexGCloseLivePosition` commits closed records to `localStorage` independently of the
evidence store.

## 3. Evidence

| set | n | closedAt range |
|---|---|---|
| Real closed, package **and** FORWARD observation | **26** | 2026-07-17T11:28:00.220Z → 2026-08-17T17:39:10.849Z |
| Real closed, **neither** | **9** | 2026-07-13T16:38:32.475Z → 2026-07-17T09:00:28.782Z |
| Developer TEST closed, neither | 4 | 2026-07-12 → 2026-07-13 |

Boundary is strictly contiguous, and falls *within* 07-17: last missing close 09:00:28.782Z
(NZD_USD), first preserved 11:28:00.220Z (EUR_JPY). Package-set and observation-set are
identical — no trade has one without the other.

**Backlog numbers corrected:** "9 of 34" → **9 of 35**; 25 packages → **26**.

**No forward capture gap — CONFIRMED twice, independently.** Every close from 11:28Z onward has
both a package and an observation, including the three after the recreation. The last was
captured 274 ms after exit.

**Standing exposure (this is the part with forward consequences).** 35 real closed trades
against a 25-record automatic re-mint window. Packages are never evicted
(`evidenceEnforceBufferLimits`, `:16327-16340`, evicts setups and zones only), so store
destruction is the sole loss vector — **but if the store is lost again today, the automatic
seam recovers only the newest 25 of 35; a further 10 would be silently absent, widening by one
per close.** The JVM twin carries the identical window (`:16293`). The only remedy is the
operator clicking "Backfill history (read-only)" (`:16908`), which nothing surfaces and nothing
prompts. **Recorded separately as B-25.**

**Are the 9 still recoverable today? YES, completely.** Field-by-field against the preserved 26:
no field is non-null in the 26 and absent from the 9 (other than `strategyProvenance`, present
on 1 of 26 anyway). They carry entry/stop/target, plannedRR, riskAmount, positionSize,
balanceAtEntry, pnl, resultR, MAE/MFE, full zone/session context and complete
`configurationSnapshot`. Engine versions 4.3–12.1.1 wrote the same schema as 11.4.0–12.39.1.

**What ends that recoverability:** the 9 exist in exactly one place — `fxhub_alexg_account` in
one Chrome profile's `localStorage`, with no tracked backup. Same artifact class the wipe
already destroyed once. Ended by: an account reset (`:5817`), a profile wipe or storage clear,
an INC-001-class load failure followed by overwrite, or any future bound on `closedPositions`.
None carries a warning today.

**The provenance argument is weaker than it looks — and this matters.** 25 of the 26 existing
packages were themselves **bulk-minted a month late**, at 2026-08-17T12:56:09.9xx. Only the
GBP/USD close has true capture-at-close fidelity (+274 ms). There is no separate `capturedAt`;
`createdAt` is mint time. So capture latency does **not** distinguish a backfill from almost
every existing package. The honest differentiators are `captureBasis` and
`completenessReport.level` — both machine-set and already fail-closed:

| | LIVE_CLOSE (26) | HISTORICAL_BACKFILL (9) |
|---|---|---|
| `completenessReport.level` | `PARTIAL` | `MINIMAL` |
| `completenessReport.missing` | no `*` entry | `{field:'*', reason:'UNSAFE_TO_RECONSTRUCT'}` |
| corpus importer | → `paper_trade` | **refused**, `UNKNOWN_CAPTURE_BASIS` |

**A backfill path already exists in production.** `evidenceBackfillFromLocalStorage()`
(`:16704-16736`) is read-only over every store, idempotent per tradeId, mints as
`HISTORICAL_BACKFILL`, and is wired to a button. **No code change is required to mint the 9.**

## 4-7. Choices

**A** do nothing · **B** decide the window only · **C** mint only · **D** sequenced: window →
mint → import under a distinct `sourceType` · **E** import the 9 as `paper_trade`.

**E is rejected outright.** It destroys the one distinction the corpus exists to keep. Filing a
`MINIMAL`/`UNSAFE_TO_RECONSTRUCT` record alongside a live-captured one under a single type makes
them indistinguishable forever and retroactively weakens all 26 genuine forward records.

**A's cost is not "slightly less data".** The truncation is **not random** — it is the oldest
contiguous block, spanning engine versions 4.3–12.1.1. Any early-vs-late comparison,
engine-version effect, or account equity curve is structurally censored. Three preserved
records already fail balance reconciliation solely because their lifetimes reach before the
preserved window, and stay unexplainable from the corpus.

**Doing C without B is the trap:** 35 packages restored behind a repair that still caps at 25
means the next store loss reproduces a worse version of the same hole.

Reversibility: B fully (no data written); C fully (packages deletable, re-mintable, invisible to
the corpus); **D one-way in data** — corpus records are immutable under P11, so removal is a
supersede, not a delete.

## 8. Recommendation — **D, and the sequencing is the recommendation, not a detail**

1. **Decide the 25-record window first.** This is the only step with forward consequences.
2. **Then mint**, via the existing button. Expected `created: 13` (9 real + 4 TEST),
   `skipped: 26`, `failed: 0`. Any deviation is a stop condition.
3. **Then import under an explicitly non-`paper_trade` `sourceType`**, so the 9 form a third,
   separately-named population.

This gives the corpus a complete 35-trade view of the account while the forward-capture-fidelity
population stays exactly the 26 captured live.

> **What you are approving, in order:** (1) a decision on the capture window at
> `index.html:15951` — raise, remove, or keep plus a shortfall detector; (2) one click of the
> existing "Backfill history (read-only)" button; (3) a new non-`paper_trade` corpus
> `sourceType` for the reconstructed records. **Approving (2) without (1) is the one combination
> not recommended.**

## 9. Required before implementing

Ten fixtures, each mutation-verified. Three are load-bearing:

- **N-1 boundary control on the capture window** — closes B-17, and is the reason the 13 were
  lost. Mutating the slice bound in either direction must fail.
- **Positive control on the basis mapping** — a `HISTORICAL_BACKFILL` package imports to the new
  `sourceType`; mapping it to `paper_trade` must make a fixture asserting FORWARD's size fail.
  **Without this, D degrades into E by a one-character edit.**
- **Analysis-tool guard** — `population_fidelity.py` must refuse to fold the reconstructed
  population into HISTORICAL or FORWARD.

Plus: dedup keyed on `sourceContentHash` not `packageId` (the bug already fixed once in
`0ac22e0` would otherwise recur); additivity proven by diff, not asserted; and the boundary
pinned **as a relation** — reconstructed max `closedAt` strictly less than forward min
`closedAt`, disjoint and jointly covering all 35 — not as a count. That last point is B-23's
lesson applied.

`MOGO_022_REPLAY_VS_FORWARD_FIDELITY.md` §2 and §4 must change in the same commit: the caveat
does not disappear, it changes shape.

---

## Addendum — the corpus already outlives the store, demonstrably

Measured 2026-08-18T16:0xZ, after the decision packages above were written. Every FORWARD
observation was joined against the packages currently recoverable from the live store:

```
FORWARD observations                                          28
  package still present and hash-verifying in the live store  27
  package NO LONGER in the live store                          1
    TOBS|MOGO|20260806|025  current_strategy  closed 2026-08-06T13:11:15.575Z
store packages with no corresponding observation               0
```

Two things follow, both bearing directly on the B-22 recommendation.

**The preservation mechanism is already the sole record for a real trade.** The package behind
`TOBS|MOGO|20260806|025` no longer exists in the browser — it predates the 2026-08-17 store
recreation. The observation survives only because it had been imported into the tracked corpus
first. This is not a hypothetical about what a future wipe would cost; it is the same loss,
already suffered, and survived only where preservation had happened in time.

**Nothing currently in the store is unpreserved.** Zero store packages lack an observation, so
the corpus is fully caught up with what the browser holds today. The 9 missing trades of B-22
are therefore not a backlog of un-imported evidence — they are trades whose packages never
existed to import, which is exactly why minting them requires the operator decision above
rather than another capture run.

## Open UNKNOWNs, stated rather than filled in

- Whether OANDA can return a short forward page for a reason other than "caught up to now".
  If it can, the cursor still advances only over walked bars, so the safety invariant holds —
  but the gap would be retried each tick rather than closed.
- Whether `closedPositions` will ever be bounded. No cap exists in current code.
