# Release Notes

This is a readable, maintained summary of every MOGO release. It is deliberately condensed —
the original, complete, as-shipped text for every release (including full verification detail,
fixture counts, and forensic detail for reliability releases) remains in-code as
`APP_VERSION_LOG` in `index.html` and is never rewritten here. If a summary below and the
in-code log ever appear to disagree, the in-code log is the source of record.

**Rule for future releases:** every release that changes behavior must add an entry here (in
addition to its own `APP_VERSION_LOG` entry), and must update [TESTING.md](TESTING.md) and
[KNOWN_ISSUES.md](KNOWN_ISSUES.md), plus any ADR or [ARCHITECTURE.md](ARCHITECTURE.md) section
its change actually affects.

---

## v12.8.3 — Market Data Completeness Contract (ADR-011)

**Closes a verified defect: a materially truncated candle history was treated as complete and
still produced signals and confluence scores.** Zero protected drift (63 functions, 4 constants
byte-identical) — `detectSignals`, `bestConfluence`, `scoreConfluence` and `findSwingPoints` are
**not** modified, re-implemented or wrapped.

### What was actually wrong

An initial audit alleged `fetchCandles()` paginated and returned truncated data after HTTP 429.
**Test-first investigation disproved that** — it issues one request and returns `null` on any
non-OK status, and `null` is rejected by every guard.

The real risk arrived through a **perfectly successful HTTP 200**. A response carrying fewer
candles than requested was indistinguishable from a full one, because production validated only a
minimum usable length (`candles.length < 10`), never the requested lookback. `scanPair()` requested
220 and scored `conf.total=20` with 1 signal from **80**.

The pagination mechanism does exist — in `fetchCandlesRange()` (replay/backtest consumers), which
breaks on a later-page HTTP 429 and returned the partial accumulation silently.

### The contract

**One abstraction: `completenessState` ∈ {`COMPLETE`, `PARTIAL`, `UNAVAILABLE`}. Consumers depend
on that and nothing else.** `httpStatus`, `paginationTerminationReason`, `pagesRequested`,
`pagesReceived`, `fetchDurationMs` and `retryCount` are diagnostics only.

That rule is load-bearing: **a consumer branching on `httpStatus === 429` would re-create the
original defect**, because the case that actually reached scoring was `httpStatus === 200`.

**`PARTIAL` means the request was not fully satisfied — never that N candles are missing.**
Session, weekend, holiday, instrument and liquidity gaps are all legitimate, so there is
deliberately **no `missingCandles` field**, and a fixture asserts its absence.

**Classification compares the RAW response size against the request**, never the
post-completeness-filter size — the newest candle is almost always still forming, so comparing
filtered length would mark essentially every healthy scan `PARTIAL`.

### Implementation

Completeness is attached to the returned array as **non-enumerable** properties, so all 21
existing call sites are byte-for-byte unaffected. `scanPair()` gates evaluation by passing `null`
into the protected evaluators when the state is not `COMPLETE` — relying on guards they **already**
have. Full candles are still recorded for charting and diagnostics; only *evaluation* is gated.

### Accepted trade-off

An instrument whose **genuine** history is shorter than the requested lookback is `PARTIAL` and
will not be scanned. MOGO cannot distinguish that from a truncated response, and the conservative
reading was chosen deliberately. The remedy is a per-request lookback the instrument can satisfy —
not a relaxed contract.

### Verification

**789/789 fixtures across 17 suites, zero drift.** `SAFETY-1` … `SAFETY-4` were written first and
failed against the previous build. `BEHAVIOUR-2b` was added to prove a healthy scan with one
still-forming candle stays `COMPLETE` and still evaluates — the fix must not suppress normal
scanning.

---

## v12.8.2 — EXP-001: a browser download is an attempt, not a durability proof

**Evidence-integrity correction — no trading behavior change.** Zero protected drift (63 functions,
4 constants byte-identical).

### The defect, found by literal browser verification

`evidenceExportPackage()` marked a package **successfully exported** whenever `downloadTextFile()`
returned without throwing. It cannot throw on refusal — the anchor-`click()` idiom **returns
nothing, has no error handling, and cannot report whether the browser accepted, blocked, cancelled
or failed the write.**

Chrome silently refused two real downloads while the app reported `ok:true`, set
`exportVerified: true`, and **cleared the standing unexported-evidence warning — with no file
anywhere on disk.** That violated the milestone's own rule and made the banner lie, which is worse
than having no banner. The original fixture missed it because its stub *threw*; the real API never does.

### The correction

| Stage | Recorded | Warning |
|---|---|---|
| Download attempted | `exportAttemptedAt`, `exportMechanism`, `exportFilename`, `exportAttemptCount`. **`exportedAt: null`** | ❌ **does not clear** |
| Operator re-imports the file | all five conditions below | ✅ **clears** |

**All five required:** bytes parse · package validates · **identity matches** (`packageId` and
`sourceTradeId`) · **SHA-256 verifies** · **exact canonical content byte-identical to the stored
package**. Only then are `exportedAt`, `exportVerified: true` and
`exportVerificationMethod: 'REIMPORT_VERIFIED'` recorded.

**MOGO now only claims evidence is on disk when it has actually read it back off disk.**

**No shortcuts:** no File System Access API, and **no operator-confirmation override** — an operator
saying *"yes, it downloaded"* is not evidence; the bytes are. An `UNVERIFIABLE` hash can never
confirm an export. The banner and Diagnostics now state plainly that a download alone proves
nothing, and report attempted-but-unconfirmed downloads separately.

### Verification

**779/779 fixtures across 16 suites, zero drift.** v128 grows 62 → 74: **E1–E12** exercise the real,
pure `evidenceEvaluateExportReimport()` decision offline across attempted export, cancelled/missing
download, absent re-import, malformed re-import, identity mismatch, failed SHA-256, unverifiable
hash, noncanonical content mismatch, valid re-import, warning clearance, absence of any shortcut,
and that the import path actually routes through the decision.

**X4 was strengthened, not weakened** — it previously asserted ordering around a marking step that
should not exist; it now asserts the export path can never stamp `exportedAt` under any ordering.

**No browser was opened and no Chrome profile was accessed for this release.**

---

## v12.8.1 — INC-001 Load-Integrity Correction + INC-004 Mandatory Browser-Test Isolation

**Safety release — no trading behavior change.** Zero protected-function/protected-constant drift
(63 functions, 4 constants byte-identical). No strategy rule, replay logic, analytics, or
evidence-package behavior changed.

### Why this release exists

On 2026-07-31, developer browser verification issued a browser storage-clearing call **three times**
against `http://localhost:8744` inside the operator's **active Chrome Profile 2** — the live MOGO
origin. Real ALEX and JVM paper-trading data was destroyed and recovered from a Time Machine backup.

The origin had been **inferred** from `.claude/launch.json` (port 8743) and assumed isolated. That
assumption was never verified, and it was wrong. **No MOGO code was involved** — the calls were
ad-hoc inline scripts at the tool layer. Full account: [INCIDENTS.md → INC-004](INCIDENTS.md).

### The real code defect it exposed — INC-001 load integrity

`loadSaved()`, `loadAlexGSaved()` and `loadAlexV2Saved()` each wrapped **every key in one
`try/catch`**. A single `JSON.parse` throw on the first key silently abandoned **every remaining
key**, leaving empty in-memory defaults that the next ordinary `save()` wrote straight over real,
intact stored data. **The stored bytes were readable the whole time.**

**Fixed in two halves — either alone is insufficient:**

1. **Per-key isolation** — `loadStoredKey()` loads each key independently, so one unreadable key can
   never suppress the others.
2. **Refusal to overwrite** — keys **present but unreadable** become unwritable for the session.
   `persistStorageKey()` enforces this for the unguarded savers; `savePaperAccountGuarded()` and
   `saveAlexGAccountGuarded()` refuse outright with `reason:'LOAD_INTEGRITY_BLOCKED'`.

A failed read now degrades into *"don't touch it"*, never *"replace it with a default"*. This also
closes the **missing-version hole**, where an account key with no version key left `0 > 0` false and
let the staleness guard pass.

An **absent** key is not a failure — the in-memory default is correct there, and a fresh install
writes normally. Every failure is reported loudly through both engine-error channels, so the operator
learns their data is being **preserved**, not silently frozen. Return **shapes** are unchanged;
`LOAD_INTEGRITY_BLOCKED` is additive and no call site compares `reason` by equality.

