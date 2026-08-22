# Incidents

A log of real production defects found in MOGO: what happened, who/what it affected, the actual
root cause, and how it was resolved and verified. This is distinct from
[KNOWN_ISSUES.md](KNOWN_ISSUES.md), which documents intentional, currently-accepted limitations —
everything in this file was a genuine bug that has since been fixed.

**Rule for future releases:** add an entry here for any defect that reached a point where it
could produce incorrect data or behavior for a real user, even if caught before a formal
"release" boundary. Include the actual root cause, not just the symptom and the patch.

---

## INC-006 — 35 pairs unevaluated: an upstream provider outage that MOGO could not name

**Status:** Root cause established 2026-08-21 (MOGO-023). External provider outage, ongoing at time
of writing. **No data was corrupted, no trade was fabricated, no evidence was lost.** MOGO's
fail-closed contract worked exactly as designed. The defect this incident exposes is not the
suppression — it is that MOGO **could not tell the operator why**.

### Symptom (operator-observed)

The MOGO interface reported:

> ⚠ 35 pairs not evaluated — incomplete candle history

Approximately 35 FX pairs each requested 220 candles and received 0, while other chart/market
information still appeared on screen.

### What the banner could and could not say

`renderMarketDataCompletenessDiagnostics()` renders one row per suppressed pair:

```
<pair> — UNAVAILABLE · requested 220 · received 0 · — · HTTP —
```

The `reason` and `HTTP` columns rendered as `—` for every pair. They were empty **not because the
information did not exist**, but because `fetchCandles()` had already discarded it:

```js
if(!r.ok) return null;          // r.status thrown away
const d=await r.json();
if(!d.candles) return null;     // condition thrown away
...
}catch{return null;}            // the error itself thrown away
```

Three materially different failures — a non-OK HTTP status, a response with no `candles` field, and
a thrown network/CORS error — all collapsed into one bare `null`. `scanPair()` then recorded
`receivedCount: 0, httpStatus: null`, which is what the operator saw.

The banner's own explanatory prose then actively pointed away from the truth:

> **This is not a claim that market data is missing** — session, weekend, holiday and liquidity gaps
> are all legitimate reasons a request may not be fully satisfied.

That text is correct for `PARTIAL`. For this incident — state `UNAVAILABLE`, zero candles, every
pair, total provider failure — it reads as reassurance. **A total upstream outage was rendered in the
vocabulary of a quiet market.** Distinguishing those two is the single thing this platform must never
get wrong.

### Root cause — DATA PROVIDER (measured)

`api-fxpractice.oanda.com` was returning **HTTP 520** (Cloudflare: origin returned an invalid
response) on **every endpoint**, not merely the candles endpoint:

| Endpoint (unauthenticated probe) | Practice host | Live host |
|---|---|---|
| `/v3/instruments/EUR_USD/candles?count=220&granularity=H1&price=M` | **520** | 401 |
| `/v3/instruments/GBP_USD/candles?count=220&granularity=H1&price=M` | **520** | — |
| `/v3/instruments/EUR_USD/candles?count=5&granularity=D&price=M` | **520** | — |
| `/v3/accounts` | **520** | — |
| `/v3/accounts/<id>/pricing?instruments=EUR_USD` | **520** | — |

Reproduced **9/9 consecutive probes** across a 7-minute window (2026-08-21 23:45:16Z → 23:52:19Z).
`server: cloudflare`, `content-length: 16`, body `error code: 520`.

The live host `api-fxtrade.oanda.com` answered **401** to the identical unauthenticated request —
the correct response for a healthy host — proving this is **not** local DNS, network, TLS or
machine configuration. DNS resolved normally (104.18.34.254 / 172.64.153.2).

**Eliminated by evidence:**

- **AUTH/SESSION** — a dead token yields 401, which the live host demonstrably returns. 520 is an
  origin failure raised independently of credentials.
- **SYMBOL MAPPING** — `ALL_PAIRS` holds OANDA-native underscore identifiers (`EUR_USD`); the URL
  built by `fetchCandles()` is well-formed.
- **TIMEFRAME** — 520 reproduced across `H1` and `D` granularities alike.
- **REQUEST CONSTRUCTION** — reproduced at `count=220` and `count=5`.
- **NETWORK / ENVIRONMENT** — live host and unrelated hosts reachable from the same shell.
- **MOGO CODE** — no code path can turn a healthy 200 into a 520.

**Classification: DATA PROVIDER.** Not a MOGO defect. External, upstream, and outside MOGO's control.

This is **not unprecedented**: `tests/v126_phase2c_wave1_tests.js:601` already records a prior
verification step "BLOCKED BY EXTERNAL OANDA HTTP 503 MAINTENANCE". Practice-environment outages are
a recurring operating condition, not a one-off — which is precisely why MOGO must be able to name one.

