# MOGO-002.8A — ALEX v1.1 Strategy Reconciliation

**Date:** 2026-07-30 · **HEAD:** `a332d04` · **Current version:** `alex_g_sr_v1` / `alex_g_sr_v1.impl.1` / `APP_VERSION` 12.6.0

**Inputs (only these two):**
1. [`ALEX-CURRENT-IMPLEMENTATION-SPECIFICATION.md`](ALEX-CURRENT-IMPLEMENTATION-SPECIFICATION.md) — repository truth, MOGO-002.8A
2. [`audit/alex-canonical-rule-register.json`](audit/alex-canonical-rule-register.json) — 41 educator rules from 9 ingested ALEX_G sources, with [`audit/alex-implementation-fidelity-matrix.json`](audit/alex-implementation-fidelity-matrix.json)

**No research was expanded. No code was written or modified.**

---

> ## ⚠️ Governance precondition — one paragraph, then the reconciliation proceeds
>
> Three standing constraints bear on this document and are unresolved: **KEREV-A** is open (stop
> placement); **all 341 library claims sit at `emerging`** so `POLICY-001` currently permits no
> promotion; and **`DECISION|MOGO|20260727|004`** records that `alex_g_sr_v1`'s rules are MOGO's own,
> not the educator's — making any "modify the engine to match the educator" action a lineage decision
> the Authority has not yet taken (KEREV-B). **This document is therefore written as a decision-ready
> plan, not an authorisation.** Every ADD/MODIFY row below states the decision it depends on. Nothing
> here should be executed before those decisions are made.

---

# SECTION 1 — EXECUTIVE SUMMARY

## 1.1 Disposition counts

| Disposition | Rules | Share |
|---|---|---|
| **KEEP** | **23** | 56% |
| **DEFER** | **12 groups** (24 rules) | 34% |
| **REMOVE** | **8** | — |
| **MODIFY** | **4** | — |
| **ADD** | **1** | <1% |

Percentages are of the **41 educator rules** in the canonical register. REMOVE and MODIFY carry no
percentage because they act on implementation artefacts (dead keys, dead computation, statistics
defects) rather than on educator rules — only R-7 and R-8 map to a register entry.

## 1.2 The finding that determines the whole plan

**Only 6 of 41 educator rules are deterministic.** Every non-deterministic rule requires MOGO to
author a parameter the educator never stated — which is precisely the action under dispute in
KEREV-A. **Determinism is therefore the gate for ADD and MODIFY**, and applying it honestly produces
an almost-empty ADD list.

**Exactly one educator rule can be implemented today without inventing anything: the Monday–Wednesday
entry restriction.** It is explicit, deterministic, and the evaluation function (`isPreferredTradingDay`,
`index.html:5726`) already exists and already returns exactly Mon–Wed. MOGO computes it and discards
the result.

Every other divergence — including the three largest — is blocked on a missing parameter:

| Divergence | Why it cannot be actioned now |
|---|---|
| **No confirmation gate** (largest trade-eligibility gap) | The qualifying pattern family is ambiguous; the educator-referenced video could not be identified |
| **Stop anchor differs** (zone boundary vs rejection formation) | KEREV-A open; buffer distance absent from all 9 sources |
| **Fixed 2R vs stated minimum** | No target-selection procedure exists above the floor |

## 1.3 What is actually actionable now

**MODIFY and REMOVE together form a self-contained work package that touches no trading logic.** All
4 MODIFY rows are measurement/observability defects found in the implementation itself — none depends
on educator evidence, KEREV-A, or D2. Six of the eight REMOVE rows (R-1…R-6) are dead
configuration and dead computation; R-7 and R-8 need decisions first.

**This package is the only part of ALEX v1.1 that can proceed on repository evidence alone.**

## 1.4 Sequencing

```
Phase A (unblocked)   MODIFY 4 observability defects + REMOVE 6 dead items (R-1…R-6)
                      R-7 (ALEX_SCORE_V2) and R-8 (setup ordering) need decisions first
                      → no trading behaviour changes; no decision required

Phase B (KEREV-A)     Stop anchor / buffer / short-side  → currently DEFER
Phase C (AXG-03)      Confirmation gate                  → currently DEFER
Phase D (Phase C)     Mon–Wed filter                     → the single ADD, sequenced after C
Phase E (D2)          Anything requiring promoted rules  → blocked library-wide
```

**The single ADD is placed after Phase C deliberately** — see §3.1 for the scope dependency.

## 1.5 What this plan does not do

It does not change any stop, target, entry price, position size, or qualification threshold. **After
Phase A, ALEX would take exactly the same trades it takes today.**

