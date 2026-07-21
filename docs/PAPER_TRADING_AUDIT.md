# Paper Trading Operational Audit

Completed as a pre-TJR-Phase-2 milestone (v12.3.2). Scope: verify whether MOGO's existing ALEX
and JVM paper-trading, journal, and analytics pipeline actually behaves the way it's assumed to —
before adding any new strategy intelligence on top of it. This is primarily a verification
document, not a design document; see [ARCHITECTURE.md](ARCHITECTURE.md) for how the pieces fit
together and [STORAGE_KEYS.md](STORAGE_KEYS.md) for the full key inventory.

This was a multi-phase corrective milestone. **Phase 1** (investigation) found and corrected two
narrow defects, and surfaced three further findings that required a product/architecture
decision rather than a silent fix. **Phase 2**, reviewed and approved separately, implemented all
three of those decisions plus four further requested improvements (§6). A **Final Ledger
Atomicity Review** then found and corrected a real defect in Phase 2's own ALEX version-guard
design — see §0. Everything described below reflects the state after all phases.

## 0. The real persistence contract (account, journal, and version)

This section is the single source of truth for how MOGO actually guarantees paper-ledger
consistency. An earlier draft of this document (and of the Phase 2 implementation report)
described a thrown journal-write failure as "correctly non-gating" — treating the account write
as the only one that mattered, with the journal write allowed to fail silently after the account
had already been persisted. **That was wrong and has been corrected.** A successful account
write followed by a failed journal write is exactly the kind of divergence
([INC-001](INCIDENTS.md#inc-001), the historical JOURNAL_ONLY-orphan incident this project has
already been burned by once) this whole audit exists to prevent — it is never acceptable to
describe it as safe merely because it doesn't throw an uncaught exception.

**Ownership.** For both JVM and ALEX, the account, its version counter, and its journal are one
logical unit, owned and written by exactly one function each:
- JVM: `paperAccount` + `fxhub_paper_version` + `journalEntries`, owned by
  `savePaperAccountGuarded()`, called only from `commitPaperLedger()`.
- ALEX: `alexGAccount` + `fxhub_alexg_account_version` + `alexGJournalEntries`, owned by
  `saveAlexGAccountGuarded()`, called only from `commitAlexGLedger()`.

Non-ledger state (JVM: `scanData`/`checklistState`/`alertLog`/`autoTrading`/etc., persisted by the
general `save()`; ALEX: `alexGAutoTrading`/`alexGZoneState`/`alexGSetupState`, persisted by
`saveAlexGRest()`) is deliberately **outside** this unit and keeps its pre-existing best-effort
semantics — bundling it in would reproduce the false-stale-rejection bug (an unrelated tab action
silently advancing the version and making a different tab's real trade look stale) that JVM's own
v11.0.1 fix, and this project's whole version-guard design, exists to prevent.

**JavaScript's `localStorage` has no native transactions.** There is no way to write three keys
"at once" and have the browser guarantee all-or-nothing. MOGO instead implements logical
atomicity itself, entirely inside `savePaperAccountGuarded()`/`saveAlexGAccountGuarded()`:

1. Read the exact current serialized value of every key in the unit (account, version, journal)
   — even if a key doesn't exist yet (`null`).
2. Verify the version guard (reject a stale write before touching storage at all).
3. Serialize the new account and journal values **before writing anything** — a serialization
   exception here means literally nothing has been written yet, so there is nothing to roll back.
4. Write account, then version, then journal, in that order, tracking exactly which of the three
   keys this specific attempt has actually written.
5. If any of the three writes throws, restore every already-written key to its exact pre-op
   value — or, if a key didn't exist before the operation, remove it (never leave it as a
   stray `"null"` string or an empty placeholder) — and report failure.
6. Only if all three writes succeed does the session's known version counter advance, and only
   then does the function return success.

**Stale-write behavior** is unchanged from Phase 2: a version already ahead of what this session
last knew is rejected before any write is attempted, with the exact reason recorded via
`recordPaperEngineError()`/`recordAlexGEngineError()`.

**Failure behavior**, corrected here: *any* write failure in the unit — account, version, or
journal — is now treated identically. All three are rolled back together, the function returns
`false`/`{ok:false}`, and the caller's own snapshot/rollback (see below) restores in-memory state
to match. There is no longer a distinction where the account write's success alone determines the
outcome.

**Reload behavior**: `loadSaved()`/`loadAlexGSaved()` read whatever is actually in storage. Because
the unit above is genuinely all-or-nothing, a reload after a successful commit always shows the
complete new state, and a reload after a failed commit always shows the complete pre-op state —
proven directly, including simulated reloads inside the fixture suite itself, not just checks of
in-memory variables immediately after the call (AlexAtomic.3b/4b/7, JvmAtomic.3).

**Rollback behavior, and the caller's own responsibility.** `savePaperAccountGuarded()`/
`saveAlexGAccountGuarded()` guarantee that **storage** ends up either fully updated or fully
unchanged. They cannot, by themselves, undo an in-memory mutation the *caller* made before
calling them — that snapshot/restore is each mutation call site's own job (`openPaperPosition`,
`closePaperPosition`, `alexGAttemptOpenLivePosition`, `alexGCloseLivePosition`,
`resetAlexGLiveAccount`, `clearTestTradesAlex`, and the manual `logTrade()`/`deleteEntry()` paths
all snapshot before mutating and restore on `{ok:false}`). A caller that skips this step and
calls the guarded function directly will see storage correctly protected, but must still restore
its own in-memory state itself — exactly the pattern the fixture suite uses when it exercises
`commitPaperLedger()`/`commitAlexGLedger()` directly rather than through a real caller.

