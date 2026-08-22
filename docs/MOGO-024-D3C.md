# MOGO-024 / D3C — the universal trade-geometry invariant

**Success condition.** No production paper position can enter ACTIVE state anywhere in MOGO
without satisfying the canonical strategy-neutral trade-geometry contract.

**Status: MET for every production insertion path, with one disclosed coverage limit (§7).**

D3 closed JVM creation. D3B closed JVM rehydration. Both required an owner-authorized protected
change. **D3C required none: every gate is in non-protected code, and the drift check reports
63/63 protected functions and 4/4 protected constants byte-identical.**

---

## 1. The definitive active-position insertion inventory

Built before any code was modified, by enumerating every expression that can place an element into
any `openPositions` array anywhere in `index.html` — `push`, `unshift`, splice-insert, indexed
assignment and whole-container assignment — then classifying each.

| # | Site | Engine | Route | Before D3C | After |
|---|---|---|---|---|---|
| 1 | `openPaperPosition` (`push`) | JVM | creation | guarded (D3) | guarded |
| 2 | `loadStoredKey('fxhub_paper')` | JVM | rehydration | guarded (D3B) | guarded |
| 3 | `alexGAttemptOpenLivePosition` (`push`) | ALEX | creation | **unguarded** | **gated (E2)** |
| 4 | `generateTestAlexTrade` (`push`) | ALEX | developer | unguarded | **covered by E3** |
| 5 | `loadStoredKey('fxhub_alexg_account')` | ALEX | rehydration | **unguarded** | **gated (E3+E4)** |
| 6 | `alexV2OpenPaperResearchTrade` (`push`) | ALEX V2 | latent | **unguarded** | **gated (E5)** |

Everything else that touches these arrays is a **removal** (`splice`, `filter`), a **read-only
derivation** (`concat`), a **reset to empty**, or a **rollback to a snapshot taken before the
push** — none can introduce an unvalidated position. Verified individually.

## 2. Were ALEX / ALEX V2 really the only remaining unguarded production paths?

**ALEX: yes, and not for the reason the D3 report assumed.** D3 recorded ALEX as "a separate engine
with its own protected construction function", out of scope. On inspection that function,
`alexGConstructLivePosition`, **already enforces the signed stop check D3 had to add to JVM**:

```js
if(!isFinite(stop)||(direction==='buy'&&!(stop<liveFillPrice))||(direction==='sell'&&!(stop>liveFillPrice)))
```

So ALEX was never exposed to the wrong-side stop. What it has **no notion of is a minimum risk
distance** — `riskDistance` need only make `positionSize` finite and positive. That is D3 defect (3),
unbounded size, reachable by a different route.

**This is not theoretical.** Fixture D3C.37/.38 drive the **real, protected, unmodified**
constructor with a zone edge a fraction of a pip under the live fill and a genuinely small ATR:

> `status = TRADE OPENED`, `riskPips = 0.65`, `positionSize = 15.38 lots = 1,538,462 units`
> on a $10,000 account — ~153× leverage, where a ~6.5 pip adverse move takes the account.

**ALEX V2: it is not a production path at all.** `alexV2OpenPaperResearchTrade` has exactly one
reference in the repository — its own definition. No caller, no UI binding, no registry entry, and
there is no ALEX V2 monitoring or close function anywhere, so a position created there could never
be serviced. It is nonetheless the **worst** geometry handling left (risk via `Math.abs()`, no
floor, target side never checked), so the gate was added rather than leaving the invariant as
"universal except the function nobody calls yet".

## 3. Semantic and historical compatibility — measured, not assumed

`scripts/trader_intelligence/geometry_corpus_compatibility.py` (new, reusable) replays every
preserved observation through a faithful port of the contract. Populations kept distinguishable
per CLAUDE.md — replay measures the *implementation* `alex_g_sr_v1`, never the trader.

| strategyId | population | n | VALID | tightest real risk |
|---|---|---|---|---|
| `alex_g_sr_v1` | forward | 36 | **36/36** | 7.262 pips |
| `alex_g_sr_v1` | replay | 221 | **221/221** | 5.027 pips |
| `current_strategy` | forward | 2 | **2/2** | 10.467 pips |

Zero wrong-side, zero non-finite, zero sub-floor across all 259. `MIN_RISK_PIPS = 1.0` sits **five
to seven times** below anything ALEX has ever traded, so it cannot act as a strategy filter — which
is the whole difference between a safety floor and a strategy parameter. **The gate rejects nothing
ALEX has ever done.** The diagnostic has a positive control: raising the floor to 6.0 makes it
report a rejection, so a clean run is evidence rather than silence.

## 4. The correction (all non-protected)

- **E1** `RISK_GEOMETRY_CONTRACT_VIOLATION` registered in `REASON_CODE_REGISTRY` *before* first use.
  An unregistered code is silently dropped by `validateDecisionEvent` — the v12.7.1 defect.