---

# SECTION 2 — KEEP

**23 rules.** The implementation stands unchanged.

### 2.1 Educator-convergent — implementation already consistent

| Rule | Current implementation | Educator evidence | Conf. | Det.? | Action | Rationale |
|---|---|---|---|---|---|---|
| **AXR-001** Zone role | `alexGZoneRole` (2735): above→support, below→resistance, within→inside | EXPLICIT, `CLAIM\|ALEX_G\|20260729\|006` — S/R, supply-demand and AOI are one concept | High | No | **KEEP** | `FUNCTIONAL_MATCH`. Positional derivation is a faithful mechanisation of a definitional concept. Nothing to change |
| **AXR-004** Break-and-retest | `alexGEvaluateBreakRetest` (3147), first-class setup type `B_breakRetest` | EXPLICIT, `CLAIM\|ALEX_G\|20260729\|004` — continuation pattern | High | No | **KEEP** | `FUNCTIONAL_MATCH`. The full ordered sequence (break → strictly-after retest → side match → one per break cycle) is enforced |
| **AXR-007** Setups only at zones | `alexGRunZoneEngine` (2996) — setups are only ever evaluated at detected zones | EXPLICIT but **comparative** (*"most effective"*), not mandatory | High | No | **KEEP** | Implementation satisfies a comparative preference by construction. Recording it as a hard requirement would over-read the source |
| **AXR-040** Percentage risk | `riskAmount = balanceBefore * (riskPercent/100)` (4012) | EXPLICIT, **2 distinct sources** (`…098`, `…096`, `…093`) — percentage of balance, never a fixed dollar amount | **High** | **Yes** | **KEEP** | Strongest agreement in the corpus and the only educator rule family backed by two sources. Implementation matches exactly |
| **AXR-043** Risk stability | `riskPercent` is a constant — never raised after wins or lowered after losses | EXPLICIT, deterministic | High | **Yes** | **KEEP** | Satisfied **by construction** (a constant cannot drift). No mechanism needed |
| **AXR-050** No intervention to stop | Stop frozen at entry; `alexGUpdatePositionExcursionAndCheckExit` (4307) returns only `{hitStop,hitTarget,exitVal}` | ILLUSTRATIVE — demonstrated once, never stated as a rule | Medium | No | **KEEP** | Behaviour aligns. Held at ILLUSTRATIVE because one demonstration is not a rule — keeping is safe, promoting would not be |
| **AXR-051** No action before arrival | `alexGRunSetupEngine` (3349) takes no action until a setup qualifies at the zone | EXPLICIT, **3 distinct sources** — the most-repeated claim in the corpus | High | No | **KEEP** | `FUNCTIONAL_MATCH`. Note: 3 same-educator sources are repetition, not independent corroboration (`DECISION\|MOGO\|20260727\|006`) |
| **AXR-052** Target never cut early | `pos.target` never modified after creation | EXPLICIT — a preset target should run, not be cut on the dollar figure | High | No | **KEEP** | Implementation cannot cut a target early; there is no code path to do so |

### 2.2 Educator-silent, MOGO does nothing — keep the null behaviour

| Rule | Current implementation | Educator evidence | Conf. | Det.? | Action | Rationale |
|---|---|---|---|---|---|---|
| **AXR-060** Break-even | Never moves to break-even (documented MOGO choice, `APP_VERSION_LOG` v4.0) | **UNSUPPORTED** — zero mentions in 9 sources | High | No | **KEEP + relabel** | Behaviour is correct to keep. **The action is documentation**: record it explicitly as MOGO-authored in an evidentiary vacuum, not as educator agreement |
| **AXR-061** Partial profit | Takes no partials; positions close in full | **UNSUPPORTED** — zero mentions | High | No | **KEEP + relabel** | As above |
| **AXR-062** Scaling | Single entry, never adds or reduces | **UNSUPPORTED** — zero mentions | High | No | **KEEP + relabel** | As above. The one near-match in the corpus refers to scaling an *account*, not a position |
| **AXR-063** Trailing stops | Never trails | **UNSUPPORTED** — zero mentions | High | No | **KEEP + relabel** | As above |
| **AXR-092** News filter | None implemented | **UNSUPPORTED** — zero mentions | High | No | **KEEP** | Absence in both is not agreement, but there is nothing to act on |

> **The four "KEEP + relabel" rows are the cheapest integrity win in this plan.** MOGO's
> no-intervention defaults are very likely right, but "likely right" is not evidence. Labelling them
> MOGO-authored costs one documentation change and removes a standing lineage risk.

