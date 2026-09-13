# aoi_close_v1 — STOOD DOWN

> ## ⛔ SUPERSEDED — DO NOT ACT ON THIS DOCUMENT
>
> **Classification:** superseded / retracted. Retained as the historical record of a
> reasoning error. It is **not** a decision record and must not be executed against.
>
> **Authoritative record:** `NEGATIVE_ACQUISITION_LOG.md`, entry *"Session 2026-09-09 — an
> arm stopped before it was tested"* (commit `bae846922`). Where this file and that entry
> disagree, **the log entry is correct.**
>
> This document was written from a second-hand characterisation of a failure rather than from
> running the arm. Two of its three stated reasons did not survive contact with the code. The
> conclusion — stand down — happens to hold, but on a reason stated nowhere in this file.
>
> | This document claims | Measured correction |
> |---|---|
> | "It produces **zero trades**" | The arm fires, at a stable ~0.44 trades / 1,000 H1 bars from 9,000 to 144,000 bars, with its shifted control firing alongside it within a few percent at every length |
> | The chart-pattern family "has been measured, and is empty", so this is a fifth arm from it | The pooled randomness bound covers *MOGO's ALEX implementation's* entries, not Revelio's rules, which differ in **stated rules** rather than parameters |
> | Stand down because n = 0, so no test is possible in either direction | Stand down because the pre-registered scope yields ~146 trades against a **measured 0.274R detection floor** (σ = 1.69R over 64 trades) while the effect sought is 0.16R net — underpowered by roughly 3×, needing ~429 trades |
> | Delete **AOI-1, AOI-1b, AOI-F1, AOI-C1** and register the suite at **25** | **Do not delete them.** All four are good fixtures starved by an under-length synthetic walk. Deleting them would remove the look-ahead proof, its positive control, the firing-rate gate and the per-trade spread check. Lengthen the walk from 9,000 to 18,000 bars; the correct end state is **29**. |
>
> **The "Decided by: operator" line below is not a live operator decision.** The disposition
> it records was reversed the same day, before any of it was carried out.
>
> **Nothing in this document was executed.** As of 2026-09-13
> `tests/run_v170_aoi_close_tests.js` still contains all **29** fixture IDs, including the
> four named above, and the suite is registered in neither `tests/expected_fixture_counts.tsv`
> nor `tests/run_all.sh`. No fixture was deleted and no count was registered at 25.
>
> The body below is preserved verbatim. Only this banner and two inline retraction markers
> have been added; no original sentence has been altered or removed.

**Date:** 2026-09-09
**Decided by:** operator (Joe Mogollon), on the recommendation below
**Class:** `TESTED_NULL` — no. See "Why this is not TESTED_NULL" below.
**Class:** `STOOD_DOWN_BEFORE_TEST` — a new class. This arm was never tested, and recording
it as a null would misrepresent the evidence.

---

## What was built

A pre-registered replay arm for an area-of-interest close rule, coded and committed. Its
pre-registration (`preregistration-aoi_close_v1.md`) was written before any arm code, which
is the correct order and should be noted as such.

It produces **zero trades**.

> **⛔ RETRACTED.** False. The arm was pulled from `claude/v12.42.0-exit-fidelity-rebased` and
> run: it fires at ~0.44 trades / 1,000 H1 bars, stably across 9,000–144,000 bars. Every
> argument below that rests on "zero trades" — including the n = 0 / undefined-detection-floor
> reasoning in Reason 1 — is void. See `NEGATIVE_ACQUISITION_LOG.md`, 2026-09-09.

---

## Why it was stood down

**Reason 1 — there is no test here.** Zero trades means n = 0. The detection floor
(1.96·σ/√n) is undefined, not small. No result can come out of this arm in either
direction. It cannot pass and it cannot fail; it can only be silent. Debugging it into
producing trades would mean changing the rule until it fires, which is rule-fitting, not
testing.