### Mandatory browser-test isolation

**`scripts/browser_test_profile.sh`** creates a **disposable** Chrome `--user-data-dir` and **fails
closed** — refusing an inferred origin, a profile root inside the operator's Chrome directory, a
reused profile directory, or a profile that is not verifiably empty. It records the profile path,
exact origin, not-the-operator-profile confirmation, and a pre-clear inventory.

**`docs/TESTING.md` Rule 0:** browser testing never attaches to, reuses, inspects, modifies, or
clears the operator's Chrome profile — with an absolute prohibition on storage clearing, IndexedDB
deletion, account resets, and session/tab reuse outside a verified disposable profile.

### Verification

**767/767 fixtures across 16 suites, zero drift.** New suite
`tests/v129_browser_isolation_guard_tests.js` (26 fixtures): **L1–L14** drive the *real* loaders and
savers through a controllable storage stub — **L4 reproduces the exact original overwrite and
asserts the stored bytes survive it**; L8/L9 prove both guarded ledgers refuse to commit; L10 proves
the guard is not a freeze. **G1–G12** statically assert no committed source performs a destructive
storage call, none targets the operator's Chrome profile directory, and the launcher keeps its
fail-closed behaviour.

**No browser was opened and no Chrome profile was accessed during this release.** The launcher is
statically asserted, never executed.

⚠️ **Disclosed limitation:** these guards constrain the *repository* only. They cannot intercept
ad-hoc inline scripts at the tool layer — which is how INC-004 actually happened. Recorded in
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) rather than implied away.

---

## v12.8.0 — MOGO-003 Phase 1: Evidence Platform (Durable Capture & Export)

**Infrastructure release — no trading behavior change.** The same market data produces the same
trades before and after, proven by zero protected-function/protected-constant drift (63 functions
and 4 constants byte-identical). No strategy rule, entry, exit, stop, target or sizing value changed.

### The defect this closes

`saveAlexGRest()` and `save()` were both `try{…}catch(e){}`. A quota-exceeded write failed and
**nothing anywhere reported it** — silent evidence loss was the default. Both now classify the
error, record it to the existing engine-error channel, emit a `DATA_UNAVAILABLE` decision event and
raise a persistent banner. **Both still never throw**, because `commitAlexGLedger()` /
`commitPaperLedger()` call them *after* their guarded units already succeeded and depend on that
best-effort behaviour. `saveAlexGAccountGuarded()` now distinguishes a quota exhaustion from the
`STALE_VERSION` concurrent-tab conflict, with its `{ok,integrityCompromised,reason}` return **shape
unchanged**.

### Three storage tiers — and what each one does *not* survive

| Tier | Medium | Automatic? | Site-data clear | Device / disk loss |
|---|---|---|---|---|
| (a) | `localStorage` — working buffer only | ✅ | ❌ | ❌ |
| (b) | **IndexedDB `mogo_evidence`** — evidence store | ✅ **no user action, ever** | ❌ | ❌ |
| (c) | **Completed file export** | 🟡 after one download grant | ✅ | 🟡 only if backed up off-device |

⚠️ **IndexedDB is not a backup**, and MOGO now says so in the Diagnostics card and the banner
rather than implying durability it does not have.

### Integrity — and the limits of the claim

Each package carries a **SHA-256** `contentHash` over `mogo.evidence-canon.v1`: object keys sorted
(order insignificant), **array order significant**, `undefined` → explicit `null`, non-finite numbers
rejected, UTF-8, and the integrity fields plus the whole `export` block excluded — so marking a
package exported can never change its hash.

**This detects alteration. It is not authenticity, not identity verification, and not a signature** —
anyone who can modify a package can recompute its hash. `alexGStableHash` is a 64-bit FNV variant and
is deliberately **not** used here. When Web Crypto is unavailable (e.g. a `file://` origin), capture
still proceeds and the package is stored with `contentHash: null` + `UNAVAILABLE`; it **never** falls
back to a weak digest, and such packages are counted separately and never shown as verified.

### What else Phase 1 delivers

- **Automatic capture** at the approved seam — *after* the `alexGCheckLivePositions` loop, in its own
  try/catch. `alexGCloseLivePosition` is protected and untouched. Capture cannot prevent, repeat,
  delay or alter a close, and is idempotent per `tradeId` via a unique store index.
- **Standing unexported-evidence banner** with a live count, escalating to a blocking confirmation
  above 50 when live trading is switched on.
- **Export** with the exact bytes re-hashed before writing. **A failed or cancelled export is never
  marked successful** — optimistic marking would make the banner lie.
- **Import** that rejects an altered package outright and never repairs it, rejects a
  duplicate `packageId` carrying a different hash, and never touches live trading state.
- **Read-only historical backfill** that adopts existing trades as `MINIMAL` packages without
  modifying one record or fabricating one value; unstamped trades stay honestly unstamped.
- **Bounded buffers** on `fxhub_alexg_setups` (1,000) and `fxhub_alexg_zones` (200/pair) — the two
  genuinely unbounded stores. **The guarded journal/ledger is never capped, evicted, rewritten or
  bypassed.** No tier-(a) record is evicted until its evidence is committed to tier (b), and
  tier-(b) packages are never automatically deleted.

### Deliberately excluded

Replay, analytics, strategy optimization, market-context/candle capture (Phase 3), durable decision
chains (Phase 2), and the **File System Access API** (not implemented, not referenced, not
capability-detected). Every Phase 1 package therefore honestly reports `PARTIAL` — a package
claiming `COMPLETE` while lacking market context would be dishonest.

### Verification

**741/741 fixtures across 15 suites, zero drift.** New suite:
`tests/v128_evidence_platform_tests.js` (62 fixtures).

⚠️ **Disclosed limitation:** the offline JXA harness has neither `crypto.subtle` nor `indexedDB`, so
the SHA-256 digest itself and the IndexedDB layer are **browser-verified, not fixture-verified** —
the same documented split already used for `alexGCloseLivePosition`. See
[TESTING.md](TESTING.md) §1 and [ADR-010](adr/ADR-010-evidence-package-persistence.md).

---

## v12.7.1 — MOGO-002.8B: ALEX Setup-Level Execution Policy

**Execution Policy**

| Setup | Status |
|---|---|
| **Break & Retest** (`B_breakRetest`) | **ACTIVE** |
| **Repeated Zone Reaction** (`A_repeatedReaction`) | **SUSPENDED FOR RESEARCH** |

**Reason:** MOGO-002.8B Setup Isolation Audit. An operational suspension pending Tier 2+ replay
evidence — **not** a finding that the setup is invalid. The basis is a Tier 1 forward-paper
observation (18 RZR trades, 1W/17L) which, per the MOGO Research & Validation Standard §9, may justify
an operational change but cannot support any conclusion about the setup's validity.

**Additive only.** Zero protected functions and zero protected constants modified; drift check clean.

**No silent skip.** A suspended candidate is still detected, still classified, still recorded and
still persisted — **only the trade-open step is withheld**. Each withheld candidate gets a permanent
`SUSPENDED — RESEARCH HOLD` status row plus a linked `RULE_EVALUATED` / `CANDIDATE_REJECTED` pair
carrying `SETUP_SUSPENDED_FOR_RESEARCH`, so the suppression is countable and the candidate stays
visible to future replay analysis.

**Replay is untouched** and continues generating both setup types — replay is research, and is the
only route to the sample that could retire this suspension.

**Reversible by one boolean:** `RULES_ALEXG_V11.v11Config.setupSuspensionEnabled`. The gate fails
**open** in every ambiguous case, so a misconfiguration can never silently stop trading. A recorded
suspension window (start/end/authority/reason) keeps later period-over-period comparisons valid.

**Not a rule change** — `ruleVersion` remains `alex_g_sr_v1_1`. Entry, stop, target, risk, sizing,
confirmation, zone logic, analytics, historical trades and existing open trades are all unchanged. An
already-open RZR position closes normally; the exit path never consults `setupType`.

**Defect found and fixed:** `CONFIG_ENTRY_DAY_NOT_ELIGIBLE` — used by the v12.7.0 Monday–Wednesday
gate — was never added to `REASON_CODE_REGISTRY`. Unregistered reason codes are rejected by
`validateDecisionEvent`, so **both v1.1 entry-day rejection events were being silently dropped**. The
gate blocked trades correctly but produced no decision-event evidence. Both codes are now registered
and asserted by fixtures.