### 2.3 Engineering necessities — educator silent, MOGO must decide something

| Rule | Current implementation | Educator evidence | Conf. | Det.? | Action | Rationale |
|---|---|---|---|---|---|---|
| **ALEX_X_002** Entry-delay gate | `maxLiveEntryDelayPips = 5`; rejects fill >5 pips from `qualificationClose` (3991) | None — source never addresses live execution latency | High | **Yes** | **KEEP** | Live-execution necessity with no educator analogue. Removing it would allow unbounded chasing |
| **ALEX_X_003** Signal staleness | `{H1:60, H4:240, D:1440, W:10080}` minutes (4177) | None — source never addresses signal age | High | **Yes** | **KEEP** | One bar-period per timeframe. Deterministic and self-consistent |
| **ALEX_X_004** Activation cutoff | `qualificationTimestamp >= activatedAt` (4165) | None | High | **Yes** | **KEEP** | Prevents backfilling a paused period on resume. Pure safety |
| **—** One trade per pair+TF | `openPositions.some(p=>p.pair===… && p.timeframe===…)` (3972) | None | High | **Yes** | **KEEP** | Concurrency control with no educator analogue. See §6.12 for the exposure question it raises |
| **—** Duplicate-signal guard | Four-store check: `tradedSignals`, open, closed, journal (3959) | None | High | **Yes** | **KEEP** | Correctness guard |
| **—** Ledger integrity guard | `commitAlexGLedger()` with snapshot rollback (4466) | None | High | **Yes** | **KEEP** | Data-integrity guard. Restores account and journal together on rejection |
| **—** Ambiguous-candle resolution | Same-candle stop+target → Loss, `ambiguous:true` (4338) | None | High | **Yes** | **KEEP** | Conservative and flagged, never hidden |

### 2.4 Record-only metadata — keep as metadata

| Rule | Current implementation | Educator evidence | Conf. | Det.? | Action | Rationale |
|---|---|---|---|---|---|---|
| **AXR-002** Trend definition | `alexGComputeTrendContext` (3199) computes UPTREND/DOWNTREND/RANGE_MIXED; **no gate reads it** | EXPLICIT — HH/HL and LH/LL defined | High | No | **KEEP as record-only** | The educator's own soft framing (*"increases the odds"*, never a requirement) matches record-only treatment. Promoting it to a gate needs a swing-significance threshold that does not exist |
| **AXR-006** Recursive chaining | Not modelled — a retested zone does not become a new structure point | EXPLICIT, deterministic | Medium | **Yes** | **KEEP** (`NOT_APPLICABLE`) | Deterministic in principle, but MOGO's zone model has no representation for it. Implementing it is an architecture change, not a rule change |
| **AXR-090** Market selection | Fixed 12-pair `SCAN_PAIRS` (2003) | EXPLICIT — applies to all instruments (a **non**-restriction) | Medium | No | **KEEP** | The educator states no restriction; MOGO narrowing the universe cannot violate a non-restriction |
| **AXR-070** HTF more respected | `htfPriority {W:4,D:3,H4:2,H1:1}` orders competing setups (`alexGSetupSortComparator`, 3589) | EXPLICIT but **comparative** — no ranking, weighting or threshold stated | Medium | No | **KEEP as record-only** | `PARTIAL_MATCH`. Ordering realises the comparative preference without inventing a weight. **Note the defect in §5:** the comparator is called only from the replay engine, so `htfPriority` does not influence the live path |
| **AXR-053** Alarm on missed entry | Not modelled — no alert-and-wait mechanism | ILLUSTRATIVE — set an alarm rather than chase | Low | No | **KEEP** (`NOT_APPLICABLE`) | Describes human behaviour with no automation analogue. MOGO's equivalent is the entry-delay gate (`ALEX_X_002`), which already refuses to chase |
| **AXR-091** Market-condition filter | None implemented | **UNSUPPORTED** — MARKET_CONDITIONS carries 19 claims yielding **0 rules**; claims describe the market, none gates a decision | High | No | **KEEP + relabel** | MOGO's choppy-zone filter (`ALEX_X_005`, ≥3 penetrations / 50 bars) is a **MOGO-authored** condition filter with no educator counterpart. Keep the behaviour; record the authorship, as with §2.2 |

---

# SECTION 3 — ADD

**One rule.** It is the only educator rule that is explicit, deterministic, and implementable without
inventing a parameter.

### 3.1 Monday–Wednesday entry restriction

