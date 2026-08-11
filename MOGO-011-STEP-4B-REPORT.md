# MOGO-011 STEP 4B — READ-ONLY BROWSER EVIDENCE MANIFEST AND RECONCILIATION

**Status:** **CAPABILITY IMPLEMENTED AND VALIDATED — STOPPED AT THE STOPPING GATE**
**Step 4A committed (not pushed). Step 4B is UNCOMMITTED. No evidence changed. ALEX forward paper trading OFF.**
**Date:** 2026-08-09
**HEAD:** `f139b8b90526388398ca12ce5489981bc42d3dc3` (Step 4A) · parent `c7527a4…` · **not pushed**

---

## 1. The finding that stops Step 4B

> **The authoritative browser store holding the 222 packages is not on this machine.**

This was established by measurement, offline, without opening a browser:

| | |
|---|---:|
| Real evidence packages, observed mean size | **40,556 bytes** (n=122, median 44,867) |
| Storage 222 packages would therefore require | **≈ 8.6 MB** |
| **Total size of every MOGO-origin IndexedDB store on this machine** | **0.22 MB** |
| Discrepancy | **≈ 39×** |

Every MOGO-origin store was then copied and the **copies** scanned for evidence markers:

| Store (copy scanned) | Bytes | Distinct packageIds | Trade ids found |
|---|---:|---:|---|
| `Profile 2` → `http_localhost_8744` | 30,060 | 1 | `AGT\|REALEXPORT\|1` |
| `Profile 2` → `http_10.143.1.187_8744` | 8,936 | 4 | `AGT\|INSECURE\|1` |
| `Profile 2 copy` → both origins | same | same | same |
| `Profile 2 Safety Copy 2026-07-31` → both origins | same | same | same |

**Four distinct packageIds, all dated 2026-07-31, all EXP-001-era test artifacts.** Every MOGO store
on this machine was last written **2026-07-31** — before the Campaign C1 runs (2026-08-06) and before
the export attempts (2026-08-09).

**Therefore the "222" could not be independently derived from browser state on this machine.** Per
your instruction, I am reporting that discrepancy rather than forcing reconciliation to 222. The
number remains **OPERATOR_REPORTED and unverified**.

MOGO is served over the LAN (origin `http://10.143.1.187:8744`), so the store almost certainly lives
in a browser on **a different device**. The manifest must be taken from whichever device the
operator actually uses. That device is not reachable from here, and reaching for it was not
authorized.

---

## 2. Why I stopped rather than proceeding

Your stopping gate allowed for exactly this: *"or sooner if accessing the real browser store would
require a potentially mutating operation."*

Two independent reasons to stop:

1. **The store is not here.** No amount of local work can produce the authoritative manifest.
2. **Reaching the real store would mean driving the operator's live browser.** Loading MOGO runs
   application code — `evidenceInitPlatform()`, migrations, ledger persistence, a `visibilitychange`
   handler that can auto-export. That is not an observational act, and it was not authorized.

So Step 4B delivers the **capability**, validated, and stops. No browser was opened. The stores were
**copied** and the copies scanned; the originals were never opened by a writer.

---

## 3. What was built

### 3.1 `scripts/mogo_evidence_browser_manifest.js` — the read-only manifest exporter

A snippet the operator pastes into the DevTools console of a tab already running MOGO. It emits a
manifest carrying every field §"RECONCILIATION OUTPUT" requires: canonical identity, `packageId`,
`sourceTradeId`, `contentHash` (+ provenance and algorithm), strategy/engine identity, run/session
identity (`runId`, `datasetHash`, `configHash`, `paramsHash`), creation timestamp, export-attempt
state, and confirmation/verification state.

**Four structural read-only guarantees, not four promises:**

| | Guarantee |
|---|---|
| 1 | It calls exactly two IndexedDB APIs: `open()` and a **`readonly`** transaction's `getAll()`. It asserts about **its own source** that no mutating call is present, and **refuses to run** if one appears |
| 2 | It opens **without a version number**. `indexedDB.open(name)` with no version cannot fire `onupgradeneeded`, so it can never migrate, create or alter a store — and it refuses outright if an upgrade is somehow requested |
| 3 | It calls **no** MOGO writer: not `evidenceUpdateExportState`, `evidenceExportPackage`, `evidenceExportPending`, `evidenceExportAll`, `evidenceImportPackageObject`, `evidencePutPackage` or `evidenceAllocateSequence` |
| 4 | It reads the store **three times** and fingerprints it — **including every mutable export field** — before and after. If anything moved it **refuses to emit a manifest** |