**Testing:** 23 new fixtures (K1–K23). Full suite **679/679** across 14 suites, zero drift.

---

## v12.7.0 — MOGO-002.8A: ALEX v1.1 Release (`alex_g_sr_v1_1`)

**The first behaviour-changing ALEX release since v4.2.1**, and the first to introduce a new ALEX
rule version. Additive only: `RULES_ALEXG` remains a protected constant and is byte-identical, with
zero drift across all 63 protected functions and 4 protected constants.

`RULES_ALEXG`'s own change-control rule requires that any rule or default change take a **new
`ruleVersion`** rather than an in-place edit, so historical `alex_g_sr_v1` results can never be
silently recalculated. v1.1 follows that exactly, via a new additive constant `RULES_ALEXG_V11`.

**Engine parameters are unchanged.** Zone detection, touch counting, break-of-structure,
break-and-retest, entry sequencing, the `zoneLow/High ∓ 0.25×ATR` stop and the fixed 2R target all
still read `RULES_ALEXG.config` from the same protected functions — a v1.1 trade and a v1.0 trade on
identical data qualify and size identically.

**One behavioural change:** `ALEX_V11_001`, a **Monday–Wednesday entry-eligibility gate** (UTC),
evaluated at the live entry moment in the non-protected evaluation loop, after staleness and before
the open attempt. It mirrors the existing activation/staleness gate pattern, including a permanent
`IGNORED — ENTRY DAY NOT ELIGIBLE` status and a linked decision-event pair. Evidence: `AXR-080` /
`CLAIM|ALEX_G|20260728|083`. A scope caveat is recorded in the rule registry — the educator claim is
scoped to a confirmation setup MOGO does not implement — so the gate is config-controlled and **fails
open**, never blocking a trade if disabled or if its inputs are unreadable.

**Statistics corrected** (reporting only, zero trading effect; applies to v1.0 and v1.1 records alike,
so historical *reporting* is fixed without any historical *record* being rewritten):

- **Realized R** — computed from each trade's own entry/stop/exit instead of the frozen `+plannedRR`/`-1`. A v1.0 win recorded `+2.00R` regardless of the actual exit price.
- **Chronological equity** — the curve is now walked by `closedAt` ascending. `closedPositions` is stored newest-first, so the previous walk described a reversed curve.
- **Current vs maximum drawdown** — now two separate cards. The single previous card was labelled "Current drawdown" while computing the maximum.
- **Configured starting balance** — replaces a hardcoded `10000` in dashboard P&L.

**Versioning:** every newly opened trade is stamped `strategyVersion: alex_g_sr_v1_1`.
`strategySpecificationVersion` deliberately remains `alex_g_sr_v1`, because no engine parameter
changed. Existing trades are never back-filled, open positions continue under the version that opened
them, and mixed history still reports `MIXED_VERSION` rather than being silently averaged.

**Dead configuration:** v1.1 omits the four v1.0 keys read by nothing (`zoneTimeframes`,
`requireWick`, `minWickRatio`, `maxZoneAgeBars`). They remain in `RULES_ALEXG` because it is protected.

**Testing:** new suite `run_v127_alex_v11_release_tests.js` (65 fixtures). Full suite **656/656**
across 14 suites, zero drift.

**Defect found and fixed during this release:** the new date-dependent gate made 9 pre-existing v126
fixtures pass Mon–Wed and fail Thu–Sun with no code change, because they drive the evaluation loop
end-to-end against the live wall clock. Fixed in the **v126 runner only**, by pinning that test
process's clock — zero assertions changed, zero production code changed, zero fixtures rewritten.

---

