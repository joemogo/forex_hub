# Rule Register — Candle Range Theory (CRT)

**Attribution:** none. CRT is widely republished across trading blogs and video channels with no
single attributable originator. There is **no trader entity** behind this register, which is why it
lives here and **not** in `acquisition/candidates/` — that registry indexes *sources* discovered and
scored by `prioritize_sources.py`, and hand-writing a record into it would corrupt a
script-managed store.

**Sources consulted (2026-09-06 session):** `tradingwyckoff.com`, `writofinance.com`.

> **PROVENANCE CAVEAT — read before quoting anything below.** These sources were fetched earlier in
> the same session, and the extraction below is a **faithful paraphrase from that reading, not
> preserved verbatim text**. A re-fetch to capture exact sentences was attempted on 2026-09-06 and
> **failed**: the fetch required an approval that was not answered. Nothing here is marked
> `Explicit` with a quotation, because no quotation was preserved. Treat every line as
> `SOURCE_STATED (paraphrase)` at best. **Re-acquire with verbatim capture before this register is
> cited anywhere as evidence.**

**Legend — Status:** SOURCE_STATED (the sources say it) · UNKNOWN (the sources do not define it) ·
INFERRED (MOGO concluded it — never promoted).
**Nature:** Objective (mechanically checkable) · Discretionary (needs human judgement).

---

## A. The pattern

### A1 — Candle 1 defines a range
- **Rule:** the first candle of the three establishes a range, bounded by its own high and low.
- **Status:** SOURCE_STATED · **Nature:** Objective
- **Algorithmic representation:** `range = [C1.l, C1.h]`
- **Replay feasibility:** ✅ high
- **Implemented in `crt_v1`:** yes

### A2 — Candle 2 sweeps ONE extreme of that range
- **Rule:** the second candle takes out one side of candle 1 — the liquidity sweep, described
  elsewhere as the "manipulation" leg.
- **Status:** SOURCE_STATED · **Nature:** Objective *once A6 is resolved*
- **Algorithmic representation:** `C2.h > C1.h XOR C2.l < C1.l`
- **Implemented in `crt_v1`:** yes. A candle 2 taking **both** extremes is **refused**, not resolved
  by a tie-break — the direction it implies is genuinely ambiguous and no source states one.
  Fixture `CRT-4`.

### A3 — Candle 3 closes back INSIDE the range
- **Rule:** the third candle closes back within candle 1's range; this is the confirmation.
- **Status:** SOURCE_STATED · **Nature:** Objective
- **Algorithmic representation:** `C1.l < C3.c < C1.h` (strict; a boundary close is refused —
  fixture `CRT-6`)
- **Implemented in `crt_v1`:** yes

### A4 — Direction is the fade of the sweep
- **Rule:** a sweep of the high is traded short; a sweep of the low, long.
- **Status:** SOURCE_STATED · **Nature:** Objective
- **Implemented in `crt_v1`:** yes. Fixtures `CRT-2`, `CRT-3`.

### A5 — Analysis on H1/H4/D1, entries refined on M15/M5/M1
- **Status:** SOURCE_STATED · **Nature:** Objective
- **Implemented in `crt_v1`:** **partially.** The arm runs on **H4 only**. Lower-timeframe entry
  refinement is not implemented, because it needs intrabar data this replay does not have (see D2).

### A6 — Whether the sweep must CLOSE beyond the extreme, or may merely wick it
- **Status:** **UNKNOWN** · **Nature:** Objective once defined, undefined as published
- The sources are consistent with the wick reading and do not state the body-close variant.
- **`crt_v1` uses the WICK reading** and records this as a choice, not a finding. The body-close
  variant is a **different experiment**, not a refinement of this one, and would need its own arm.

---

## B. Risk geometry

### B1 — Stop goes beyond the swept extreme
- **Status:** SOURCE_STATED · **Nature:** Objective as to SIDE, **UNKNOWN as to distance**
- "Beyond" fixes which side of the wick the stop sits on and says nothing about how far. A stop
  resting exactly on the wick tip is taken out by its own bar, so a distance had to be chosen.
