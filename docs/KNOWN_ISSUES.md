# Known Issues & Limitations

This is a list of **documented, intentional** current limitations — scope boundaries and tooling
constraints that are already understood and disclosed, not bugs waiting to be quietly patched
around. If you're about to "fix" one of these, check [ROADMAP.md](ROADMAP.md) first: it may
already be a planned, scoped future release rather than an oversight.

For actual production defects that were found and fixed, see [INCIDENTS.md](INCIDENTS.md)
instead — this file is for things that are working exactly as currently designed.

**Rule for future releases:** update this file whenever a release closes one of these gaps, or
opens a new one that should be disclosed here rather than silently shipped.

## ~~Incomplete candle history is treated as complete~~ — RESOLVED in v12.8.3

**Status:** ✅ **Resolved** by the Market Data Completeness Contract
([ADR-011](adr/ADR-011-market-data-completeness-contract.md)). Retained here as the record of a
verified defect and the reasoning that produced the contract.

`tests/v130_candle_completeness_regression_tests.js` now passes 10/10. `SAFETY-1` … `SAFETY-4`
were written **first** and failed against the pre-fix build; they are the regression guard and
**must not be weakened, inverted, skipped or deleted**.

**One accepted trade-off shipped with the fix:** an instrument whose *genuine* history is shorter
than the requested lookback is classified `PARTIAL` and will not be scanned. MOGO cannot
distinguish a truncated response from an instrument that simply has less history, and the
conservative reading was chosen deliberately. The remedy for a legitimately short-history
instrument is a per-request lookback it can satisfy — **not** a relaxation of the contract.

*The defect as originally found is recorded below.*

**Initial audit hypothesized** that `fetchCandles()` silently paginated and returned truncated
data after HTTP 429. **Test-first investigation disproved that** for `fetchCandles()`: it issues a
single request and returns `null` on any non-OK status, and `null` is rejected by every downstream
guard.

**The mechanism does exist in `fetchCandlesRange()`**, which paginates and `break`s on a
later-page HTTP 429, returning the partial accumulation with no error signal. Its consumers are
the replay/backtest paths, so it does not reach `scanPair()` — but it is directly relevant to
replay trustworthiness.

**The risk on the live scanner path is different in kind.** A *successful* response containing
materially fewer candles than requested is treated as complete, because production validates only
a minimum usable length (`candles.length < 10`), never the requested lookback. `scanPair()`
requests 220 and will score confluence and emit signals from 80.

**Future completeness protections should therefore key on requested-versus-observed history, not
HTTP error handling alone** — while recording only directly observable facts. Requested-minus-received
is *not* a count of missing market candles; legitimate session, weekend, holiday and liquidity gaps
make that subtraction unsound. The observable facts are `requestedCount`, `receivedCount`,
`pagesRequested`, `pagesReceived`, `paginationTerminationReason`, `httpStatus`, `fetchDurationMs`
and `retryCount`.

**Measured behaviour** (real functions, network scripted only at the `fetch()` boundary):

| Path | Requested | Result |
|---|---|---|
| `fetchCandles()` + HTTP 429 | 220 | `null` — 1 request, no accumulation ✅ safe |
| `fetchCandles()` + HTTP 200 carrying 80 complete candles | 220 | 80-length array, no completeness metadata |
| `fetchCandlesRange()`, page 2 HTTP 429 | 220 | 80-length array after 2 pages, HTTP 429 invisible |
| `scanPair()` with an 80-candle response | 220 | `signals=1`, `conf.total=20`, `pairData` records only `[candles, price, signals, conf]` |

~~`v130` is deliberately **excluded** from `FIXTURE_COUNTS` in `regression-baseline-tools.py` until
production satisfies the contract, so its red state is not recorded as an accepted baseline.~~

**Superseded 2026-08-04.** Production now satisfies the contract, `v130` passes **14/14**, and it is
carried in `FIXTURE_COUNTS` as a normal suite. The exclusion was correct while the suite was red and
is obsolete now that it is green.

---

## A 4-millisecond forward observation carries an exactly-2R win (MOGO-023)

**Status:** Measured 2026-08-21, **not repaired**. Diagnosis only — preserved evidence must not be
bulk-rewritten. Severity **P2** (forward-statistic validity).

