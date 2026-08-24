# MOGO-024 / Item D + backtest disposition

Two tracks, deliberately kept out of the Item C protected re-baseline. **Neither changes a
protected function; drift is 0 for both.**

---

## Item D — the manual-review bypass of the Item C gate

**Item D was NOT closed as "no change needed". A genuine executable leak was demonstrated.**

### The finding

`evaluateSetupFullBreakdownCore` carries its own `htf_alignment` gate, marked `category:'hard'`:

```js
pass: score>=2
```

`getScore` returns **2** for `Bullish/Bullish/'—'` exactly as it does for
`Bullish/Bullish/Ranging` — the same collapse Item C identified. And `MANUAL REVIEW ELIGIBLE`
requires every *hard* gate to have passed, with only the weekday preference failing.

So the path was:

```
Bullish/Bullish/missing → htf_alignment passes (score 2) → MANUAL REVIEW ELIGIBLE
  → approveManualReviewTrade → openPaperPosition → a real paper position
```

**Gating only `evaluateLiveTrigger` would have moved the leak, not closed it.**

### The repair

The gate now reuses `htfAlignmentPasses` — the same predicate the live executable path uses.
The authorization's three conditions were each checked rather than assumed:

| Condition | Finding |
|---|---|
| Input contract matches the executable path | **Yes** — `scanLike = {weekly, daily, fh}`, byte-identical shape |
| Does not misrepresent suppressed/partial states | **Yes** — the predicate's codes distinguish never-evaluated from insufficient-agreement, and the `observed` string now carries that reason |
| Consistent with the authorized missing-timeframe policy | **Yes** — it *is* that policy |

Neither `evaluateSetupFullBreakdownCore` nor `approveManualReviewTrade` is protected, so this
required no protected change and no baseline movement.

### Testing — `ItemD.1`–`ItemD.10`

* **ItemD.1/2/6** positive controls: `Bullish/Bullish/Ranging` still passes, still classifies
  `AUTO ENTRY ELIGIBLE`, and a Thursday 2-of-3 is still `MANUAL REVIEW ELIGIBLE` — proving the
  guarded path is genuinely reachable rather than dead.
* **ItemD.7** the executable consequence: the same Thursday setup with an unevaluated third
  timeframe can never reach `approveManualReviewTrade`.
* **ItemD.8** proves `htf_alignment` is the gate that stopped it, so ItemD.7 is not accidental.
* **ItemD.9/10** both paths answer identically across eight state combinations, and that agreement
  is non-vacuous.

| Mutation | Killed by |
|---|---|
| Revert the breakdown gate to `score>=2` (the original bypass) | ItemD.3, 5, 7, 8, 9 |
| Force the gate to always fail (over-block) | pre-existing Fixtures 19–23, 30 |

---

## Backtest disposition (Phase 6) — confirmed, contained, labelled, **not quarantined**

### Confirmed

`index.html`, inside `runBacktest`:

```js
const rollingBias=calcBiasFromCandles(slice.slice(-200));
const rollingScore=(rollingBias==='Bullish'||rollingBias==='Bearish')?3:0;
```

`slice` is **the very candle series being backtested**. The engine never reads a real Weekly,
Daily or 4H series, and then records the alignment score as a fixed **3** whenever the bias is
directional — awarding full `WEIGHTS.bias3` credit the frozen strategy would not have granted.
That inflates the trigger count and every figure derived from it, win rate and expectancy included.

**The fabricated 3 was NOT replaced with a fabricated 0**, and `scoreConfluence` and the
backtesting engine are untouched. Fixture `BACKTEST-PROXY-1` reads this from the real source text,
and a mutation replacing the 3 with 0 fails it.

### Actual downstream consumers, traced

| Consumer | Reached? |
|---|---|
| Backtest tab display (`renderBacktestResults`) | yes |
| `renderMTFComparison` — legacy column beside TRUE MTF Replay | yes |
| `replayState.lastLegacyStats` (in-memory only) | yes |
| Evidence packages / observation corpus | **no** |
| Strategy promotion, rankings, edge claims | **no** |
| AI context (`buildAiContext`) | **no** |
| Exports, automated research workflows | **no** |

Evidence packages are built only by `evidencePersistTradePackageResolved`, whose callers are the
ALEX replay seam and the live-paper path. `runBacktest` reaches neither. `BACKTEST-PROXY-2`
asserts this from the function's real body rather than from prose.

### What was done, and what was deliberately not

The two display surfaces now carry the required classification —
**SINGLE-TIMEFRAME PROXY · NOT THE FROZEN MTF SPECIFICATION · NOT VALIDATED STRATEGY EVIDENCE** —
and name the specific defect. The pre-existing warning described only the *AOI* gap and never
mentioned the alignment score at all.

**This is a LABEL, and it is not presented as a quarantine.** No machine-enforced ineligibility was
added, because there is no authoritative consumer to enforce ineligibility *against* — verified
above, not assumed. Claiming enforcement here would be the fabrication this repository's own rules
prohibit.

`BACKTEST-PROXY-3` pins both surfaces; removing the label from either one fails it.

### Requires separate authorization

A genuine machine-enforced quarantine — a provenance field on backtest results, carried into any
future promotion/ranking/evidence path — would need a new schema field and broader governance
work. **That is stopped here at this recommendation and is not attempted.** It is not currently
load-bearing, because no such path exists today; it becomes load-bearing the moment one is built.
