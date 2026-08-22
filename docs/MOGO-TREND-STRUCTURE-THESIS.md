# MOGO Trend-Structure — Research Thesis v0.1

**Track status: `RESEARCH THESIS`.** This is the first rung of the promotion ladder. It is **not** a
specification, **not** an implemented evaluator, **not** a paper candidate, and carries **no**
trading authority of any kind.

**Opened:** 2026-08-21 (MOGO-023). **Author:** MOGO engineering session MOGO-023.
**Nothing in this document has been backtested, and no parameter in it has been chosen by looking at
a result.** That is the point of writing it before measuring anything.

**NO LIVE-MONEY AUTHORITY EXISTS. PAPER SIMULATION ONLY.**

---

## 1. Why this track exists, stated honestly

MOGO's only strategy producing evidence is `alex_g_sr_v1` — MOGO's *implementation* of a published
method. It carries a structural limitation recorded in `CLAUDE.md`: replaying it measures the
implementation, not whether the trader's stated rule holds. Its hypothesis registry currently holds
41 hypotheses with **zero SUPPORTED**.

MOGO Trend-Structure is different in kind: it is **MOGO's own hypothesis**, derived from published
systematic-trading literature rather than reconstructed from one person's screenshots. That makes it
the only lane where MOGO can, in principle, own the full chain from hypothesis to falsification
without an acquisition dependency.

It is opened as a *thesis*, not a strategy, because MOGO currently has **no evidence** that it works.

---

## 2. Core hypothesis (the claim to be falsified)

> A rules-based system that trades **only with an objectively-defined higher-timeframe trend**,
> enters **only on a pullback into structure followed by objective evidence of trend resumption**,
> **declines entries that chase excessive displacement**, and sizes positions by **volatility-normalized
> risk**, produces **positive expectancy** net of realistic costs across multiple FX pairs and
> multiple regimes — and does so with **higher expectancy than a same-universe, same-cost baseline
> that omits the pullback and resumption conditions.**

The second clause matters more than the first. A profitable trend system that is no better than
"buy the trend, any entry" has not demonstrated that *structure* contributes anything, and structure
is the part this thesis is actually about.

### Falsification conditions, declared now

This thesis is **rejected** if any of the following holds on the untouched holdout:

- expectancy per trade ≤ 0 net of assumed costs;
- expectancy not materially better than the no-structure control (§6);
- positive results confined to a single pair or a single regime;
- results that invert when the development/holdout split is moved.

Declaring these in advance is what makes a later negative result reportable instead of negotiable.

---

## 3. Candidate definitions — the vague terms, made explicit BEFORE measurement

The single largest overfitting risk in this thesis is silently choosing whichever definition of
"trend" or "meaningful pullback" makes the equity curve look best. So each term below is given
**several named candidate definitions**, and **one is designated the preregistered baseline** before
any result is seen. Alternatives may be tested only as explicitly-labelled sensitivity analysis, and
a better-performing alternative **does not** retroactively become the baseline — it becomes a
`v0.2` with its own holdout.

Every candidate below is `UNVALIDATED`. None is known to work.

### 3.1 "Trend" (Daily / H4 direction)

| id | Definition | Notes |
|---|---|---|
| `TREND-A` **(baseline)** | Daily close above/below the 200-period SMA **and** 50-SMA on the same side of the 200-SMA | Two-condition, widely documented, no lookahead |
| `TREND-B` | Higher highs and higher lows over the last N=5 confirmed Daily swing points | Structural rather than average-based |
| `TREND-C` | Sign of a Donchian(55) breakout regime, classic trend-following | Literature-standard control |

### 3.2 "Meaningful pullback"

| id | Definition | Notes |
|---|---|---|
| `PB-A` **(baseline)** | Retracement of **38.2%–78.6%** of the most recent confirmed impulse leg, measured on H4 | Band, not a point; rejects both shallow noise and full reversal |
| `PB-B` | Price trades back into a prior H4 supply/demand zone | Overlaps ALEX's AOI concept — deliberately kept separate |
| `PB-C` | Close beyond a 20-period EMA against the trend, then back | Simpler, weaker structural claim |

