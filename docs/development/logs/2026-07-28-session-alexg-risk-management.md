# Session Report — Alex G "Best Risk Management Strategy to Make Millions with Trading" (Transcript #8)

**Date:** 2026-07-28 · **Workstream:** Trader Intelligence
**Source:** `EVSRC|ALEX_G|20260728|005` · `https://www.youtube.com/watch?v=VzMlFZbWA0Y`
**Channel:** `fxalexg` (`@fxalexg__`) — **verified before extraction**
**Status:** Applied, validated, awaiting owner review. **Nothing committed, tagged or pushed.**

---

## 1. Ingestion status

✅ **Complete.** `INTAKE|ALEX_G|20260728|005` at `review_required`.

| | |
|---|---|
| Raw archive | `imports/alex-g/raw/alexg-risk-management.raw.txt` + `.sha256` (byte-verified) |
| SHA-256 / size | `193966d9…4618b1` · 16,073 bytes · 738 lines · ~12:38 |
| Normalization | `youtube_timestamp_lines_chaptered` — **6 chapter headings correctly removed as non-spoken**, zero words changed, reversibility asserted per line |
| Sections | 15, cut on chapter and topic boundaries |
| Graph | `BUILD\|20260728\|007` — **1,503 nodes, 3,011 edges, zero findings** |
| Integrity | Evidence **0** · graph **0** · provenance **300 checks, 0 findings** |
| Regression | 307 Python (4 known-obsolete) · 530/530 JS, 0 execution errors · **zero protected-function drift** |

## 2. The headline — `risk_rule` 0 → 13, and `stop_rule` still 0

`ALEX_G` rule-type counts after this cycle:

| Rule type | Count | Change |
|---|---|---|
| `risk_rule` | **13** | **+13 — largest single-cycle change in any category** |
| `session_rule` | 7 | +1 |
| `target_rule` | 3 | +2 |
| **`stop_rule`** | **0** | **— (six sources)** |

**What the source supplies:**

| | |
|---|---|
| Sizing basis | A percentage of deposited account balance, **never** a dollar amount |
| Conservative | **0.5–1%** per trade — for lower-timeframe traders taking 1–3 trades per day or session |
| Standard | **1–2%** per trade — his general recommendation, "the industry standard" |
| High | **3–5%** — personal or disposable accounts **only**, explicitly to avoid breaching funded-account rules |
| Stability | Same percentage every trade; never raised after wins; one percentage chosen per month and held regardless of streaks |
| Seasonal | 3–5% only November–March; reduced through June–August |
| Stated purpose | A stable P&L curve is what lets capital allocators fund a trader |

**What it does not supply, and this is the point.**

Risk sizing tells you *how much* to lose. Stop placement tells you *where*.
**Position size = risk amount ÷ stop distance** — and after six sources the second term does not
exist. A trader following this video knows to risk 1% and has **no rule for converting that into a
lot size.**

This is the cycle where the gap stopped being "not covered yet" and became **demonstrably
structural**: the educator devoted an entire video to risk, and the missing piece is still missing.

## 3. The inference MOGO must not make — recorded so it stays unmade

Source #5 gives an average take-profit of **80–100 pips**. This source uses **1:2 and 1:3** in worked
examples. Together those imply a stop of roughly **27–50 pips**.

**MOGO must not perform that inference.** Both ratios appear only as illustrative arithmetic inside
an argument about escalating risk after a winning streak — neither is stated as required. The pip
figure was given as a *past average*, not a target-selection rule. Combining two descriptive
statements from two different sources into a prescriptive third would be inventing a rule and
attributing it to an educator who never stated it.

Filed as a `high`-priority open question rather than left as an unspoken temptation.

## 4. Contradictions — 2 new, both **within-source** and both **arithmetic**

### `XCONTRA|20260728|006` · SCOPE_MISMATCH · material

Three figures from one video that cannot describe the same operation:

| | |
|---|---|
| Opening | *"I make anywhere from $50 to $100,000 every single day"* |
| Body | *"8 to 10% a month … anybody can do that"*; 50% a day/week/month is *"not going to happen"* |
| Flagship evidence | A **100K** funded account returning 27–28% over ~39 days for a **$28,000** payout |

At 8–10% per month, $50–100k per **day** implies an account in the tens of millions. The evidence
offered is six figures. **The video's own benchmark for realism and its opening claim differ by
roughly two orders of magnitude.** No external data was needed to detect this — only the source's own
numbers, checked against each other.

### `XCONTRA|20260728|007` · TEMPORAL_DRIFT · minor

Four durations for one career in one video: 2½ years before making any money · profitable ~6 years ·
predicting markets ~5 years · 5½ years to work out seasonality.

Filed **minor** deliberately. Casual speech rounds numbers, and inflating this would cheapen the
`material` severity carried by the liquidity and income contradictions. Recorded because every
performance claim in the source is anchored to experience length.

## 5. Replay candidate created — RC-27, and a standing constraint

**RC-27 — is November–March materially better than June–August?**

The seasonal rule is **the only claim in the library that changes position size**, its entire basis
is *"months statistically that I've seen in my trading"* with no data shown, and — unusually — it is
**testable without the missing stop rule**: count RC-25 setup frequency and directional outcome by
calendar month, controlled against unconditional monthly volatility.

An honest limit is written into the candidate: a positive result validates the *pattern*, not the
*risk escalation*. Whether raising risk in better months is correct depends on drawdown, which is not
derivable without the stop rule.

**A standing note now sits at the top of `REPLAY-CANDIDATES.md`**, because a reader seeing 13 risk
rules could reasonably assume P&L replay had become possible. It has not. RC-12 through RC-27 all
measure trigger accuracy, reach-rate, frequency or direction; **not one can produce an expectancy.**

## 6. Unsupported claims — the densest concentration in the library

| Claim | Problem |
|---|---|
| **$50k–$100k per day**, 1–2 hours' work | No account size or verification, **and internally inconsistent** with the same video's realism benchmark |
| **8–10% per month, "anybody can do that"** | No sample, no period, and **no drawdown figure** — notable in a source about risk management. A return target without its drawdown is not a risk claim |
| **100K funded, 27–28%, $28,000 payout** | No statement or firm named; period given inconsistently as "a single month" and "about 39 days" |
| **Students earn $1,000–1,500/week in 3 months** | **No denominator.** "Hundreds of them" with no cohort size and no failure rate carries no information |
| **99% of traders lose money** | Unsourced, like the "retail is 3% of the market" figure in source #3 — used as a premise, not an observation |
| **Seasonal best months** | Prescriptive, multiplies risk 3–5×, and rests on an unshown personal observation → RC-27 |

## 7. Missing definitions

| Gap | Consequence |
|---|---|
| **Stop placement** | Six sources, zero. **Blocks all P&L replay permanently** unless a source states it |
| **Funded-account rules** | High risk is confined to personal accounts *specifically* to avoid breaching funded rules — no drawdown or daily-loss limit is ever named. The constraint motivating the whole banding is unspecified |
| **Which clock the fixed percentage runs on** | Three rules on three clocks: same % every trade · one % per month · 3–5% only Nov–Mar. Reconcilable, but the hierarchy is never stated and the first is phrased as absolute |
| **Required minimum R:R** | 1:2 and 1:3 appear only as illustrative arithmetic |
| **Drawdown at 8–10%/month** | Never given |

## 8. Files created or modified