- **E2** Canonical gate in `alexGAttemptOpenLivePosition`, on the object the protected constructor
  already returned (the same seam MOGO-002.5's provenance stamp uses). Mirrors the existing
  construction-failure branch exactly — same event, pipeline stage, setup-status row and
  duplicate-prevention mark — because an inconsistent duplicate-prevention path is itself a defect.
- **E3** Servicing gate in `alexGCheckLivePositions`. **This is the universal half**: nothing in ALEX
  becomes ACTIVE without passing it, whatever route it arrived by, so a future writer cannot reopen
  the hole by forgetting a check.
- **E4** `alexGAuditRehydratedPositions()` + shared `auditOpenPositionsGeometry()` core, wired into
  `loadAlexGSaved()`. ALEX was added by **parameterising** D3B's loop, not forking it.
- **E5** Canonical gate in `alexV2OpenPaperResearchTrade`.

### The one design decision worth recording

The servicing gate asks a **geometry-specific** question (`openPositionGeometryQuarantined`), not
the general "is this quarantined at all" question D3B uses on the JVM side.

Reusing the general predicate looked like the consistent choice and is the wrong one. ALEX has a
`TRADE_INTEGRITY` profile; JVM's `current_strategy` does not. So for ALEX the general question
*additionally* asks whether the trade id looks engine-minted — a **provenance** question. Suppressing
exit monitoring on those grounds would leave a legitimate open position sitting unmonitored: a real
operational freeze, materially worse than the defect being fixed, and not what D3C is authorized to
establish.

On the JVM side the two questions are already equivalent for an open position — every other rule
short-circuits on a missing `result`/`closedAt`. **Asking the geometry question directly makes the
two engines behave identically; reusing the general predicate would have made them diverge.** The
provenance rule keeps its existing effect unchanged (excluded from statistics, badged on surfaces).

Fixtures D3C.30–D3C.34 pin this both ways, and mutation M5 (revert to the general predicate) is killed.

## 5. Adversarial bypass review

- **TDZ at load.** `MIN_RISK_PIPS` is declared ~4,000 lines *after* `TRADE_INTEGRITY_RULES`. If the
  loaders ran at top level the rule would throw, and `evaluateTradeIntegrity` swallows throws and
  **never quarantines** — the audit would silently report everything valid. Checked: `loadAlexGSaved`
  has exactly one call site, inside a `setTimeout` after the async connect flow, long after every
  top-level `const` initialises. **Not exposed.**
- **`{fake:true}` account swap** in `alexGIsolationCheck` — synchronous swap and restore with no
  `await` between, so the async monitor cannot interleave. **Not a bypass.**
- **Unjudgeable records.** The rule returns `null` (never guesses) when it cannot derive a pip size,
  i.e. when `pair` is falsy. Such a position also has no price to look up (`pairData[pair]` /
  `fetchBidAsk`), so it cannot be acted on either. **Cannot become active.**
- **Rule throws never quarantine** — by design. `validateTradeGeometry` is pure arithmetic behind
  `typeof` guards and has no throwing path.
- **Rollback paths** restore snapshots taken *before* the push, so they remove rather than introduce.

## 6. Mutation analysis — 11 mutations, 10 killed

| Mutation | Verdict |
|---|---|
| M1 delete ALEX servicing guard | killed (4 fixtures) |
| M2 delete ALEX creation gate | **SURVIVED — see §7** |
| M3 delete ALEX V2 gate | killed (4) |
| M4 delete audit call in `loadAlexGSaved` | killed (1) — *after* adding D3C.35 |
| M5 revert geometry scoping to general predicate | killed (1) |
| M6 audit reports any quarantine, not geometry | killed (1) |
| M7 invert the sign in the canonical contract | killed (execution error) |
| M8 remove the risk floor | killed (6, incl. D3/D3B) |
| M9 short-circuit the servicing guard | killed (4) |
| M10 predicate always false | killed (5) |
| M11 predicate always **true** (refuse everything) | killed (5, incl. positive controls) |

**Three defects in my own verification, found by mutation and fixed:**

1. **A false survivor.** My first mutation harness grepped for `^FAIL` lines. M7 (sign inversion)
   *crashed* the suite, producing no FAIL lines, and was reported as SURVIVED. The harness now
   treats an execution error or a short run as a kill. This is the "a suite that runs SHORT is a
   failure" rule from v12.30.0, rediscovered the hard way.
2. **A vacuous fixture.** D3C.13 used the same pair for both positions, so an unguarded monitor
   suspends on the first and still yields `fetches.length === 1` — it passed either way. It now
   asserts *which* pair was fetched.
3. **An untested wiring.** Deleting the audit call from `loadAlexGSaved` killed nothing: the audit
   *function* was covered, its *invocation* was not. D3C.35/.36 close it against the real loader.

## 7. Disclosed limitation — read this before trusting §6

**M2 genuinely survives.** The E2 creation gate sits after `await fetchBidAsk(setup.pair)` inside
async `alexGAttemptOpenLivePosition`. The offline JXA runner cannot resolve a real `await` — the
same long-standing, documented limitation that applies to `closePaperPosition` and
`alexGCloseLivePosition`. Deleting that gate therefore breaks no fixture.

It is **not** closeable by adding a Node-based suite: `run_all.sh` executes only
`tests/run_*_tests.js` under `osascript`, and modifying the canonical gate is separately governed
(ADR-012 D-12).

What *is* proven about E2, on real code: the protected constructor genuinely produces the offending
geometry (D3C.37), the canonical contract genuinely refuses it (D3C.38), and it agrees with the
constructor's legitimate output (D3C.21/.22). **The unproven link is one line of wiring.**

This matters less than it would have, because **E3 is the universal boundary and is fully covered**:
even if E2 were deleted entirely, a sub-floor ALEX position could be created but could never be
monitored, exited, closed or booked to P&L (D3C.39 asserts exactly this).

**Recommended next step for the operator:** live browser verification of E2 under INC-004 isolation
(disposable profile, confirmed test origin), which is the only environment that can execute it.

## 8. Not done, deliberately

D1, D2, D4, floating-point/tick quantization, finite-exposure governance and repository hygiene are
all **out of scope** and untouched. Two pre-existing generated integrity reports remain
**intentionally unstaged** (timestamp-only churn; see the handoff's own "expect only the 2 generated
integrity reports"). **No overall MOGO GREEN is claimed by this document.**
