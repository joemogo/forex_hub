# Validation Queue

**Updated:** 2026-07-29 (source #11, **third educator**) · **Entries:** 33 · **Claims in library:** 310, all `emerging`

What each claim is waiting on before it could exceed `emerging`. Populated per
`DECISION|MOGO|20260727|003` (confidence rises only via independent corroboration, replay, paper
trading or historical testing).

> ### The structural fact this queue exists to make visible
>
> Two mechanisms now bound every claim in the library:
>
> 1. **`DECISION|MOGO|20260727|006`** — same-educator repetition shares one independence group, so a
>    trader restating himself never corroborates.
> 2. **Trader-scoped claim fingerprints** — `compute_claim_fingerprint()` includes `traderId`, so two
>    educators asserting the same thing produce two separate claims that never merge.
>
> **Together these leave replay validation as the only remaining route to `supported`.** That is a
> defensible position — a trader repeating himself and a second trader agreeing are both weaker than
> a test — but it means the "independent corroboration" route in DECISION 003 is currently
> unreachable in practice. Flagged for owner review; the proposed fix is Concept-level consensus
> counting (`CROSS-STRATEGY-ANALYSIS.md` §8 D2), not relaxing either mechanism.

---

## Priority 1 — Blocked on replay, and replay is specified

| Claim | Rule | Waiting on | Feasible? |
|---|---|---|---|
| `ALEX_G\|…\|022`, `\|20260728\|007` | Body-close structure shift | **RC-12** | ✅ needs price data only |
| `ALEX_G\|…\|020` vs `TJR\|…\|065` | Bodies vs wicks (**contradiction**) | **RC-13** | ✅ cheapest decisive test in the library |
| `ALEX_G\|…\|016`, `\|20260728\|002` | HH/HL and LL/LH reassignment | **RC-19**, gated by RC-16 | ⚠️ needs a pivot definition |
| `ALEX_G\|20260728\|005` | Visual slope is a trap | **RC-14** | ✅ |
| `ALEX_G\|20260728\|006`, `\|008` | Structure inside ranges; any size counts | **RC-15**, **RC-17** | ✅ |
| `TJR\|…\|018`, `\|020` | Step 2B pre-market manipulation | **RC-01** | ✅ needs ES/NQ data |
| `TJR\|…\|038` | Order/breaker block redundancy | **RC-02** | ✅ testable against JVM data MOGO holds |
| `ALEX_G\|20260728\|025` vs `TJR\|…\|006` | **Can a strategy be built on liquidity sweeps?** (`blocking`) | **RC-20** | ✅ price data only — settles the library's only blocking contradiction |
| `ALEX_G\|20260728\|022` vs `TJR\|…\|036` | Why price sweeps levels (mechanism) | **RC-21** (partial) | ⚠️ clustering testable; **intent is not** — no dataset can establish it |
| `ALEX_G\|20260728\|035`, `\|038` | **Two-timeframe-sync gate** — first quantified rule in the library | **RC-22** | ✅ multi-timeframe price data only |
| `ALEX_G\|20260728\|040`, `\|041`, `\|042` | The LH/LL box constraint on zone selection | **RC-23** | ✅ needs no entry model at all |
| `ALEX_G\|20260728\|047` vs `\|028` | Potential vs completed lower high (**within-educator contradiction**) | **RC-24** | ✅ price data only |
| `ALEX_G\|20260728\|046`, `\|048`, `\|049` | Sell at a lower high; 4H structure point; wait for BOS on first approach | **RC-24** (shares the harness) | ✅ |
| `ALEX_G\|20260728\|065`, `\|063`, `\|056` | **The ~70% next-day continuation setup** — the most precisely specified claim in the library | **RC-25** | ✅ daily + 4H data. Fully stated as a countable conditional |
| `ALEX_G\|20260728\|087` vs `\|082` | **What waiting for the session actually costs** (within-source contradiction) | **RC-26** | ✅ intraday data; ⚠️ session hours not in the source |
| `ALEX_G\|20260728\|060`, `\|068`, `\|070`, `\|074` | Closed-candle gate; only at a level; side must match; pro-trend only | **RC-25/26** harness | ✅ the four together are a complete, mechanical trigger definition |
| `ALEX_G\|20260728\|083`, `\|085` | Monday–Wednesday-only restriction and its stated rationale | **RC-26** (secondary) | ✅ directly countable |
| `ALEX_G\|20260728\|117`, `\|118`, `\|119` | **Seasonal risk escalation** — the only claim in the library that changes position size | **RC-27** | ✅ testable **without** the missing stop rule |
| `RAYNER_TEO\|20260729\|035`, `\|036`, `\|037`, `\|039`, `\|007` | ⭐ **The complete RAYNER_TEO setup** — entry, stop, target and sizing all present | **RC-30** | ✅ **The library's first P&L-capable candidate.** Needs price data and nothing else |
| `RAYNER_TEO\|20260729\|019` vs `ALEX_G\|20260728\|008` | **Which highs and lows count as structure** (cross-educator) | **RC-29** | ✅ sweeps the parameter that already gates RC-12/13/19 |
| `RAYNER_TEO\|20260729\|037` vs `TJR\|…\|036` | Why price spikes past a level — **three positions now held** | ⚠️ partial | Rayner declines to explain it and gets a usable parameter anyway |
| `ALEX_G\|20260728\|136` vs `\|068`, `\|069` | **Proximity tolerance** — taught binary, demonstrated graded | **RC-28** | ✅ price data only. Measures the tolerance curve rather than assuming a threshold |
| `ALEX_G\|20260728\|125`, `\|126` | EMA as dynamic S/R, and EMA + structure convergence as the entry zone | ⚠️ blocked | **Period still unstated after two sources** — not reproducible |
| `ALEX_G\|20260728\|134`, `\|131` | Confluence counting; "worth the risk" selectivity | ⚠️ blocked | **Both are discretionary filters with no stated parameters.** The confluence list exists only on screen |

## Priority 2 — Blocked on a definition the source does not supply

| Claim | Missing | Resolution |
|---|---|---|
| `ALEX_G\|20260728\|009` (snake trick) | Pivot strength `k`; what counts as "a sharp turn" | **RC-16** sweeps `k` and reports sensitivity. **MOGO must not pick one** — that would be inventing a missing definition |
| `ALEX_G\|20260728\|012` (retracement) | Retracement depth, invalidation | **RC-18** sweeps X |
| `ALEX_G\|20260728\|014`, `\|053` ("right times" / "the proper session") | **Never defined in any of the four Alex G sources.** Named as necessary twice | Source acquisition — `BACKLOG-002/A6` |
| `ALEX_G\|20260728\|039` (10 points per timeframe) | The **maximum of the scale**. Caption garbled; 30 and 40 are both derivable | ⚠️ **MOGO must not pick one.** RC-22 tests the agreement *count*, which is unambiguous, and leaves the threshold alone |
| `ALEX_G\|20260728\|050` (four-hour EMA) | EMA period — first indicator reference in any Alex G source, and unspecified | Not reproducible as stated |
| `ALEX_G\|20260728\|079` (session windows) | **The hours themselves.** Shown as coloured bands on an on-screen map, never spoken | ⚠️ **MOGO must not import TJR's sessions.** RC-26 runs standard session definitions and reports sensitivity |
| `ALEX_G\|20260728\|084` (80–100 pip target) | Whether it is a selection rule or a past average; instrument; timeframe | Descriptive as stated. **First target-shaped statement in five sources** |
| `ALEX_G\|20260728\|086` (day-rule overrides) | "shorter" TP, "very strong" confirmation, "a lot of" momentum | Three unquantified overrides make the black-and-white rule unfalsifiable in practice |
| `ALEX_G\|20260728\|059` (engulfing) | Body-engulfs-body or body-closes-beyond-range? | Different detectors, different bars. Run both in RC-25 and report sensitivity |
| `ALEX_G\|20260728\|110`, `\|113` (1:2 and 1:3 R:R) | Whether either is a **required minimum** or illustrative arithmetic | Illustrative as stated. ⚠️ **Do not combine with source #5's 80–100 pip average to derive a stop distance** — that would invent a rule the educator never stated |
| `ALEX_G\|20260728\|103`, `\|112` (funded-account rules) | Which drawdown or daily-loss limits constrain the bands | The constraint motivating the whole banding is never named |
| `ALEX_G\|20260728\|052` (B / B+ grades) | Percentage bands, explicitly deferred to a paid programme | Not derivable; not to be reconstructed by inference |

## Priority 3 — Blocked on evidence that does not exist yet

| Claim | Waiting on |
|---|---|
| All 195 ALEX_G claims | Replay. ⚠️ **A third educator has now asserted several of the same rules and it changed nothing** — trader-scoped fingerprints keep the claims separate. See the D2 decision |
| All 46 RAYNER_TEO claims | Same. Single source, single independence group |
| All 69 TJR claims | Same, for TJR |
| **Stop placement — ALEX_G** | ❌ **Still 0 across EIGHT sources.** RAYNER_TEO now supplies 6 `stop_rule` claims, but **for himself only** — borrowing them across educators would fabricate a rule. The ALEX_G gap is unchanged. Source #8 discusses 1:4 and 1:2 ratios, a $650 risk figure and a 100K account without ever placing the stop that defines that risk. Source #7 is live commentary across four pairs, discussing entries, targets and a 1:4 ratio, and never states where a stop goes. Source #6 is *about risk management* and supplies 13 `risk_rule` claims (0.5–1% / 1–2% / 3–5%) — that is risk **sizing**, not stop **placement**. Position size = risk ÷ stop distance, and the second term is missing. ⚠️ **Consequence: no Alex G claim can ever be replayed for P&L — only for trigger accuracy, reach-rate, frequency or direction.** A property of the source material, not the harness |
| **Risk per trade** | ✅ **Now evidenced** (`\|20260728\|093`–`\|114`). Blocked only on the general routes: a non-Alex-G source, or replay — and replay of a risk rule requires the stop rule it depends on |

## Not eligible for validation

| Claim | Why |
|---|---|
| `ALEX_G\|20260728\|015` — **60–75% accuracy** | `performance_hypothesis`, structurally ineligible to become a rule candidate. No sample, period, instrument, or definition of "accuracy". **Must never be treated as evidence-backed.** Blocked `critical` |
| All 6 TJR performance claims | Same |
| `ALEX_G\|20260728\|034` — **$60k/day on gold, $50k/day on GJ** | `performance_hypothesis`. No statement, date, size, risk or record, and causally attributed to the technique being sold in the same breath as a watch purchase. Blocked `critical` |
| `ALEX_G\|20260728\|054` — **$500/day** | `performance_hypothesis`, no capital base or sample. ⚠️ The published title of the same video claims **$1000/day**; the spoken content says $500 twice. **MOGO records the discrepancy and does not choose** |
| `ALEX_G\|20260728\|065` — **~70% next-day continuation** | Ineligible as a *claim* (no sample, no definitions) — but **uniquely, the underlying setup is fully specified and therefore testable as a hypothesis.** RC-25 tests the setup, not the number |
| `ALEX_G\|20260728\|089` — **$50k–$100k per day** | `performance_hypothesis`, and **internally inconsistent with the same video's own 8–10%/month benchmark and its 100K funded-account evidence** — `XCONTRA\|20260728\|006`. Blocked `critical` |
| `ALEX_G\|20260728\|100` — **8–10% per month, "anybody can do that"** | No sample, no period, and **no drawdown figure** — notable in a source about risk management. A return target stated without its drawdown is not a risk claim |
| `ALEX_G\|20260728\|102` — 100K funded, 27–28%, $28,000 | No statement or verification; the period is given inconsistently as "a single month" and "about 39 days" |
| `ALEX_G\|20260728\|122` — students earn $1,000–1,500/week | **No denominator.** "Hundreds of them" with no cohort size and no failure rate carries no information |
| `ALEX_G\|20260728\|149` — $650–700 fee → 100K funded → $5,000 per 1:2 trade | **The failure branch is absent**: no pass rate, no note that the fee is lost on breach, no reference to the drawdown rules source #6 said constrain risk. A specific provider is named. Blocked `critical` |
| `ALEX_G\|20260728\|150` — 7/12/15% per month | Third overlapping monthly-return range from this channel (`XCONTRA\|20260728\|009`). None evidenced, none with a drawdown figure. **MOGO must not average or pick** |
| `ALEX_G\|20260728\|004` — "trend is identified by market structure" | **Definitional, not empirical.** It defines trend as structure; it cannot be falsified. Only the paired claim `\|005` is testable (RC-14) |

---

## Gate

**No item here may proceed.** Replay requires an `OwnerDecision` with `replayAuthorization: true`;
all six current decisions record `false`. MOGO also holds no market data for any instrument.

**Two things must happen before any entry moves:** the owner authorizes replay, and price data is
sourced. Neither is an engineering task.