It prefers MOGO's own `evidenceListPackages()`, which is already readonly by construction, and falls
back to its own readonly connection only if that function is absent.

**It never triggers a download.** Output goes to the console and the clipboard. A download is the
very mechanism EXP-001 showed cannot be trusted, and Step 4B forbids one.

**Counts are derived from the store itself.** The in-memory banner counters are recorded *separately*
under `bannerCounts` with the note that they are not authoritative, so the two can be **compared
rather than conflated**. If they disagree, the disagreement is the finding.

### 3.2 The twelve-point reconciliation, in `scripts/mogo_evidence_verify.js`

`--manifest <file>` now produces every item you specified:

| # | Output |
|---|---|
| 1 | authoritative browser package count |
| 2 | authoritative browser unique evidence identities |
| 3 | disk unique evidence identities |
| 4 | identities present in both |
| 5 | **browser identities missing from disk** |
| 6 | disk identities absent from browser |
| 7 | duplicate physical disk copies |
| 8 | packageId collisions — **on disk and inside the browser store**, each with the identities `packageId`-keyed counting would lose |
| 9 | contentHash mismatches — recomputation, and disk-vs-manifest |
| 10 | no-hash / synthetic / undetermined artifacts |
| 11 | export-attempt state discrepancies |
| 12 | confirmation-state discrepancies |

**`sourceTradeId` is the identity key throughout. `packageId` is never treated as authoritative**,
because Step 4A demonstrated real collisions — and §5 below shows the mechanism.

Items 11 and 12 **fail the run**. A browser/disk state disagreement means one population asserts a
fact the other denies; that is an inconsistency in the evidence record, not a presentational detail.
Item 6 is reported but does *not* fail, because Step 4A established that legitimate cross-profile
evidence exists on disk which the current store never held.

---

## 4. Validation

| Gate | Result |
|---|---|
| `tests/v131_evidence_verifier_tests.js` | **73/73 PASS** (49 → 73; +24 for Step 4B) |
| `node scripts/mogo_evidence_verify.js --selftest` | **43/43 PASS** |
| **Canonical gate `tests/run_all.sh`** | **18 suites · 1020 fixtures · 1020 passed · 0 failed** |
| Protected-function drift | **63 functions · 4 constants · 0 drift** |
| Campaign C1 | **33/33 · byte-identical across 42 files** |
| `index.html` | **unmodified** |

New fixtures V49–V72 cover: the twelve-point reconciliation against a synthetic browser manifest;
stored-but-not-found detection; a packageId collision **inside** the browser store; a
confirmation-state discrepancy; reconciliation returning **`null`** rather than a guess when no
manifest is supplied; and the snippet's read-only properties asserted against its own source.

**V62 caught a real defect during validation.** State discrepancies were being reported but not
counted as problems, so a corpus with a confirmation disagreement would still have exited zero. The
fixture failed, and the counting was fixed — not the fixture.

---

## 5. New defects

### D-12 — MOGO is reachable at two origins with **separate** evidence stores (High)

`http://localhost:8744` and `http://10.143.1.187:8744` are **different browser origins**. Browsers
isolate IndexedDB per origin, so each has its own `mogo_evidence` database **and its own
`evidenceAllocateSequence` counter**.

**This is demonstrated, not theorised:** both stores on this machine contain
`PKG|alex_g_sr_v1|20260731|1` — the same packageId minted independently, at the same origin-port,
for different evidence.

**This is the mechanism behind Step 4A's 12 collisions.** D-4 said "per-profile"; the truth is
**per-origin, and the operator demonstrably uses two origins for the same application**. Evidence
captured at one origin is completely invisible at the other — a standing evidence-fragmentation
hazard, and one that no amount of exporting will fix.

`.claude/launch.json` already records INC-004 on this exact ground: *"8743 was read from here, 8744
was assumed isolated because it differed, and 8744 was the operator's live MOGO origin. Nothing has
ever served on 8743."*

### D-13 — the browser stores contain synthetic test artifacts mixed with evidence (Medium)

`AGT|INSECURE|1` and `AGT|REALEXPORT|1` sit in the MOGO stores alongside real packages. Together
with `AGT|NOCRYPTO|1` and `AGT|MANUAL-B|…` from Step 4A, that is **at least four** synthetic
artifacts in the evidence population. The Decision 1 classifier handles them structurally, but any
count taken before classification — including the banner's — is inflated by an unknown number of
test artifacts.

