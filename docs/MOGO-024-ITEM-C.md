# MOGO-024 / Item C — the explicit higher-timeframe alignment gate

**Success condition.** No automated JVM paper trade can execute unless Weekly, Daily and 4H all
hold a recognized evaluated state and at least two agree directionally.

**Status: MET at engine level, and executably verified. Browser-runtime verification was NOT
performed and is not claimed.**

---

## 1. The leak

`evaluateLiveTrigger` **never read the Weekly/Daily/4H states at all.** Higher-timeframe alignment
entered the executable path only *implicitly*, through `detectSignals`' `biasMatch` flag:

```js
sigs.forEach(s=>{s.biasMatch=(bias==='Bullish'&&s.dir==='buy')||...});
```

and `bias` comes from `getBias`, which **filters to directional values and then compares counts**:

```js
const dirs=[d.weekly,d.daily,d.fh].filter(x=>x==='Bullish'||x==='Bearish');
return b>br?'Bullish':br>b?'Bearish':'Split';
```

With `weekly='Bullish'` and the other two unset, `dirs=['Bullish']`, `b=1 > br=0` → a full
directional **`'Bullish'`**. `scoreConfluence` awards bias points only at `score>=2`, so a 1-of-3
earned none — but confluence can still clear `ALERT_THRESHOLD` from its other components.

### Why `getBias`/`getScore` could not express the authorized policy

Both discard everything that is not `Bullish`/`Bearish`, so **`'—'` (never evaluated) and
`'Ranging'` (evaluated, non-directional) are indistinguishable to them.** The policy requires
`Bullish/Bullish/Ranging` **permitted** and `Bullish/Bullish/missing` **blocked** — two cases those
functions collapse onto the identical `bias='Bullish', score=2`. The gate therefore had to read the
**raw** states. That is the whole reason a new predicate exists rather than a threshold change.

## 2. What the data model can and cannot establish

`TF_OPTS = ['—','Bullish','Bearish','Ranging']` — four directional **strings**. `scanData` carries
**no per-timeframe timestamp, no provenance, no freshness marker and no error state.**

The gate therefore **does not claim staleness or provenance checking**. It enforces exactly what
the contract supports — that each required timeframe holds a *recognized evaluated state* — and
treats everything else (`'—'`, `null`, `undefined`, non-strings, unrecognized strings) as
unevaluable and blocking. Fail-closed: an unknown value is never assumed evaluated.

## 3. Historical materiality

| Source | What it holds | Verdict |
|---|---|---|
| `autoTrading.log` (`fxhub_auto`) | pair, dir, entry/stop/target, riskPips, ratio, confluence, `firedAt` | **no HTF states** |
| JVM journal (`fxhub_journal`) | `biasSummary` is the literal constant `JOURNAL_NOT_RECORDED` (`computeJVMExplanations`) | **no HTF states** |
| Decision events | emitted on **rejection only**; `context` carries `confluence` alone | **no HTF states**, and memory-only |
| `fxhub_scan` | mutable, overwritten every scan | **must not** be used to reconstruct entry-time state |

Two historical auto trades were recovered from the live `fxhub_auto` value (read-only copy of
Chrome Profile 2): **AUD/USD 2026-08-18T09:30:34Z** and **USD/CHF 2026-08-20T21:45:44Z**, both
`source:"auto"`, confluence 75.

**Classification: `TRADE_LEVEL_MATERIALITY_UNRECOVERABLE`** for both. No contemporaneous record of
their Weekly/Daily/4H states exists anywhere, and current `scanData` is mutable and therefore
inadmissible. Nothing was deleted, rewritten or retro-fitted.

**Classification: `DEFECT_RUNTIME_CONFIRMED` at the executable-path level.** Reverting the repair
and re-running the suite opens **real paper positions** for `Bullish/Bullish/missing`,
`Bullish/Bullish/undefined`, `Bullish/Bullish/null` and `Bullish/Bullish/{object}` (fixtures
ITEMC-4/5/6/8 fail on the faithful revert). This is demonstrated through the real protected path,
not inferred.

A precise nuance, recorded because it changes what the gate actually adds: the **1-of-3** cases
(`Bullish/—/—`, `Bullish/Ranging/Ranging`) did **not** open under the old code — but only because
`getScore=1` withheld the bias points and confluence fell below threshold. They were blocked by an
**incidental arithmetic side-effect, never by any higher-timeframe rule.** Both are now explicitly
gated.

## 4. The repair

`htfAlignmentPasses(scanLike)` — **pure**, takes the snapshot, never re-reads `scanData`:

1. every required timeframe must be in `{Bullish, Bearish, Ranging}`, else `HTF_TIMEFRAME_NOT_EVALUATED`;
2. bias must be recognized directional, else `HTF_NO_DIRECTIONAL_BIAS`;
3. at least two must agree, else `HTF_INSUFFICIENT_AGREEMENT`;
4. a missing/non-object snapshot is `HTF_SNAPSHOT_MISSING`.

`htfSnapshotOf(oPair)` captures once, **before the first `await`**. `evaluateLiveTrigger` has four
awaits and `scanAll`/`runAutoTopDownScan` can rewrite `scanData` during any of them — reading at
the gate but letting the evaluators re-read later would mean *the trade that executes is not the
trade the gate approved*.

**No new evaluator was written and `scoreConfluence` was not touched.** The gate's own
snapshot-derived values are handed to the existing, already-shipped override parameters —
`detectSignals(candles, oPair, htf.bias)` and `bestConfluence(candles, oPair, {score, bias})` — so
`getBias` and `getScore` are computed **once, from one snapshot**, and cannot silently disagree.