**Created**
```
docs/trader-intelligence/intake/completed/alexg-risk-management.txt
docs/trader-intelligence/intake/manifests/alexg-risk-management.ingest.json
docs/trader-intelligence/imports/alex-g/raw/alexg-risk-management.raw.txt (+ .sha256)
docs/trader-intelligence/imports/alex-g/normalized/…normalized.txt + …normalization-map.json
docs/development/logs/2026-07-28-session-alexg-risk-management.md
evidence/: 1 source · 1 intake · 15 segments · 35 annotations · 35 items · 35 claims · 35 links
           · 16 questions · 2 contradictions · 1 blueprint · 1 profile · 9 gaps · 82 hypotheses
```

**Modified**
```
docs/trader-intelligence/CROSS-STRATEGY-ANALYSIS.md        (v5 → v6, new §3f, C-3, C-4)
docs/trader-intelligence/GLOSSARY.md                       (+3 terms, 42 → 45)
docs/trader-intelligence/RESEARCH-LOG.md                   (cycle 012 + ROI review)
docs/trader-intelligence/proposals/REPLAY-CANDIDATES.md    (RC-27 + standing P&L constraint)
docs/trader-intelligence/proposals/BACKLOG-002-tjr-source-acquisition.md (A1-STOP)
docs/trader-intelligence/queues/validation/VALIDATION-QUEUE.md (22 → 25 entries)
docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md            (regenerated)
docs/trader-intelligence/graph/build/…                     (BUILD|20260728|007)
```

**Untouched:** `index.html`, `APP_VERSION`, all 63 protected functions and 4 protected constants,
JVM, ALEX, and all trading execution logic.

## 9. Updated knowledge metrics

| Metric | Before | After | Δ |
|---|---|---|---|
| Transcripts processed | 7 | **8** | +1 |
| Educators | 2 | 2 | — |
| Claims | 192 | **226** | +34 |
| Evidence items | 241 | **276** | +35 |
| Segments | 120 | **135** | +15 |
| Open questions | 164 | **180** | +16 |
| Contradictions | 8 | **10** | +2 (both within-source) |
| Replay candidates | 26 | **27** | +1 |
| Rule candidates | 0 | **0** | — |
| Graph nodes / edges | 1,286 / 2,498 | **1,503 / 3,011** | +217 / +513 |
| **ALEX_G `risk_rule`** | **0** | **13** | **+13** |
| **ALEX_G `stop_rule`** | **0** | **0** | **—** |
| **Independent confirmations** | 0 | **0** | — |
| **Confidence changes** | — | **0 state changes** | — |
| Claims at `supported` or above | 0 | **0** | — |

---

## The finding that matters most

**A gap can be confirmed by the very source that should have closed it.**

Before this cycle, "no stop rule" was an absence across five sources about other topics — plausibly
incidental, plausibly coming in a future video. After a dedicated risk-management video that supplies
thirteen risk rules and still omits it, the absence is a **property of the material**.

Negative results about source coverage are results. This one changes what MOGO should expect from
every future Alex G source, and it produced the library's single highest-value acquisition target
(`BACKLOG-002/A1-STOP`): one video stating where the stop goes would unlock P&L replay for six
sources at once. That target is written with an explicit instruction to **accept the negative result
if a reasonable search finds nothing** — the pattern across six sources is that free content stops
where risk begins, and establishing that would itself be a permanent, useful constraint.

A second finding, smaller but now repeatable: **both contradictions this cycle were found by
checking the source's own numbers against each other.** Two of the last three cycles produced a
material finding that way. Cross-checking every quantitative claim in a source against every other
one — income figures, account sizes, percentages, durations — is now an extraction step, not a lucky
catch.

## Next recommended action

Two, and they have now diverged:

1. **Authorize replay and source price data** — unchanged for a sixth cycle. RC-25 remains the best
   first test: fully specified by its source, needs only daily and 4-hour candles.
2. **Acquire an Alex G source that states stop placement, or record that none exists.** This is the
   only missing piece in an otherwise complete method, and it is the one piece that would convert
   sixteen direction-only replay candidates into P&L-capable ones.

`replayAuthorization` is `false` on all six OwnerDecisions, and MOGO holds no market data.