| Field | Value |
|---|---|
| **Rule name** | Day-of-week entry restriction |
| **Current implementation** | **None.** `alexGComputeSessionMetadata` (3225) computes `insideCurrentStrategyPreferredWindow` using `isPreferredTradingDay(date)` and stores it on every setup and position record. **No gate reads it.** `ALEX_X_007` records this as *"a deliberate design choice, not a source gap"* |
| **Educator evidence** | `CLAIM\|ALEX_G\|20260728\|083` — *"Entries on this confirmation are restricted to Monday, Tuesday and Wednesday"* (`rule_statement`, `direct_explicit`). Supported by `CLAIM\|ALEX_G\|20260728\|078` — *"a valid confirmation at the wrong time is not to be traded"* |
| **Confidence** | **Medium** (see scope caveat) |
| **Deterministic?** | **Yes** — `getUTCDay() >= 1 && <= 3`. No threshold to invent |
| **Recommended action** | **ADD**, config-gated, **sequenced after the confirmation decision (Phase C)** |
| **Engineering rationale** | The mechanism already exists and already returns exactly Mon–Wed (`isPreferredTradingDay`, 5726). The gate would be a single conditional reading a value already computed and stored. No new parameter, no new function, no ATR, no threshold |

> **⚠️ Scope caveat — the reason confidence is Medium, not High.** The claim reads *"entries **on this
> confirmation**"* — it is scoped to the confirmation setup taught in that source. **MOGO implements
> no confirmation gate at all** (AXR-011, DEFER). Applying Mon–Wed to MOGO's setups would apply an
> educator constraint scoped to a setup type MOGO does not implement.
>
> **This is why the single ADD is sequenced after Phase C rather than executed first.** If the
> Authority resolves the confirmation gate, the scope resolves with it. If the Authority prefers to
> act sooner, the defensible interim is to add it **config-gated and default-OFF**, which makes the
> filter testable in replay without changing live behaviour.

**Impact if enabled:** materially reduces trade eligibility — roughly 3 of 5 trading days become
eligible. This is a real behavioural change and should not be enabled silently.

### 3.2 Nothing else qualifies for ADD

Every other candidate fails the determinism gate:

| Candidate | Blocked by |
|---|---|
| Confirmation gate (AXR-011) | Pattern family ambiguous — DEFER §6.1 |
| Session-hour filter (AXR-081) | Hours exist as on-screen pixels, never spoken — DEFER §6.4 |
| Risk bands by account type (AXR-042) | Requires an account-type model MOGO does not have; affects only the 3–5% band MOGO never uses — DEFER §6.10 |
| HTF→LTF entry split (AXR-010) | Which lower timeframe is unspecified — DEFER §6.7 |
| Day-trade vs swing modes (AXR-072) | Mode concept does not exist; source phrasing is a default, not a constraint — DEFER §6.8 |

---

# SECTION 4 — MODIFY

**Four rows. All are measurement or observability defects found in the implementation itself.** None
depends on educator evidence, KEREV-A, or D2. **None changes trading behaviour.**

| # | Rule name | Current implementation | Educator evidence | Conf. | Det.? | Action | Rationale |
|---|---|---|---|---|---|---|---|
| **M-1** | Realised R on close | `resultR = result==='Win' ? plannedRR : -1` (4461) — a **fixed** ±R, described in-code as *"not recomputed from actual slippage"* | **None — not an educator question** | High | Yes | **MODIFY** | Every win records exactly `+2.0`R regardless of the actual exit. Net R on the dashboard therefore does not reflect slippage, spread, or ambiguous-candle exits. **Reported performance is systematically detached from realised performance.** The inputs to compute it correctly (`entry`, `exitPrice`, `stop`, `pip`) are all already on the record |
| **M-2** | Dashboard P&L baseline | `pnlTotal = alexGAccount.balance - 10000` (4732) — a **hardcoded literal** | None | High | Yes | **MODIFY** | The starting balance is a literal duplicated from the account default (2100). If an account were ever restored from a state with a different starting balance, P&L would be silently wrong. Should read a stored starting balance |
| **M-3** | Drawdown label | Labelled **"Current drawdown"**; computes a running **peak-to-trough maximum** over all decided trades (4730) | None | High | Yes | **MODIFY** | The label and the calculation disagree. Either relabel to "Max drawdown" or compute current drawdown. **Relabelling is the lower-risk fix** — the existing number is meaningful, just misnamed |
| **M-4** | Drawdown iteration order | Iterates `closedPositions` in stored order, which is **newest-first** (closes are `unshift`ed, 4482) | None | High | Yes | **MODIFY** | A peak-to-trough equity walk over a reversed series does not produce the drawdown of the actual equity curve. This is a genuine calculation defect independent of M-3's naming issue |