## v12.6.0 — PROGRAM-001 Phase 2C Wave 1: ALEX Candidate Lifecycle Instrumentation
Infrastructure-only release — no trading behavior change; the exact same market data produces the
exact same ALEX trades before and after this release, confirmed by zero protected-function/
protected-constant drift against the committed v12.5.0 baseline. **Pre-release correction:** an
earlier draft's `CANDIDATE_CREATED` logic deduped only by "already reported this session," which
would have mislabeled a historical setup ALEX's zone engine simply reconstructs from 90 days of
candles (e.g. on the first poll after a page load) as an ordinary live candidate. Corrected before
commit: `CANDIDATE_CREATED` now additionally requires the setup's real `qualificationTimestamp` to
fall strictly after a real, pre-existing, non-persisted timestamp (`alexGLastEvaluatedCloseTime`)
already captured by the app — never persisted, resetting to empty on every real reload — so a cold
start's backfill is never mistaken for a genuine live candidate. A historical setup's real trading
treatment (rule evaluation, duplicate checking, trade-open) is completely unchanged; only its
`CANDIDATE_CREATED` label is suppressed. Connects the Phase 2A Decision
Event bus to ALEX's real candidate lifecycle for the first time. Per the prior Phase 2B repository
analysis, ALEX's real gate (`alexGConstructLivePosition`) is protected but **pure**, feeding a
complete structured result to its non-protected caller (`alexGAttemptOpenLivePosition`) — while
JVM's equivalent detail is trapped inside a protected-calls-protected chain with no safe external
hook. This release implements ALEX's full lifecycle only; **JVM remains exactly
`SCAN_STARTED`/`SCAN_COMPLETED`/`ENGINE_ERROR`, byte-identical to v12.5.0** — JVM and ALEX are
deliberately not forced into artificial observability parity. New events, all from the two
existing, non-protected call sites (`alexGEvaluatePairForLiveSetups()`/
`alexGAttemptOpenLivePosition()`; every protected function they call — `alexGConstructLivePosition`,
`alexGRunSetupEngine`, `alexGCreateSetupRecord`, `alexGClassifyTouch`, and the whole zone engine —
remains completely unedited): `CANDIDATE_CREATED` (once per genuinely new setup, via a new bounded
dedup set separate from ALEX's own trading-state dedup), `RULE_EVALUATED` (activation-cutoff and
signal-staleness gates, PASS/FAIL), linked `CANDIDATE_REJECTED` events, `TRADE_OPEN_REQUESTED`,
`CANDIDATE_APPROVED`/`TRADE_OPEN_FAILED` (mapped honestly from the real construction result via a
new `ALEXG_CONSTRUCTION_REASON_CODE_MAP`), and `TRADE_OPENED`/`TRADE_OPEN_FAILED` after the ledger
commit. Eight new reason codes added to `REASON_CODE_REGISTRY`. Identity (`candidateId = setupId`,
`signalId`, `tradeId`) and `scanId`/`correlationId` (threaded from the existing Phase 2A `__scanId`
via two new, additive function parameters on non-protected functions) required no new plumbing —
the app already computed all of it. The pre-existing silent `catch` in
`alexGEvaluatePairForLiveSetups()` now additionally emits `ENGINE_ERROR`, with its
swallow-and-continue behavior completely unchanged. 61 fixtures in
`tests/v126_phase2c_wave1_tests.js` — unlike Phase 2A's boundary-only proof, this suite engineered
a genuinely qualifying setup and ran it through the real, unmodified zone/setup engine end-to-end
(network stubbed only at `fetch()`, in OANDA's own response shapes), then verified the full
lifecycle, all 10 real construction outcomes, a real ledger rollback, a real `ENGINE_ERROR`, the
first-poll/reload historical-exclusion correction, boundary determinism at exact/±1ms, deterministic
FIFO eviction of the bounded dedup set, and the session dedup set's role as a secondary guard.
Full regression 530/530; zero protected drift. Live-verified in a real Chrome tab (identical
result to the offline suite, including the corrected first-poll exclusion); Paper Trading Health
Check reported CLEAN for both engines. Real OANDA connectivity could not be exercised — OANDA's own
practice API was independently confirmed to be returning HTTP 503 (system maintenance) during this
release; anything requiring it is disclosed as blocked, not faked. See
[DECISION_EVENT_ARCHITECTURE.md](DECISION_EVENT_ARCHITECTURE.md) for the complete updated
schema/event/reason-code documentation and the deferred Wave 2+ scope.

## v12.5.0 — PROGRAM-001 Phase 2A: Decision Event Schema & Observability Foundation
Infrastructure-only release — no trading behavior change; the exact same market data produces
the exact same trades before and after this release, confirmed by zero protected-function/
protected-constant drift verified directly against the true committed v12.4.0 baseline. Builds
the universal Decision Event architecture every strategy (JVM/ALEX/TJR/future) will eventually
emit through: a versioned schema (`mogo.decision-event.v1`, `createDecisionEvent()`) supporting
all 13 required event types and every required field, with missing values always an explicit
`null` — never fabricated; a centralized, closed **reason-code registry**
(`REASON_CODE_REGISTRY`, 14 categories) that `reasonCode` is validated against directly (not a
loose prefix guess), keeping codes stable while `reasonText` stays independent free-form human
wording; an **evidence model** distinguishing an overall per-event completeness level
(`COMPLETE`/`PARTIAL`/`MINIMAL`/`UNKNOWN`) from a per-field provenance taxonomy
(`OBSERVED`/`DERIVED`/`UNAVAILABLE`/`UNSAFE_TO_RECONSTRUCT`/`FUTURE_WORK`) — JVM and ALEX are
deliberately never forced into artificial parity; and a lightweight, **memory-only, append-only
event bus** (`emitDecisionEvent()`/`getDecisionEvents()`/`clearDecisionEvents()`/
`validateDecisionEvent()`) that `Object.freeze()`s every event before storing it (true
immutability, not just convention), assigns `sequenceNumber` only to events that pass validation,
and writes **zero** `localStorage` keys — this entire log is gone on reload, by explicit Phase 2A
mandate. Only `SCAN_STARTED`/`SCAN_COMPLETED`/`ENGINE_ERROR` are actually emitted so far, from
the two genuine outer scan-tick boundaries — `scanAll()` (JVM) and `alexGLivePollTick()` (ALEX) —
both confirmed **not** protected functions; every original statement inside both is byte-identical
and unreordered, only wrapped in try/catch with emit calls at the boundaries. No protected rule
logic (`checkAutoTrades`, `evaluateLiveTrigger`, `scoreConfluence`, `bestConfluence`,
`computeAOI`, `detectSignals`, `getBias`, `getSession`, or any `alexG*` protected function) is
touched anywhere in this release. A new Developer-Mode-gated Diagnostics preview shows Schema
Version, Event Bus Status, Events in Memory, Last Event, Validation Failures, and Persistence
Status. 40 new fixtures in `tests/v125_decision_event_tests.js`; full regression 469/469; zero
protected drift. See [DECISION_EVENT_ARCHITECTURE.md](DECISION_EVENT_ARCHITECTURE.md) for the
complete schema/registry/evidence-model/identifier/immutability/memory-limit documentation,
known limitations, and the recommended Phase 2B scope.

---

## v12.4.0 — PROGRAM-001 Phase 1: Baseline Registry & Logic Protection
Infrastructure-only release — no trading behavior change; JVM and ALEX produce the exact same
decisions before and after this release, confirmed by zero protected-function/protected-constant
drift. Establishes a formal, identifiable baseline for JVM and ALEX so future logic drift is
detectable in-app, in Developer Mode, without running a script — a lightweight runtime
**companion** to the existing build-time `regression-baseline-tools.py` drift check, never a
replacement for it. `computeBaselineRegistry()` builds one entry per strategy (deterministic
`logicFingerprint`/`riskFingerprint`/`configurationFingerprint` via a new 32-bit FNV-1a hash over
each protected function's own `.toString()` source, sorted alphabetically so array-declaration
order can never itself affect the fingerprint) plus `instruments`/`timeframes`/`sessionRules`/
`riskModel`/`dataSource`/`executionModel` drawn from real, already-disclosed app state;
`dataContractVersion`/`metricsVersion` are explicitly `null` (no such versioning scheme exists yet
for either strategy) rather than fabricated. `BASELINE_JVM_FUNCTIONS`/`BASELINE_ALEX_FUNCTIONS`
are a byte-for-byte, programmatically-generated copy of `regression-baseline-tools.py`'s
`PROTECTED_FUNCTIONS` list — there is no shared source between that Python tool and this browser
code, so the two must be kept in manual sync going forward (a disclosed, accepted limitation, see
[KNOWN_ISSUES.md](KNOWN_ISSUES.md)). The registry is computed fresh every time (pure,
deterministic, never touches `localStorage` or any account/journal state); the only thing ever
**written** is an explicitly-locked reference snapshot, via a new isolated
`fxhub_baseline_registry` key, written only by `lockBaselineRegistry()` — never automatic,
mirroring the Python tool's own manual `--update` philosophy. A new Developer-Mode-gated
Diagnostics card shows both strategies' Baseline IDs, Fingerprint Status
(MATCH/DRIFT DETECTED/NO BASELINE LOCKED YET), Application Version, and Baseline Registry
Version, plus a confirmation-gated "Lock Current Baseline" action. 31 new fixtures in
`tests/v124_baseline_registry_tests.js`; full regression 429/429; zero protected drift verified
directly against the true committed v12.3.2 baseline.

---

## v12.3.2 — Paper Trading Integrity & Analytics Consistency
A corrective engineering milestone in two phases: a Paper Trading Operational Audit
(investigation/verification) followed, in the same version, by a reviewed corrective pass. No
new strategy intelligence; TJR Phase 2 not started; JVM/ALEX entry rules, stop/target logic, and
ALEX's fixed-R policy untouched. **Phase 1 (audit)** fixed two narrow defects: the unified
Journal tab didn't refresh on navigation (`showPanel()` had no dispatch branch for it); and
`openPaperPosition()` didn't itself reject a zero-risk trade (the guard existed only in the UI
wrapper). It also surfaced three findings requiring a decision — all three were approved and
implemented in **Phase 2**: (1) **ALEX version-guard** — a new `commitAlexGLedger()`/
`fxhub_alexg_account_version` pair (scoped to the account only, exactly mirroring why JVM's own
guard excludes its journal, to avoid reproducing JVM's own historical false-stale-rejection bug)
gives ALEX the same stale-write/rollback protection JVM already had. (2) **Canonical analytics**
— one `computeCanonicalPerformance()` (Win Rate = Wins/(Wins+Losses), break-even reported
separately and never in the denominator, null instead of a fabricated 0% at zero decisive trades)
now backs both Dashboard's tile and Strategy Center's `computeMogoStrategyPerformance()`, which
could previously disagree on identical data. (3) **Normalized close reason**
(TAKE_PROFIT/STOP_LOSS/MANUAL_CLOSE/BREAK_EVEN/SYSTEM_CLOSE) on new JVM closes, shown in Trade
Inspector; legacy records stay `null`, never backfilled. (4) A documented
`BREAK_EVEN_R_EPSILON=1e-9` replaces the exact `pnl===0` break-even check — a numerical-precision
floor only, not a trading tolerance. (5) The unified Journal's strategy filter now matches
`strategyId`, not the display label. (6) A new, strictly read-only Developer Mode **Paper
Trading Health Check** (Diagnostics page) reports JVM/ALEX counts/balances/versions and
duplicate/orphan/mismatch detection, with a Copy Health Report button proven never to include
OANDA/Anthropic credentials — run it in your own MOGO browser tab to check your own real data.
Protected-function drift vs. the v12.3.1 baseline: exactly three, all disclosed above
(`openPaperPosition`, `closePaperPosition`, `alexGCloseLivePosition`).

**A Final Ledger Atomicity Review, same version, corrected a real defect in item (1) above.**
The initial ALEX version-guard split the account (guarded) from the journal (written separately,
unguarded) the same way JVM's own architecture used to — but a successful account/version write
followed by a failed journal write left storage genuinely divergent after reload, exactly the
class of defect [INC-001](PAPER_TRADING_AUDIT.md) already proved this codebase is vulnerable to.
Both `savePaperAccountGuarded()` (JVM) and `saveAlexGAccountGuarded()` (ALEX) now persist their
account, version, and journal as one atomic, all-or-nothing unit: every write is prepared before
anything is written, and any single write failing rolls every already-written key in the unit
back to its exact prior value. Proven with real injected write failures on each key individually,
each followed by a real simulated reload confirming complete restoration — not just an in-memory
check. This added zero further protected-function drift (the corrected functions are not on the
protected list). 93 fixtures in `tests/v_paper_trading_audit_tests.js` (up from 32, then 73, then
93); full regression 376/376. See [PAPER_TRADING_AUDIT.md](PAPER_TRADING_AUDIT.md) for the
complete architecture map, the real persistence contract, and remaining limitations.

**A Final Pre-Commit Integrity Gate, same version, closed the last gap in the atomicity work
above: what happens when the compensating ROLLBACK write itself also fails.** `localStorage` has
no native transaction, so a third outcome exists beyond success/ordinary-rejection: a commit write
fails, and at least one of its own rollback writes also fails, leaving storage partially,
indeterminately written. `savePaperAccountGuarded()`/`saveAlexGAccountGuarded()` now detect this
directly and return a categorically distinct fatal result
(`{ok:false,integrityCompromised:true,reason,reasonCode:'ROLLBACK_FAILED',failedCommitStep,
failedRollbackKeys}`) — never conflated with an ordinary rejection. `commitPaperLedger()`/
`commitAlexGLedger()` now set a new, separate runtime warning (its own red banner on Paper Trading
and Alex G Live, distinct from the existing "reload and retry" banner) directing to Developer
Mode > Paper Trading Health Check — a plain in-memory assignment that never itself writes to
`localStorage`. `approveManualReviewTrade()`'s own reconciling second commit (used to persist an
in-memory undo after an *ordinary* rejection) is now explicitly skipped when the first commit
came back `integrityCompromised`, so a fatal result is never followed by an automatic second write
against possibly-corrupted storage — the one caller-side gap this review found. No automatic
retry, repair, reset, or migration is attempted anywhere in this path; Health Check remains
strictly read-only. MOGO's honest guarantee is **logical atomicity under normal `localStorage`
operation, with explicit detection of unrecoverable compensating-write failure** — not absolute
atomicity under storage-engine failure, which no `localStorage`-based design can promise. 22 new
`RollbackFailure.*` fixtures (115 total, up from 93) cover both engines' fatal-result detection,
in-memory snapshot preservation, the no-localStorage-write guarantee on the warning itself, Health
Check's continued read-only behavior, no-automatic-retry, credential-free diagnostic logging, and
confirmation that ordinary rollback-success behavior is unchanged; full regression 398/398, zero
skipped. Protected drift reconfirmed unchanged at the same three items, verified directly against
both the regenerated baseline and the original committed v12.3.1 baseline. See
[PAPER_TRADING_AUDIT.md §0.1](PAPER_TRADING_AUDIT.md#01-when-the-compensating-rollback-write-itself-fails-final-pre-commit-integrity-gate)
for the complete rollback-failure contract.

---

## v12.3.1 — Strategy Workspace Framework & Dedicated TJR Workspace
An architecture/navigation release — transforms MOGO from strategy overlays into a modular
multi-strategy Trading Operating System. **No new trading intelligence**: no Zone Interaction
Engine, Reaction Engine, BOS Confirmation, Candidate Generation, Risk Engine, Entry/Target Logic,
Paper Trading, Replay Logic, or Live Trading. JVM/ALEX logic, all protected functions/constants,
OANDA integration, paper-account logic, unified journal ownership, and the existing replay engine
are completely untouched. The v12.3.0 TJR Session & Zone Engine is unchanged and remains fully
functional; **v12.3.0's commit and tag are untouched**. TJR becomes a first-class strategy
alongside ALEX and JVM via a reusable Strategy Workspace pattern. **Registry**: four new,
additive Manifest fields (`navLabel`, `workspaceTitle`, `currentPhase`, and for TJR a real
`panelId:'tjrworkspace'`) added to all three manifests; JVM/ALEX keep their exact existing
`panelId`s and are otherwise untouched. **Navigation**: a new registry-driven "Strategies" nav
group generates one button per `STRATEGY_REGISTRY` entry (proven not hardcoded — injecting a 4th
synthetic strategy produces a 4th button automatically); "Paper Trading"/"ALEX" moved out of the
Trading dropdown into it. **Dedicated TJR workspace**: a new panel with an always-visible
Strategy Header (name/version/phase/detection/candidate/paper/live/profitability status/current
pair/timeframe/session/previous session) and seven tabs — Chart (a fully separate, isolated chart
instance with its own instrument/timeframe selectors and Show/Hide Zones toggle — never touches
the shared chart's state), Rules (Implemented vs. Approved-for-Implementation vs. Future, per
[ADR-007](adr/ADR-007-tjr-strategy-definition.md)'s per-component status), Diagnostics (full
session/zone/candle field list, never hiding incomplete data), Paper Trading (every control
disabled, exact required message), Replay and Journal (exact required placeholders, no logic
created), and Developer (raw session/zone objects, no credentials). The pure Phase 1 engine
(`buildTjrSessionZones` and its nine core functions) is reused completely unmodified. **Shared
chart cleanup**: the shared Scanner chart no longer auto-renders TJR zones/legend — the single
call site was removed while every Phase 1 function/state variable it used is retained, unmodified,
and still directly testable. **Strategy Center**: TJR's tab is now a thin overview card with an
"Open TJR Workspace" button, avoiding duplicating the workspace's own detailed diagnostics. 31 new
fixtures in `tests/v1231_strategy_workspace_framework_tests.js`. Full regression: 283/283
discovered fixtures pass, zero skipped/excluded, zero protected-function/constant drift. Live
browser verification: zero console errors, zero real trade data, zero new `localStorage` keys
throughout. **Known limitation, disclosed**: the architecture diagram's top-level placement of
Journal/Replay/Developer as standalone nav items was intentionally not implemented this release —
Phase 3's own literal scope only covered the Trading/Strategies split; the larger nav flattening
is treated as a longer-term target, not silently decided.

---

## v12.3.0 — TJR_SLR Phase 1: Session and Zone Engine
The first real strategy built on the [ADR-006](adr/ADR-006-multi-strategy-foundation.md)
Multi-Strategy Foundation — deliberately narrow scope: deterministic, timezone-aware
previous-session (Asian/London/New York) high/low zone construction only. No zone-interaction
engine, no break-of-structure/fair-value-gap/entry logic, no candidates, no paper trading, no
live execution — see [ADR-007](adr/ADR-007-tjr-strategy-definition.md), whose per-component
status records the Session/Zone Engine as **implemented in v12.3.0**; the Zone Interaction/
Reaction Engine and five-minute BOS confirmation as **approved for implementation** (via the
owner's authoritative architecture process, not yet built — no Phase 2 code exists in this
release); candidate analytics/grading as **specified, not yet built**; and paper/live execution
as **not approved**. `TJR_SLR` ("TJR Session Level Reaction")
registered as `STRATEGY_REGISTRY`'s third entry (`status:'development'`, scanning/paperTrading/
automation all `false`) using the existing Manifest/Services schema exactly, no parallel fields.
Session boundaries resolve via native `Intl.DateTimeFormat` (no timezone library added) against
real Europe/London GMT/BST offsets, computed independently per boundary — proven correct on the
UK's own spring-forward and autumn-back transition days, where a single session's start and end
fall on opposite sides of the DST change. Nine pure, fully synchronous core functions
(`resolveTjrSessionBoundaries`, `getTjrSessionForTimestamp`, `getPreviousCompletedTjrSession`,
`isTjrSessionComplete`, `getCandlesForResolvedSession`, `findTjrSessionExtremes`,
`buildTjrHighZone`, `buildTjrLowZone`, `buildTjrSessionZones`) aggregate completed M30 candles
with strict no-lookahead, reject (never silently repair) malformed/duplicate candles, select the
true session high/low with an isolated, swappable tie-break rule, and construct immutable
(`Object.freeze()`), deterministically-`zoneId`'d body-to-wick zones matching all four mandatory
spec formulas exactly. Zone status is ACTIVE/DATA_INCOMPLETE/INVALID_SOURCE only — assigned once
at build time from data quality alone; no interaction/expiration engine exists yet. Zones render
on the chart as a new, fully separate dashed-price-line overlay (own toggle, own legend), fetched
via a fire-and-forget async wrapper around the existing `fetchCandles()` so a slow/failing fetch
can never delay or break the primary chart. Strategy Center gained a registry-driven TJR tab
(session/zone diagnostics only — no win rate/PnL, since none exist), and Developer Mode gained a
matching diagnostics card. 48 new fixtures in `tests/v123_tjr_phase1_session_zone_tests.js`; one
pre-existing `v121` fixture updated (not weakened) for the now-3-strategy registry. **Pre-commit
release-readiness correction:** 4 fixtures in `tests/v1212_manual_review_and_replay_diagnostics_tests.js`
were found to be nondeterministic — real, unmodified, pre-existing production code
(`approveManualReviewTrade()`) gates on `getSession().active` using the actual wall clock, so
those fixtures failed only when the suite happened to run during the real 00:00–08:00 UTC
off-hours window (confirmed pre-existing and unrelated to TJR via `git stash` against unmodified
v12.2.0). Fixed in the **test harness only** — `tests/run_v1212_tests.js` now injects a
deterministic session override for the affected fixtures and restores it immediately after;
`getSession()` itself (protected, production) was never edited. Full regression is now genuinely
deterministic: **252/252 discovered fixtures pass, zero skipped/excluded, zero
protected-function/constant drift**, reproducible via one canonical command
(`tests/run_all.sh`) regardless of time of day. JVM and ALEX trading logic completely untouched.