---

## 6. Reconciliation output — what it says today

Every one of the twelve points is **UNDETERMINABLE** on this machine, and the tool reports it that
way rather than inventing an answer:

```
reconciliation : null          -- no browser manifest supplied
storedButNotFound : null       -- UNDETERMINABLE; disk contents MUST NOT be assumed complete
expectedStoredTotal : 222      -- OPERATOR_REPORTED, unverified
realEvidencePopulationOnDisk : 77
remainingGap : 145
```

This is the correct output. Fixture V63 asserts that reconciliation is `null` rather than guessed
when no manifest exists.

---

## 7. Constraint compliance

| Constraint | Status |
|---|---|
| Manifest operation observational / read-only | ✅ four structural guarantees, asserted by V65–V72 |
| Must not mark exported / confirmed, alter `exportedAt` or attempt metadata | ✅ no writer is called; asserted against the snippet's own source |
| Must not delete, clear, rewrite, regenerate identity | ✅ no such API appears in its logic |
| Must not trigger downloads | ✅ V71 |
| Must not execute trades or change paper-trading state | ✅ reads the evidence store only |
| Must not modify Campaign C1 | ✅ 33/33, 42 files byte-identical |
| Must not alter browser storage in any way | ✅ **no browser was opened**; stores were copied and the copies scanned |
| Prove read-only with before/after fingerprints | ✅ snippet: three reads, fingerprint covering every mutable export field. Verifier: 338-file SHA-256 + size + mtime |
| 222 independently derived from browser state, not the banner | ✅ attempted; **it could not be — reported as a discrepancy, not forced** |
| Do not treat packageId as authoritative identity | ✅ `sourceTradeId` throughout; browser-side collisions detected too |
| Do not repair / bulk export / confirm / auto-confirm | ✅ none attempted |
| Do not enable ALEX forward paper trading | ✅ OFF |
| Do not clear browser storage | ✅ nothing touched |
| Do not delete duplicate disk files | ✅ 338 files before and after |

---

## 8. Exact file state

### Committed (Step 4A) — `f139b8b`, **not pushed**

`scripts/mogo_evidence_verify.js` · `tests/v131_evidence_verifier_tests.js` ·
`tests/run_v131_evidence_verifier_tests.js`

### Uncommitted (Step 4B) — awaiting authorization

| File | State |
|---|---|
| `scripts/mogo_evidence_verify.js` | **modified** — reconciliation extended to twelve points |
| `tests/v131_evidence_verifier_tests.js` | **modified** — +24 fixtures (49 → 73) |
| `scripts/mogo_evidence_browser_manifest.js` | **new, untracked** |
| `MOGO-011-STEP-4B-REPORT.md` | **new, untracked** — this report |

`index.html` remains unmodified. Nothing staged, nothing tagged, nothing pushed.

---

## 9. What Step 4C needs, and the decision it now requires

**The single blocking item: run `scripts/mogo_evidence_browser_manifest.js` on the device that
actually holds the evidence store, and save the printed JSON.** Everything else is built and tested.

Then: `node scripts/mogo_evidence_verify.js --scan <DIR> --manifest <FILE>` produces the full
twelve-point reconciliation and the named stored-but-not-found work list.

**D-12 needs a decision before any repair.** The evidence store is split across two origins, and
`localhost:8744` and `10.143.1.187:8744` each hold packages the other cannot see. A manifest from one
origin reconciles only that origin. Deciding which origin is authoritative — or capturing a manifest
from **both** — must happen before any export or confirmation work, or Step 4C will confirm one
fragment and silently leave the other behind.

Also still outstanding from the Step 4 plan: **D-2 must be fixed before any re-export**, or a later
`Export all` will clear `exportedAt` on everything it touches. E-5 approved that fix; it is not yet
implemented.

---

## 10. Gate

**Stopped, as instructed.** Nothing repaired, no bulk export, no package confirmed, no automatic
confirmation implemented, no browser storage touched, no duplicate deleted, Campaign C1 untouched,
ALEX forward paper trading OFF.

**Requesting authorization for:**

1. committing Step 4B;
2. pushing Steps 4A and 4B;
3. a ruling on **D-12** — which origin is authoritative, or capture both;
4. Step 4C.