`TOBS|MOGO|20260806|025` records `openedAt 2026-08-06T13:11:15.571Z` and
`closedAt 2026-08-06T13:11:15.575Z` — a **4-millisecond holding period** — with `outcome Win` and
`rMultiple` exactly `2`. The next-shortest hold in the FORWARD population is 945 seconds, roughly
**236,000× longer**.

That combination is the signature described in **INC-005**: a hand-seeded record with a
zero-duration hold and a clean +2.00R win. INC-005's record was confined to a non-production origin
and never entered the corpus. **This one is in the corpus, is anchored in the identity manifest, and
is classified FORWARD** — the population forward performance is computed from.

Measured impact on the 29-observation FORWARD population:

| | with the record | excluding it |
|---|---|---|
| n | 29 | 28 |
| Σ R | **−5.180** | −7.180 |
| mean R | **−0.1786** | −0.2564 |
| win rate | **27.6 %** | 25.0 % |

A single record of doubtful provenance is **flattering forward performance by 2.0R** — 39 % of the
population's total loss, and 44 % of its mean.

It is also one of the two observations carrying `strategyId: current_strategy` rather than
`alex_g_sr_v1`. `current_strategy` is a **placeholder literal** appearing at 8 sites in `index.html`
(`emitDecisionEvent` calls in `scanAll()` among them); it reached a persisted `sourcePackageId`
(`PKG|current_strategy|20260806|1`) and from there the observation. A placeholder string is acting
as a strategy identity — a contract weakness, not a naming nit.

**Honest on every other axis:** both records declare `timeframe` in `unknowns`, so the importer
invented nothing. The missing-timeframe item and the `current_strategy` item are the **same two
records**, not four separate defects.

**Do not** rewrite, delete or reclassify these records to tidy the counts. The open question is
provenance: what minted a 4 ms trade. Until answered, every forward figure carries this caveat
alongside B-22.

---

## Stop/target detection is suspended while market data is unavailable (INC-006)

**Status:** Disclosed 2026-08-21. Correct fail-closed behaviour; recorded as a fidelity limit.
Severity **P3**.

`checkPaperPositions()` evaluates stops and targets only from a live price, and returns early per
position when there is none (`if(!live)return;`). Through a provider outage that guard holds — which
is right, since inventing a fill price would be far worse.

The consequence is that a stop or target which *would* have been hit **during** an outage is instead
detected at the first price **after** it. Realized R for any position open across an outage window is
therefore measured against a later price than the simulation implies, in an unpredictable direction.

No position, balance or record is corrupted. But an outage window is **not** an observed window, and
forward statistics spanning one should say so.

---

## `regression-baseline.json` is stale — four suites behind `FIXTURE_COUNTS`

**Status:** Disclosed, deliberately not fixed. Found during the MOGO-004 isolation audit, 2026-08-04.

`regression-baseline-tools.py`'s `FIXTURE_COUNTS` dict is the source of truth and is current.
**The committed `regression-baseline.json` snapshot is not**, and has not been regenerated since
v12.5.0:

| | `FIXTURE_COUNTS` (current) | `regression-baseline.json` (committed) |
|---|---|---|
| Suite entries | **34** | 30 |
| Total fixtures | **984** | 759 |
| `appVersion` | — | **absent** |

**Four whole suites are missing from the committed snapshot:** `v127` (ALEX v1.1 release), `v128`
(Evidence Platform), **`v129` (INC-001/INC-004 isolation guards)** and `v130` (ADR-011 candle
completeness). The isolation guard suite being invisible to the committed baseline is the most
notable of these, and is why it is recorded here rather than left to a commit message.

**What is and is not affected.** The **protected-function/constant drift gate is unaffected and
fully current** — it hashes the 63 functions and 4 constants out of `index.html` on every run and
reports zero drift. `tests/run_all.sh` counts fixtures live and reports the real number (944 as of
this entry; the 984 dict total includes the 22 historical scratch-only suites that a fresh clone
cannot run). **Only the committed fixture-count snapshot is stale.**

**Why it has not been fixed here.** Regenerating it means running
`regression-baseline-tools.py --update`, which redefines the committed baseline wholesale — sweeping
in thirteen releases of accumulated change under whatever task happened to notice. This file's own
rule and [TESTING.md](TESTING.md) §3 both say the same thing: *never run `--update` reflexively just
to make the tool pass.* **Rebaselining is a deliberate, separately-reviewed act**, not a side effect
of an audit. Any release that does it must first confirm every suite's count and disclose the
version jump.