**Why these four and nothing else:** they are the only divergences in the entire reconciliation that
can be corrected using repository evidence alone, with no educator input and no invented parameter.
M-1 and M-4 are correctness defects; M-2 and M-3 are robustness and naming.

> **Scope discipline:** all four live in reporting and statistics. **None touches
> `alexGConstructLivePosition`, `alexGEvaluateBreakRetest`, `alexGEvaluateRepeatedReaction`, or any
> protected function.** After these changes ALEX takes identical trades; only the reported numbers
> become correct.

---

# SECTION 5 — REMOVE

**Seven rows.** Dead configuration, dead computation, and one unresolved status.

| # | Rule name | Current implementation | Educator evidence | Conf. | Det.? | Action | Rationale |
|---|---|---|---|---|---|---|---|
| **R-1** | `config.zoneTimeframes` | Declared `['H1','H4','D','W']`; **appears exactly once in the file** — its own declaration. All three timeframe loops use a hardcoded literal | n/a | High | Yes | **REMOVE or wire** | Dead key. A future edit to it would silently have no effect — the exact failure mode recorded as `FIDELITY-DISC-001`. **Removing is safer than wiring**, since wiring touches protected functions |
| **R-2** | `config.requireWick` | Declared `false`; read by nothing | `hubTestStandardizations`: *"Wick strength is recorded but never required"* | High | Yes | **REMOVE** | Dead key. Carried into every `configurationSnapshot`, implying a control that does not exist |
| **R-3** | `config.minWickRatio` | Declared `0.0`; read by nothing | As above | High | Yes | **REMOVE** | Dead key, same reasoning |
| **R-4** | `config.maxZoneAgeBars` | Declared `null`; read by nothing. `zone.ageBars` is maintained every candle and never read | `hubTestStandardizations`: *"Zone aging is OFF by default"* | High | Yes | **REMOVE** | Dead key **and** dead computation. The educator favours older, more-touched zones, so no ageing rule is wanted — the key implies an unimplemented capability |
| **R-5** | `zone.quality` | Initialised at creation, **rewritten on every candle** (2986), **read by nothing** — appears elsewhere only in comments. Persisted into `fxhub_alexg_zones` | n/a | High | Yes | **REMOVE** | Dead computation running on every zone on every candle. `alexGCorrectedQuality` (3137) is the value that actually gates. Two coexisting choppy calculations, one inert, is a standing misreading risk |
| **R-6** | `alexGAutoTrading.tradedToday` | Maintained but described in-code as *"only a secondary, non-controlling guard"* | n/a | High | Yes | **REMOVE** | Suggests a daily-trade limit that does not exist. `tradedSignals` is the controlling guard |
| **R-7** | `ALEX_SCORE_V2` | Second strategy claiming the ALEX name; `alexV2AutoTrading.enabled === false`, nothing flips it (`ALEX_X_008`, 14952) | n/a | High | n/a | **REMOVE, retire, or ratify** | **This is OD-7, open since MOGO-002.5.** Two strategies claiming one name will confuse every future report. Needs an explicit status decision, not silent persistence |
| **R-8** | Unreachable setup ordering | `alexGSetupSortComparator` (3589) — the only consumer of `config.htfPriority` — is called **solely** from `alexGRunSetupReplay` (3617). The live path iterates `alexGSetupState.filter(...)` in array order (4205) | AXR-070 EXPLICIT but comparative | High | Yes | **REMOVE or wire** | **`htfPriority` has no effect on live trading.** When several setups qualify in one evaluation, the order attempted is array order, not timeframe priority — and because of the one-per-pair+timeframe rule, order can decide which setup gets the slot. Either wire the comparator into the live loop or record that priority is replay-only |

**R-1 through R-6 are pure hygiene** — no behaviour changes, and each removes a false affordance that
a future engineer could reasonably mistake for a working control.

**R-7 is a decision, not a task.** It is listed under REMOVE because that is the recommended
disposition, but retiring or ratifying are equally valid answers; the requirement is that one be chosen.

---

# SECTION 6 — DEFER

Twelve groups. Each is blocked on a named decision or a missing parameter — **not on engineering effort.**

### 6.1 Confirmation gate — **highest-priority defer** (AXR-011, AXR-012, AXR-015)

