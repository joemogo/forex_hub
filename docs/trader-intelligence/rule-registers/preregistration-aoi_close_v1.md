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
---

## 10. Amendments before first run

**Recorded 7 September 2026, before any arm code and before any replay run.** The header rule
permits exactly this: these are changes made *before* the first run, so no run is discarded and
nothing is re-run. Each entry states the ruling and the reason it was given. Nothing above this
section has been edited — where an amendment supersedes an earlier row, that row is left exactly as
pre-registered and the supersession is stated here instead.

### 10.1 Zone construction — resolves the §3 row 2 circularity

§3 row 1 defined a touch against the zone band; §3 row 2 defined the band from the touching bodies.
Neither is computable without the other, and §2/§3 supply no seed, no grouping tolerance and no
linkage rule.

**`alexGAcceptReaction`'s ATR clustering is NOT imported.** It groups *wick* anchors at
`dailyATR(14) x zoneClusterATRMultiplier`, a multiplier the codebase itself marks EXPERIMENTAL and
untuned (`index.html`, rule `ALEX_SR_008`, "Zone tightness (no source formula)"). Importing it would
decide zone membership on wicks while counting touches on bodies, and would rest the whole arm on a
parameter nobody has justified.

The construction below uses only numbers the source already states — 3 touches, 5 pips, 60 pips —
plus the swing detector §8 already permits reusing:

1. **Touch candidates are daily swing points**, from `alexGFindSwingPoints(candles, 3)` reused
   byte-identically — not every daily bar. A **touch** is the swing bar's **body edge on the swing
   side**: `max(open, close)` for a swing high, `min(open, close)` for a swing low.
2. **A zone forms** when a newly confirmed swing body edge, together with **at least 2 earlier
   unexpired** swing body edges, fits in a band of width **<= 60 pips**. If several such sets exist,
   take the **tightest** (smallest max - min); ties break to the set containing the **most edges**,
   then to the **earliest**.
3. **Band = min..max of those edges.** If the width is **< 5 pips**, expand **symmetrically about
   the midpoint** to 5 pips.
4. **Zones never overlap.** If a candidate band overlaps an existing unexpired zone, **no new zone
   is created**: the swing counts as a **touch of the existing zone**, and the existing band **does
   not change**. First-formed wins.
5. **Formation time = the confirmation bar of the third touch.** The 3-bar swing lag applies and is
   disclosed. **Expiry = formation + 2 years.** Later touches do **not** extend expiry — the source
   runs expiry from formation.

**Reason:** introduces no tunable parameter and no wick/body hybrid. Reading "touched at least three
times" as **three reactions at the level**, rather than three bars passing through it, is recorded
here as a **MOGO choice**, not as a source-stated rule.

### 10.2 Clip anchor — resolves the §3 row 2 clip ambiguity

**Moot on the high side.** Under §10.1 a band is created only if its edges already fit inside 60
pips, so no band is ever clipped down and the "which edge moves" question never arises. On the low
side, a sub-5-pip band is expanded **symmetrically about the midpoint** to 5 pips, per §10.1(3).

Recorded explicitly: **the 60-pip figure is a formation constraint, not a post-hoc clip.**

### 10.3 Target selection — supersedes §3 row 6

§2 rule 6 says **nearest**; §3 row 6 said **most recent**. **§2.6 is the source and wins. §3 row 6
is amended and is no longer operative.**

Target = the **nearest-in-price** daily swing point beyond the entry in the trade direction — swing
high for buys, swing low for sells — from `alexGFindSwingPoints(candles, 3)`, selected among swing
points **confirmed before the signal bar**. §2.6 then applies unchanged: **planned R < 2 -> skip**;
**planned R > 4 -> target moved to exactly 4R**.

§3 row 6's *swing definition* survives intact; only its *selection* rule is replaced.

### 10.4 Equity path for P4 — fixes the construction; the criterion is unchanged

**P4's threshold is untouched: max drawdown < 30% at 0.5% HWM sizing.** Only the previously
unspecified equity path is fixed.

One **shared equity line across all 12 pairs**. Each trade is sized at **0.5% of the high-water mark
as of its own open**. Concurrent positions across pairs are allowed, one per pair.

The **deciding** drawdown is **daily mark-to-market**: every open position marked at each daily
close, plus realised P&L, peak-to-trough on that line via **`carryMaxDrawdown` unchanged**. The
**closed-trade-only** equity drawdown is reported **beside** it, for comparison with the source's
-28.8%, and **does not decide**.

**Reason:** mark-to-market is the harder test, and it is the drawdown an operator would actually sit
through. Choosing the more conservative statistic **before seeing any data** is the principled
direction.

### 10.5 Approach direction on an exact boundary close

`alexGZoneRole` is reused **as-is, with its inclusive boundaries**. A prior close sitting exactly on
a zone edge therefore reads as `inside`, which under §3 row 3 means **no approach direction and no
trade**. This is **disclosed** in `replayDisclosures` and is **not special-cased**.

### 10.6 What these amendments do not touch

Every pass/fail criterion in §5 stands exactly as pre-registered: P1, P2, P3 and P4's 30% threshold
are unchanged, as are all four fail clauses. §6, §7, §8 and §9 are unchanged.

### 10.7 Additional exploratory variant — `aoi_close_v1_bodytouch`

**Added 8 September 2026, before any arm code and before any replay run**, on the same terms as the
rest of §10. Appended after §10.6 rather than inserted, so the amendment record stays append-only.
§10.6 still holds: this variant touches no §5 criterion.

Identical to the primary arm in every respect except the **touch candidate set**: a touch is **any
daily bar whose body enters the band**, not only a daily swing point. The band is still built from
the **first three such body edges**, under the **same rules as §10.1** — width **<= 60 pips** as a
formation constraint, expansion **symmetrically about the midpoint** to 5 pips if narrower, **no
overlap** with an existing unexpired zone (first-formed wins), formation at the **third** touch, and
**expiry = formation + 2 years** with no extension by later touches.

**Reported for direction only. Not part of pass/fail** — it cannot rescue a fail and cannot upgrade
a pass, on the same terms as the §6 slices and the two §7 variants. Everything else is unchanged:
entry, stop, target selection (§10.3), costs, the shifted-zone control, and every §5 criterion.

**Why it is worth running.** §10.1 recorded "three reactions at the level", rather than "three bars
passing through it", as a **MOGO choice** and not a source-stated rule. This variant is the direct
test of that choice: it restores §3 row 1's literal reading, which §10.1 had to replace in order to
break the circularity. A large divergence between the two arms is evidence that the choice, rather
than the rule, is carrying the result — which is exactly the kind of thing a null or a pass here
would otherwise hide.

**UNRESOLVED — must be settled before this variant is built.** §10.1 obtains exactly one price per
touch by naming the swing side: `max(open, close)` for a swing high, `min(open, close)` for a swing
low. A non-swing bar has no swing side, so "such body edges" does not yet name a single price. At
least three readings are live, and they place the band differently — which moves the far edge, and
therefore the stop and planned R:

  (a) both body edges of a qualifying bar are candidate edges;
  (b) only the body edge nearer the band's current extent;
  (c) the body treated as an interval, the band being the hull of the qualifying intervals.

Recorded as UNKNOWN rather than inferred, per the project's own rule. No reading is chosen here, and
this variant is not built until one is.
