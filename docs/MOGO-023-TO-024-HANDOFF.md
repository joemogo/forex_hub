# MOGO-023 → MOGO-024 Engineering Handoff

**Status: MOGO-023 (Stabilization & Architectural Hardening) reached its stopping condition.
MOGO-024 has NOT begun.**

Every figure here was **measured in this session** against the working tree, the corpus, the
filesystem or the live provider. Anything not established by direct evidence is labelled
**UNVERIFIED**. Where this document contradicts an earlier one, the earlier one was wrong and the
correction is stated rather than quietly applied.

**NO LIVE-MONEY AUTHORITY EXISTS. PAPER SIMULATION ONLY.**

---

## 1. Repository authority

| Item | Value |
|---|---|
| Repository | `/Users/joemogollon/Desktop/Forex Hub` |
| Local branch | `main` → upstream **`origin/mogo-main`** |
| HEAD when written | `55f2a3355003217784ad253c7fc616a199c1e5fd` |
| Ahead / behind | `0 / 0` — fully pushed, verified by `git ls-remote` |
| Milestone start | `209fa02` (the MOGO-022 → 023 handoff commit) |
| Net change | **+2,648 / −34 across 16 files**, 6 commits (plus the two that follow this document) |
| Working tree | clean except two **generated** `integrity-report.json` timestamp files |

### Branch topology — unchanged, still an operator decision

`origin/main` is `abfc763`, **unrelated history**: `git merge-base HEAD origin/main` fails with no
common ancestor (independently re-verified this session). Never `checkout`, `merge`, `rebase` or
force-push to resolve it. Not touched.

**On the HEAD above.** It is the HEAD this document was *measured against*. Two further commits
follow it — the enforcement fixture and this handoff itself — so a fresh session will find a later
HEAD. MOGO-022's handoff had the identical property and MOGO-023 wrongly spent time treating it as a
discrepancy; it is not one. Verify by `git log --oneline 209fa02..HEAD`, not by matching this SHA.

### The commits

```
55f2a33  one health authority, and its answer is UNKNOWN
38e6759  the corpus had no analogue of the guard INC-005 forced into the app
bd7c218  the base rate divided by ALEX and counted JVM
a1b303b  the checkpoint's own handoff verdict contradicted its JVM finding
0ef40a9  current_strategy is JVM's id, and JVM has forward evidence
631a5ab  a dead provider was being narrated as a quiet market
```

---

## 2. Canonical gate — final measured state

```bash
bash tests/run_all.sh          # exit 0 required
```

| Gate | Result |
|---|---|
| Suites / fixtures | **34 suites, 2393 / 2393, 0 failed, 0 execution errors** |
| Python tests | **`Ran 1467 tests … OK`** |
| Python collection | IN SYNC (29 modules, 1467 tests) |
| Selftests | **4 PASS** (extractor, coverage, checkpoint, **platform health**) |
| `validate_evidence.py` | `{INFO 0, WARNING 2, ERROR 0, FATAL 0}` |
| `validate_graph.py` | `{INFO 0, WARNING 31, ERROR 0, FATAL 0}` |
| `validate_acquisition.py` | all 0 |
| Reconcile | RECONCILED (STRUCTURE ONLY) |
| Protected drift | **none** — 63 functions + 4 constants byte-identical |
| Auto-mode governance | IN SYNC (27 / 21 / 74), all 11 MOGO rules intact |
| **Exit code** | **0**, and the summary VERDICT line agrees with it |

The 2 evidence WARNINGs and 31 graph WARNINGs are the **same honest warnings** MOGO-022 documented
(`PACKAGE_WITNESS_UNAVAILABLE`, `PACKAGE_WITNESS_DEGRADED`, 31 genuine orphan sources). Unchanged.

---

## 3. What MOGO-023 actually changed

### 3.1 INC-006 — a dead provider narrated as a quiet market

`api-fxpractice.oanda.com` returned **HTTP 520 on every endpoint**, reproduced 12/12 over a
continuous 28-minute window; the live host answered a correct 401 throughout. **DATA PROVIDER**,
external. Auth, symbol mapping, timeframe, request construction and local network each eliminated by
evidence. ADR-011 correctly suppressed all 35 evaluations.

**The MOGO defect was that it could not say why.** `fetchCandles()` collapsed three different
failures into one bare `null`, discarding `r.status` one line after learning it, so the banner
rendered `HTTP —` and its own prose reassured the operator that session/weekend gaps are legitimate.

