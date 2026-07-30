# ALEX — Strategy Freeze Readiness & KEREV-A Assessment

**Milestone:** MOGO-002.8 · **Phases 7–8** · **Date:** 2026-07-29
**Machine-readable:** [`alex-strategy-freeze-readiness.json`](alex-strategy-freeze-readiness.json)

---

# VERDICT: `NOT_READY_BOTH`

# REPLAY AUTHORIZATION: **NOT AUTHORIZED**

---

## 1. What "freeze" means here

**Two different things could be frozen, and they must not be conflated:**

| | Status |
|---|---|
| **`alex_g_sr_v1`** — the production strategy, specified by its own 13-rule artifact | **Already frozen** against its own specification (hash `a0b7641e288c1725`). Unchanged by this audit. |
| **An educator-faithful ALEX v1** — a specification that matches what Alex G teaches | **`NOT_READY_BOTH`** — this is what the verdict addresses |

## 2. Why `NOT_READY_BOTH`

Both failure classes are present. Either alone would block; both are.

### Source gaps — 3 blocking

| ID | Finding |
|---|---|
| **FRZ-01** | **The stop buffer is absent** (AXG-01). No educator-faithful position size is computable, and MOGO's 0.25 ATR stays unattributable |
| **FRZ-06** | **Break-even, partials, scaling and trailing are at absolute zero** across 9 sources. Realized-R behaviour cannot be validated |
| **FRZ-07** | **Session hours exist only as on-screen pixels** (AXG-04). No transcript acquisition can close them |

### Implementation mismatches — 5 blocking

| ID | Finding |
|---|---|
| **FRZ-02** | **MOGO has no candlestick-confirmation gate**, which the educator states as a necessary entry condition. Trade eligibility differs materially |
| **FRZ-03** | **MOGO applies no session or day-of-week restriction** while the educator states an explicit Mon–Wed and session gate. MOGO computes the metadata and deliberately ignores it |
| **FRZ-04** | **`minRR = 2.0` is fixed; the educator states 1:2 as a minimum.** Also the subject of open contradiction `XCONTRA\|20260729\|004` |
| **FRZ-05** | **MOGO requires 4+ touches; the educator states a minimum of ONE structure point.** MOGO is materially stricter |
| **FRZ-08** | MOGO imposes `zoneClusterATRMultiplier = 0.5` where the educator **explicitly declines** to constrain zone width (also a source ambiguity — class BOTH) |

### Governance — 2 material

| ID | Finding |
|---|---|
| **FRZ-09** | **All 341 library claims sit at `emerging` and 0 rule candidates exist.** Under `POLICY-001` **nothing in the educator library is promotable today**, so no educator rule can be frozen into a specification regardless of its content |
| **FRZ-10** | Execution readiness for `alex_g_sr_v1` is `NOT_VERIFIED` (6/10 criteria failed); profitability `UNVALIDATED` |

**FRZ-09 is the one that would survive perfect acquisition.** Even if every source gap closed tomorrow,
the D2 blocker would still prevent promotion. **Freeze readiness is gated on a governance decision, not
only on evidence.**

## 3. What would change the verdict

| Action | Effect |
|---|---|
| Close AXG-01 (stop buffer) | Removes FRZ-01 |
| **An Authority ruling that explicitly-labelled MOGO-authored parameters are acceptable** | Could move the **source-gap** class to `READY_WITH_DOCUMENTED_MOGO_PARAMETERS` — **but not the five implementation mismatches** |
| Resolve D2 | Removes FRZ-09 |

**Note carefully:** even the most permissive plausible ruling on MOGO-authored parameters does **not**
reach `READY_WITH_DOCUMENTED_MOGO_PARAMETERS` overall, because FRZ-02 through FRZ-05 are not parameter
gaps — they are behavioural differences between what the educator teaches and what the engine does.
Those require either an implementation decision or an explicit decision to remain divergent.

## 4. Replay authorization

**NOT AUTHORIZED. This audit does not request it.**