| Field | Value |
|---|---|
| **Current implementation** | **No candlestick-confirmation gate exists.** Entry is the qualification candle's close. No engulfing, doji, Morning Star, body-percentage, close-location or volume test exists anywhere |
| **Educator evidence** | EXPLICIT and **binding**: *"in order for us to take a trade we need to have a bullish engulfing Candlestick confirmation"*. Reinforced by AXR-015 — a structurally ideal setup was **declined on camera** because the engulfing never appeared |
| **Confidence** | **High** that a confirmation is required · **Low** on which patterns qualify |
| **Deterministic?** | **No** — three inconsistent phrasings: *"bullish engulfing"*, a demonstrated **Morning Star** (3 doji + engulfing), and *"rejection candlesticks"* generally |
| **Action** | **DEFER** pending `AXG-03` |
| **Rationale** | This is the **largest trade-eligibility divergence in the audit** — the educator's single hardest entry precondition is entirely absent. It cannot be added now because implementing it means MOGO selects the pattern set, and the bearish mirror is never stated. The educator-referenced video (5:33, source #9) **could not be identified**: it is an on-screen card, and date-filtering all 200 catalogue titles eliminated the strongest candidate |
| **Unblocks** | The single ADD (§3.1), whose scope depends on this |

### 6.2 Stop anchor and buffer — **KEREV-A** (AXR-020, AXR-021, AXR-022)

| Field | Value |
|---|---|
| **Current implementation** | `stop = zoneLow − 0.25×ATR` (buy) / `zoneHigh + 0.25×ATR` (sell). Anchor is the **frozen zone boundary**; ATR is as of the qualification bar. Short side mirrored symmetrically |
| **Educator evidence** | AXR-020 EXPLICIT and universalised — *"the same thing every single time your stop-loss is right under it"*, anchored on the **rejection formation at the retest**. AXR-021 buffer: **UNSUPPORTED, zero mentions in 9 sources — no ALEX_G claim mentions ATR at all**. AXR-022 short side: **never stated** |
| **Confidence** | **High** on the relationship · **None** on the buffer · **None** on the short side |
| **Deterministic?** | **No** — the anchor is deictic with three readings; the buffer has no unit |
| **Action** | **DEFER** pending **KEREV-A** |
| **Rationale** | The relationship matches, but **the anchors are different objects** — a rejection wick routinely extends beyond the zone boundary, so the stop distances differ. `0.25 ATR` is entirely MOGO-authored. Changing the anchor without the buffer would replace one MOGO-authored parameter with another while adding an unresolved three-way anchor choice. **Deferring is the only action that does not fabricate attribution** |

### 6.3 Target ratio and selection (AXR-030, AXR-031)

| Field | Value |
|---|---|
| **Current implementation** | `minRR = 2.0` applied as a **fixed** multiplier: `target = fill ± 2.0 × riskDistance`. MOGO can never take 1:3 or 1:4 |
| **Educator evidence** | AXR-030 EXPLICIT — 1:2 stated **twice as a minimum**. AXR-031 selection procedure: **UNSUPPORTED** — the four cited claims (80–100 pip average, 1:3, 1:4) are all annotated ILLUSTRATIVE, distances observed after the fact |
| **Confidence** | High on the floor · **None** on selection above it |
| **Deterministic?** | **No** — a floor without a selection rule is not evaluable |
| **Action** | **DEFER** pending `AXG-06` **and** contradiction `XCONTRA\|20260729\|004` |
| **Rationale** | Converting the fixed ratio to a floor requires a rule for choosing the level above it, which does not exist. Implementing "always exactly 1:2" is what MOGO already does, and the word *minimum* explicitly contradicts it. **Additionally contested**: `XCONTRA\|20260729\|004` (material, open) asks whether 1:2 is a floor a trade may be *set at*, or a level a preset target must never be *revised down to* — a distinction that governs whether the target may change after entry. **No further ALEX_G source can settle it; both positions are already the educator's** |
| **Note** | The parameter name `minRR` does not match its use. Renaming is a documentation fix available independently of this defer |

### 6.4 Session hours (AXR-080 session component, AXR-081)

| Field | Value |
|---|---|
| **Current implementation** | Session metadata computed and stored; **no session gate**. `getSession()` (7922) defines London/NY Overlap 12:00–15:59, London 08:00–19:59, New York 20:00–23:59 UTC |
| **Educator evidence** | The **rule** is explicit and prescriptive across 7 session claims; the **hours** are displayed on an on-screen session map and **never spoken** |
| **Confidence** | High on the rule · **None** on the parameter |
| **Deterministic?** | **No** |
| **Action** | **DEFER** pending `AXG-04` |
| **Rationale** | **No further transcript can close this** — the parameter exists in the source material as pixels, not words. Closing it requires either a source that reads the hours aloud or an Authority-approved frame-reading method, which is not a transcript-acquisition task. Using MOGO's existing `getSession()` windows would substitute MOGO's session definition for the educator's unstated one |