### 3.3 "Structure" / "value"

| id | Definition |
|---|---|
| `STR-A` **(baseline)** | The pullback terminates within a zone bounded by a prior confirmed H4 swing point ± 0.5 × ATR(14, H4) |
| `STR-B` | Volume-weighted value area of the prior N sessions (**BLOCKED** — see §8, MOGO has no volume data) |

### 3.4 "Trend resumption" (the entry trigger)

| id | Definition |
|---|---|
| `RES-A` **(baseline)** | An H1 close beyond the high/low of the pullback's most recent confirmed swing, in the trend direction |
| `RES-B` | An H1 bullish/bearish engulfing close within the structure zone |
| `RES-C` | Break of a descending trendline drawn across the pullback (**rejected as baseline** — trendline construction is not mechanically unambiguous) |

### 3.5 "Excessive displacement" (the anti-chase filter)

| id | Definition |
|---|---|
| `DISP-A` **(baseline)** | Reject if the entry candle's range > 2.0 × ATR(14, H1), or if price is > 3.0 × ATR(14, H4) from the structure zone |

### 3.6 "Regime"

| id | Definition |
|---|---|
| `REG-A` **(baseline)** | ATR(14, D) percentile rank over a trailing 252-day window, bucketed into terciles (low / normal / high volatility) |

### 3.7 Risk and sizing

- **Risk per trade:** `0.25%` of equity, baseline. `0.50%` tested **only** as declared sensitivity.
- **Stop:** structure-based — beyond the pullback extreme ± `0.5 × ATR(14, H1)`.
- **Sizing:** position size = risk amount ÷ stop distance. Volatility-normalized by construction —
  a wider stop buys a smaller position, so per-trade risk is constant in equity terms, which is what
  makes R-multiples comparable across pairs and regimes.
- **Target:** baseline is a fixed `2R`, chosen **for comparability with existing MOGO evidence**, not
  because 2R is believed optimal. Trailing and volatility-scaled targets are `v0.2` questions.

### 3.8 Carry / rate context — hypothesis only, and deliberately NOT in the baseline

Whether interest-rate differential or carry improves expectancy is a **named open question**, not a
baseline rule. Adding a macro input before establishing that the price-structure core works would
make a failure uninterpretable. Sequenced for `v0.2`, conditional on `v0.1` surviving.

---

## 4. Preregistration and anti-overfitting governance

The ladder this track must climb, in order, with no stage skipped:

```
RESEARCH THESIS          <-- YOU ARE HERE (v0.1)
  -> BASELINE SPECIFICATION       (mechanical, unambiguous, versioned, frozen)
  -> HISTORICAL EVALUATION        (development sample only)
  -> OUT-OF-SAMPLE VALIDATION     (untouched holdout, ONE look)
  -> SHADOW FORWARD OBSERVATION   (evaluates, records, trades nothing)
  -> PAPER CANDIDATE              (dossier assembled)
  -> PAPER AUTHORIZED             (OPERATOR GOVERNANCE BOUNDARY -- not a MOGO decision)
  -> FORWARD PAPER EVALUATION
```

**Binding rules for this track:**

1. The baseline spec is **frozen and version-stamped** before any historical evaluation runs.
2. The **holdout is looked at once.** A second look makes it a development set, permanently.
3. Rules are **not** adjusted until results become attractive. If forward evidence motivates a
   change, that produces **`v0.2` with its own untouched holdout** — the `v0.1` record is never
   retroactively rewritten.
4. A negative result is a **result**, recorded with the same weight as a positive one.
5. Subagents may **recommend** promotion. They may never perform it.

### Proposed data split (to be fixed at specification time, before any run)

| Sample | Purpose |
|---|---|
| Development | Earlier portion of available history — all definition selection happens here |
| Holdout | Most recent contiguous portion — **untouched**, one look |
| Walk-forward | Rolling re-fit windows across the development sample, regime-segmented per `REG-A` |

