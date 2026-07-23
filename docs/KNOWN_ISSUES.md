# Known Issues & Limitations

This is a list of **documented, intentional** current limitations — scope boundaries and tooling
constraints that are already understood and disclosed, not bugs waiting to be quietly patched
around. If you're about to "fix" one of these, check [ROADMAP.md](ROADMAP.md) first: it may
already be a planned, scoped future release rather than an oversight.

For actual production defects that were found and fixed, see [INCIDENTS.md](INCIDENTS.md)
instead — this file is for things that are working exactly as currently designed.

**Rule for future releases:** update this file whenever a release closes one of these gaps, or
opens a new one that should be disclosed here rather than silently shipped.

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

The JXA-based offline fixture harness (`osascript -l JavaScript`) cannot complete a function that
contains a genuine `await` on an asynchronously-settling promise. This is a permanent constraint
of the tooling, not something to "fix" — the established, correct workaround is live browser
verification for anything that needs it. See [TESTING.md](TESTING.md) for the full explanation
and pattern.

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
