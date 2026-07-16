# Incidents

A log of real production defects found in MOGO: what happened, who/what it affected, the actual
root cause, and how it was resolved and verified. This is distinct from
[KNOWN_ISSUES.md](KNOWN_ISSUES.md), which documents intentional, currently-accepted limitations —
everything in this file was a genuine bug that has since been fixed.

**Rule for future releases:** add an entry here for any defect that reached a point where it
could produce incorrect data or behavior for a real user, even if caught before a formal
"release" boundary. Include the actual root cause, not just the symptom and the patch.

---

## INC-001 — Completed paper trades appearing as "JOURNAL ONLY" after a reset

**Status:** Resolved (v11.0 partial fix, v11.0.1 root-cause correction).

### Symptom

Three EUR/USD trades in the unified Journal showed real, complete results (`Win`,
`+2.00R`, valid entry/stop/target, recent timestamps) — but the Paper Trading page showed a
fully-reset account: `$10,000` balance, `$0` total P&L, `0` open positions, `0` closed positions,
and an empty Auto Trade Log. The three trades were classified `JOURNAL_ONLY`: a journal record
with no matching position in the paper account.

### User impact

A user could not trust that the Paper Trading page reflected their actual trading history —
completed trades with real results were invisible in their account balance and closed-position
list, even though the same trades were fully visible and correctly detailed in the Journal.

### Root cause — v11.0 finding

`save()` persisted `paperAccount` to `localStorage` with **no staleness or version check at
all**. Reproduced directly: opening and closing a real trade through the actual engine produced
the correct result, but then reassigning the in-memory `paperAccount` variable to an earlier
snapshot (simulating a stale second tab/session) and calling `save()` again **silently
overwrote** the correct, newer data — while `journalEntries` (a separate, untouched variable)
still held the real trade. This exactly reproduced the reported symptom.

### v11.0 fix (partial)

A monotonic version guard (`fxhub_paper_version` + `savePaperAccountGuarded()`) that refuses to
write `paperAccount` if storage already holds a version newer than what the current session last
knew, recording a visible error instead of overwriting. Also added: an in-flight duplicate-close
guard, developer-mode-gated lifecycle logging, and the Paper Ledger Integrity diagnostic that
first made this class of defect visible in the UI at all.

### v11.0.1 — the more precise root cause an independent review found

The v11.0 fix addressed a real mechanism (a stale, unguarded overwrite) but not the more precise
one that could still occur even with the version guard in place:

1. **Split transaction.** `save()` wrote `fxhub_journal` **unconditionally**, before attempting
   the now-guarded `paperAccount` write — and that guarded write could still be legitimately
   rejected (a genuine two-tab/two-session version conflict). When it was, the journal write had
   already happened: a real `JOURNAL_ONLY` orphan, produced by an incomplete transaction rather
   than a plain stale overwrite.
2. **False staleness from unrelated activity.** `savePaperAccountGuarded()` ran on *every* call
   to general `save()` — and `save()` is called from dozens of unrelated places (scanner
   renders, alert log writes, checklist edits, Academy progress, manual journal edits). Any one
   of those in one tab could silently advance `fxhub_paper_version`, making a different,
   actively-trading tab's next real trade look falsely stale and get rejected with no actual
   conflict.

### v11.0.1 fix

Reframed as a ledger-transaction problem rather than a classification problem:

- General `save()` no longer writes or versions `paperAccount` **at all**.
- A new `commitPaperLedger()` is the only function allowed to persist `paperAccount` — it writes
  the guarded paper-account state first, and only persists everything else the transaction
  touched (the linked journal mutation, `tradedToday`, the auto-trade log) if that succeeds.
- Every paper-ledger mutation call site now snapshots before mutating and rolls both
  `paperAccount` and any linked `journalEntries`/`autoTrading` change back to that snapshot, in
  memory, if the commit is rejected — so a blocked action can never be partially applied.
- A rejected commit now renders a persistent, always-visible red banner on Paper Trading (not
  gated behind Developer Mode) rather than failing silently.

See [ADR-003](adr/ADR-003-paper-ledger-transaction-model.md) for the full design reasoning.

### Verification

- **v11.0**: 17 new fixtures; full pre-existing suite (335) unchanged; live browser reproduction
  of both the original bug and the fix blocking it; live reproduction of a full open→close
  lifecycle, three sequential trades, sequential and concurrent duplicate-close idempotency.