**Retry safety.** Because a failed commit leaves storage and (once the caller restores its own
in-memory state) memory in the exact pre-op condition, the same logical operation can always be
retried once the underlying failure is gone, with no duplicate journal record and no double
balance change — proven directly (AlexAtomic.8–13).

**JVM and ALEX differences, unchanged by this correction:** ALEX's live-open mutation site is the
async `alexGAttemptOpenLivePosition()` (not the pure, unmodified `alexGConstructLivePosition()`);
`alexGCloseLivePosition()` has no internal `await` and needs no `paperPositionsClosing`-style
guard, unlike JVM's `closePaperPosition()`; ALEX's R-multiple is fixed at the planned R:R, never
recomputed. None of that changed — only how the account+journal+version unit is persisted did.

### 0.1 When the compensating rollback write itself fails (Final Pre-Commit Integrity Gate)

Everything above describes what happens when step 5's rollback (re-writing or removing whatever
this attempt had already written) *succeeds*. But `rollbackWritten()`'s own `setItem`/`removeItem`
calls are themselves ordinary `localStorage` calls, and `localStorage` can throw on any call, for
the same underlying reasons (quota, private-browsing restrictions, a browser/extension
intercepting storage access) the original write could throw. **There are therefore three distinct
outcomes for a commit attempt, not two:**

1. **Successful logical transaction.** All three writes (account, version, journal) succeed. This
   is the normal case and is what §0 above describes in full.
