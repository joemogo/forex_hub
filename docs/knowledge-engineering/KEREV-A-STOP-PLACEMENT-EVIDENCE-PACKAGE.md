# KEREV-A — Stop-Placement Evidence Package (v2, post-ingestion)

**Decision:** KEREV-A · review-queue record [`KEREV|058`](human-review-queue.json) · gaps `KEGAP-001` / `GAP-RISK-001`
**Milestone:** MOGO-002.7 · **Revised:** 2026-07-29 after ingesting `EVSRC|ALEX_G|20260729|001`
**Status:** ⚠️ **OPEN — not decided by this milestone. Now decidable on primary-source evidence.**
**Machine-readable:** [`MOGO-002.7-kerev-a-stop-placement-evidence.json`](MOGO-002.7-kerev-a-stop-placement-evidence.json)

> ## Answer to the question the Authority asked
>
> **KEREV-A is NOT resolved. The gap it describes has changed state.**
>
> Stop placement moved from **`ABSENT_FROM_REVIEWED_SOURCES`** to **`PARTIALLY_SUPPORTED`**.
> Alex G **does** state a stop rule, and states it as an invariant. What remains missing is narrower,
> precisely enumerable, and still blocking: **the buffer distance, the identity of the anchor, and the
> short side.** Two of KEREV-A's four options are now factually unavailable.

---

## 1. What changed

`ALEX_G` `stop_rule` claims: **0 → 2.** Stop-referencing evidence items: **5 → 10.**

The previous version of this package recorded that across 8 sources and 195 claims, five items
*referenced* a stop and **none placed one**. The ninth source places one, three times, and then
generalises it.

| | Before (8 sources) | After (9 sources) |
|---|---|---|
| `stop_rule` claims | **0** | **2** |
| Explicit stop-placement **rule** | 0 | **1** |
| Demonstrated placements | 0 | **2** |
| Stated buffer distance | none | **still none** |
| Unambiguous anchor | n/a | **still deictic** |
| Short-side rule | none | **still none** |

## 2. The three new statements, verbatim

### N-1 · `EV|EVSRC|ALEX_G|20260729|001|023` — **EXAMPLE / DEMONSTRATED PLACEMENT**
**7:52–8:17** · `claimType: stop_rule` · `evidenceType: demonstrated_behavior` · `directness: direct_demonstrated`

> *"you would have simply put your entry point right here and then you would have put **your stop loss
> right under this point**"*

The first ALEX_G evidence in nine sources that places a stop at all. States the **relationship** —
immediately beyond the rejection structure — and leaves the **anchor deictic** and the **distance
unstated**.

### N-2 · `EV|EVSRC|ALEX_G|20260729|001|026` — **EXAMPLE / DEMONSTRATED PLACEMENT**
**8:25–8:50** · `claimType: stop_rule` · `directness: direct_demonstrated`

> *"our **stop loss point would be right here** if we were to have a one to2 rward ratio"*

Second consistent demonstration, same construction. This is the trade that then **loses** — *"we would
have simply been Wicked out simply because the market had fluctuation"* — which is useful: the stop is
shown working against him and is not moved.

### N-3 · `EV|EVSRC|ALEX_G|20260729|001|028` — ⭐ **EXPLICIT RULE**
**8:59–9:16** · `claimType: stop_rule` · `evidenceType: rule_statement` · `directness: direct_explicit` · `extractionCertainty: certain`

> *"**it's literally the same thing every single time your stop- loss is right under it** you have a
> minimum of a 1 to two risk to reward"*

**This is the decisive item.** *"the same thing every single time"* generalises two chart
demonstrations into an **invariant**. It is a `rule_statement` with `direct_explicit` directness — not
a chart aside, not an example. It is the statement that moves `KEGAP-001` off `ABSENT`.

## 3. Full classification, all 10 stop-referencing items

| Classification | Count | Which |
|---|---|---|
| **`EXPLICIT_RULE`** | **1** | N-3 |
| **`EXAMPLE_DEMONSTRATED_PLACEMENT`** | **2** | N-1, N-2 |
| `INCOMPLETE` (references a stop, does not place it) | 2 | the two pre-existing "needs room" / "wrong origin invalidates it" items |
| `NOT_A_STOP_STATEMENT` | 3 | sweep-narrative opinion, 3%-of-market statistic, "set and forget" label |
| `TRADE_MANAGEMENT_NOT_PLACEMENT` | 1 | the stopped-out trade accepted without intervention |
| `LEXICAL_FALSE_POSITIVE` | 1 | *"stop losing money"* — retained deliberately |