Repaired in **v12.40.0**: `fetchCandlesDiagnosed()` carries `transportOutcome` ∈ `{OK, HTTP_ERROR,
NO_CANDLES_FIELD, NETWORK_ERROR}` plus the real status; `scanPair` records them **even when candles
is null**. `fetchCandles`' return contract is unchanged — returning `[]` would be truthy and would
silently disable every `if(!candles)` guard in the app.

**Provider recovered** (401 on both endpoints). **UNVERIFIED:** that *authenticated* requests return
220 complete candles — only observable inside the running engine.

### 3.2 Strategy-population isolation

`forward_coverage.py` divided by ALEX's base rate (221, pure ALEX) and counted ALEX + JVM (27 + 2).
Scoped to ALEX, **`AUD/USD` flips `PRESENT` → `ABSENT_CONSISTENT_WITH_RARITY`** — the one "forward
AUD/USD trade" was JVM's. Also fixed: silent exclusion of `timeframe:null` records, and a
`--configured` default that injected timeframe labels into instrument and direction reports.

### 3.3 Observation integrity — RAW vs AUTHORITATIVE

The app has had `TRADE_INTEGRITY_RULES` since v12.15.0 (added because of INC-005). **The corpus had
no equivalent**, and those rules key on MAE/MFE which the observation schema lacks. New
`observation_integrity.py` partitions and prices the gap. Zero false positives across 230 other
records.

### 3.4 The health authority

`platform_health.py` — one auditable answer, four states, **UNKNOWN never aggregates to GREEN**.
Selftest injects 15 failure conditions and is wired into the gate.

### 3.5 A gate that rendered green while red

`run_all.sh` exited 1 on a fixture-count mismatch while printing `Failed: 0`. The summary now derives
a `VERDICT` line from `OVERALL_EXIT`, so it cannot disagree with the exit code by construction.

---

## 4. Corrections to the MOGO-022 handoff

| Claim | Verdict |
|---|---|
| All test/count/population/gate figures | **Accurate.** Every one re-measured and held. |
| *"JVM — Evidence produced: zero observations. Not paper trading."* | **FALSE.** JVM has 2 FORWARD observations. |
| *"`current_strategy` — anomaly, not a strategy"* | **FALSE.** It is JVM's canonical registry id. |
| HEAD `b23085f` | Superseded by `209fa02`, the handoff commit itself. Not an error. |

**The numeric claims were sound; the strategy-governance narrative was not.**

---

## 5. Strategy status — measured, per strategy

| | ALEX `alex_g_sr_v1` | JVM `current_strategy` | TJR `tjr_slr` |
|---|---|---|---|
| Registry id | explicit | **bare literal `current_strategy`** | `TJR_STRATEGY_ID` |
| `paperTrading` capability | true | **true** | false |
| Forward observations | 27 | **2** | **0** |
| Authoritative (integrity-passed) | **27** | **1** | 0 |
| ΣR / mean R / win rate | **−6.063 / −0.2245 / 25.9 %** | −1.118 / −1.1178 / 0 % | — |
| Authorization file | 2 | **none** | metadata-only |
| Preregistration | 2 | none | none |

**JVM's authoritative forward population is one trade.** Its apparent performance — +0.882R at 50 % —
is produced entirely by the record classified UNVERIFIED; removing it inverts the sign. No JVM
performance claim is possible, so the owner's conditional PAPER-promotion grant **is not triggered**:
it authorises promotion where every scientific gate is met and only approval remains, and the gates
are not met at n=1. The grant explicitly does not authorise lowering them.

**JVM is not a promotion candidate in the first place.** `JVM_MANIFEST` is MOGO's *own* original
strategy (`MOGO Strategy` v1.0, `status: Active`, "frozen at inception"), operator-gated by
`autoTrading.enabled` (default `false`). The research→PAPER ladder governs *externally researched*
strategies.

**TJR carries no stale-status defect** — independently re-measured: zero observations under any
identifier, `paperTrading:false`, no execution path. The defect was bounded to JVM.

---

## 6. B-22 — quantified, and it has a direction

The standing caveat was *"forward statistics describe the preserved subset; the oldest closes minted
no package."* Now measured. ALEX's preserved ledger holds **35 real closes** (plus 4 developer tests):