---

## Browser-isolation guards cannot intercept ad-hoc tool-layer scripts (INC-004)

**Status:** Accepted limitation, disclosed rather than implied away.

`tests/v129_browser_isolation_guard_tests.js` and
[`scripts/browser_test_profile.sh`](../scripts/browser_test_profile.sh) enforce the mandatory
browser-profile isolation introduced after
[INC-004](INCIDENTS.md#inc-004--real-alex-and-jvm-paper-trading-data-destroyed-by-developer-browser-testing).
They are effective against a **committed** regression: no source file in this repository can
perform a destructive browser-storage call, reference the operator's Chrome profile directory, or
weaken the launcher's fail-closed behaviour without failing the suite.

**What they cannot do:** INC-004 was not caused by anything in this repository. It was caused by
**ad-hoc inline JavaScript issued at the tool layer** — `localStorage.clear()` typed directly into a
live browser tab through automation. No repository fixture can observe or veto that. `run_all.sh`
runs offline JXA suites; it has no visibility into a browser session at all.

**What actually controls this risk:**

1. The Browser Testing Policy's Rule 0 in [TESTING.md](TESTING.md) — procedural, and binding on
   whoever is performing verification.
2. Always launching through `scripts/browser_test_profile.sh`, so the only profile ever exposed is
   disposable and empty.
3. **The only hard technical stop:** removing the browser automation tools from the session's
   permitted-tool configuration (`.claude/settings.json`). That file is operator configuration and
   is deliberately **not** modified by the repository or by any automated change.

This is recorded here because a guard that appears to prevent something it cannot prevent is worse
than no guard — it converts a known risk into an assumed-safe one.

---

## Browser evidence export fails silently — no file, no error (EXP-001)

**Status:** Open defect, disclosed. A supported workaround exists; the underlying failure is unfixed.

During the MOGO-004 Step 1 pilot, an evidence export from a disposable test profile produced **no
file and no error**. The run had in fact succeeded: fifty packages were captured to IndexedDB and
every one of them later hash-verified. But nothing reached disk, nothing surfaced to the operator,
and the run was believed to have produced no artifacts at all for roughly a day.

**The evidence for what happened, rather than a theory about it:** Chrome's `downloads` table for
that profile contained **zero rows**, and the profile's `Preferences` carried no download keys.
The export did not fail partway and it was not interrupted — **no download was ever registered
with the browser**. The precise mechanism is not established, and it is recorded that way rather
than guessed at.

**What is NOT the defect.** The v12.8.0 design is correct and behaved correctly: a package is
marked exported only after the write resolves *and* re-verification passes, so nothing was ever
falsely marked as exported, and the unexported count stayed honest. The gap is narrower and
nastier — **silence was indistinguishable from success.** There was no failure surface at all.

**Workaround, and the current supported path:**
[`scripts/mogo_evidence_receiver.js`](../scripts/mogo_evidence_receiver.js) — see *Evidence egress*
in [TESTING.md](TESTING.md). It writes POSTed bytes verbatim, so it cannot alter evidence, and
`--selftest` proves that byte-for-byte before a run depends on it.

**Consequence while this is open:** the download path must not be relied on for any campaign run.
Combined with `alexGReplayRejected` being memory-only and surviving exactly one replay
(`index.html:4119`), an unnoticed export failure between runs destroys the earlier run's rejection
record permanently — which is exactly what happened to the pilot's first run.

---

## Diagnostics: "Paper trading engine (sizing + auto-close)" self-test failing

Discovered during v12.0.0 (Strategy Framework Foundation, Release 1) live verification, this is
a genuine defect, not an intentional limitation — flagged here rather than silently left
undocumented because it was out of scope for that release to fix. The check (in `runDiagnostics()`,
`index.html`) simulates a JVM paper trade end-to-end against a synthetic account and currently
fails with `Cannot read properties of undefined (reading 'id')`, meaning `placePaperTrade(true)`
did not open a position in the isolated synthetic `paperAccount` the test constructs. Confirmed
**not** caused by the v12.0.0 Strategy Framework work: all 63 `PROTECTED_FUNCTIONS` (including
`openPaperPosition`, `closePaperPosition`, `placePaperTrade`'s dependencies) are byte-identical
to the v11.4.0 baseline, and `paperAccount` was never touched by that release's code changes. The
check's own `finally` block still restores and re-commits the real `paperAccount` regardless of
the simulation's outcome, so this failure does not put real paper-trading data at risk — confirmed
live by a byte-identical `fxhub_paper` before/after. Root cause not yet investigated (a follow-up
investigation task has been queued). See [RELEASE_NOTES.md](RELEASE_NOTES.md#v1200) for context.

## Manual Review Eligible: several gates are disclosed, not enforced

As of v12.1.2, the MANUAL REVIEW ELIGIBLE workflow's eligibility checklist includes 17 items, but
only the ones already enforced somewhere in this codebase are actually gated:
higher-timeframe alignment, structural AOI, confluence, directional confirmation, minimum R:R,
approved session, duplicate-position exclusion, and the weekday preference itself (the one gate
this workflow deliberately overrides). Five items have **no enforced code path anywhere in the
app today** — not in `checkAutoTrades()`, not here: news blackout protection, spread protection,
correlated/pair-exposure limits, a daily-loss or account-risk circuit breaker, and the Friday
cutoff as a hard block (a cutoff *warning* is shown and does gate approval, but there is no
general-purpose hard-block mechanism reused from elsewhere, since none exists). Rather than
silently treating these as passing, `classifySetupEligibility()` populates a
`gatesNotYetEnforced` list that the Review Trade modal displays explicitly. This scope was a
deliberate decision, confirmed with the user before implementation (see the release's scope
assessment) — building real enforcement for these was assessed as materially larger and riskier
scope than this release. See [RELEASE_NOTES.md](RELEASE_NOTES.md) for v12.1.2 context.

## Navigation items with no dedicated page yet

Six top-nav items open a shared, honest "Coming Soon" panel (`comingSoonOpen()`) rather than a
built page. Each states in-app what's planned and where the closest working functionality lives
today:

| Nav item | Closest working functionality today |
|---|---|
| Charts | The full charting experience (including drawing tools) already lives on the Scanner page. |
| Analytics | Trade-level filtering and stats are available on the Journal page. |
| Reports | The same underlying data is fully browsable on the Journal page. |
| Market Outlook | The closest available view is Sunday Scan. |
| Preferences | Available toggles live on the Diagnostics page. |
| Developer | Developer Mode and the Developer Test Tools it reveals already exist on the Diagnostics page. |

(Trade Inspector was on this list through v9.0 and graduated to a real, dedicated page in v10.0
— it is not in this table anymore.)

## MOGO Academy content coverage

As of v11.4.0's School restructure (the original 5 Tracks were renamed to Schools, and a 6th,
Market Intelligence, was added), the Academy has **55** named modules across 6 Schools. **1**
module — Forex Foundations, "How the Forex Market Works" — has the full v11.4.0 premium lesson
treatment (structured content, worked examples, an interactive exercise, a scored knowledge
check with retry/best-score, homework, and personal notes). **2** more (also in Forex
Foundations: *Understanding Currency Pairs*, *Pips, Lots, Spread, and Leverage*) still have their
original v8.0-era legacy content and simple quiz. The remaining **52** are real, titled,
School-assigned, and time-estimated, but honestly display "content coming in a future release"
rather than placeholder/filler text — this is intentional per v11.4.0's own stated goal ("build
the system and one excellent lesson first," not many shallow ones).

One Academy feature remains explicitly not built yet:
- Interactive Trading Drills (spotting AOIs, grading confluence, sizing risk on real historical
  charts) is a named, scoped, not-yet-built feature — opens its own "Coming Soon" panel.

(The Academy Home "study streak" placeholder mentioned in earlier releases was removed in
v11.4.0's Academy Home rewrite — it was never wired to anything and the user's v11.4.0 spec
explicitly called for professional progress indicators over gamification.)

## Strategy Center — ALEX tab

The Strategy Center's Strategy/ALEX tab selector shows a full, built-out Strategy tab for JVM;
the ALEX tab currently shows an honest "Coming Soon" panel rather than an ALEX-specific
methodology writeup.

## Strategy Performance requires a minimum real sample

`computeMogoStrategyPerformance()` (Strategy Center) intentionally shows an "insufficient clean
sample" message rather than a computed win rate/expectancy until there are at least 50 real
(non-test) closed JVM trades. This is a deliberate anti-fabrication design choice, not a bug —
see [ADR-004](adr/ADR-004-read-only-analytics-principle.md).

## Trade Inspector — AI Review

The Trade Inspector's "AI Review" section is a static, clearly-labeled "Coming Soon" card. No AI
call happens on that page. AI-assisted trade grading/coaching was explicitly deferred when the
Trade Inspector foundation shipped (v10.0) and remains unbuilt.

## Offline test harness cannot resolve real async calls

The JXA-based offline fixture harness (`osascript -l JavaScript`) cannot complete a function whose
promise settles on **genuinely pending external I/O**. See [TESTING.md](TESTING.md) for the full
explanation and pattern.

**SCOPE CORRECTED (MOGO-021).** This was previously written as an unqualified permanent constraint,
and was used to defer JVM close-math coverage to a live browser. It does **not** apply when `fetch`
is stubbed to return an already-resolved promise — which every offline suite here already does. In
that case the microtask chain drains and `await` completes. Demonstrated:
`run_v1233_jvm_autotrade_reliability_tests.js` awaits a real `closePaperPosition()` and observes
post-`await` state, proven by mutations after the `await` being killed. **Do not cite this section to
defer coverage without first checking whether the I/O in question is stubbed.**

## Two visual/design passes are scoped but not started

- **v7.3**: a visual/spacing redesign pass on Journal, Paper Trading, and the AI Assistant pages.
- **v7.4**: a design-system pass and full responsive audit.

Neither has been started as of v11.0.1. See [ROADMAP.md](ROADMAP.md).

## No Content Security Policy in production (v12.1.3)

A CSP was built and verified in a scratch/dev copy during the v12.1.3 Security Baseline release
(see [SECURITY.md](SECURITY.md#content-security-policy--built-tested-not-yet-in-production)) but
was deliberately **not** added to production `index.html` — it requires explicit approval and
a live-browser verification pass against the real file first (Charts, Scanner, Replay, exports,
Anthropic connectivity), per the release's own stop-and-approve discipline. Not a silent gap: the
policy, its allow-list rationale, and its `'unsafe-inline'` limitation are fully documented and
ready to ship in a follow-up once approved.

## Anthropic AI key uses a temporary, provider-discouraged direct-browser design

As of v12.1.3's security inspection, the AI Assistant's Anthropic API key is a real, persisted
(client-side, explicit-user-action) provider credential sent directly from the browser using
Anthropic's own `anthropic-dangerous-direct-browser-access` opt-in header — a pattern the provider's
own naming signals is discouraged outside personal/local use, and one MOGO's own error handling
already anticipates being CORS-fragile depending on hosting context. This is disclosed, not a
silent defect: no leakage was found (the key never reaches `innerHTML`, logs, diagnostics, or
exports), but a formal Future AI Security Boundary rule now governs any expansion — see
[SECURITY.md](SECURITY.md#anthropic-api-key--temporary-design-disclosed). The existing AI
Assistant chat feature is frozen as-is; new AI features require a real backend/serverless
endpoint first.

## No real order execution

MOGO never places a real order against any brokerage account — every trade it opens or closes is
a simulated paper position. This is a permanent design boundary, not a gap to be filled — see
[ADR-004](adr/ADR-004-read-only-analytics-principle.md).

## Baseline Registry's JS-side protected-function lists are manually synced, not shared-source

As of v12.4.0 (PROGRAM-001 Phase 1), `BASELINE_JVM_FUNCTIONS`/`BASELINE_ALEX_FUNCTIONS` in
`index.html` are a copy of `regression-baseline-tools.py`'s `PROTECTED_FUNCTIONS` list, generated
programmatically from that file at the time this feature was built (not hand-transcribed), so they
started in exact agreement. There is no shared source between that Python build-time tool and this
browser-side JS, so if a future release adds a name to `PROTECTED_FUNCTIONS`, these two JS arrays
must be updated by hand to match, or the in-app Baseline Registry Diagnostics card will silently
under-cover the real protected set (it will still correctly fingerprint everything it knows about,
it just won't know about the new addition until synced). This is an accepted limitation for this
release, not a defect: the in-app registry is explicitly a lightweight **companion** diagnostic for
Developer Mode, never a replacement for `regression-baseline-tools.py`, which remains the sole
authoritative, build-time drift gate `tests/run_all.sh` actually fails on. Do not expand this into
a shared-source refactor (e.g., generating the JS arrays from the Python file at build time) without
a deliberate, scoped follow-up release — this repository has no build step today, and introducing
one is a significant architectural change of its own.