**UNVERIFIED:** that the operator's instance is configured to the practice environment
(`cfg.env !== 'live'`). It is strongly inferred — the practice host is failing, the live host is
healthy, the symptom is present, and PAPER-only operation implies practice. It cannot be confirmed
from the repository because `cfg` lives in browser storage. The repair below makes the live UI state
self-evidencing, so this stops being an inference.

**UNVERIFIED:** the outage start time. MOGO records it — `scanAll()`'s `finally` block writes
`instrumentsSkipped[].reason = 'MARKET_DATA_UNAVAILABLE'` into the forward-observation ledger on
every tick — but that ledger lives in the origin's `localStorage`, which is inside Chrome's *shared*
Local Storage store holding 136 unrelated origins. Reading it would cross the privacy boundary
declined as option (B) in MOGO-022, so it was **not** read. The IndexedDB checkpoints are
snappy-compressed and carry evidence packages, not this ledger.

### Blast radius (derived from the production call graph)

| Surface | Effect | Integrity |
|---|---|---|
| Historical candle acquisition | **Halted** — `fetchCandles()` returns `null` for all 35 pairs | intact |
| UI scanner | All 35 pairs suppressed; banner shown | intact |
| Strategy evaluation | **Suppressed by contract** — `detectSignals(null)` / `bestConfluence(null)` | intact |
| Decision generation | No signals ⇒ no alerts (`conf.total` never reaches `ALERT_THRESHOLD`) | intact |
| PAPER entry | `checkAutoTrades()` opens nothing | **no fabricated trades** |
| PAPER position management | `checkPaperPositions()` returns early per position on `if(!live)return;` | **no NaN, no corruption** |
| Evidence capture / provenance | Untouched; no packages minted | intact |
| Forward-observation ledger | Still written each tick, recording the skip and its reason | **outage IS recorded** |
| Research / corpus | Untouched | intact |

**Forward PAPER is halted, not damaged.** No trade, position, balance, package or observation was
created, altered or lost. The 259-observation corpus is unchanged and still validates.

**One real scientific caveat.** `checkPaperPositions()` evaluates stops and targets only from a live
price. Through an outage that guard returns early, so a stop or target that would have been hit
*during* the outage is instead detected at the first price after it. Realized R for any position open
across an outage window is therefore measured against a later price than the simulation implies. This
is correct fail-closed behaviour — inventing a fill price would be worse — but it is a genuine
limitation on forward-statistic fidelity and is now recorded as such.

### The MOGO defect this exposed — and the repair

The provider outage is not MOGO's fault. **Being unable to name it is.**

This is the eighth recurring defect category from B-32 — *absence is not silence* — reaching a
surface B-32 never covered. B-32 repaired it three times in the evidence layer (package resolution,
witness value, derived field). The market-data acquisition path was never audited for it, and it had
the same hole: a check that could not evaluate did not report why.

**Repair (v12.40.0):** capture the transport reason where it is known and carry it out of band.

- New `fetchCandlesDiagnosed()` returns `{candles, diagnostics}`, where `diagnostics.transportOutcome`
  is one of `OK` / `HTTP_ERROR` / `NO_CANDLES_FIELD` / `NETWORK_ERROR`, alongside the real
  `httpStatus`.
- **`fetchCandles()`'s return contract is unchanged** — still the array on success, still bare `null`
  on every failure — so all 21 existing call sites and their `null` guards behave byte-for-byte as
  before. Fixture `BEHAVIOUR-1` (a 429 must yield `null`, not a partial array) pins this and still
  passes.
- `scanPair()` records the transport facts into `pairData` even when `candles` is `null`.
- The suppression banner renders them, and separates a provider failure from a legitimate gap
  instead of narrating both as "incomplete candle history".

**`completenessState` remains the sole evaluation contract (ADR-011).** `transportOutcome` and
`httpStatus` are diagnostics and display only. No consumer branches on them to make an evaluation
decision — a consumer branching on `httpStatus===429` would re-create the original ADR-011 defect,
because the case that actually reached scoring was `httpStatus===200`.

**Deliberately NOT done:** no relaxation of the 220-candle lookback, no fabricated or interpolated
candles, no stale-data reuse, no retry storm against a failing origin, and no automatic failover to
the live host — failing over a PAPER platform onto a live-money endpoint is a governance boundary,
not a repair.

### Correct operator reading

A suppressed pair is **not** a no-trade signal. During INC-006 MOGO is not saying "no setups exist";
it is saying "I cannot see the market." Silence from the scanner in this window carries no
information about market opportunity, and no forward statistic should treat this period as observed.

---

## INC-005 — A hand-seeded record counted as a real ALEX paper trade