## 5. Files and protected changes

| File | Change | Protected? |
|---|---|---|
| `index.html` | `htfAlignmentPasses`, `htfSnapshotOf`, `HTF_*` constants | **new, now protected** |
| `index.html` | `evaluateLiveTrigger` — gate + snapshot propagation | **yes, authorized** |
| `index.html` | `checkAutoTrades` — two statements (durable `htf` capture + approved recorder) | **yes, authorized** |
| `index.html` | `jvmRecordCandidateApproved`, 2 reason codes, `jvmLiveTriggerReasonCode`, `BASELINE_JVM_FUNCTIONS`, `baselineGetAllFunctionRefs` | no |
| `regression-baseline-tools.py` | `PROTECTED_FUNCTIONS` += `htfAlignmentPasses` | registry |
| `regression-baseline.json` | count 63→64, 2 changed hashes, 1 new entry | baseline |

Verified byte-identical: **`scoreConfluence`, `detectSignals`, `bestConfluence`, `getScore`,
`getBias`, `openPaperPosition`**, plus the other 61 protected functions and all 4 constants.

## 6. `getScore` was NOT added to the protected registry

Tested against the four authorized conditions rather than assumed:

| Condition | Result |
|---|---|
| Transitive protection is policy? | **No** — `getScore` already fed protected `scoreConfluence` before this change and was never protected. |
| Influences decisions without coverage? | Influences, but coverage is strong: mutating it to `3` kills 1 fixture, to `0` kills **150**. |
| A mutation bypasses the gate? | **No.** The permit/block decision is derived from raw state counts, never from `getScore`. |
| Material governance gap? | Not demonstrated. |

**Fixture ITEMC-26 now enforces that independence** — corrupting `getScore` in both directions
cannot change any gate verdict — so this is an invariant, not a claim.

## 7. Decision-time capture (Phase 5)

No existing additive path was available: the v12.6.0 architecture review recorded that JVM's
decision detail is *"trapped inside a protected-calls-protected chain … with no safe external
hook."* Following the precedent v12.20.0 set for the rejected side, **two statements** were added
inside protected `checkAutoTrades`:

* `htf: result.htf` on the **durable, persisted** `autoTrading.log` entry;
* `jvmRecordCandidateApproved(...)` — non-protected, wholly wrapped, returns undefined, result
  never read, so it cannot alter, delay or prevent a decision.

Captured: decision timestamp, instrument, direction, all three timeframe states, per-timeframe
evaluation status, bias, alignment score, gate outcome, and `tradeId`. **Snapshot accuracy is
proven, not asserted**: ITEMC-22 rewrites `scanData` after the trade and shows the record unchanged,
and ITEMC-23 proves that rewrite genuinely changes what the gate would now answer — so ITEMC-22
demonstrates immutability rather than a `scanData` that never moved.

**Not claimed:** the JVM *journal* record still shows `JOURNAL_NOT_RECORDED` for `biasSummary`.
Reaching it requires modifying `openPaperPosition`, which is outside this authorization.

## 8. Testing

`tests/run_v1233_jvm_autotrade_reliability_tests.js` 127 → 155; `run_v124_baseline_registry_tests.js`
31 → 34.

* **ITEMC-0/1/2/3** positive controls; **ITEMC-4…13** negative controls, each re-asserted against
  the firing baseline so only the timeframe states differ.
* **ITEMC-14** exhaustively sweeps **all 1331** combinations of eleven value kinds against the
  policy computed independently; **ITEMC-15** proves that sweep is non-vacuous.
* **ITEMC-17** requires the refusal *codes* to distinguish never-evaluated from
  evaluated-but-insufficient.
* **BaselineRegistry.28/29/30** close a real governance gap: cross-file parity between
  `index.html` and `regression-baseline-tools.py` was *disclosed as manual* in v12.4.0 and checked
  by nothing. It is now parsed from disk and asserted.

### Mutations

| Mutation | Killed by |
|---|---|
| Faithful revert (gate **and** overrides removed = original defect) | JVM-3a, **ITEMC-4/5/6/8**, ITEMC-20/21/24 |
| `'—'` accepted as an evaluated state | ITEMC-4, 14, 17 |
| Agreement threshold weakened to 1 | ITEMC-14, 17 |
| `getScore` → 3 | ITEMC-20 |
| `getScore` → 0 | 150 fixtures |
| `htfAlignmentPasses` removed from the `.py` registry only | BaselineRegistry.29, 30 |

**A disclosed mutation-design correction:** the first "gate removed" mutation deleted only the
early `return` and killed just 2 fixtures — because `htf.bias` was still being passed as the
override, which blocked the trade downstream anyway. That mutation was **not faithful to the
original defect**. The faithful revert (gate *and* overrides removed) kills 8 and reproduces real
position openings. A mutation that does not restore the actual pre-change behaviour proves nothing.

### ITEMC-2, disclosed rather than hidden

This suite's synthetic "firing" market data produces a **bullish** engulf only; there is no
bearish-firing mode. A Bearish seed therefore cannot open a position here for reasons unrelated to
the gate. Rather than a fixture that would silently prove nothing, ITEMC-2 asserts the stronger
provable claim: the gate **permits** the Bearish alignment, and the downstream refusal is *not* the
HTF gate. Authoring bearish market data is outside this bounded change.

## 9. Not claimed

* **No browser-runtime verification.** All verification is engine-level via the offline harness.
* **No staleness or provenance checking** — the data model cannot support it.
* **Historical trade materiality is unrecoverable**, not "clean".
