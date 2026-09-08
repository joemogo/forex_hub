# Pre-registration — `aoi_close_v1` (the "everything off" AOI arm)

**Written 7 September 2026, before any code or data.** This document fixes what counts as a pass
and a fail. Nothing below may be changed after the first replay run. If a change is needed, the
run is discarded, the change is recorded here with the reason, and the arm is re-run from scratch.

**Expected result, stated now: NULL.** Four chart-pattern arms have measured as random entries.
The prior for a fifth is zero. A null is the normal outcome and is recorded in
`NEGATIVE_ACQUISITION_LOG.md`. A pass is a surprise and earns nothing more than an operator
decision about forward paper testing.

---

## 1. Source

| | |
|---|---|
| Method | Revelio Trading, *I Tried to Improve fxalexg's Trading Strategy* (YouTube, `HzVSi9ux1NU`), final-rules screen at ~19:30. Part 1: `nFIJ0z8_01w`. |
| Source class | `PRACTITIONER_STATED`, with an **independent external replication on a 2016–2021 / 2022–2026 train-test split**. Not peer-reviewed. Not primary data. |
| Claimed result | Profit factor 1.1–1.35, positive on 14/16 pairs, ~18.7%/yr at 0.5% high-watermark risk, −28.8% drawdown, after IC Markets costs. Edge concentrated after 2020. |
| Why it clears the bar | First candidate whose rules are fully mechanical **and** whose author used a holdout. Nothing in the 58-candidate registry has both. |
| Known weaknesses | Timeframe / pair / risk selections after the split appear full-period. Costs are ECN-raw, not OANDA. Profit factors are thin. |

## 2. The rules, as stated (SOURCE_STATED)