- **v11.0.1**: 15 new fixtures (two pre-existing v11.0 fixtures updated in place to call the new
  `commitPaperLedger()`, since the bare-`save()` path they exercised no longer touches
  `paperAccount` by design); full suite (352) unchanged (367 total). Live browser verification
  of: a blocked `closePaperPosition()` correctly rolling back both `paperAccount` and
  `journalEntries`; a real `checkAutoTrades()` call under a rigged version conflict leaving
  `tradedToday`/the auto-trade log/`paperAccount`/`journalEntries` completely untouched; the
  full 3-trade clean lifecycle still passing; unrelated `save()` calls confirmed not to advance
  `fxhub_paper_version`; a reload correctly retaining all committed trades; and the new blocking
  banner rendering correctly (screenshotted) with the balance left untouched.
- Both releases: `regression-baseline-tools.py` comparison disclosed exactly which protected
  functions changed (`openPaperPosition`/`closePaperPosition`, plus `checkAutoTrades` in v11.0
  only) with the underlying sizing/entry/stop/target/direction/pnl/result math confirmed
  byte-identical in every case.

No trading methodology (JVM or ALEX) was touched by either release.

---

## INC-002 — Chart showing a small cluster of candles with a large blank area

**Status:** Resolved (v11.1.0).

### Symptom

A chart could load showing only a small cluster of real candles crammed against one edge, with a
large blank area across the rest of the panel. Candle data, indicators, and Fit All were all
confirmed working correctly — clicking the existing "Reset Saved View" button immediately fixed
the display.

### User impact

The affected pair/timeframe was effectively unreadable until the user found and clicked Reset
Saved View — a real usability defect, though purely cosmetic/display-layer (no trading data was
ever at risk; the chart-viewport subsystem doesn't read or write `paperAccount`/`journalEntries`).

### Root cause

`saveChartView()` (v6.0) persists a saved viewport's `visibleLogicalRange` as raw positional
indices into whatever candle array was loaded at save time, with no record of how many candles
that array had. `loadChart()` always requests 200 candles from `fetchCandles()`, but the array
actually returned varies (off-hours/weekend gaps, limited available history, pagination). At
restore time, the saved range was applied via `setVisibleLogicalRange()` completely
unconditionally — if the array had since shrunk drastically, the saved range pointed mostly at
indices that no longer existed, so the chart rendered only whatever real candles happened to fall
inside that now-stale request and left the rest blank. `applyFitVisible()` ran immediately after
but only refits the price scale, never the logical (time) range itself, so the broken layout
persisted until something replaced the logical range outright (Reset Saved View → `applyFitAll()`
→ `fitContent()`).

### Fix

A new, pure, read-only `isSavedChartViewValid(savedView, candleCount)` validates a saved view
against the *current* candle count before it is ever applied — checking candle-count drift
(>50% change since the view was saved invalidates it), whether the saved range has any real
overlap with current data at all, and whether too little of the saved window's width actually
corresponds to real candles (a small amount of normal trailing margin is tolerated). An invalid
view is discarded and the chart falls through to the same `fitContent()` path already used when
no saved view exists — no user action required, and the corrected viewport is automatically
persisted afterward via the pre-existing `applyFitVisible()` → `saveChartViewDebounced()` call.
Backward compatible: a saved view from before this fix (no recorded candle count) is still fully
protected by the overlap check alone. No new [ADR](adr/) was needed — this is a bug fix within
the existing v6.0 chart-viewport design, not a new architectural decision.

### Verification

17 new fixtures (core validity checks, the exact reported bug scenario reproduced and correctly
invalidated, backward compatibility with pre-fix saved views, candle-count drift threshold
behavior, edge cases, `saveChartView()` recording candle count, `discardSavedChartView()`/
`resetSavedChartView()` behavior, and a dedicated isolation fixture proving no trading state is
touched), plus the complete pre-existing 367-fixture suite unchanged (384 total). Live browser
verification reproduced the actual bug through the real `loadChart()` restore path — 200 candles
saved with a deep-history view, then reloaded returning only 15 candles (simulating the reported
off-hours collapse) — confirmed the stale view was discarded, the chart auto-fit to show all real
candles cleanly across the full panel width (screenshotted), and the corrected viewport was
persisted. Separately confirmed the valid-view path (unchanged candle count) restores exactly as
before, and the manual Reset Saved View button's behavior is unchanged. `regression-baseline-tools.py`
showed zero drift — no chart-viewport function has ever been on the protected list, and none of
this touched any JVM/ALEX/paper-ledger function or state.

---

## INC-003 — Diagnostics self-test could silently persist a fake trade into the real journal

**Status:** Resolved (v12.1.1).

### Symptom

Running the "Paper trading engine (sizing + auto-close)" Diagnostics self-test could leave a new,
untagged, real-looking journal record (`tradeSource:"MANUAL"`, no developer-trade flag, a genuine
same-day timestamp) in `fxhub_journal` — even though the self-test's own `paperAccount` was
correctly restored afterward (`{balance:10000,openPositions:[],closedPositions:[]}`) and the
self-test itself reported success (green). This is the same class of defect as
[INC-001](#inc-001--completed-paper-trades-appearing-as-journal-only-after-a-reset) (a
`JOURNAL_ONLY` orphan — a journal record with no matching account position) but produced by the
diagnostic tool meant to verify data integrity, not by a real trading action.

### User impact

Discovered during v12.1.0's live verification (disclosed then, not fixed — out of scope for that
release), before it could reach a real user session. Directly contradicted the app's own stated
claim that Diagnostics is "safe to run any time" and "restores your real data afterward."