---

## 5. Reproducibility requirement

No performance figure from this track is quotable unless it carries: strategy spec version, code
commit SHA, dataset identity and version, instrument universe, date range, transaction-cost
assumptions, full parameter set, test method, and random seed where relevant. A result that cannot
be reproduced from that metadata does not become authoritative, however good it looks.

---

## 6. Fair comparison — the controls, declared now

Trend-Structure will be compared against controls sharing **identical** periods, instruments, spread
and slippage assumptions, cost model, risk normalization and sample sizes:

- **Control 1 — no structure:** trend filter only, enter at the next bar. *Isolates whether pullback
  + resumption contributes anything at all.* **This is the control that decides the thesis.**
- **Control 2 — no trend filter:** structure entries taken in both directions. *Isolates the trend condition.*
- **Control 3 — random entry, identical risk/stop/target geometry.* Establishes the cost floor.*

Reported metrics: expectancy, win rate, average win, average loss, profit factor, realized R,
drawdown, MAE, MFE, setup frequency, exposure, tail behaviour, regime dependence, stability, and
**statistical uncertainty** on every one. Win rate is explicitly **not** an optimization target — a
2R system at 40% and a 0.5R system at 75% are not comparable on win rate, and optimizing it selects
for the wrong thing.

**No superiority claim from a small sample.** Sample-size adequacy is declared before, not after.

---

## 7. Relationship to existing lanes

| Lane | Status | Interaction |
|---|---|---|
| ALEX `alex_g_sr_v1` | PAPER, frozen semantics | **Untouched.** Trend-Structure changes no ALEX rule, threshold or constant. |
| JVM | Research / structural only | None yet. |
| TJR `tjr_slr` | Research / phase-1 engine | Shares vocabulary around structure; the recorded ALEX-vs-TJR liquidity contradiction is **not** resolved by this thesis and must not be assumed resolved. |

Trend-Structure's `STR-A` and ALEX's AOI are **different constructs** and must not be conflated,
even where they coincide on a chart.

---

## 8. Declared UNKNOWNs and blockers — recorded, not guessed

- `UNKNOWN` — every performance property. Nothing has been measured.
- `UNKNOWN` — whether any candidate definition in §3 is superior to any other.
- `UNKNOWN` — realistic spread/slippage for the exotic pairs in `ALL_PAIRS` (`USD_TRY`, `USD_ZAR`,
  `USD_MXN`, `USD_DKK`). Costs there may dominate the edge. **Baseline universe therefore restricts
  to majors and liquid crosses**; exotics are a separate question.
- **BLOCKED** — `STR-B` (volume value area). MOGO's OANDA candle feed carries OHLC mid prices only;
  there is no volume. Not deferred — *not currently possible*, and it must not be silently replaced
  with a tick-count proxy pretending to be volume.
- **BLOCKED** — carry/rate differential data. MOGO has no rates feed and no authorized provider for
  one. §3.8 cannot be tested until that is resolved through an approved source.
- `UNKNOWN` — whether MOGO's available candle history is deep enough for a credible
  development/holdout split at H4/D across a full regime cycle. **This must be measured before the
  specification is frozen**, because a holdout too short to contain a regime change cannot falsify a
  regime-dependent claim.
- **CONSTRAINT** — historical evaluation depends on `fetchCandlesRange()`, whose completeness
  contract classifies short pagination as `PARTIAL`. Any dataset assembled for this track must
  record its completeness state per instrument. A `PARTIAL` dataset is not a research input.

---

## 9. What MOGO-023 explicitly did NOT do

- Did **not** implement an evaluator.
- Did **not** run a backtest, or a single-pair "quick look".
- Did **not** tune, fit, or select any parameter from a result.
- Did **not** promote this track past `RESEARCH THESIS`.

The next legitimate step is **not** to test this. It is to measure the §8 data-availability question
and then write the frozen baseline specification. Testing before freezing the spec is how a thesis
becomes an overfit.
