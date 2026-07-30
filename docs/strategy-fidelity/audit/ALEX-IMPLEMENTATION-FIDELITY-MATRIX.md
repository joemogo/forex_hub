# ALEX — Implementation Fidelity Matrix (educator register vs MOGO)

**Milestone:** MOGO-002.8 · **Phase 5** · **Date:** 2026-07-29
**Subject:** `alex_g_sr_v1` — the ALEX paper-trading implementation, engine `12.6.0`
**Machine-readable:** [`alex-implementation-fidelity-matrix.json`](alex-implementation-fidelity-matrix.json)

> ## ⚠️ This comparison has never been performed before, and it is observational only
>
> MOGO-002.5 compared the implementation against **`alex_g_sr_v1`** — the approved 13-rule
> specification extracted from `RULES_ALEXG`. **That remains the authoritative fidelity result and is
> unchanged by this audit.**
>
> This matrix compares the implementation against the **educator library** instead. Doing so is what
> the audit brief asks for, and it carries a standing hazard: `DECISION|MOGO|20260727|004` states
> `alex_g_sr_v1`'s rules are **MOGO's own**, not the educator's. **Every agreement below is
> CONVERGENCE, NOT DERIVATION.** This matrix does not re-specify anything, does not merge the two
> bodies of knowledge, and does not resolve KEREV-B.

---

## 1. Verdict

**41 educator rules compared. The implementation is materially divergent from what the educator
teaches, in both directions.**

| Status | Count |
|---|---|
| `FUNCTIONAL_MATCH` | **8** |
| `PARTIAL_MATCH` | **6** |
| **`PRESENT_BUT_DIFFERENT`** | **6** |
| **`MISSING_FROM_MOGO`** | **7** |
| **`IMPLEMENTED_WITHOUT_EDUCATOR_SUPPORT`** | **6** |
| `MOGO_AUTHORED_PARAMETER` | 1 |
| `NON_IMPLEMENTABLE_DISCRETION` | 2 |
| `NOT_APPLICABLE` | 3 |
| `UNRESOLVED` | 2 |
| **`EXACT_MATCH`** | **0** |

**Zero exact matches.** Not one educator rule is implemented exactly as stated — which is the expected
result when 35 of 41 rules are non-deterministic, and is itself the strongest possible argument that
the two bodies were developed independently.

**Against `alex_g_sr_v1` (unchanged, for contrast):** 9 MATCH · 2 APPROXIMATED · 1 AMBIGUOUS ·
1 NOT_APPLICABLE · 8 EXTRA · **0 MISSING · 0 DIFFERING**. The engine is faithful to *its own*
specification and divergent from *the educator's*. Both statements are true simultaneously, and
conflating them is the error this matrix is designed to prevent.

---

## 2. Rules Alex teaches that MOGO lacks — 7

| Rule | What the educator requires | MOGO |
|---|---|---|
| **AXR-011** | **A bullish engulfing confirmation is REQUIRED before entry** | **No candlestick-confirmation gate exists at all.** Entry is the qualification candle's close |
| **AXR-015** | A structurally ideal setup is **declined** when the confirmation is absent | MOGO cannot decline for this reason — it has no confirmation concept |
| **AXR-012** | Morning Star (3 doji + engulfing) as the demonstrated confirmation | No Morning Star detection |
| **AXR-010** | HTF structure, **LTF entry signal** | MOGO evaluates zones and setups on H1/H4/D/W with no HTF→LTF split |
| **AXR-080** | **Session and day-of-week gate entry; Mon–Wed only** | `alexGComputeSessionMetadata` computes it and **never restricts entry** (`ALEX_X_007`) |
| **AXR-072** | Day-trade 4H/1H vs swing D/W modes | No mode distinction |
| **AXR-042** | Risk band varies by account type and calendar month | No modulation |

### The two that matter

**AXR-011 / AXR-015 — the confirmation gate — is the largest trade-eligibility divergence in the
audit.** The educator's single hardest entry precondition is entirely absent from the implementation.
Every ALEX paper trade ever opened was opened without the confirmation he says is mandatory. This does
not make the engine wrong — its own specification never required one — but it means **MOGO and the
educator would take materially different sets of trades.**