**Status:** Root cause established 2026-08-03. Detection shipped in v12.15.0 (Trade Integrity &
Quarantine). **The operator's live account was never affected.** The stored balance on the affected
origin has NOT yet been corrected — that is a separate, explicit act.

### Symptom

An ALEX paper trade appeared with EUR_USD H1 BREAK & RETEST, BUY, entry 1.10000, stop 1.09500,
target 1.11000, exit 1.11000, Win +2.00R / +$200, opened and closed at the same timestamp
(2026-08-02T01:37:56.564Z), duration 0m, **MAE 0.0 and MFE 0.0**, exit detected "Live snapshot",
trade source AUTO.

### Why it was impossible

`alexGUpdatePositionExcursionAndCheckExit` updates the excursion **before** it evaluates the exit,
from the same bid/ask. For a BUY, `hitTarget` requires `bid >= target`, which forces
`mfePips >= 100`. **A Win at target with MFE 0.0 cannot be produced by any MOGO code path.**

### Root cause — hand-seeded record

Read-only forensics on a copy of the Chrome storage recovered the record:

| Field | Value | Verdict |
|---|---|---|
| `tradeId` | `AGT\|MANUAL-B\|1785634676564` | placeholder token |
| `signalId` | `SIG\|MANUAL-B\|1` | placeholder token |
| `setupId` | `AGS\|EUR_USD\|H1\|zB\|B_breakRetest\|rB` | `zB` / `rB` are stand-ins |

The engine mints ids of the form `AGT|AGS|alex_g_sr_v1|<pair>|<tf>|AGZ|AGC|…`, visible on genuine
records in the same store. **`MANUAL-B` appears nowhere in the repository** — no code path, fixture,
script or test can produce it. The record also carried `tradeSource: AUTO` and
`isDeveloperTrade: false`, which is why every statistic counted it.

### Scope

Confined to origin `http://localhost:8899`, whose ALEX account read `balance 10200` holding only
this record. The operator's live origin `http://localhost:8744` read
`{"balance":10000,"openPositions":[],"closedPositions":[]}` — **pristine**. RUN-001 and the 24
Evidence Packages were unaffected (re-verified 24/24, byte-identical). No Evidence Package was ever
created from this trade.

### Control added (v12.15.0)

A **rule-based** Trade Integrity layer, not an identifier blocklist: a Win must record a favourable
excursion above zero, a Loss an adverse excursion above zero, a trade must close strictly after it
opened, the result must agree with the direction of the exit price, and (per strategy profile) the
trade id must match what that strategy's engine mints. Four of the five rules are strategy-agnostic,
so every future strategy inherits them. Quarantine is computed on read — **nothing is deleted or
rewritten** — statistics exclude quarantined records, and the trade tables still list them with a
`QUARANTINED` badge naming the violated rules. A rule that throws never quarantines, and a record
lacking the fields a rule needs is treated as clean.

### Lesson

`tradeSource` and `isDeveloperTrade` are **self-declared flags**. Anything that can write storage can
set them. Trust the arithmetic a record cannot fake, not the label it carries.

---

## INC-004 — Real ALEX and JVM paper-trading data destroyed by developer browser testing

**Status:** Resolved for the operator (data restored from a Time Machine backup). Controls added in
v12.8.1. **Cause was the verification process, not MOGO's code.**

### Symptom

After MOGO-003 Phase 1 implementation and browser verification on 2026-07-31, the operator opened
MOGO at `http://localhost:8744/index.html` and found **all ALEX and JVM paper-trading data absent**.
Chrome Profile 2 was restored from the pre-implementation Time Machine backup, MOGO was served again
at the same origin, and **the records reappeared** — proving both that the data had been intact in
the backup and that `http://localhost:8744` was the live MOGO origin.

### Proven root cause

**Developer browser verification executed `localStorage.clear()` three times against
`http://localhost:8744` inside the operator's active Chrome Profile 2.**

The calls were ad-hoc inline scripts issued through browser automation
(`javascript_exec` on a reused tab), not committed code. One of the three — the first statement of
the export-verification script — **took no pre-clear inventory**, so there is no record of what it
removed. Chrome Profile 2 was confirmed as the profile used: it contains
`IndexedDB/http_localhost_8744.indexeddb.leveldb`, created by that session.

**The originating mistake was an unverified assumption.** The operator's origin was inferred from
`.claude/launch.json` (port **8743**), port **8744** was chosen as "a different origin, therefore
isolated", and that assumption was never checked. 8744 was the operator's real working origin. Every
subsequent safety claim rested on that one unchecked inference.

**Aggravating factors:**

- No disposable Chrome profile was used. A pre-existing tab, window, and the operator's live profile
  were all reused.