| | n | ΣR | mean R | win rate |
|---|---|---|---|---|
| FORWARD (package-witnessed) | **26** of 35, +1 later close = **27** | −6.063 | −0.2245 | 25.9 % |
| RECONSTRUCTED (journal-derived, no package) | **9** | +3.032 | +0.3369 | 44.4 % |
| Missing entirely | **0** | — | — | — |

**25.7 % of ALEX's preserved closes sit outside the FORWARD population, and that excluded cohort
looks materially BETTER than the included one.** ALEX's forward figure is drawn from the more recent,
worse-performing subset.

**Do not combine them** — different evidence strength; RECONSTRUCTED has no package witness. Whether
the divergence is regime, learning, or evidence-capture bias is **UNKNOWN**. This is the single most
important open question for any future ALEX performance claim.

---

## 7. Completion standard — honest scoring

| # | Question | Verdict |
|---|---|---|
| 1 | No setup vs. inability to evaluate | **YES** |
| 2 | Provider failure vs. legitimate short history | **YES** |
| 3 | UNKNOWN avoids becoming GREEN | **YES** |
| 4 | Strategy populations isolated end-to-end | **YES** |
| 5 | Unverified evidence cannot contaminate authoritative performance | **YES** |
| 6 | Routine failures detected before the operator notices | **PARTIAL** |
| 7 | Bounded recovery without weakening integrity | **PARTIAL** |
| 8 | Recovery avoids duplicate PAPER activity | **YES** |
| 9 | Health claims traceable to production truth | **YES** |
| 10 | Research independent of production semantics | **YES** |

**#6 — PARTIAL, and it needs one operator action, not more engineering.** `platform_health.py`
detects these conditions and exits 1 on RED, which is exactly what a scheduler needs. Nothing
schedules it. Installing a `launchd` job is a persistent machine-local change and is therefore an
operator decision, not something to do unilaterally:

```bash
# runs every 15 min; exits 1 only on RED, silent otherwise
*/15 * * * * cd "/Users/joemogollon/Desktop/Forex Hub" && \
  python3 scripts/trader_intelligence/platform_health.py --network || \
  echo "MOGO HEALTH RED $(date -u)" >> ~/mogo-health-alerts.log
```

**#7 — PARTIAL, and largely inherent.** MOGO is a browser application with no server, no workers and
no services. The narrow-recovery ladder (request → connection → worker → service) has almost no
surface to act on. The meaningful recovery for the failure that actually occurred is *fail closed,
report why, verify on return* — which is now implemented and tested. Rather than manufacture
self-healing where there is nothing to heal, this is recorded as **architecturally bounded**.

---

## 8. Open items