**AXR-080 — the session gate — is a live divergence, not merely a gap.** MOGO computes session and
day metadata and then deliberately ignores it. The manifest records this as *"a deliberate design
choice, not a source gap."* **That note predates the session evidence.** Sources #4 and #5 now carry
7 explicit session rules including a Mon–Wed restriction, so the characterization should be revisited.

---

## 3. Rules MOGO implements differently — 6

| Rule | Educator | MOGO | Consequence |
|---|---|---|---|
| **AXR-005** | **Minimum of ONE** structure point | `touchIndex>=3` **and** `touches.length>=4` | **MOGO is materially STRICTER.** It rejects setups the educator would accept |
| **AXR-008** | Zone width **explicitly unconstrained** | `zoneClusterATRMultiplier = 0.5` | MOGO imposes a constraint the educator **actively declines** to impose |
| **AXR-030** | 1:2 as a **MINIMUM** | `minRR = 2.0`, a **fixed** ratio | MOGO can **never** take the 1:3 or 1:4 the educator also describes |
| **AXR-013** | Retest ends when rejection candles appear | Confirmed within 1 bar + ≥0.25 ATR displacement | Quantifies a qualitative test |
| **AXR-014** | Entry at the confirmation candle | Entry at the qualification candle **close** | Different price on the same bar |
| **AXR-090** | Applies to **all** instruments | Fixed instrument set via scan config | Narrower universe |

**AXR-005 and AXR-030 are the two with real P&L consequence.** A 4-touch minimum against a stated
1-touch minimum changes which setups qualify; a fixed 2R against a 1:2 floor changes every exit.

---

## 4. Rules MOGO implements that Alex never taught — 6 educator-side + 6 MOGO-only

**Educator-silent behaviours MOGO nonetheless decides:**

| Rule | MOGO behaviour | Educator |
|---|---|---|
| **AXR-060** | Never moves to break-even (documented as a MOGO choice, `APP_VERSION_LOG` v4.0) | **Silent** |
| **AXR-061** | Takes no partials | **Silent** |
| **AXR-062** | Single entry, never scales | **Silent** |
| **AXR-063** | Never trails | **Silent** |
| **AXR-022** | Symmetric short-side stop (`zoneHigh + buffer`) | **Never states the short side** |
| **AXR-091** | Choppy-zone filter (≥3 penetrations / 50 bars) | States no such filter |

**MOGO's no-intervention defaults are probably right** — they align with the demonstrated behaviour in
AXR-050 and with "set and forget" branding. **But "probably right" is not evidence**, and each of
these is a MOGO decision taken in an evidentiary vacuum, not a match.

**Behaviour with no educator counterpart at all** (from the implementation manifest, all affecting
trading except `ALEX_X_008`): `ALEX_X_002` live entry-delay 5 pips · `ALEX_X_003` signal staleness ·
`ALEX_X_004` activation cutoff · `ALEX_X_005` choppy filter · `ALEX_X_006` rejection window + 0.25 ATR
displacement · `ALEX_X_008` `ALEX_SCORE_V2` (shadow only).

---

## 5. Parameters MOGO had to author because the educator was non-deterministic

**This is the heart of the audit.** 35 of 41 educator rules are non-deterministic, so any
implementation must supply values. Every one of these is **MOGO-authored** and must be labelled so:

| Parameter | Value | Educator basis | Status |
|---|---|---|---|
| **`stopATRBuffer`** | **0.25 ATR** | **NONE.** No ALEX_G claim in 9 sources mentions ATR | **MOGO-AUTHORED** |
| `minRR` | 2.0 fixed | 1:2 stated as a *minimum* | MOGO-authored (different rule shape) |
| `riskPercent` | 1.0 | Falls inside **both** stated bands (0.5–1% and 1–2%) | MOGO-authored *value*, educator-consistent |
| `zoneClusterATRMultiplier` | 0.5 | Educator explicitly declines to constrain | **MOGO-authored, against the source** |
| `rejectionDisplacementATRMultiplier` | 0.25 | Qualitative only | MOGO-authored |
| `rejectionConfirmWithinBars` | 1 | No window stated | MOGO-authored |
| `maxPenetrationsBeforeChoppyFlag` | 3 / 50 bars | No such filter | MOGO-authored |
| Touch minimum | 4 | Educator says **1** | MOGO-authored, **stricter** |
| `maxBarsBetweenBreakAndRetest` | 50 | No time limit stated | MOGO-authored |
| Short-side stop symmetry | mirrored | Never stated | **MOGO-authored assumption** |

**`riskPercent = 1.0` is the single genuinely well-aligned parameter** — it sits inside both bands the
educator names. Even so, MOGO chose the value; the educator states bands plus an account-type
dependency MOGO does not model.

---

## 6. Where Alex is discretionary and MOGO necessarily formalizes

**AXR-100** records that several gates are explicit judgement calls with named inputs and **no
thresholds** — whether a second confirmation is needed *"depends on level strength, timeframe, days
left in the week, R:R and other confluences."* The KE layer records **40 claims** in
`DISCRETIONARY_ELEMENTS` yielding **7 rules, 0 deterministic**.

An automated system cannot hold discretion. Every formalization of these is legitimate engineering and
is **not** a fidelity defect — but each is a MOGO authorship event and appears in §5.

---

## 7. Rules that cannot yet be evaluated — 2 `UNRESOLVED`

- **AXR-031** (target selection above the floor) — no educator procedure exists, so MOGO's fixed 2R
  cannot be compared against one.
- **AXR-081** (session hours) — parameter absent from source; nothing to compare.

---

## 8. Where MOGO and the educator genuinely agree — 8 `FUNCTIONAL_MATCH`

Recorded for balance, and **all convergent, none derived**:

`AXR-001` zone role derivation · `AXR-004` break-then-retest as a first-class setup · `AXR-007` setups
only at zones · `AXR-040` percentage-of-balance risk · `AXR-043` risk constant (never raised after
wins — satisfied *by construction*, since `riskPercent` is a constant) · `AXR-050` no intervention
between entry and exit · `AXR-051` no action before price arrives · `AXR-052` target frozen at entry,
never cut early.

**The strongest agreement is on risk *stability* and *no intervention*** — MOGO satisfies both
trivially because its parameters are constants and its stops never move. Agreement by construction is
weaker evidence of shared method than agreement by design.

---

## 9. Fidelity impact summary

| Divergence | Affects | Severity |
|---|---|---|
| No confirmation gate (AXR-011/015) | **Trade eligibility** — different trade sets | **HIGH** |
| No session/day gate (AXR-080) | **Trade eligibility, entry timing** | **HIGH** |
| Touch minimum 4 vs 1 (AXR-005) | **Trade eligibility** | **HIGH** |
| Fixed 2R vs 1:2 floor (AXR-030) | **Every exit, expectancy** | **HIGH** |
| Stop anchor: zone boundary vs rejection formation (AXR-020) | **Stop distance, position size, every R multiple** | **HIGH** |
| `stopATRBuffer` unattributable (AXR-021) | Stop distance | **HIGH** |
| Zone-width constraint against an explicit non-constraint (AXR-008) | Zone construction | MEDIUM |
| No HTF→LTF entry split (AXR-010) | Entry precision | MEDIUM |

**The stop anchor deserves particular attention.** MOGO anchors on `setup.zoneLow`/`zoneHigh` — the
**zone boundary**. The educator anchors on the **rejection formation at the retest**. A rejection wick
routinely extends beyond the zone boundary, so these are **not the same object**, and the resulting
stop distances differ. The surface similarity ("stop just beyond the structure") is real and must not
be read as the same rule.

---

*Phase 5 complete. **No code was read into, modified, or executed.** The implementation is unchanged;
`index.html` shows 113 insertions / 0 deletions from MOGO-002.5 and zero protected-function drift.*