2. **Failed commit with successful compensating rollback.** One of the three writes throws, but
   every key that had already been written this attempt is successfully restored (or removed, if
   it didn't exist before) by `rollbackWritten()`. Storage ends up exactly as it was before the
   attempt. This is an *ordinary* rejection: `{ok:false,integrityCompromised:false,reason:'...'}`,
   surfaced via the existing `paperLedgerBlockingError`/`alexGLedgerBlockingError` banner
   ("reload and retry").
3. **Failed commit with failed compensating rollback.** One of the three writes throws, **and**
   at least one of the restoring/removing calls inside `rollbackWritten()` *also* throws. Storage
   is now left in a partial, indeterminate state: some keys reflect the new attempted values, some
   reflect old values, and MOGO has no way to know which without reading storage back and
   comparing it against what it expected — which is exactly what the Health Check does, manually,
   on request (see §10), not automatically.

**`localStorage` has no true transaction support, and this is the concrete, load-bearing
consequence of that fact.** Ordinary partial writes (outcome 2) are compensated through rollback
and are fully recoverable. A rollback-write failure (outcome 3) cannot be guaranteed recoverable
automatically — there is no fourth write MOGO could attempt that wouldn't have the exact same
failure mode. What MOGO guarantees instead is **logical atomicity under normal localStorage
operation, with explicit detection of unrecoverable compensating-write failure.** It detects the
condition, reports it distinctly from an ordinary rejection, and stops — it does not pretend the
rollback succeeded, and it does not attempt automatic repair.

**The fatal-integrity result.** `savePaperAccountGuarded()`/`saveAlexGAccountGuarded()` return
`{ok:false,integrityCompromised:true,reason:'ROLLBACK_FAILED',failedCommitStep,failedRollbackKeys}`
in outcome 3 — categorically distinct from outcome 2's
`{ok:false,integrityCompromised:false,reason:'...'}`. `commitPaperLedger()`/`commitAlexGLedger()`
propagate this as `{ok:false,integrityCompromised:true,reason:<human-readable text>,
reasonCode:'ROLLBACK_FAILED',failedCommitStep,failedRollbackKeys}` — `reason` is deliberately
human-readable (matching the runtime warning text below) rather than the terse code, since every
existing caller displays `reason` directly (via `alert()` or as inline text); the terse code is
still available under `reasonCode` for anything that needs to branch on it programmatically.

**What happens on detection, per the safety contract this correction implements:**
1. The commit never claims the rollback restored state it did not actually restore.
2. The caller never reports trade success (every `commitPaperLedger()`/`commitAlexGLedger()`
   caller checks `.ok` before doing anything success-shaped; none of them special-case
   `integrityCompromised` into a success path).
3. The caller does not continue normal downstream behavior (no auto-trading bookkeeping, no
   toast/alert notification, no journal-linked side effect fires after a fatal result).
4. In-memory account/journal state is restored to its pre-operation snapshot where the caller
   took one (every real mutation call site does); no code path re-attempts a persisted write
   against a possibly-corrupted store after a fatal result is returned. In particular,
   `approveManualReviewTrade()`'s own reconciling second commit — which exists to persist an
   in-memory undo after an *ordinary* rejection — is explicitly skipped when the first commit
   came back `integrityCompromised:true`, so a fatal result is never followed by an automatic
   second write attempt.
5. In-memory state is never silently synchronized to the partially-written persisted state — the
   caller's own snapshot/rollback continues to run exactly as it does for an ordinary rejection.
6. A new, categorically separate runtime warning — `paperLedgerIntegrityWarning` (JVM) /
   `alexGLedgerIntegrityWarning` (ALEX), rendered by dedicated banners on the Paper Trading and
   Alex G Live panels — tells the user persisted state may be inconsistent and directs them to
   Diagnostics > Developer Mode > Paper Trading Health Check. This is deliberately a *different*
   variable from `paperLedgerBlockingError`/`alexGLedgerBlockingError` (the ordinary-rejection
   banner), never conflated with it, and never with a normal "trade opened"/"trade closed"/
   "journal saved"/"account updated" state. Setting this warning is a plain in-memory assignment
   inside `commitPaperLedger()`/`commitAlexGLedger()` — it never itself creates or modifies any
   `localStorage` key (verified directly: `RollbackFailure.14`).
7. No automatic reset, delete, migration, or repair of the ledger is attempted.
8. No automatic retry loop: a single failed attempt results in exactly one recorded outcome, not
   a retry (verified directly: `RollbackFailure.13`).
9. `recordPaperEngineError()`/`recordAlexGEngineError()` log `strategy`, `operation`,
   `failedCommitStep`, `failedRollbackKeys`, `expectedVersion`, and `persistedVersionAtStart` —
   never credentials, tokens, account IDs, or unrelated storage values (these functions never had
   access to `cfg.key`/`cfg.accountId` in the first place; verified directly against the live
   error log, not just by construction: `RollbackFailure.15`).

**Health Check remains strictly read-only** when analyzing a rollback-failure-shaped
inconsistency — it detects the likely shape where possible (an account/version mismatch, a closed
trade with no matching journal record, a journal record with no matching account trade, a P&L
mismatch, a duplicate/orphaned record) but never repairs, deletes, or migrates anything on its own
(verified directly: `RollbackFailure.11`/`12`). Manual engineering review may be required to
actually reconcile a genuine partial-write inconsistency; MOGO does not claim to resolve one for
the user automatically.

**On Sequence C.** The four required failure sequences for this gate include one — "the journal
write fails, and the journal's own restoration fails where a prior journal value existed" — that
is structurally impossible to construct honestly under this design, disclosed here rather than
faked with an artificial test. The write order is always account → version → journal (journal
last), and `rollbackWritten()` only ever restores keys that this attempt's `written` array already
contains — i.e., keys that were *successfully* written before the one that threw. Journal, being
written last, can only be the key that throws, never a key that was successfully written earlier
in the same attempt; it can therefore never itself appear in `written` and never itself be a
rollback target when it is also the one that failed. Sequences A and B (a prior key — version or
account — failing to restore after journal is the one that throws) are the only two ways a
"restoration fails for a key with genuine prior data" scenario can actually occur in this design,
and both are covered directly (`RollbackFailure.ALEX.A*`/`B*`, `RollbackFailure.JVM.A1`/`A2`/`B1`).
Sequence D (a key that never existed before this operation, whose `removeItem()` rollback then
fails) is covered separately and does occur (`RollbackFailure.ALEX.D1`/`D2`).

## 1. Trade lifecycle (JVM)

```
openPaperPosition(oPair,dir,entry,stop,target,source)
  -> reject if pipValuePerLot() has no live conversion rate
  -> reject if riskPips<=0 (stop===entry)                      [added in this audit, §6]
  -> snapshot paperAccount + journalEntries
  -> paperAccount.openPositions.push(pos)
  -> journalNoteOpenJVM(pos)                                    [writes one OPEN journal record]
  -> commitPaperLedger()
       -> savePaperAccountGuarded()  [rejects if localStorage's fxhub_paper_version > this
                                       session's known version -- multi-tab protection.
                                       Writes paperAccount+version+journalEntries as ONE
                                       atomic unit -- see §0.]
       -> save()                     [everything else EXCEPT paperAccount/version/journal]
  -> on {ok:false}: roll back to the snapshot, return {error, blocked:true}
  -> on success: return the position, pos.committed=true

closePaperPosition(id,manual,autoResult)     -- async, ONE internal await
  -> if paperPositionsClosing.has(id): return  [duplicate-close guard, synchronous, pre-await]
  -> paperPositionsClosing.add(id)
  -> await fetchBidAsk(pos.oPair)                                [the only await in the function]
  -> resolve exitPrice (live bid/ask, or pairData fallback for a manual close)
  -> re-check the position is still open (idx2) -- guards a *sequential* duplicate close
  -> compute movePips / pnl from pos.pipValueAtEntry (fixed at open, never re-fetched)
  -> classify result: fixed autoResult, or pnl>0?Win:pnl<0?Loss:'Break even' (manual),
     or exitPrice-vs-target (auto)
  -> snapshot paperAccount + journalEntries
  -> mutate balance, splice openPositions, unshift closedPositions
  -> journalNoteCloseJVM(pos,closedPos)                          [updates the same OPEN record]
  -> commitPaperLedger()
  -> on {ok:false}: roll back, return {error, blocked:true}
  -> on success: return {closedPos, committed:true}
  -> finally: paperPositionsClosing.delete(id)
```

`commitPaperLedger()` is the **only** function allowed to persist `paperAccount`/
`fxhub_paper_version`/`journalEntries` (§0). Every mutation site snapshots before mutating and
restores the snapshot on a rejected commit — proven directly against the real function in
`tests/v_paper_trading_audit_tests.js` (TEST H, JvmAtomic.1–4).

## 2. Trade lifecycle (ALEX)

ALEX's live-paper path is architecturally different from JVM's, not a copy of it — even after
Phase 2 gave it equivalent safety guarantees:

- The real live-open mutation site is `alexGAttemptOpenLivePosition()` (async, one `await
  fetchBidAsk(...)`) — **not** `alexGConstructLivePosition()`, which is a pure function that only
  builds a position object and mutates nothing; it stays completely unmodified and still
  protected. `alexGCloseLivePosition(tradeId,result,exitPrice,ba,exitMeta)` closes, and is
  **fully synchronous** — no internal `await` — so unlike JVM's `closePaperPosition()` there is
  no sequential-duplicate-close window to guard against; each call re-derives its position index
  fresh and runs to completion atomically. The existing `if(idx===-1) return` early-return is
  what makes a repeated close on an already-closed `tradeId` a safe no-op.
- Result R is **fixed at the planned R:R**, not recomputed from the actual fill
  (`resultR = result==='Win' ? pos.plannedRR : -1`) — confirmed directly (ALEX.1–3) and
  **unchanged by Phase 2**, per the explicit instruction not to touch ALEX's fixed-R policy.
- **Persistence (§0 has the full contract):** `commitAlexGLedger()` calls
  `saveAlexGAccountGuarded()`, which writes `fxhub_alexg_account` + `fxhub_alexg_account_version`
  + `fxhub_alexg_journal` as **one atomic unit**, rejecting a stale write exactly like JVM's
  `savePaperAccountGuarded()`. `alexGAutoTrading`/`alexGZoneState`/`alexGSetupState` are
  deliberately outside this unit (`saveAlexGRest()`, unguarded) — bundling the auto-trading
  toggle or zone state into the same gate would reproduce the exact false-stale-rejection bug
  JVM's own v11.0.1 fix exists to prevent (an unrelated tab action silently advancing the version
  and making a different tab's real trade look falsely stale). `saveAlexG()` is now a thin alias
  for `saveAlexGRest()`, used only by its one remaining non-account-mutating call site
  (`toggleAlexGLiveTrading()`); the journalEntryId backfill migration's ALEX branch now goes
  through `commitAlexGLedger()` directly, since it mutates the journal. Every account-mutating
  call site (`alexGAttemptOpenLivePosition`, `alexGCloseLivePosition`, `resetAlexGLiveAccount()`,
  `clearTestTradesAlex()`) snapshots `alexGAccount`/`alexGJournalEntries` before mutating and
  rolls back to that snapshot on a rejected commit — proven directly (ALEX-Version.1–14,
  AlexAtomic.1–13), including a real two-tab scenario (a stale in-memory copy attempting to close
  a position another tab already closed and persisted) and simulated `localStorage.setItem`
  failures on the account, version, and journal keys individually — each one now rolls back the
  entire atomic unit, not just the key that failed.

## 3. Journal ownership

One journal-record builder per strategy (`buildJVMJournalOpenRecord`/`buildAlexJournalOpenRecord`),
one shared `normalizeJournalRecord(raw,storeStrategy)`, one shared read path
(`getUnifiedJournalRecords()`) that loops `STRATEGY_REGISTRY` and calls each strategy's
`Services.getJournal()`/`normalize()`. `journalNoteOpenJVM`/`journalNoteCloseJVM` and
`journalNoteOpenAlex`/`journalNoteCloseAlex` are additive-only side effects — they never
recompute P&L/result, only attach it to the journal record the engine already decided.

**Phase 2 correction:** `getFilteredJournalRecords()`'s strategy filter now matches `r.strategyId`
instead of `r.strategyLabel` — `strategyId` is the stable ownership key (ADR-006 §0);
`strategyLabel` is display metadata only. The real Journal filter dropdown's option *values*
changed from `"JVM"`/`"ALEX"` to the registry ids `"current_strategy"`/`"alex_g_sr_v1"` (the
visible text is unchanged). `normalizeJournalRecord()` already guarantees every record —
including a legacy one with no `strategyId` field of its own — has one populated (falling back to
the literal store it was read from), so no separate legacy-fallback branch was needed at the
filter site itself. Proven against a deliberately mislabeled record (`strategyLabel:'ALEX'`,
`strategyId:'current_strategy'`), which now correctly filters under JVM, not ALEX — the exact
class of misattribution label-based filtering could never rule out (Ownership.1–5).

## 4. Analytics formulas

**Phase 2 correction:** one canonical function, `computeCanonicalPerformance(records)`, is now
the single place `wins`/`losses`/`breakEven`/`decisiveTrades`/`winRate`/`netPnl`/`netR`/
`averageR`/`grossProfit`/`grossLoss`/`profitFactor` are ever computed. It takes an
already-filtered array of closed trade-like records (strategy scoping and test-trade exclusion
happen in the caller, kept generic so it works for JVM's and ALEX's differently-shaped records
alike) and returns:

- **Win Rate = Wins / (Wins + Losses).** Break-even trades are reported separately
  (`breakEven`) and never appear in the denominator — a trade classified Break Even stays Break
  Even, never silently folded into a win or loss to make a percentage computable.
- `winRate` is `null` — never `NaN`, `Infinity`, or a fabricated `0%` — when `decisiveTrades` is 0.
- A record is excluded entirely (not counted anywhere) unless `result` is exactly `'Win'`,
  `'Loss'`, or `'Break even'` — an unrecognized or missing result can't be confidently classified
  and is never guessed at.
- R-multiple prefers an existing `resultR` field (ALEX's fixed-R policy, never recomputed) and
  falls back to `pnl/riskAmount` only when `resultR` is absent (JVM's raw account records).

Before this correction, Dashboard's inline tile formula (`wins/closed.length*100`, break-even
counted against the denominator, no `isDeveloperTrade` filter, no minimum sample) and Strategy
Center's `computeMogoStrategyPerformance()` (excludes test trades, requires `count>=50`)
genuinely disagreed on identical data — confirmed both offline and live (Dashboard showed 100%
JVM win rate on a single real closed trade with no gate). Both now build on
`computeCanonicalPerformance()`: Dashboard's tile filters `isDeveloperTrade` and calls it
directly; `computeMogoStrategyPerformance()` calls it and layers its own pre-existing `count>=50`
`sufficientSample` gate and pair/session breakdown on top, unchanged. **That minimum-sample gate
is intentionally still Strategy-Center-only** — it is a separate, pre-existing display policy
(when to show a number at all), not part of the formula itself (what the number is when shown);
unifying the formula did not require or imply also unifying that gate onto Dashboard, and doing
so was out of this milestone's explicit scope.

`computeGroupTradeStats()`/`computeManualReviewGroupedPerformance()` and
`computePaperLedgerIntegrity()` (reconciliation, below) are unaffected — both already exclude
test trades and require no minimum sample gate of their own for their specific purposes.

## 5. Persistence, versioning, and reconciliation

- **JVM**: `fxhub_paper` + `fxhub_paper_version` (monotonic, session-tracked via
  `paperAccountKnownVersion`), written only by `commitPaperLedger()`. A write is rejected outright
  if storage's persisted version exceeds this session's last-known version (another tab/session
  wrote first) — proven directly (TEST H): the rejected write leaves both `paperAccount` and
  `journalEntries` byte-identical to their pre-attempt snapshot.
- **ALEX**: `fxhub_alexg_account` + `fxhub_alexg_account_version` + `fxhub_alexg_journal`, all
  written together as one unit only by `commitAlexGLedger()`/`saveAlexGAccountGuarded()` (§0, §2)
  — a stale write is rejected exactly like JVM's, and a write failure on any one of the three
  keys rolls back all three, proven directly (ALEX.4, ALEX-Version.5–8/14, AlexAtomic.3–7).
- **Reload**: `loadSaved()`/`loadAlexGSaved()` restore both accounts and both journals exactly —
  proven directly (TEST G): one open position, one matching journal record, byte-consistent
  balance after a simulated wipe-and-reload.
- **Reconciliation**: `computePaperLedgerIntegrity()` (JVM-only, unchanged) is a real,
  already-built, read-only engine — orphaned journal records, orphaned account positions,
  duplicate IDs, missing P&L, and an expected-vs-actual balance diff. Confirmed live via the
  Diagnostics page's "Paper Ledger Integrity" card, and directly against the real function with
  synthetic clean/orphan/duplicate inputs (Reconciliation.1–4). `applyPaperReconciliation()`
  requires explicit confirmation per trade ID and never guesses. **Phase 2** added an equivalent
  basic reconciliation for ALEX (duplicate IDs, orphaned journal records, expected-vs-actual
  balance) inside the new combined Health Check (§10) rather than a second standalone
  ALEX-specific card, since the two are read simultaneously there anyway.

## 6. Corrections made (both phases, v12.3.2)

**Phase 1** — both met all nine of the audit's own narrow-correction criteria (proven, root-cause
isolated, narrowly scoped, no change to entry rules/signal logic/analytics definitions/version
protection, no data deleted, no product decision required, a deterministic fixture addable):

1. **`showPanel()` had no dispatch branch for `'journal'`.** Navigating to the unified Journal
   tab only ever showed whatever `renderJournal()` last rendered — typically the empty state from
   `initAll()` at connect time — never a fresh read, since neither `openPaperPosition()`/
   `closePaperPosition()` nor ALEX's open/close functions call `renderJournal()` themselves.
   Reproduced live: two real closed trades existed, `getUnifiedJournalRecords()` correctly
   returned both, but the Journal tab showed "No trades yet" until an unrelated filter edit or a
   full reload happened to trigger a refresh. Fixed with one additive
   `if(name==='journal') renderJournal();` line, mirroring every other real panel's own
   self-refresh pattern.
2. **`openPaperPosition()` did not itself reject a zero-risk trade** (`stop===entry`). The guard
   existed only in the UI wrapper `placePaperTrade()` — any other caller invoking the engine
   function directly (including a future TJR Phase 2 candidate-execution path) would silently
   construct a position with a non-finite lot size. Fixed with an early
   `if(!(riskPips>0)) return{error:...}` guard inside the engine function itself, matching the UI
   wrapper's existing rejection message.

**Phase 2** — reviewed and approved separately; implements the three Phase-1 findings that
required a decision, plus four further requested corrections:

3. **ALEX version-guard and atomicity** (§0, §2, §5) — `commitAlexGLedger()`/
   `saveAlexGAccountGuarded()`, a new `fxhub_alexg_account_version` key, snapshot+rollback at
   every account-mutating call site. **Corrected by the Final Ledger Atomicity Review:** an
   initial version of this correction split the account (guarded) from the journal (written
   separately, unguarded) the same way JVM's own `save()` used to — but that reintroduced the
   exact account/journal divergence-after-reload gap for ALEX. The account, version, and journal
   are now written as one atomic unit; see §0 for the full contract.
4. **Canonical analytics** (§4) — `computeCanonicalPerformance()` now backs both Dashboard and
   Strategy Center.
5. **Normalized close reason** — `closePaperPosition()` derives `closeReason`
   (`TAKE_PROFIT`/`STOP_LOSS`/`MANUAL_CLOSE`/`BREAK_EVEN`/`SYSTEM_CLOSE`) from data already known
   deterministically at close time: `pos.isDeveloperTrade` forces `SYSTEM_CLOSE` regardless of
   Win/Loss (a developer/self-test forced close is neither a real price cross nor a discretionary
   decision); otherwise an automated Win/Loss maps to `TAKE_PROFIT`/`STOP_LOSS`; a manual close
   maps to `BREAK_EVEN`/`MANUAL_CLOSE`. Propagated additively through
   `applyJournalCloseUpdate()`/`normalizeJournalRecord()` — `null`, never fabricated, for any
   record closed before this release — and displayed in Trade Inspector's Exit section.
6. **Break-even epsilon** — replaces the exact `pnl===0` check with a documented
   `BREAK_EVEN_R_EPSILON=1e-9` realized-R threshold: nine orders of magnitude above JS's own
   `Number.EPSILON`, safely absorbing floating-point noise from the exit-price/pip/lots
   arithmetic while remaining astronomically smaller than any realistic real trade's R-value. This
   is a numerical-precision floor, **not** a discretionary trading tolerance — a genuinely small
   1-pip profit or loss is still classified Win/Loss exactly as before (proven live: F2's 1-pip
   case still classifies Win).
7. **`strategyId`-based journal filtering** (§3).
8. **Read-only Developer Mode Paper Trading Health Check** (§10).

All eight are covered by dedicated fixtures in `tests/v_paper_trading_audit_tests.js` (grown from
32 to 73 fixtures). Protected-function drift versus the original committed v12.3.1 baseline is
exactly three items, all disclosed above: `openPaperPosition` (#2), `closePaperPosition` (#5–6),
`alexGCloseLivePosition` (#3). `showPanel`, `getFilteredJournalRecords`,
`computeMogoStrategyPerformance`, and every ALEX function touched other than
`alexGCloseLivePosition` (notably `alexGConstructLivePosition`, which needed no change at all —
see §2) are not on the protected list. The v12.3.2 baseline was regenerated and accepted only
after all eight corrections were complete and verified.

## 7. Remaining limitations (disclosed)

Everything Phase 1 originally listed here has now been corrected in Phase 2 (§6), except the one
that is a fundamental access limitation, not a code defect:

- **Real-data health check still cannot be run from this development environment.** It has no
  access to any real end user's actual browser `localStorage` — only a fresh, always-empty
  automation browser session. The new Paper Trading Health Check utility (§10) exists precisely
  so the *user* can run this check in their own normal MOGO browser tab; this document does not
  and cannot claim that any real production account's data has actually been inspected.
- **Dashboard's tile has no minimum-sample gate; Strategy Center's does (`count>=50`).** This is
  an intentional, disclosed difference in *when* a number is shown, not in *how* it's computed
  (§4) — deliberately not unified, since doing so would be a separate display-policy change
  beyond this milestone's requested scope.

## 8. TJR non-participation

Confirmed both offline and live: `TJR_MANIFEST.capabilities.paperTrading === false`,
`TJR_SERVICES.getAccount()` returns `null`, `getJournal()` returns `[]`, and computing session
zones (`buildTjrSessionZones`) causes zero mutation of any JVM/ALEX state. The live TJR
workspace's Paper Trading tab renders every control disabled with an explicit "becomes available
only after..." message. No paper P&L tile — fabricated or otherwise — exists anywhere for TJR.

## 10. Paper Trading Health Check (Developer Mode, read-only)

A new Diagnostics-page card, gated by `developerModeEnabled` exactly like the existing Developer
Test Tools sections. `computePaperTradingHealthReport()` is a pure function over whatever
JVM/ALEX state is already loaded in the browser it runs in — it never writes to `localStorage`,
never mutates `paperAccount`/`journalEntries`/`alexGAccount`/`alexGJournalEntries`, never advances
a version counter, and never repairs, resets, or migrates anything. Proven directly: every
relevant piece of state is snapshotted before the call and asserted byte-identical after
(HealthCheck.1–4).

Reports, per strategy: open/closed position counts, journal record count, balance, realized P&L,
and the current ledger/account version. JVM's reconciliation detail reuses the existing
`computePaperLedgerIntegrity()` directly rather than duplicating it; ALEX's equivalent (duplicate
IDs, orphaned journal records, expected-vs-actual balance) is new, since no ALEX reconciliation
tooling existed before this release. Combined checks — computed once, across both stores —
cover duplicate trade IDs, account trades missing a journal record and vice versa,
`strategyId` mismatches (a journal record's `strategyId` not matching the store it's actually
in), result/P&L/R mismatches between a journal record and its matching account position, invalid
timestamps and prices, records missing `strategyId` entirely, legacy records, and likely test
artifacts (`isDeveloperTrade`) — proven against deliberately-constructed duplicate/orphan/
mismatched/invalid inputs (HealthCheck.7–14).

The **Copy Health Report** button copies a plain-text report built field-by-field from the
computed report object only — never a raw dump of `paperAccount`/`alexGAccount`/`cfg`/`aiChat` or
any other live object — so it structurally cannot include the OANDA token, OANDA account ID, or
Anthropic key. Proven directly by setting realistic-looking values for all three
(`cfg.key`/`cfg.accountId`/`aiChat.key`) and asserting none of them appear anywhere in the copied
text (HealthCheck.15), and reconfirmed live.

**This utility must be run in the user's own normal MOGO browser tab to evaluate their own real,
stored records.** This document does not claim, and this development environment has no way to
claim, that any actual production account's data has been inspected by it.

## 11. TJR non-participation

Confirmed both offline and live: `TJR_MANIFEST.capabilities.paperTrading === false`,
`TJR_SERVICES.getAccount()` returns `null`, `getJournal()` returns `[]`, and computing session
zones (`buildTjrSessionZones`) causes zero mutation of any JVM/ALEX state. The live TJR
workspace's Paper Trading tab renders every control disabled with an explicit "becomes available
only after..." message. No paper P&L tile — fabricated or otherwise — exists anywhere for TJR.

## 12. Test coverage

`tests/v_paper_trading_audit_tests.js` (**93 fixtures**, up from 32 after Phase 2 and 73 after the
Final Ledger Atomicity Review, run via `tests/run_v_paper_trading_audit_tests.js`) exercises the
real, unmodified (except §6's corrections) production functions against isolated in-memory state,
verifying actual serialized storage values and simulated reloads, not just in-memory variables —
the same offline JXA-harness
pattern as every other suite in this repository. `closePaperPosition()`'s one genuine internal
`await fetchBidAsk(...)` cannot be resolved by this harness (reconfirmed empirically, independent
of prior precedent, via three techniques: a bare top-level `await`, an ObjC `NSRunLoop`
spin-wait, and JXA's own `delay()` — none drain the JS microtask queue). Its exit-price/P&L/
result-classification math was instead proven directly against the real running app in a live
browser session (winning/losing long, winning/losing short, manual partial close, break-even, and
the confirmed absence of a discretionary tolerance band — all six scenarios, all correct).
`alexGCloseLivePosition()`, by contrast, has no internal `await` (confirmed by direct reading) and
its Phase-2 version-guard/atomicity fixtures (ALEX-Version.1–14) call it directly and observe a
real, synchronous return value — no live-browser dependency needed for those. See
[TESTING.md](TESTING.md) for the general offline-harness pattern this suite follows.