### 6.5 Touch minimum (AXR-005)

| Field | Value |
|---|---|
| **Current implementation** | `A_repeatedReaction` requires `touchIndex >= 3` **and** `zone.touches.length >= 4` |
| **Educator evidence** | AXR-005 EXPLICIT — *"a minimum of one structure point"* for a valid break-and-retest level |
| **Confidence** | **Low that these are the same rule** |
| **Deterministic?** | **No** — a quantified minimum over an **undefined unit**; "structure point" is never defined |
| **Action** | **DEFER** pending `AXG-07` |
| **Rationale** | MOGO appears materially stricter (4 vs 1), **but the two rules may not be comparable.** MOGO's 4-touch rule derives from a different concept — *"three confirmed reactions validate a zone; the fourth is the first trade opportunity"* — which is about **zone validation**. The educator's minimum-one is about **what makes a level valid for break-and-retest**. Treating them as the same rule and relaxing 4→1 would conflate two distinct concepts and materially loosen trade eligibility on a misreading |

### 6.6 Zone width constraint (AXR-008)

| Field | Value |
|---|---|
| **Current implementation** | `zoneClusterATRMultiplier = 0.5` bounds reaction grouping. Zone boundaries are then locked to the three reaction prices. **No minimum or maximum zone width exists** |
| **Educator evidence** | EXPLICIT **non-constraint** — *"doesn't matter the size of the box"*, subject only to leaving "enough room" for multiple touches |
| **Confidence** | High that the educator declines to constrain · Low on what should replace the parameter |
| **Deterministic?** | **No** — "enough room" is unquantified |
| **Action** | **DEFER** |
| **Rationale** | MOGO imposes a constraint where the educator explicitly declines to. **But `zoneClusterATRMultiplier` is the grouping mechanism itself** — removing it removes clustering entirely, not just the constraint. It is already flagged `EXPERIMENTAL` with a declared `sensitivityRange: [0.25, 0.5, 0.75, 1.0]` and *"not tuned against outcomes"*. Resolving it is a **sensitivity-testing question requiring replay**, which is unauthorised |

### 6.7 HTF structure / LTF entry split (AXR-010)

| Field | Value |
|---|---|
| **Current implementation** | Zones and setups evaluated on H1/H4/D/W; entry taken on the same timeframe as the zone. **No HTF→LTF split** |
| **Educator evidence** | EXPLICIT requirement — *"the actual entry signal you have to go on the lower time frame"* |
| **Confidence** | High that a split is required · **None** on which lower timeframe |
| **Deterministic?** | **No** |
| **Action** | **DEFER** |
| **Rationale** | The educator never specifies the entry timeframe; the worked example uses the 4-hour, which is itself one of MOGO's zone timeframes. Implementing a split means MOGO selects the entry timeframe. **Architecturally significant** — MOGO's H1 master clock would need a sub-timeframe entry pass |

### 6.8 Timeframe set and trading modes (AXR-071, AXR-072)

| Field | Value |
|---|---|
| **Current implementation** | Exactly H1/H4/D/W. No day-trade vs swing mode distinction |
| **Educator evidence** | AXR-071 EXPLICIT and **deterministic** — four tiers W/D/4H plus 2H/1H/30m/15m, with *"below 15-minute is not a strong timeframe"*. AXR-072 — day trade 4H/1H, swing D/W |
| **Confidence** | High on the tier list · Medium on the mode pairing |
| **Deterministic?** | AXR-071 **Yes** · AXR-072 **No** |
| **Action** | **DEFER** |
| **Rationale** | AXR-071 is one of only six deterministic educator rules, but adopting it means adding sub-H1 timeframes — an architectural change to the master clock and the dataset fetch, not a rule change. AXR-072 is immediately qualified in-source (*"depending on how approach you want to take it"*), making it a default rather than a constraint. **Its swing clause also contains a garbled word (`Inay`) that was deliberately not guessed** |

### 6.9 Break-of-structure threshold (AXR-003)

| Field | Value |
|---|---|
| **Current implementation** | `breakConfirmationCloses = 1` — one close beyond the zone in the prior-role direction. Plus `rejectionDisplacementATRMultiplier = 0.25` for reaction confirmation |
| **Educator evidence** | EXPLICIT — a body close beyond a level counts, **no minimum size** |
| **Confidence** | Medium |
| **Deterministic?** | **No** — no minimum displacement stated |
| **Action** | **DEFER** pending `AXG-07` / replay |
| **Rationale** | The implementation is consistent with "any body close counts". **Cross-educator contradicted** (`XCONTRA\|20260729\|001`): a second educator uses only major swing points. **Two educators give contradictory guidance about a number neither supplies.** Recorded as replay candidate RC-29; acquisition is unlikely to resolve it |