---

## v12.2.0 — Multi-Strategy Foundation
A framework-generalization release under [ADR-006](adr/ADR-006-multi-strategy-foundation.md) —
not Phase 2/Strategy Expansion itself (no TJR/ICT/Silver Bullet trading logic added; zero drift
across all 63 protected functions and 4 protected constants). ADR-005 (v12.0.0/v12.1.0) built
`STRATEGY_REGISTRY`/Manifest/Services and proved the contract twice, but every consuming seam was
still hardcoded "JVM and ALEX by id," not "iterate whatever is registered" — explicitly disclosed
as deferred scope at the time. This release closes that gap. **Approved with one required
revision before implementation**: strategy-owned records must carry a stable `strategyId`
(registry id), never treating the display `strategyLabel` as permanent identity. Both journal
builders were found to already write an id-shaped `strategy` field — `strategyId` was added
alongside it on new records only, with existing persisted records never rewritten; a new 3-tier
resolver (`resolveStrategyEntryForRecord()`: `strategyId` → legacy `strategyLabel` via
`findStrategyEntryByLabel()`, explicitly documented as legacy-only → safe null) replaces every
"is this ALEX?" ternary. **Seven seams generalized** to iterate the registry instead of
hardcoding a third id: the unified journal build, Dashboard's P&L/win-rate tiles *and* its
running-trades table (a second, previously undocumented hardcoded badge color was found and
fixed in the same pass), the panel-open hook, Developer Mode card visibility, the mini-journal
inspector lookup, the journal strategy badge color, and Strategy Center's tabs (the static
two-DOM-id scheme replaced with tabs generated per registry entry, in array order). Two new,
additive Manifest fields (`badgeColor`, `capabilities.strategyCenterContent`) round out the
contract; an unresolved/unregistered record now renders a dedicated neutral color and a shared
generic inspector card — never silently defaulting to JVM's own styling. A fixture-only,
never-shipped synthetic third strategy proves genuine N-strategy support (not just N=2 with
nicer code) at all seven seams, both offline and in a real live-browser session, with zero
change to JVM's or ALEX's own output. Two pre-existing v12.1.0 fixtures were updated — not
weakened — since they asserted a per-id fallback behavior that cannot generalize to a third
strategy; two new fixtures cover the still-supported "whole registry empty" case, and one
fixture's stale comment was corrected. 30 new fixtures
(`tests/v122_multi_strategy_foundation_tests.js`); regression-relevant total 200/200 passing.
Four unrelated, pre-existing fixtures in a different suite (real-wall-clock session dependency,
tracked as a documented follow-up, not fixed this release) fail only during the documented
00:00–08:00 UTC off-hours window and were confirmed to fail identically on the unmodified prior
release. Zero protected-function/constant drift. Live browser verification confirmed a live-injected
synthetic third strategy rendering correctly across Dashboard, Strategy Center, Developer Mode,
and the unified journal, and a live-injected unresolvable record rendering its own neutral,
non-JVM badge color. See ADR-006 for the full design, the seam-by-seam table, and the new-strategy
onboarding checklist.