- **`crt_v1`:** `stopBufferATRMultiple = 0.1`, applied **identically to both arms** and never tuned
  against a result. This is an implementation parameter, **not a source-stated rule**, and it is
  labelled that way in the code and in the exported package.

### B2 — Target is the OPPOSITE extreme of candle 1
- **Status:** SOURCE_STATED · **Nature:** Objective
- **Consequence that matters:** planned R is therefore **not fixed**. Every other MOGO arm books a
  flat 2R; this one cannot, because the target is a price, not a multiple. And a **deeper sweep
  widens the stop and lowers planned R by itself** — a confound between the swept and unswept arms
  that exists before any question of edge. `crtCompareArms` reports `meanPlannedRR` per arm for
  exactly this reason. Fixtures `CRT-R1`…`CRT-R5`.

### B3 — Risk-to-reward floor, position sizing, session filter, trade cap
- **Status:** **UNKNOWN — none stated by either source.**
- **`crt_v1` implements none of them.** Inventing a minimum R:R would be fitting a filter this
  method does not have.

---

## C. The part that cannot be tested

### C1 — WHICH candle qualifies as candle 1
- **Status:** **UNKNOWN — and this is the load-bearing gap.**
- Every source qualifies the reference candle: it must close *at or near a liquidity zone, an order
  block, a key level*. **None of them defines any of those mechanically.** No swing-lookback, no
  zone width, no freshness rule, no ranking when several qualify.
- **`crt_v1` does not attempt it.** The arm applies the pattern to **every** three-bar window.
- **What that does to the result, stated plainly:** this is a **strictly weaker test** than a CRT
  trader would run. A positive result would be strong (the geometry alone pays). A **null result
  does NOT falsify CRT as practised** — it establishes that the geometry alone carries no edge,
  which places any remaining edge entirely inside the undefined selection step. That step is not
  specifiable from the published material, which makes it **unfalsifiable and untradeable by
  MOGO** until a source defines it.
- This paragraph is duplicated into every exported evidence package
  (`replayDisclosures.referenceCandleSelection`) so it travels with the numbers rather than living
  in this file. Fixture `CRT-20`.

---

## D. Implementation deviations, declared

### D1 — The control arm is MOGO's, not CRT's
- **Status:** INFERRED (MOGO's experimental design) — **never** to be read as a CRT rule.
- Mean reversion after a probe at a recent extreme is not a claim unique to CRT. So the identical
  rule also runs on windows where candle 2 stayed **inside** the range: same three-bar shape, same
  reclaim requirement, same stop and target construction, same bars. The **only** variable is the
  breach — the mechanism CRT actually claims.
- An inverted-direction control was **considered and rejected**: with both arms sharing one
  geometry, an inverted arm is close to a mirror by construction and answers a question nobody
  asked.

### D2 — Entry is candle 4's open, not intrabar on candle 3
- **Status:** deviation, declared.
- CRT traders describe entering *during* candle 3 once the reclaim is visible. That needs intrabar
  data this replay does not have, and pricing off candle 3's close would be reading the bar that
  produced the signal. Candle 4's open is the conservative reading and **gives up part of the
  move**. Recorded in `replayDisclosures.entryNote`; fixtures `CRT-1`, `CRT-13`, `CRT-22`.

### D3 — No friction
- Spread and slippage are **not charged**. Both arms are equally optimistic, so the comparison
  **between** them stands; **neither figure is a return anyone could have earned.** Spread is left
  **absent** in the export, never written as zero. Fixture `CRT-21`.

---

## Status

| | |
|---|---|
| Rule reconstruction | partial — §A and §B implemented, §C **not implemented and not implementable** from these sources |
| Confidence | `emerging`. Zero rule candidates. **Not** a production rule. |
| Replay arm | `crt_v1`, built v12.61.0, **replay only** |
| Paper trading | **NOT AUTHORIZED.** Manifest declares `paperTrading:false`; fixture `CRT-23` fails if that changes. |
| Result | **none yet.** The arm has not been run on real candles. |
| Blocking re-acquisition | verbatim capture of both sources, to replace the paraphrase above |
