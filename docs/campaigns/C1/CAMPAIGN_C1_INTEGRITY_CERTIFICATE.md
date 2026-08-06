# Campaign C1 — Integrity Certificate

**Campaign:** `CAMP|ALEX|C1|2026-08-05` · **Issued:** 2026-08-06 · **Engine:** 12.19.0 · **Runs commit:** `f7f0c40`

This certificate attests to **process and integrity only**. It contains no statistic, no
interpretation, and no conclusion about strategy performance. Limitations are recorded in Part B,
deliberately separated from the certified claims in Part A so that neither dilutes the other.

---

# Part A — Certified claims

Each claim below was verified mechanically against the evidence set, not asserted from a record of
it. The method is stated so a reader can repeat it.

### A1 — All replay runs executed ✅

Eleven of eleven declared runs executed and captured.
*Verified:* eleven `PACKAGES` artifacts exist, each containing at least one `mode == REPLAY` package.

### A2 — Declared order preserved ✅

Runs executed C1-01 → C1-11 in the order pre-registered in PREREG-002 §1: GBP/USD, GBP/JPY, AUD/USD,
USD/JPY, GBP/CHF, GBP/CAD, NZD/USD, AUD/JPY, EUR/JPY, USD/CAD, USD/CHF.
*Verified:* each run's captured instrument matches its declared pair, checked in-run by the capture
script's instrument cross-check and again during verification.

### A3 — No substitutions ✅

No pair was reordered, substituted, added, or dropped. The set of instruments observed equals the set
declared, exactly.

### A4 — One `configHash` ✅

`dbbb29b690f6692ae4d44a6833876193435ad66cc13c6e7226031e5f462c5adb` on **221 / 221** packages.
*Verified:* `len(set(configHash)) == 1`, and the value equals PREREG-002 §2, declared before the
first run.

### A5 — One `paramsHash` ✅

`8fe841e602be86cd335c9aa6804a8f30c76c57cac229a50b349194d821c6cae5` on **221 / 221** packages.
*Verified:* as A4.

### A6 — Engine constant ✅

`APP_VERSION` 12.19.0 on **221 / 221** packages.
*Verified:* `len(set(engineVersion)) == 1`. `index.html` byte-identical to `f7f0c40` throughout the
campaign and at lock time.

### A7 — Replay settings constant ✅

90-day lookback, `conservative` ambiguous mode, spread `none`, fixed spread 0, slippage 0, start
balance 10,000 — identical on every run.
*Verified:* structurally by A5 — `paramsHash` is computed over that parameter set, and it has one
value.

### A8 — Replay inventory complete ✅

**221 campaign packages** across eleven runs, **eleven distinct `runId`s**, no duplicates, no
commingling between runs.
*Verified:* each run's capture isolated its own `runId` by excluding all prior ones and aborted
rather than guessing if isolation was ambiguous; a dry run against every previously captured package
confirmed the exclusion list was exact in both directions before each run.

### A9 — Rejection inventory complete ✅

All eleven runs have a `REJECTED` artifact. **128 suppression records**, every one carrying a reason.
*Verified:* `every record has a reason: true` on all eleven.

### A10 — Gate fields complete ✅

`triggeredConditions`, `timeToMFE`, `timeToMAE` and market context populated on **216 / 221**
packages. The five exceptions are enumerated in **B1** and are nulls because the underlying event did
not occur — not capture failures.

### A11 — Replay hashes verified ✅

**221 / 221 PASS, 0 FAIL.** Every package independently re-canonicalized under
`mogo.evidence-canon.v1` (rules K1–K8) and its SHA-256 recomputed in a clean-room verifier written
outside the application.
*Verified:* the same verifier reproduces all 24 RUN-001 `contentHash` values, so the canonicalizer is
validated against known-good data rather than trusted.

### A12 — Repository clean ✅

`main` at `b71e222`, **0 tracked modifications**, `index.html` byte-identical to `f7f0c40`.

### A13 — Regression passed ✅

**947 / 947 fixtures across 17 suites, 0 failures, 0 execution errors.** Zero protected-function and
protected-constant drift: 63 functions and 4 constants byte-identical to the committed baseline.