## v12.1.3 — Security Baseline
A platform-hardening release (not Phase 2/Strategy Expansion — no strategy logic touched; zero
drift across all 63 protected functions and 4 protected constants). Preceded by a mandatory
inspection report the user reviewed and approved before any code changed. **Findings**: the OANDA
token was already memory-only (never persisted) — the one real credential gap was `disconnect()`
clearing the API key input field but not the account ID field (fixed). **Escaping**:
`renderAlertLog()` and `inspectorRows()` previously rendered values into `innerHTML` without
`escapeHtml()` (no live free-text path was found feeding either, but the render functions
provided no defense-in-depth escaping); fixing `inspectorRows()` required pulling its two
HTML-badge rows out of the generic escaping path so real badge markup isn't double-escaped into
visible tag text. Writing the fixture suite for this fix caught a related, previously-undetected
gap live: six `fmtDash(r.pair)` sinks across the Trade Inspector header, Strategy Center hero
name, and mini-journal rows were also unescaped — all closed the same way. **Confirmations**:
`toggleAutoTrading()`/`toggleAlexGLiveTrading()` previously flipped automated trading with zero
confirmation; both now confirm first. `deleteEntry()`'s confirm text was strengthened. **Manual
Lock (new)**: a client-side privacy barrier — explicitly disclosed as *not* authentication — that
conceals the whole app behind a full-screen overlay and blocks credential changes, automation
toggles, destructive actions, and Manual Review approval while locked, via one reused guard at 14
call sites. Locking never pauses Scanner polling, chart updates, position monitoring, or
already-running automation; toast alerts (already non-sensitive) render above the overlay and
were confirmed live to keep appearing while locked. **Dependency cleanup**: removed a fully dead
external Google Fonts import (a leftover `.jvm-signature` class applied to zero elements). **CSP**:
an allow-list was built and verified in a scratch copy only (confirmed to actively block a
non-allow-listed host while permitting OANDA and Anthropic); per explicit instruction it is *not*
in production yet — `Content-Security-Policy-Report-Only` cannot be set via `<meta>` at all, and
GitHub Pages doesn't give this repo HTTP header control — documented as a pending limitation.
**Anthropic key**: confirmed clean of the leakage patterns checked, but its persisted,
direct-browser-credential design is now formally documented as temporary, with a Future AI
Security Boundary rule governing any expansion. A pre-push reconciliation review flagged that an
earlier verification summary line risked reading as "no key anywhere in storage" — inaccurate for
the Anthropic key, which is persisted by design. No committed doc or fixture actually made that
claim, but two fixtures were added to make both behaviors explicit and directly tested: the OANDA
token proven to never appear in any localStorage value, and the Anthropic key proven to be
persisted to `fxhub_ai_key` on Save and removed from both memory and storage on Clear. 50 new
fixtures total (`tests/v1213_security_baseline_tests.js`); full regression 172/172 passing, zero
drift. Live
browser verification confirmed the Lock/Unlock flow, the overlay's concealment, and a toast
alert rendering above it while locked, with zero real trade data touched throughout and zero
console errors after every change. See [SECURITY.md](SECURITY.md) for full detail.