- `replayAuthorization` is **`false` on all six `OwnerDecision` records**
- MOGO holds **no market data**
- **5 of 8** audit gaps are annotated `blocksReplay`
- A replay run today would measure the **MOGO** strategy, not the educator's — which is legitimate,
  but it must not be reported as validating the educator's method

**`POLICY-001` rule 4** establishes that replay evidence *counts* toward confidence; it does **not**
authorize replay *execution*. That remains a separate Engineering Authority decision.

---

# 5. KEREV-A ASSESSMENT

## Recommendation: **`REFRAME_KEREV_A`**

### 5.1 Is the proposed separation supported by evidence? — **YES**

| Component | Verdict | Basis |
|---|---|---|
| **Alex-authored:** *"Stop-loss belongs beyond the rejection structure"* | ✅ **SUPPORTED** | `CLAIM\|ALEX_G\|20260729\|025` — `rule_statement`, `direct_explicit`, `extractionCertainty: certain`, explicitly universalized (*"the same thing every single time"*), plus two same-source demonstrations (`CLAIM\|ALEX_G\|20260729\|022` at 7:52 and 8:25) |
| **MOGO-authored:** the numerical/volatility buffer beyond that structure | ✅ **CONFIRMED UNSUPPORTED** | **Zero** ALEX_G claims across 9 sources and 226 claims state any buffer in any unit. **No ALEX_G claim mentions ATR at all.** `stopATRBuffer = 0.25` has no educator provenance whatsoever |

**The separation the Authority proposed is exactly what the evidence shows.** The relationship is his;
the number is MOGO's.

### 5.2 What can be closed

1. **"Does Alex state a stop-placement rule at all?"** — **YES**, and it is now evidenced. That
   sub-question is settled.
2. **Option B — "accept stop placement as absent from the ALEX_G specification" — is FACTUALLY
   UNAVAILABLE** and can be struck. Adopting it would make the record false.
3. **Option D — "use a separately attributed cross-educator module" — can be struck as unnecessary.**
   Alex now has his own stated relationship; importing Rayner Teo's ATR rule would overwrite a real
   attribution with a foreign one.

### 5.3 What must remain open

1. **The buffer distance** — explicitly MOGO-authored, and **must be labelled as such wherever it
   appears** (`AXR-021` / `AXG-01`).
2. **The anchor identity** — three readings, unresolved (`AXG-02`). **And MOGO currently picks a
   fourth-order variant of reading (c)** — the zone boundary — while the educator's words most
   naturally read as (a) or (b).
3. **The short-side rule** — never stated. MOGO's symmetric implementation is an **assumption**
   (`AXR-022` / `AXG-08`).

### 5.4 Why not `CLOSE_KEREV_A`

Closing would imply stop placement is **settled**. It is not: **two of the three parameters needed to
place a stop mechanically are still absent**, and MOGO's anchor is a *different object* from the
educator's. Closing would also license reading MOGO's existing 0.25 ATR as educator-supported — which
is precisely the lineage error `KEREV|058` exists to prevent.

### 5.5 Why not `ADDITIONAL_SOURCE_REQUIRED` alone

That understates what has changed. The decision as originally framed offered four options, **two of
which are now dead**. Leaving it unchanged sends the Authority back to a menu that no longer matches
the evidence.

### 5.6 Proposed reframing

> **KEREV-A (reframed):** The stop **relationship** is educator-authored and evidenced. May MOGO author
> the **buffer** and the **anchor reading** as explicitly-labelled MOGO parameters — or must
> acquisition continue first?
>
> **Standing constraint either way:** neither the buffer nor the anchor choice may ever be presented as
> Alex's.

---

## 6. Summary table

| Question | Answer |
|---|---|
| Freeze readiness | **`NOT_READY_BOTH`** |
| Blocking findings | **8** (3 source gaps, 5 implementation mismatches) + 2 material governance |
| Replay authorized | **NO** |
| KEREV-A | **`REFRAME_KEREV_A`** |
| Alex-authored stop relationship | **Evidenced** |
| MOGO-authored stop buffer | **Confirmed unsupported by any source** |
| Production strategy changed | **No** |
| Draft rules promoted | **No** |

---

*Phases 7–8 complete. KEREV-A remains OPEN pending Engineering Authority review.*