1. **Zones:** daily timeframe, drawn "exactly as Alex teaches" — body touches ≥ 3, width 5–60 pips, expire 2 years after formation.
2. **Entry timeframes:** 2H, 1H, 30M, 15M — "they take similar trades."
3. **Sessions:** all, 24/5.
4. **Entry:** first candle that closes inside a daily zone. No trend, no bias, no pattern, no retest. Buy at support, sell at resistance.
5. **Stop:** 5 pips below the support for buys, 5 pips above the resistance for sells.
6. **Target:** nearest daily swing point. Under 2R → skip. Over 4R → cap at 4R.
7. **One open trade per pair.**
8. **Risk:** 0.5% of high-water mark (sizing only; not part of the replay's R figures).

## 3. MOGO decisions where the source is silent (recorded as choices, not rules)

| gap | MOGO choice | why |
|---|---|---|
| What is a "touch" | Daily candle **body** enters the zone band | Alex uses bodies for everything (part 1). |
| Zone bounds from touches | Band from lowest to highest touching body edge, clipped to 5–60 pips | Simplest reading. |
| Support vs resistance | Support if the entry-TF close before the qualifying close was **above** the zone; resistance if **below**. Price that opens inside a zone with no prior outside close: no trade. | "Buy at support, sell at resistance" needs an approach direction. |
| "Support" / "resistance" edge for the stop | Zone low for buys, zone high for sells | Stop is therefore 5 pips beyond the far edge. Risk = (entry − far edge) + 5 pips, so 5–65 pips. |
| Zone broken by a body close | **Zone stays valid until expiry.** No break invalidation. | Revelio tested break-count invalidation; every variant was worse. Follow the source. See §7 for the exploratory variant carrying the operator's strict broken-AOI rule. |
| "Daily swing point" | Most recent daily swing high (for buys) / low (for sells) beyond the entry, using the same swing definition ALEX's zone engine uses | Reuse, don't invent. Record the definition used. |
| Entry price | **Open of the bar after the qualifying close** | Matches every other MOGO control arm. Conservative relative to the source (he enters at the close). Disclosed in `replayDisclosures.entryNote`. |
| Re-entry after a trade closes | Allowed on the next fresh "first close inside" event for that zone (price must have closed outside first) | Rule 4 + rule 7 together. |
| Pairs | The 12 `SCAN_PAIRS` | So results compare directly with the four arms already run. Revelio's 16 are not fully listed. |

Every one of these is stamped into the exported package under `replayDisclosures`.

## 4. Test design

**Primary test (the only one that decides):**
- **Instrument set:** the 12 pairs pooled.
- **Entry timeframe:** **H1**. (Source says the four TFs take similar trades; H1 is the one OANDA history covers for the full window. M15 history is ~1.6 years at the 40,000-bar cap.)
- **Window:** **2022-01-01 → 2026-05-31** — Revelio's own out-of-sample period. Bars before 2022-01-01 may be used only for zone formation, never for a trade.
- **Costs:** OANDA's **real per-bar spread** from bid/ask at entry, charged on every trade. If bid/ask is unavailable for a bar, the measured forward-corpus median (9.8% of risk) is charged and the trade is flagged. Both **gross** and **net** figures reported; **net decides**.
- **Sizing:** fixed 1R per trade for all expectancy figures. Compounding (0.5% HWM) computed separately for the drawdown figure only.

**Control arm (same pass, same bars):** identical rule on zones **shifted by half their own width**. If real zones do not beat shifted zones, the result is "closing into any band and fading it," not "AOIs work."

**Random-entry benchmark:** from `mfeR`/`maeR` (magnitude convention — check before use), the reach rate at **+1R and +2R**. Both levels sit at or below the 2R minimum target, so MFE is not truncated there and no geometry matching is needed. Coin predicts 50.0% and 33.3%.

## 5. Pass / fail — fixed now

The arm **survives** only if **all four** hold on the primary test:

| | criterion |
|---|---|
| **P1** | Net expectancy (after real spread) **> 0**, with the 95% interval **excluding zero**. |
| **P2** | Reach rate at +1R exceeds 50.0% by **at least 2 standard errors**, and at +2R exceeds 33.3% by at least 2 SE. |
| **P3** | Net expectancy of real zones minus shifted-zone control **> 0**, two-sided **p < 0.05** (one pre-registered comparison; no correction). |
| **P4** | At 0.5% HWM sizing over the window, max drawdown **< 30%**. Carry rule, same reason. |

Anything else is a **FAIL**. Specifically:
- A positive gross figure with a negative net figure is a fail.
- Passing P1 while failing P2 is a fail (and a measurement to investigate — it means the exit, not the entry, is carrying the number).
- Passing on one timeframe or one subset of pairs while failing pooled is a fail.
- A positive result confined to 2020+ or any sub-window is a fail. The window is the window.

**On fail:** record in `NEGATIVE_ACQUISITION_LOG.md` with the net figure, the P2 reach rates, and the control result. Revelio's videos stay in the registry as an external replication of `alex_g_sr_v1`'s null (part 1) and as a tested-and-failed repair (part 2).

**On pass:** nothing is authorized. `paperTrading` stays `false`. The operator decides whether a forward paper test is worth the cost of splitting the ~5 trades/week forward stream across a second strategy. **Paper-trading readiness: not assessed.**

## 6. Exploratory slices (cannot rescue a fail, cannot upgrade a pass)

- Per pair (12), per entry TF where history allows (2H, 30M, 15M — up to 3). **Šidák for 15 comparisons: two-sided |z| > 2.94.**
- Reported for direction only. A slice that clears 2.94 with the pooled result failing is written up as "worth a separately pre-registered test," never as a result.
- Support-side vs resistance-side, and stop-size bands — reported, uncorrected, descriptive.

## 7. Two variants run in the same pass, both exploratory

| variant | what changes | why it's here |
|---|---|---|
| `aoi_close_v1_strictbreak` | Zone removed on the first daily body close through it (the operator's own broken-AOI rule) | Tests the rule the operator trades manually, against the source's "keep it" choice. Reported as a difference with a CI. Not part of pass/fail. |
| `aoi_close_v1_daily_htf` | Adds Alex's paired HTF bias (W+D or D+4H) back as a gate | Directly tests Revelio's claim that HTF bias hurts. Not part of pass/fail. |

## 8. Build constraints (for Claude Code)

- **Replay only.** `capabilities.paperTrading === false`; a fixture fails if it changes.
- The seven live entry points (`alexGLivePollTick`, `alexGCheckLivePositions`, `alexGAttemptOpenLivePosition`, `alexGEvaluatePairForLiveSetups`, `alexGConstructLivePosition`, `checkAutoTrades`, `scanAll`) reference nothing in this arm — asserted.
- **No protected function modified.** Zone building is a new, separate function even if ALEX's is close; if reused, reused byte-identically. Exits via `alexGWalkOutcome` / `alexGComputeMAEMFE` unchanged.
- **Look-ahead proved by truncation** on every trade's own signal bar (CRT-1 shape, not the first version). Zone formation, swing-point target, and any ATR all derive from the prefix only.
- **Whole-page parse fixture** (PSY-P1 shape) — the arm must load in the real page.
- **Firing-rate fixture** on a deterministic random walk: both arms must fire a workable and balanced number of times, or the control is theatre.
- Export is a `REPLAY_RUN` evidence package carrying `realizedR`, `plannedR`, `mfeR`, `maeR`, stop size in pips, spread charged in pips and in R, approach side, zone id, variant id, and every §3 choice under `replayDisclosures`.
- **Reported for every arm and variant:** n, win %, gross and net expectancy with CI, **median and mean** planned R, median stop pips, share of stops under 5 pips (should be 0 by construction — print it anyway), reach rates at +1R/+2R with SE, max drawdown at 0.5% HWM.
- Fixtures mutation-verified. Protected drift 0/64, 0/4.
- Main JXA suite cannot run in the Linux sandbox — say so in the rundown if that's where it's built.

## 9. What this test does not establish

- It measures **this implementation on OANDA H1 data over 2022–2026 for 12 pairs.** Not Revelio's code, not his data, not his 16 pairs.
- A null does not prove Revelio's result was noise; it establishes that the stated rules do not carry an edge here, at these costs. Those are different claims and only the second will be supported.
- A pass does not establish an edge. It establishes that one pre-registered test survived and that a forward test is worth an operator decision.