**Reason 2 — the family it belongs to has been measured, and is empty.** Four chart-pattern
arms — `alex_g_sr_v1`, `crt_v1`, `psych_level_v1`, `baseline_trend_v1` — across ~19,300
trades all landed on 1/(1+T), the random-walk benchmark for a zero-information entry. That
pooled result is powered:

| | |
|---|---|
| pooled deviation | −0.37% (SE 0.60%) |
| excluded edge range | −0.031R to +0.016R |
| worst case, assuming perfect correlation | +0.0275R |
| standing bar | **0.06R gross per trade** |

Every one of those is under the bar. `aoi_close_v1` is a fifth arm drawing from the same
family. The prior is not neutral — it is a measured near-zero with a tight interval.

**Reason 3 — cost.** Past roughly 5,000 trades, transaction cost dominates and more data
cannot lower the bar. There is no sample size that rescues an effect of this size at this
venue.

---

## Why this is NOT recorded as TESTED_NULL

`TESTED_NULL` means a test ran and returned no effect. No test ran here. Filing a
zero-trade arm as a null would put a fabricated result in the evidence corpus and would
imply the rule had been measured and found wanting. It has not been measured at all.

The distinction matters for anyone reading the log later to decide what has been ruled out.
This arm rules out nothing. It was stopped on a cost-and-power argument made **before** the
measurement, which is the whole point of the gate that now exists.

---

## B3 target-selection ruling

**No ruling given, deliberately.**

Ruling on a target-selection detail for an arm that will not be built spends the effort
twice: once now, and again when someone finds the ruling in the register, reads it as a
live decision, and builds against it. An unruled item is correctly readable as "this was
never decided." A ruled one is not.

If the arm is ever revived, B3 is answered then, on the evidence available then.

---

## Disposition of the code and the tests

**The arm code stays in `index.html`.** ~1,001 lines, 57 `aoiClose` references, currently
unreachable — no nav entry, no registry entry, nothing calls it. Removing it means a large
edit to a 2.4 MB single file that is running live PAPER operations. The risk of the edit
exceeds the benefit of the tidiness, and the code is inert where it sits.

**A tombstone comment goes above the arm's entry point**, so anyone who finds the code
reads the verdict before the implementation. Comment only — no executable change, and
`regression-baseline-tools.py --verify` must still report 0/64 functions, 0/4 constants
after it.

> **⛔ RETRACTED — DO NOT EXECUTE THE NEXT THREE PARAGRAPHS.** Do not delete AOI-1, AOI-1b,
> AOI-F1 or AOI-C1, and do not register this suite at 25. All four are good fixtures that were
> being starved by an under-length synthetic walk — AOI-F1 needs ≥5 trades and gets 4 on 9,000
> bars; at 18,000 it gets 7 and 8 and passes. Deleting them would remove the look-ahead proof,
> its positive control, the firing-rate gate and the per-trade spread check. The correct fix is
> to lengthen the walk from 9,000 to 18,000 bars, registering at **29**. The premise below —
> that these fixtures assert on trades "that will never be produced" — is false; the arm fires.

**`tests/run_v170_aoi_close_tests.js` stays, at 25 fixtures, registered.** The four failing
fixtures — **AOI-1, AOI-1b, AOI-F1, AOI-C1** — are deleted, not fixed. All four assert on
trades the stand-down says will never be produced; they are fixtures for an outcome that
has been decided out of existence. Fixing them would mean building the arm.

The remaining 25 cover pure helpers that stay in the page, so the suite keeps proving the
dead code has not rotted.

**This is the one move here that could look like hiding a failure**, so it is named
explicitly rather than left to a diff: four fixtures were deleted, by ID, with the reason
above. Register the suite at **25** in `tests/expected_fixture_counts.tsv`.

The alternative — registering it at 29 and leaving it permanently red — is worse. A gate
that is always red trains everyone to ignore red, which is the same failure as a green
indicator nobody has seen go red, running in the other direction.

---

## What would revive this

A source that establishes an expected effect size for the rule, large enough to clear
0.06R net of spread, from evidence published before the outcome was known. Absent that, a
sixth chart-pattern arm is not a candidate.