### Root cause

`runDiagnostics()`'s "Paper trading engine" check snapshotted and restored `pairData`,
`paperAccount`, `activePair`, `fetchBidAsk`, and the R:R Calculator's DOM fields — but never
`journalEntries`. The check's own `openPaperPosition()`/`closePaperPosition()` calls mutate
`journalEntries` directly as a side effect (via `journalNoteOpenJVM`/`journalNoteCloseJVM`), and
the check's restoring `commitPaperLedger()` call internally calls `save()`, which unconditionally
re-writes `fxhub_journal` from whatever `journalEntries` currently holds — so a successful
self-test run persisted the simulation's own leftover journal record as if it were real.

A second, subtler variant of the same root cause was caught only by writing new fixtures for this
fix (not by code review): the check isolates `paperAccount` by reassigning it to a brand-new
synthetic object before the simulation runs, so the real object is never touched at all — but
naively snapshotting/restoring `journalEntries` by *reference* does not give the same protection,
because `openPaperPosition()` mutates that array **in place** (`.unshift()` via
`upsertJournalOpenRecord`) rather than reassigning it. A snapshot taken before the mutation still
points at the same, now-mutated array by the time it's "restored."

### Fix

Added a small, Diagnostics-only, unexported helper pair — `diagSnapshot(getters)` /
`diagRestore(snap, setters)` — generalizing the existing "capture a variable, do work, write it
back" pattern already used by `alexGIsolationCheck()` and `openPaperPosition()`'s own
`paperAccountSnapshot`/`journalEntriesSnapshot` rollback fields (not a new restoration
architecture). Applied it to include `journalEntries` in the Paper trading engine check's
snapshot/restore, and — matching the in-place-mutation finding above — isolated `journalEntries`
the same way `paperAccount` already is, by reassigning it to a fresh empty array immediately
before the simulated trade runs, so the simulated record is written into a throwaway array and the
real `journalEntries` array is never mutated in the first place. Also hardened two other
self-tests (Browser storage, Pip-value/cross-rate math) whose restoration code ran outside a
`try/finally`, so an exception mid-check would have skipped cleanup.

### Verification

13 new fixtures in `tests/v1211_diagnostics_integrity_tests.js` — `diagSnapshot`/`diagRestore`
correctness in isolation; a direct reproduction, using the real, unmodified
`openPaperPosition()`/`placePaperTrade()`/`commitPaperLedger()`, proving `journalEntries` and
`fxhub_journal` are both back to their exact real pre-simulation value after the fixed pattern
runs; an exception-path proof that restoration still happens even when the check throws
mid-simulation; a zero-new-localStorage-key proof; and a full-pass proof that
`journalEntries`/`alexGJournalEntries`/`paperAccount`/`alexGAccount`/`scanData` are all
byte-identical before and after. Plus the complete pre-existing 56-fixture suite unchanged (69
total). `regression-baseline-tools.py` showed zero drift across all 63 protected functions and 4
protected constants. Live verification: seeded realistic synthetic JVM/ALEX journal and account
data (per the Browser Testing Policy — no real trades placed), clicked the real "Run Diagnostics"
button in the actual UI, and confirmed a byte-for-byte comparison of every `localStorage` key
(with the app's own background scan-polling loop stopped, to isolate Diagnostics' own effect) —
`fxhub_journal`, `fxhub_paper`'s content, `fxhub_alexg_account`, and `fxhub_alexg_journal` were all
exactly byte-identical before and after; the one key that did change, `fxhub_paper_version`, is the
pre-existing, correct-by-design v11.0.1 monotonic version counter (see
[INC-001](#inc-001--completed-paper-trades-appearing-as-journal-only-after-a-reset)), which
legitimately advances by exactly 3 on every real `commitPaperLedger()` call sequence regardless of
whether the account's content changed — not a regression introduced by this fix.

No JVM/ALEX trading methodology was touched by this release.