## v12.1.2 — TRUE MTF Replay Diagnostics + Manual Review Eligible
A platform-tooling release (not Phase 2/Strategy Expansion — no new strategy added). Two
features built on top of the existing JVM engine, neither loosening automatic-trading rules,
bypassing any existing protection, or allowing live-money execution. The pre-implementation audit
found the shared root cause behind both: `evaluateLiveTrigger()` (live auto-trading) and
`simulateTrueMTFReplay()` (Replay) both check the Monday–Wednesday weekday rule *first* and
short-circuit immediately on failure — a Thursday/Friday setup is never even scored for
confluence/AOI/confirmation/R:R today. **Part 1 — Replay Diagnostics**: a new shared,
non-short-circuiting evaluator (`evaluateSetupFullBreakdownCore()`) built entirely from calls to
existing protected primitives adds a permanent "Replay Diagnostics" section — coverage, a
labeled candidate funnel (hard gate / soft factor / informational / preference), rejection
totals (exactly one primary reason per candidate), a Rejected Candidates table with full
per-candidate detail, a Near Misses section, evaluator-parity display, five distinct empty-state
messages, and read-only CSV/JSON export. **Part 2 — Manual Review Eligible**: every setup now
classifies as INELIGIBLE / DEVELOPING / MANUAL REVIEW ELIGIBLE / AUTO ENTRY ELIGIBLE; a setup
qualifies for manual review only when every other gate passes and weekday is the sole failure —
high confluence alone can never substitute for a missing AOI/confirmation/R:R/session pass.
Gates with no enforced code today (news, spread, exposure, daily-loss) are explicitly disclosed
as not-yet-enforced rather than silently treated as passing. An amber banner and a Review Trade
modal (required acknowledgment checkbox, no one-click execution) gate approval, which commits
through the existing, unmodified `openPaperPosition()`/`commitPaperLedger()` path with full
rollback on failure and rich attribution stored on the journal record. Four separate performance
groups (Standard / Outside-Window / Thursday / Friday) keep manual-review trades visibly
separate from standard results. **Part 3 — documentation**: Strategy Center's momentum-loss
language was made explicitly symmetric for bullish/bearish setups (the underlying code was
already symmetric), plus a new Research Diagnostics panel disclosing which loss-of-momentum
conditions are executable today and what each remaining one would require. 53 new fixtures
(`tests/v1212_manual_review_and_replay_diagnostics_tests.js`) caught two real bugs before
shipping: a Friday-cutoff check that used wall-clock time instead of the setup's own decision
timestamp, and a test-state leak between fixtures — both fixed. Live browser verification covered
all 19 required scenarios and caught one more real bug: the Manual Review banner was initially
wired to the wrong panel (`panel-scan`, "Sunday Scan," instead of `panel-scanner`, the real
Scanner) — found and corrected. Zero protected-function drift; the one intentional, disclosed
constant change is `RULES`'s own display text (Part 3). See
[INCIDENTS.md](INCIDENTS.md) and the full `APP_VERSION_LOG` entry in `index.html` for complete
detail.

## v12.1.1 — Diagnostics data integrity
A focused data-integrity patch to the Diagnostics subsystem only — no new features, no Strategy
SDK/Registry work, no UI redesign. Fixed a silent journal-only-orphan leak in the "Paper trading
engine" self-test: it restored `pairData`/`paperAccount`/`activePair`/`fetchBidAsk`/the R:R
Calculator's fields, but never `journalEntries` — so a successful, green self-test run could
silently persist the simulation's own leftover journal record into the real `fxhub_journal` as an
untagged orphan, discovered during v12.1.0's live verification and disclosed but not fixed then.
Added a small, Diagnostics-only, unexported helper pair, `diagSnapshot()`/`diagRestore()`
(generalizing the existing save/restore pattern already used by `alexGIsolationCheck()` and
`openPaperPosition()`'s own snapshot fields — not a new architecture), and applied it to all three
self-tests that mutate real state, including `journalEntries`. A second, subtler defect was caught
by the new fixtures (not by code review) before shipping: `paperAccount` is isolated by reassigning
it to a fresh synthetic object before the simulation runs, so the real object is never touched —
but `journalEntries` was left pointing at the real, live array, and `openPaperPosition()` mutates
that array **in place** (`.unshift()`) rather than reassigning it, so merely restoring the
reference afterward was a no-op. Fixed by isolating `journalEntries` the same way `paperAccount`
already is. 13 new fixtures ship in `tests/v1211_diagnostics_integrity_tests.js`; zero drift across
all 63 protected functions and 4 protected constants; live verification confirmed `fxhub_journal`,
`fxhub_paper`'s content, and both ALEX storage keys are byte-identical before and after running the
real "Run Diagnostics" button (the one key that legitimately changes, `fxhub_paper_version`, is the
pre-existing v11.0.1 monotonic save counter, unrelated to this fix). See
[INCIDENTS.md](INCIDENTS.md) and the full `APP_VERSION_LOG` entry in `index.html` for complete
detail.

## v12.1.0 — Strategy Framework, Release 2: JVM registration
Registered JVM as the framework's second strategy, following the exact Manifest/Services
pattern ALEX used in v12.0.0. This was treated as the real validation of the SDK contract
(not a mechanical copy): a deliberate pre-implementation audit checked every Manifest field
and Service method JVM needs against the existing Release-1 contract, field by field. Verdict —
zero SDK extensions required. `computePerformance()`, reserved in the original design but never
exercised (ALEX has no live-performance function), is JVM's first real use of that slot, since
JVM has `computeMogoStrategyPerformance()`. `JVM_MANIFEST` reads `version`/`fullName`/`status`
directly from the existing `MOGO_STRATEGY_META` constant rather than restating them, and
`academySchoolId:'mogo'` is a real, verified link (`ACADEMY_SCHOOLS` already has that id).
4 of 8 previously-hardcoded seams needed a JVM-specific change (`getUnifiedJournalRecords`,
`renderDashboard`, `showPanel`, `applyDeveloperModeVisibility`); 3 more were reviewed and
deliberately left untouched with the reason disclosed — most notably, `renderMiniJournal()`'s
JVM branch is confirmed dead code, and Strategy Center's 2-strategy hardcoding is the optional
Release 3 scope named in [ADR-005](adr/ADR-005-strategy-framework.md), not required for this
release. Zero behavior drift: all 63 protected functions and 4 protected constants remain
byte-identical, all 28 pre-existing ALEX fixtures still pass, no `localStorage` key changed.
28 new fixtures ship in `tests/v121_jvm_registration_tests.js`, auto-discovered by
`tests/run_all.sh` with no runner changes needed.

## v12.0.0 — Strategy Framework Foundation, Release 1: ALEX registration
The first step of a multi-strategy architecture migration, approved via a two-pass architecture
design exercise before any code was written (see [ADR-005](adr/ADR-005-strategy-framework.md)).
Introduced a minimal Strategy Registry/Manifest/Services boundary and registered ALEX as its
first entry — without rewriting a single line of ALEX's existing engine. The Manifest is static,
lightweight, computed-performance-free metadata (identity, capabilities, dependencies, declared
DNA, routing ids); Services exposes thin references to ALEX's existing account/journal state and
functions (`getAccount`, `getJournal`, `normalize`, `onOpen`, `isolationCheck`, plus a reserved
`health` accessor) — only what this release's target seams actually need. Six of eight listed
seam functions were edited (`getUnifiedJournalRecords`, `renderDashboard`, `showPanel`,
`applyDeveloperModeVisibility`, `runDiagnostics`, `renderMiniJournal`), each a one-line-scoped
change with a safe fallback to the pre-v12.0.0 hardcoded behavior; the other two
(`toggleDeveloperMode`, `getFilteredJournalRecords`) needed no change, disclosed with why. JVM is
**not** registered this release — every JVM-specific code path is untouched. Zero behavior
change: all 63 protected functions and 4 protected constants remain byte-identical to v11.4.0, no
localStorage key was added/removed/renamed, and existing saved data loads with zero migration.
28 new fixtures plus the complete pre-existing suite pass. Live verification confirmed Dashboard,
Journal, the ALEX panel, Strategy Center, Developer Tools, and Diagnostics all render identically
to v11.4.0. A pre-existing, unrelated Diagnostics self-test failure ("Paper trading engine (sizing
+ auto-close)") was discovered during verification and deliberately not fixed — see
[KNOWN_ISSUES.md](KNOWN_ISSUES.md).

## v11.4.0 — MOGO Academy lesson engine foundation
Built a reusable Academy lesson engine and one complete gold-standard lesson rather than many
shallow ones. Renamed the five existing Tracks to Schools (ids kept byte-identical for backward
compatibility) and added a sixth, Market Intelligence, bringing the module count from 49 to 55.
Added a new rich lesson schema (`ACADEMY_LESSON_LIBRARY`) alongside the untouched legacy
`ACADEMY_LESSONS` store, with a pure 3-tier lookup (`academyGetLesson()`) so lessons without
written content still render an honest "coming in a future release" stub. Built a full premium
lesson template — hero, objectives, sectioned content with callouts, key takeaways, common
mistakes, professional tips, an interactive classification exercise, a scored knowledge-check
quiz with retry and a persisted best score, homework, personal notes, and gated Mark Complete —
and wrote Forex Foundations Module 1, "How the Forex Market Works," to the full spec. Extended
Academy progress (quiz scores, homework, notes, recently opened) additively, with existing
`mogo_academy_progress` data migrating forward automatically. Added Academy-wide search and a
richer Academy Home. Zero Scanner/signal/paper-trading/journal/JVM/ALEX/chart code touched,
confirmed by zero drift in the regression baseline. See [INCIDENTS.md](INCIDENTS.md) if a future
Academy-related defect needs tracing back to this restructure.

## v11.3.0 — Pre-Trade Checklist badge text + future-state prep
UI-only change to the Strategy Center's Section H Pre-Trade Checklist. Replaced the "NOT
CONNECTED" badge text with "OFF MARKET • NO SCAN" (text only — the existing gray color/size/
spacing is unchanged) and updated the informational lede to explain that the checklist will
populate automatically from the live Scanner during market hours. Added a `SC_CHECKLIST_BADGE_STATES`
config and `renderScChecklistBadge()` helper so a future release can swap which of five states
(off market/waiting/scanning/complete/attention — gray/blue/gold/green/red) a row displays
without touching markup — no state logic was implemented, every row still hardcodes the
off-market state today. The separate, already-interactive Sunday Scan checklist is untouched.