### 6.10 Risk bands and account type (AXR-041, AXR-042)

| Field | Value |
|---|---|
| **Current implementation** | Single `riskPercent = 1.0`, applied uniformly |
| **Educator evidence** | AXR-041 EXPLICIT, **deterministic** — three bands: conservative 0.5–1%, recommended 1–2%, high 3–5%. AXR-042 — high band confined to personal accounts and Nov–Mar |
| **Confidence** | High |
| **Deterministic?** | **Yes** (as percentages) |
| **Action** | **DEFER** |
| **Rationale** | **`riskPercent = 1.0` already sits inside both the conservative and recommended bands** — it is the single best-aligned parameter in the implementation, so there is no defect to fix. Adopting the band structure requires an account-type model MOGO does not have, and the calendar-month rule affects only the 3–5% band MOGO never uses. **Low value, non-trivial cost** |

### 6.11 Retest completion and entry price (AXR-013, AXR-014)

| Field | Value |
|---|---|
| **Current implementation** | AXR-013: reaction counts if confirmed within 1 bar and displaces ≥0.25 ATR. AXR-014: entry is the **live executable price** at poll time (`ba.ask`/`ba.bid`), gated to within 5 pips of `qualificationClose` |
| **Educator evidence** | AXR-013 EXPLICIT — retest ends when rejection candles appear, **not timed or measured**. AXR-014 ILLUSTRATIVE — entry at the confirmation candle, exact price never named |
| **Confidence** | Medium |
| **Deterministic?** | **No** |
| **Action** | **DEFER** — dependent on §6.1 |
| **Rationale** | Both quantify what the educator leaves qualitative. AXR-013's replacement is the confirmation gate itself (§6.1), so it cannot be resolved independently. AXR-014 is unresolvable in principle: the educator indicates a price on a chart and never names it, and MOGO must fill live rather than at a historical close |

### 6.12 Discretionary and non-implementable (AXR-093, AXR-100)

| Field | Value |
|---|---|
| **Current implementation** | No liquidity-sweep logic; no discretionary confluence scoring |
| **Educator evidence** | AXR-093 **OPINION** — sweeps cannot be traded alone; institutional-hunt narrative rejected. Subject of **blocking** cross-educator contradiction `KECON\|20260728\|001`. AXR-100 EXPLICIT — several gates are judgement calls with named inputs and **no thresholds** |
| **Confidence** | High that these are discretionary |
| **Deterministic?** | **No, by the educator's own framing** |
| **Action** | **DEFER permanently / NON_IMPLEMENTABLE** | 
| **Rationale** | An automated system cannot hold discretion. Every formalisation of AXR-100 is a MOGO authorship event and is already enumerated as such. AXR-093 is an opinion, cross-educator contradicted, and not intended to be implementable |

### 6.13 Blocked library-wide — D2

**Every DEFER above also sits behind a second, broader block.** All 341 library claims remain at
`emerging` confidence and **zero rule candidates exist**, because same-educator sources share one
independence group (`DECISION|MOGO|20260727|006`). Under `POLICY-001`, **no educator rule is
promotable today regardless of its content or quality.**

**Consequence:** even a perfect acquisition closing every parameter gap would leave every rule in
Sections 3 and 6 unpromotable until **D2** is decided. This bounds the value of all further
acquisition and is the single decision with the widest reach in this plan.

---

## Decisions required to execute this plan

| # | Decision | Unblocks |
|---|---|---|
| **D-1** | Approve Phase A (MODIFY ×4, REMOVE ×6: R-1…R-6) as a no-behaviour-change package | The only immediately actionable work |
| **D-2** | **OD-7** — `ALEX_SCORE_V2`: remove, retire, or ratify | R-7 |
| **D-3** | **KEREV-A** — may MOGO author the stop buffer and anchor reading, explicitly labelled? | §6.2 |
| **D-4** | **AXG-03** — resolve the confirmation pattern family | §6.1, then §3.1, then §6.11 |
| **D-5** | **XCONTRA\|20260729\|004** — is 1:2 a floor a trade may be set at, or one a target may never be revised to? | §6.3 |
| **D-6** | **D2** — concept-level consensus counting | Everything in §6 |
| **D-7** | Ratify the four no-intervention behaviours as **MOGO-authored** rather than educator-agreed | §2.2 relabel |

---

*MOGO-002.8A reconciliation complete. No code written or modified; no research expanded. This is a
decision-ready plan, not an authorisation — see the governance precondition above.*