**Discretionary guidance on placement: 0.** He never says placement is a judgement call. He says the
opposite — *"the same thing every single time."*

## 4. The repeated common structure — now there is one

All three demonstrations share one construction, and the fourth statement generalises it:

```
1. Higher timeframe: break and retest of a structure point         (4H / Daily)
2. Drop to lower timeframe for the entry signal
3. Wait for rejection: Morning Star / bullish engulfing
4. ENTRY   at the confirmation
5. STOP    immediately beyond the rejection structure   <-- "right under it", every single time
6. TARGET  minimum 1:2 risk-to-reward
7. Leave it alone until one of them is hit
```

**This is the first complete, mechanically-shaped ALEX_G trade in the library.** The educator names it
himself at 9:57: *"everything I've showed you in this video is an example of what I do with my set
[and forget] strategy."*

## 5. Missing definitions — reduced from four to three

The previous version listed four. The reference **relationship** is now supplied. Three remain, and
each is recorded as an authored open question against the new claim:

| ID | Missing | Why it cannot be inferred | Severity |
|---|---|---|---|
| **STOP-UNK-1** | **The buffer distance** | No unit of any kind — not pips, not an ATR multiple, not a percentage, and not an explicit "flush against the structure". **Position size = risk ÷ stop distance, so the 13 sizing rules remain non-computable.** | **BLOCKING** |
| **STOP-UNK-2** | **The identity of "it" / "this point"** | Three readings are each consistent with the words and the chart narration: (a) the low of the final rejection/engulfing candle, (b) the low of the whole Morning Star formation, (c) the far boundary of the retested zone. **They give materially different stop distances on the same setup.** | **BLOCKING** |
| **STOP-UNK-3** | **The short-side mirror** | All three demonstrations are longs and the phrasing is always *"right under"*. *"Right above"* is never spoken or shown, although the pattern is stated to work both ways. | MATERIAL |

> **Note on the brief's description.** The MOGO-002.7 brief predicted *"stop placement below or above
> the rejection structure."* Now that the transcript has been read: **"below" is confirmed; "above" is
> not in the source.** The brief overstated the source by one half. This is exactly why the previous
> version of this package refused to use the description as evidence.

## 6. Current MOGO-authored stop logic (unchanged)

```
buy :  stop   = setup.zoneLow  - stopATRBuffer * atrAtEntry     // index.html:3487
sell:  stop   = setup.zoneHigh + stopATRBuffer * atrAtEntry     // index.html:3488
       target = entry ± minRR * riskDistance                    // index.html:3494-3495
stopATRBuffer = 0.25    minRR = 2.0    riskPercent = 1.0        // index.html:2392-2394
```

## 7. ⚠️ Convergence analysis — the most important section for this decision

The resemblance between MOGO's logic and the educator's newly-stated rule is now **much closer than it
was**, which makes the lineage discipline **more** important, not less.

| | MOGO `ALEX_X_001` | Alex G, as now stated |
|---|---|---|
| Relationship | Stop just beyond the structure | Stop just beyond the structure |
| **Anchor** | **`setup.zoneLow` / `zoneHigh`** — the zone boundary | **the rejection formation at the retest** ("it" / "this point") |
| **Buffer** | **`0.25 × ATR`** | **not stated** |
| Target | **fixed** `2.0 × risk` | **minimum** 1:2 |
| Direction coverage | both | long only |

**Three findings the Authority should carry:**

1. **The anchors are not the same object.** MOGO anchors on the **zone boundary**; the educator
   anchors on the **rejection formation** at the retest. These often sit near each other and are not
   identical — a rejection wick can extend well past the zone boundary. Treating them as equivalent
   would be an assumption, not a reading.
2. **The `0.25 ATR` buffer has no educator counterpart whatsoever.** No ALEX_G claim in nine sources
   mentions ATR. This parameter remains **entirely MOGO-authored**.
3. **`minRR 2.0` and "minimum 1:2" are different rules that coincide at the boundary.** MOGO
   implements 1:2 as a **fixed ratio**; the educator states it as a **floor** and takes 1:3 and 1:4
   elsewhere. An implementation that always targets exactly 2R does **not** implement what he stated.

**None of this makes production's rules educator-derived.** `DECISION|MOGO|20260727|004` and
`traders/alex-g/profile.json` still state that `alex_g_sr_v1`'s rules are MOGO's own, and MOGO-002.6
established that overlap is **convergence, not derivation**. What has changed is that the educator
library can now support a stop *relationship* and a 1:2 *floor* **on its own footing** — which is a
statement about the draft, not about production.