### A14 — Backup verified ✅

All **33 artifacts** copied to `~/Desktop/MOGO-Evidence-C1/` with a SHA-256 `MANIFEST.txt` and the
receiver transcript.
*Verified:* full SHA-256 manifest comparison, source vs backup — identical. Source re-verified
unaltered after backup and again after commit.

---

# Part B — Known limitations

**These are not defects in the campaign's execution.** They are properties of the instrument and gaps
in the record, disclosed here so that no figure derived from this evidence is later described as more
complete than it is. They are deliberately separated from Part A.

### B1 — Five explained nulls in excursion timing

5 of 221 packages (2.3%) carry a null excursion-timing field.

| Run | Field | Cause | Outcome |
|---|---|---|---|
| C1-03, C1-04, C1-07, C1-11 | `timeToMFE` | `mfePips` = 0 | Loss — no favourable movement occurred |
| C1-06 | `timeToMAE` | `maePips` = 0 | Win — no adverse movement occurred |

All five returned `excursionAgreement: AGREES` with `matchesEngineExtremes: true` and no
data-quality flag. **Not** the `EXCURSION_RECOMPUTATION_MISMATCH` path. The null exists because the
excursion was zero; recording a timestamp for an event that never happened would be fabrication.

### B2 — The observation window is discovered, not chosen

`fetchCandlesRange` paginates backward from run time by candle count; there is no from/to control
(PREREG-001 §6, gate item **B2**, open). "90 days" is a control label — observed windows span roughly
128 calendar days. Runs executed at different times are not window-comparable, and **no result from
this campaign may be described as out-of-sample**.

### B3 — Informative censoring at 36.2%

128 of 354 considered setups were suppressed by the one-position-per-pair-per-timeframe constraint.
The suppression is **not random** — it correlates with setup clustering, which correlates with market
structure. Per-run rates range 24.2% to 58.6%. Every figure computed on this evidence must state its
suppression rate.

### B4 — `commitHash` absent from packages (L5)

Every package carries `commitHash: null` with provenance `UNAVAILABLE`. Satisfied externally: all
eleven runs were executed at `f7f0c40`, recorded in each harvest and in the §8.7 record.
**PREREG-001 §8 item 4 is met by external record, not by the package itself.**

### B5 — Export-verification by re-import not performed (L6)

**PREREG-001 §8 item 5 is NOT met.** No campaign package has been export-verified by re-import. The
`export` block on every package reads `{exportedAt: null, exportMechanism: null, exportFilename:
null, exportVerified: null}`. Packages were recovered by direct read through a `readonly` IndexedDB
transaction, not through the export path. This is the one §8 requirement genuinely unsatisfied.

### B6 — One non-campaign package inside C1-01's file

`C1-01-GBP_USD-PACKAGES.json` contains **25** packages: 24 campaign packages plus
`PKG|current_strategy|20260806|1`, a `LIVE_CLOSE` package written by the paper engine into the same
browser profile. C1-01's capture posted the whole store; every capture from C1-02 onward posted only
the isolated run. **Any analysis must filter `mode == "REPLAY"` on that file.** The package is
disclosed rather than deleted and is excluded from every recorded figure.

### B7 — Immutability is detective, not preventive

The evidence artifacts are ordinary files on disk with no write protection, no cryptographic sealing
and no WORM storage. The SHA-256 manifest and the committed record make alteration **detectable**;
they do not make it **impossible**. "Immutable" in this campaign's documentation means
tamper-evident, not tamper-proof.

### B8 — Browser-side capture is not independently reproducible

Evidence was captured from a live browser session through an operator-pasted console script. The
packages are internally verifiable and hash-checkable by anyone, but the act of capture is not
reproducible without an OANDA practice credential and a browser. See `RESEARCH_READINESS.md` for what
this does and does not permit.

### B9 — Open gate items inherited from PREREG-001

**R4**, **R8**, **B2** and §3.4 (replay ≠ live rule set) remain open and uncleared. This campaign
does not close any of them.

---

**No claim in Part A depends on any item in Part B being resolved.** Nothing in this certificate
adjudicates anything.