- Synthetic trades were driven through the real `alexGCloseLivePosition()` → `commitAlexGLedger()`,
  writing real ledger keys — the most dangerous option in the Browser Testing Policy's own preferred
  order, used without authorization for that instance and without developer-test tagging.
- An initial forensic audit wrongly exonerated the process, concluding from raw LevelDB byte counts
  that the data lived under a `file://` origin. That method was invalid — LevelDB SSTable blocks are
  Snappy-compressed, so a raw byte scan cannot see into them, and it separated none of live records,
  tombstones, or superseded versions. **Absence in that scan was not evidence of anything.** The
  conclusion was withdrawn in full.

### What MOGO's code did *not* do

Phase 1 was audited by source inspection and cleared: the evidence-platform layer contains zero
destructive storage operations, adds no reference to any load path, and its only startup hook
performs no `localStorage` write. All destructive reset functions are reachable only from explicit
UI buttons. **No repository file performs a storage-clearing call.**

### Resolution (v12.8.1)

1. **`scripts/browser_test_profile.sh`** — every browser test must launch a **disposable**
   `--user-data-dir` created fresh under a temporary directory. It **fails closed**: it refuses an
   inferred origin, a profile root inside the operator's Chrome directory, a reused profile
   directory, or a profile that is not verifiably empty, and it records the test profile path, the
   exact origin, the not-the-operator-profile confirmation, and a pre-clear inventory.
2. **Browser Testing Policy rewritten** ([TESTING.md](TESTING.md)) — mandatory profile isolation and
   an absolute prohibition on `localStorage`/`sessionStorage` clearing and IndexedDB deletion.
3. **Repository guards** — `tests/v129_browser_isolation_guard_tests.js` fails the build if any
   committed source performs a destructive storage call, targets the operator's Chrome profile
   directory, or if the launcher loses its fail-closed behaviour.
4. **INC-001 hardened in the same release** (below), so that a comparable event degrades into
   "refuse to write" rather than "overwrite with defaults".

### Honest limitation

**These controls cannot prevent an agent from repeating this by hand.** The destructive calls were
inline scripts at the tool layer; no repository fixture can intercept them. The guards prevent a
committed regression. The remaining control is procedural — and, if a hard stop is wanted, removing
the browser automation tools from the session's permitted-tool configuration. Disclosed in
[KNOWN_ISSUES.md](KNOWN_ISSUES.md).

---

## INC-001 — Completed paper trades appearing as "JOURNAL ONLY" after a reset

**Status:** Resolved (v11.0 partial fix, v11.0.1 root-cause correction). **Residual load-path
overwrite gap closed in v12.8.1 — see "v12.8.1 load-integrity correction" at the end of this entry.**

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

### v12.8.1 load-integrity correction — the residual overwrite gap

The v11.0.1 work fixed the *commit* path. It did not fix the *load* path, and a real gap survived
until v12.8.1.

**The gap.** `loadSaved()`, `loadAlexGSaved()` and `loadAlexV2Saved()` each wrapped **every key in
one `try/catch`**. A single `JSON.parse` throw on the first key silently abandoned **every remaining
key**, leaving those variables at their in-memory defaults — empty account, empty journal, empty
arrays. The next ordinary `save()` then wrote those defaults straight over real, intact stored data.
The stored bytes were readable the whole time; MOGO simply stopped reading them and then overwrote
them. A related hole: an account key present with **no** version key left `0 > 0` false, so the
staleness guard passed and a default account could overwrite a real one.

**The fix, in two halves — either alone is insufficient:**

1. **Per-key isolation.** `loadStoredKey()` loads each key independently, so one unreadable key can
   never suppress the others.
2. **Refusal to overwrite.** Keys that were **present but unreadable** are recorded in
   `storageLoadFailures` and become **unwritable for the rest of the session**. `persistStorageKey()`
   enforces this for the unguarded savers, and both `savePaperAccountGuarded()` and
   `saveAlexGAccountGuarded()` refuse the commit outright with
   `reason:'LOAD_INTEGRITY_BLOCKED'`. A failed read now degrades into *"don't touch it"*, never into
   *"replace it with a default"* — which also closes the missing-version hole.

An absent key is **not** treated as a failure: the in-memory default is genuinely correct there, and
a fresh install writes normally.

Every load failure is reported loudly through both engine-error channels
(`STORAGE LOAD FAILURE: … MOGO will NOT overwrite this key …`), so the operator learns their data is
being *preserved* rather than silently frozen.

**Verification:** 14 new fixtures (`L1`–`L14`) in `tests/v129_browser_isolation_guard_tests.js`,
driving the **real** loaders and savers through a controllable storage stub — including `L4`, which
reproduces the exact original overwrite and asserts the stored bytes survive it.

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