## 8. Engineering Authority options — two are now unavailable

| Option | Status after ingestion | Risks |
|---|---|---|
| **A — Acquire more ALEX_G material** | **STILL LIVE, and now narrowly targeted.** No longer "does he state a stop?" but "does he ever state the buffer, disambiguate the anchor, or show a short?" | The base rate is now better than it was — one of nine sources produced the rule — but the three residual unknowns may simply never be spoken. `KEGAP-003` shows this educator often shows numbers rather than saying them. |
| **B — Accept stop placement as absent** | ❌ **FACTUALLY UNAVAILABLE.** Adopting it would now make the record false. | Was the recommended fallback in v1 of this package. It is withdrawn. |
| **C — Define a clearly labelled MOGO-authored stop module** | **STILL LIVE, and materially reframed.** MOGO would now author only the **buffer** (and pick an anchor reading), on top of an **educator-stated relationship** — a much smaller authored surface than the whole mechanism. | The label still matters. A MOGO-chosen buffer inside a rule attributed to the educator is still fabricated lineage, even when the surrounding relationship is genuinely his. |
| **D — Cross-educator module** | ❌ **UNNECESSARY AND CLEARLY WRONG.** Alex G now has his own stated rule; importing Rayner Teo's ATR-based stop would overwrite a real attribution with a foreign one. | Was prohibited before; is now also pointless. |

## 9. What is still not blocking this decision

**No contradiction obstructs `KEGAP-001`.** Stop placement is **uncontested across all nine sources** —
nothing anywhere disagrees with *"right under it"*. The gap is a missing parameter, not a conflict.

That remains true after ingestion, but note the take-profit position **did** become contested — see
`XCONTRA|20260729|004` in §10.

## 10. Related finding — the new material contradiction on targets

`XCONTRA|20260729|004` · `CONDITIONAL_SCOPE` · **material**

- **This source:** the take-profit is set to *"a minimum of a 1 to two risk to reward"* — so 1:2 is an
  acceptable target.
- **Source #8** (`CLAIM|ALEX_G|20260728|145`): closing a trade that was set to 1:4 **at 1:2** is named
  as the core psychological failure — *"the exit is driven by the size of the number, not by the
  market."*

Both cannot be applied without a rule distinguishing a target **set at** the 1:2 floor from a target
**revised down to** it. **That distinction is never drawn in either source, and it governs whether a
preset target may be changed after entry** — so it bears on `KEGAP-006` as well as `KEGAP-005`.

## 11. Recommendation — based only on acquired evidence

**Recommended: A (narrowly scoped), then C with explicit labelling. B is withdrawn. Not D.**

1. **Do not close KEREV-A as "absent".** That option died with this ingestion.
2. **Do not close KEREV-A as "resolved" either.** A rule whose buffer is unstated and whose anchor has
   three readings cannot be implemented without MOGO choosing two parameters — and choosing them is
   precisely what KEREV-A exists to govern.
3. **Acquire once more, narrowly.** Target a source that states the buffer or shows a short-side stop:
   a live session with order entry (queue rank 3) is the strongest candidate, because a stop price
   must be typed into a ticket.
4. **If that fails, take option C** — a **MOGO-authored buffer** recorded explicitly as MOGO-authored,
   sitting on top of the educator's stated relationship, with the anchor reading named and justified.
   This is a much smaller and more honest authored surface than the status quo, in which the entire
   mechanism is MOGO's.
5. **Whatever is decided, record the relationship as the educator's and the buffer as MOGO's.** They
   now have different provenance and must not be collapsed into one attribution.

**Explicitly not recommended:** treating the ingestion as closing `KEGAP-001`; reading MOGO's
zone-boundary anchor as corroborated by the educator's rejection-structure anchor; promoting the new
`stop_rule` claims to candidate rules (they are at `emerging`, and `POLICY-001` correctly blocks it);
or changing any production behaviour.

**Smallest decision that unblocks progress:**
> *"Accept that stop placement is now PARTIALLY_SUPPORTED, and choose whether MOGO may author the
> buffer under an explicit MOGO-authored label — or whether one further acquisition attempt is made
> first."*

---

*Revised by MOGO-002.7 after ingesting `EVSRC|ALEX_G|20260729|001`. KEREV-A remains OPEN. No stop
logic was added, changed, promoted, or attributed by this milestone.*