## v11.2.0 — Timeframe-aware chart display history
A follow-on to v11.1.0: most Scanner charts only showed roughly one to two trading days of
history because `loadChart()` always requested a fixed 200 candles regardless of timeframe — on
M15 that's only ~50 market hours. Added a single pure helper, `getChartCandleCount(timeframe)`,
returning a sensible display count per timeframe (M15/H1: 500, H4: 400, D: 365, W: 260, M: 180),
used *only* inside `loadChart()`'s own chart fetch. Every other candle fetch in the app —
`evaluateLiveTrigger()`'s entry-timing window, `scanPair()`'s confluence/signal fetch,
`getStructuralAOI()`, `runAutoTopDownScan()`, and Replay/Backtest's paginated fetch — keeps its
own independent, unchanged count; none of them feed the visible chart's history. Falls back to
the previous fixed count if the larger request fails, and shows a loading state while the
primary fetch is in flight. A direct usability improvement rather than a defect — see
[INCIDENTS.md](INCIDENTS.md#inc-002) for the related saved-view bug (v11.1.0) this follows.

## v11.1.0 — Chart saved-view self-heal
A user-reported chart bug (a small cluster of real candles crammed against one edge with a large
blank area everywhere else) was traced to `saveChartView()` persisting raw logical-index
positions with no record of how many candles existed when the view was saved — a later reload
with a substantially different candle count (e.g. an off-hours/weekend gap) applied a now-stale
range unconditionally. Fixed with a new `isSavedChartViewValid()` check: a saved view is only
restored if it still overlaps real, current data closely enough; otherwise it's discarded and the
chart self-heals via the same `fitContent()` path already used when no saved view exists, with no
user action required. Chart-viewport subsystem only — zero trading functions touched, confirmed
by zero drift in the regression baseline. See [INCIDENTS.md](INCIDENTS.md#inc-002).

## v11.0.1 — Paper ledger transaction correction
An independent code review found a more precise defect than v11.0's own fix addressed: `save()`
could persist a journal record even when the linked paper-account write was rejected (a split
transaction), and the paper-account version guard was being triggered by totally unrelated
saves. Fixed by making paper-account persistence its own dedicated, atomic commit path,
completely separate from general app state saving. See [INCIDENTS.md](INCIDENTS.md) for the full
incident writeup.

## v11.0 — Paper Ledger Integrity: stale-save race root-cause fix
Root-caused and fixed a real defect where completed paper trades could show as "Journal only" in
the unified journal while the Paper Trading page showed a fully-reset account. Added a version
guard on the paper-account store, a Paper Ledger Integrity diagnostic, and a
confirmation-gated reconciliation tool. (Superseded in part by v11.0.1 above — see
[INCIDENTS.md](INCIDENTS.md).)

## v10.0 — Trade Intelligence Foundation
Added a dedicated, nav-reachable Trade Inspector page (summary, real compliance checks computed
from stored data, decision timeline, performance metrics, chart replay, manual notes, and a
placeholder AI Review section) on top of the existing inline Trade Inspector component from v5.0,
which remains unchanged.

## v9.0 — Paper trading data-integrity audit + durable regression baseline
Investigated and explained why Paper Trading and the Strategy Journal could disagree (they are
two independent stores; account reset never touched the journal by design). Added a read-only
classification layer for every journal record, replaced the single ambiguous "Reset Account"
confirmation with a 3-option modal, and created the durable, committed regression-baseline tool
(`regression-baseline-tools.py` / `regression-baseline.json`).

## v8.0 — Scanner layout fix, Strategy Center, nav audit, Training Academy
Fixed a real chart/panel layout clipping bug. Rebuilt the plain Rules page into a full Strategy
Center (hero, entry model, disqualifiers, risk framework, real performance stats). Audited every
navigation item and replaced silent misrouting with honest "Coming Soon" pages. Added the MOGO
Training Academy (5 tracks, 49 named modules, 3 fully written with quizzes).

## v7.0 — Rebrand + grouped navigation + Dashboard
Rebranded the app's display name from "JVM Forex Hub"/"Forex Trading Hub" to MOGO (cosmetic
strings only — the `JVM` strategy identifier in stored data and code was deliberately left
unchanged). Replaced the flat top-nav with grouped dropdown navigation. Added a Dashboard landing
page built from data the app already computes elsewhere.

## v6.1 — Manual chart drawing tools
Built the interactive drawing toolbar on top of the v6.0 data-model foundation: horizontal
lines, rectangles, trendlines, and text notes, with hit-testing, selection, undo/redo, a Drawing
Inspector, and per-pair/timeframe persistence — fully isolated from trading state.

## v6.0 — Chart usability and visual trade overlay
Fixed a flat-line/tiny-candle chart bug (an autoscale conflict between AOI reference lines and
candlesticks). Added Fit Visible/Fit All/Reset View, saved per-pair/timeframe chart views, a
full trade overlay (entry/stop/target lines, markers, risk/reward shading) driven only by stored
trade data, and the underlying (non-interactive yet) drawing data model.

## v5.0 — Unified trade experience
Unified the JVM and ALEX journals into one normalized, filterable record set with a shared inline
Trade Inspector, standardized page layout, and reorganized navigation.

## v4.3 — Developer Test Mode
Added a hidden-by-default "Developer Test Tools" section (revealed by a session-only Developer
Mode toggle) that generates synthetic BUY/SELL/WIN/LOSS trades through the same real, frozen
open/close functions a live trade uses, tagged and filterable as TEST trades.

## v4.2 – v4.2.2 — ALEX live paper trading
Connected the validated ALEX zone/setup/trade-construction pipeline to live OANDA data so it can
detect real setups and open/close simulated ALEX paper trades automatically. v4.2.1 corrected a
real exit-monitoring gap (comparing a position's stop/target against a single bid/ask instead of
walking the full historical candle range since the last check). v4.2.2 was a UI/reliability
reporting release for the exit-detection metadata v4.2.1 introduced.

## v4.0 – v4.0.1 — ALEX trade construction, replay & role correction
v4.0 converted qualified ALEX setups into complete hypothetical trades and walked them through
historical candles to a result, adding a historical replay engine and stats. v4.0.1 was a narrow
correction release fixing a zone-role initialization defect the v4.0 report itself had disclosed.

## v3.4 – v3.6.1 — ALEX G S&R foundation
Introduced the ALEX strategy from scratch as a fully independent module: the frozen rule
specification (v3.4), an independent zone-detection engine (v3.5), deterministic setup
qualification (v3.6), and a narrow correction release (v3.6.1) fixing two setup-metadata defects
found in a follow-up audit — none of which changed ALEX's actual trading methodology.

## v3.0 – v3.3 — TRUE MTF Replay
Added a dedicated multi-timeframe replay/research engine for validating the JVM strategy against
real historical data, plus three correction releases (v3.1–v3.3) fixing confluence-scoring,
statistics-display, and lookahead-timing defects the replay engine itself surfaced.

## v1.0 – v2.9 — Core JVM strategy and early hardening
The original build: paper trading, auto paper trading, the AI Assistant, Diagnostics, automatic
top-down scanning, and bias-filtered chart markers (v1.0), followed by a long series of
targeted fixes and additions — notification/UX polish, AOI zone-detection rebuilds and rendering
fixes, a Backtest tab with funnel/optimizer views, additional chart timeframes, a security pass
(v2.6 — fixed a real stored-XSS vulnerability in AI chat/journal/scan notes), bid/ask-aware paper
trading fills (v2.7), and a historical-data pagination fix (v2.9).