| Sev | Item |
|---|---|
| **P2** | **B-22 with direction** — the 9 excluded closes outperform the 27 included (§6). Any ALEX forward claim inherits this. |
| **P2** | The 4 ms / +2R record — provenance INFERRED, not established. Preserved untouched. |
| **P2** | JVM produces forward evidence with no authorization file and no preregistration — **operator decision** (§5). |
| **P2** | Forward PAPER depends on a browser tab; detection now exists, scheduling does not (§7 #6). |
| **P3** | `localStorage` three-key write is not atomic as a group; a process kill can desynchronise the journal from the ledger. Cannot duplicate a PAPER action. |
| **P3** | Outage windows are not observed windows — stop/target detection is suspended, so realized R across one is measured late. |
| **P3→P2** | **Paper P&L models no financing/carry cost** — affects existing ALEX/JVM figures; error compounds with holding period (§9). |
| **P3** | `TJR_MANIFEST.capabilities.replay:true` contradicts `profile.json`'s `replayStatus:"not_started"` (disclosed in-code). |
| **P3** | `regression-baseline-tools.py` `FIXTURE_COUNTS` is stale; the **enforced** registry is `tests/expected_fixture_counts.tsv`. |
| **P3** | Exact INC-006 recovery instant unverified. |
| **Operator** | `main` / `mogo-main` divergence. |

**No P1 open. No new P1/P2 introduced by this milestone's changes.**

---

## 9. MOGO Trend-Structure

`docs/MOGO-TREND-STRUCTURE-THESIS.md`, state **`RESEARCH THESIS`** — first rung, no trading
authority. Falsification conditions, candidate definitions for every vague term, the designated
baseline among them, and the controls are all declared **before any measurement**. **Not optimized,
not backtested, not promoted.**

### Correction: OANDA candles DO carry volume, and MOGO discards it

An earlier revision of the thesis said the feed "carries OHLC mid prices only; there is no volume."
**Wrong about the feed, right only about MOGO's ingestion.** OANDA's candles carry a `volume` field —
*"the number of prices created during the time-range"*, i.e. a count of OANDA's own price updates.
All four mappers (`index.html` 6969, 7041, 7179, 10839) keep only `t,o,h,l,c` from `c.mid`, and
**zero code paths read `c.volume`** (verified).

**This makes the hazard worse.** The risk was never that MOGO lacks a proxy it might fake — it is
that the proxy is **already in every response, free, and one line from being wired into a "value
area."** So the prohibition is now **enforced**, not documented: fixture `INC006-7` asserts `.volume`
appears nowhere in `index.html`, and is mutation-verified — adding `v:parseFloat(c.volume)` to a
mapper fails it. Deliberate future use stays possible and must be deliberate: name it
`oanda_tick_count`, keep it out of every structure/value computation, and update the fixture in the
same commit.

`STR-B` remains **not currently possible**. FX has no consolidated volume; the only genuine executed
spot volume found (CLS) is institutional sales-only, and the best self-serve substitute is CME
**futures** volume — a different instrument, which if ever adopted is `STR-B'`, never `STR-B`.

### Carry: §3.8 was unanswerable as posed, and is now split

It never said whether carry is a **signal** or a **cost**. Four non-interchangeable objects were
conflated — policy rate, OIS/overnight fixing, forward points, broker financing rate. Free, keyless,
deeply historical, redistributable data exists for the first two (BIS CBPOL; ECB/BoE/NY Fed).
**Forward points have no public price from any provider checked.** Any adoption is
snapshot-and-commit under `scripts/`, never a live browser call — the CSP allows three hosts and
`docs/SECURITY.md` forbids the browser holding a paid credential.

### NEW P3→P2, and it affects figures that already exist

**MOGO's paper engine models no financing at all.** `swapRate`, `financingCharge`, `rolloverCost`,
`interestRate`, `financing` — **zero occurrences** in `index.html`. Every P&L is pure price movement.
Spread *is* modelled (`closePaperPosition` books bid/ask); financing is not. Realized R on any
position held across a rollover is wrong by the unmodelled carry — favourable for positive-carry
longs, unfavourable for their shorts. ALEX's forward holds run hours to days, so it is not
negligible. See `docs/KNOWN_ISSUES.md`. **Do not back-fill estimated financing onto preserved
records.**

**Next legitimate step is NOT to test it.** It is to measure whether candle history is deep enough
for a credible development/holdout split at H4/D across a regime cycle, then freeze the baseline
spec. Testing before freezing is how a thesis becomes an overfit.

---

## 10. Recommended MOGO-024 direction

**Do not perform the evidence-layer refactor the MOGO-022 handoff anticipated.** Measured:
`validate_evidence.py` has 26 returns inside check functions and only 3 that report nothing, all
adjudicated benign or covered. That layer is hardened; building the "single invariant" there is
low-yield work on a solved surface. INC-006 proved the exposure was in the **runtime layer**, and
MOGO-023 addressed it there instead.

Highest-value candidates, in order:

1. **Resolve B-22's direction (§6).** The strongest scientific claim MOGO can currently make is
   blocked on it.
2. **Close #6 with the operator** — one scheduling decision.
3. **Trend-Structure data-availability measurement**, then freeze the baseline spec.
4. **JVM governance decision** (§5) — needs evidence, not engineering.

---

## 11. Fresh-session verification

```bash
cd "/Users/joemogollon/Desktop/Forex Hub"
git rev-parse HEAD                    # expect 55f2a33…
git status --porcelain                # expect only the 2 generated integrity reports
bash tests/run_all.sh                 # expect exit 0, VERDICT PASS, 2392 fixtures, 1467 tests
python3 scripts/trader_intelligence/platform_health.py --network   # expect OVERALL: UNKNOWN
python3 scripts/trader_intelligence/observation_integrity.py       # expect 1 excluded, +2.000R
scripts/forward_capture.sh            # read-only; expect 41/41 verified, 259 -> 259
```

**If any check disagrees with this document, trust the repository and investigate.** That rule found
every defect in this milestone — including two in documents I had already committed.
