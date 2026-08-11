# MOGO-011 STEP 4A — READ-ONLY OFFLINE EVIDENCE INVENTORY AND VERIFIER

**Status:** **BUILT, SELF-TESTED AND RUN — STOPPED AT THE IMPLEMENTATION/VALIDATION GATE**
**Nothing staged, committed, tagged or pushed. No evidence changed. ALEX forward paper trading OFF.**
**Date:** 2026-08-09
**Baseline:** `origin/mogo-main` = `HEAD` = `c7527a4b8c6dced08b6753667d8c76042fbfddac`

---

## 1. Headline result

| | |
|---|---|
| Locations scanned | **4** |
| Physical `.json` files considered | **338** |
| Parseable evidence packages | **122** |
| **Unique evidence identities** | **79** |
| Duplicate physical copies | **43** |
| Hash **VERIFIED** | **121** |
| Hash **MISMATCH** | **0** |
| Packages without a hash | **1** |
| **packageId collisions** | **12** |
| `sourceTradeId` splits | **0** — the identity key is sound |
| **REAL evidence identities** | **76** |
| **UNDETERMINED** | **1** (retained in counts) |
| **SYNTHETIC / test artifacts** | **2** (excluded from real-evidence counts, preserved unchanged) |
| **Files mutated by the verifier** | **0 of 338** |
| **Remaining gap against the reported 222** | **145** |

**The verifier run exits non-zero (12 problems). That is the correct outcome:** the 12 problems are
the 12 real `packageId` collisions. Nothing was mis-verified and nothing was corrupted — but the
corpus genuinely contains an identity hazard, and a tool that reported PASS over it would be lying.

---

## 2. Exact files created and modified

### Created — 5

| File | Purpose | In commit? |
|---|---|---|
| `scripts/mogo_evidence_verify.js` | The read-only inventory, verifier and artifact classifier | **yes** |
| `tests/v131_evidence_verifier_tests.js` | 49 fixtures (Node — the behaviour under test *is* filesystem + crypto) | **yes** |
| `tests/run_v131_evidence_verifier_tests.js` | JXA shim so `run_all.sh` discovers and counts the suite | **yes** |
| `MOGO-011-STEP-4A-INVENTORY.json` | Full machine-readable inventory of every location, file and decision | no — working artifact |
| `MOGO-011-STEP-4A-REPORT.md` | This report | no — governance document |

### Modified — 0

**`index.html` was not touched.** Neither was any test, any existing script, any document, any
package, or any Campaign C1 artifact. `git status` for tracked files is empty.

`MOGO-011-STEP-4A-INVENTORY.json` is a working artifact at the repository root and is currently
**untracked**. It is deliberately *not* placed under `evidence/` — that directory holds the frozen
Campaign C1 set, and the verifier refuses to write there by design (§4.3).

---

## 3. How the verifier reuses `mogo.evidence-canon.v1`

**It does not reimplement it.** A second implementation would be a second source of truth, and the
first time the two disagreed the evidence chain would have two answers and no authority.

The tool reads `index.html`, locates by brace-depth extraction the **exact source text** of:

- `const EVIDENCE_HASH_EXCLUDED_FIELDS=…`
- `function evidenceCanonValue(v,seen){…}`
- `function evidenceCanonicalize(pkg){…}`

and evaluates that text. This is the same technique the existing fixture harness
(`tests/run_v128_evidence_platform_tests.js`) uses to assert against real shipped function text
rather than a paraphrase of it. The canonical form produced here is produced by the shipped code,
byte for byte, and every run records the provenance:

```
index.html sha256    : dd160a0ccaced6339e35802d4b3ffa00565420ead2c58440758a53f08803ecd6
canonicalizer sha256 : b7bb027e323b645f7de5ae529e5f88eeed9c09d7e57312deb8a913c97b032f4b
excluded from hash   : contentHash, contentHashAlgorithm, contentHashCanonicalization,
                       contentHashProvenance, contentHashScope, export
```

**One primitive is substituted, and it is disclosed rather than buried.** The browser digests with
Web Crypto's `crypto.subtle.digest('SHA-256', …)`, which does not exist in Node, so `node:crypto`'s
SHA-256 runs over the identical UTF-8 canonical bytes. That is a standard interchangeable digest,
not MOGO-specific logic — and the substitution is **proven, not asserted**: 121 packages whose
hashes were computed *by the browser* recompute identically here, with zero mismatches.

---

## 4. Read-only guarantees, and how they are proven

### 4.1 By construction

Evidence files are opened with `fs.readFileSync` only. There is no `writeFile`, `rename`, `unlink`,
`chmod` or `utimes` call anywhere in the file that can target a scanned path.

### 4.2 By measurement, on every run

Every scanned file is fingerprinted (**SHA-256 + size + mtime**) before the scan and again after it.
Any difference is reported and fails the run.

```
files fingerprinted before and after : 338
mutations detected                   : 0
every scanned file is byte-, size- and mtime-identical after the run
```

**The mutation detector is itself negative-controlled** in the self-test: a deliberately altered
fingerprint must produce exactly one detection. A detector never shown to fire proves nothing.

### 4.3 Write-path refusals

The report output path is refused if it resolves inside:

- `evidence/` — the frozen Campaign C1 directory
- `docs/campaigns/` — the C1 manifest and certificates
- **any directory being scanned** — otherwise a report becomes an input to its own next run

All three refusals are exercised by the self-test.

---

## 5. Test results

### 5.1 `node scripts/mogo_evidence_verify.js --selftest` — **43/43 PASS, exit 0**

| Group | What it proves |
|---|---|
| Canonicalizer provenance (4) | Both real functions were located in `index.html`, the extracted text is present verbatim, and the excluded-field list came from the app — not from a constant typed here |
| Canonical form (3) | Object key order is insignificant; **array order is significant**; a differing `export` block does not change the content hash |
| Classification (6) | 7 physical files → 5 parseable packages, 3 identities, correct `NO_HASH`, malformed-not-fatal, and an unrelated `.json` is **not** treated as evidence |
| **Negative control** (1) | **One tampered byte produces exactly one `HASH_MISMATCH`** — the verifier can fail |
| Duplicates (4) | Three copies of one identity are grouped; all carry the same *recorded* hash; all three differ in file bytes; and **recomputation separates the 2 honest copies from the 1 corrupted one sharing their identity** |
| Identity (4) | The collision is detected; no `sourceTradeId` split; 3 real identities hide behind 2 packageIds; counting by `packageId` would **lose exactly 1** |
| Unparseable scoping (4) | A malformed file among evidence is a problem; the same file in a non-evidence tree is reported but is not evidence |
| Gap arithmetic (2) | `expected − unique` is computed, and stored-but-not-found is reported **UNDETERMINABLE** without a manifest |
| **Read-only proof** (5) | No scanned file changed; the run self-reports clean; all files fingerprinted; **no file was created in the scanned directory**; a corpus with a mismatch does not pass |
| **Mutation-detector control** (1) | The detector fires when a file really does change |
| Manifest reconciliation (3) | A stored-but-not-found package is detected and identified by `sourceTradeId` |
| Write guards (4) | `evidence/`, `docs/campaigns/`, and any scanned directory are all refused; an ordinary path is allowed |

**Two self-test expectations were wrong on first run and were corrected — the code was right.** My
corpus gave identity `T1` three physical copies rather than two, because the tampered file shares
that identity. That case is now asserted explicitly, and it is the more interesting one: a corrupted
copy carries the *same recorded* `contentHash` as its honest siblings, so only recomputation tells
them apart. That is precisely why the hash field is never trusted on its face.

### 5.2 Unaffected gates, re-run

| Gate | Result |
|---|---|
| Canonical regression `tests/run_all.sh` | **17 suites · 947 fixtures · 947 passed · 0 failed** |
| Protected-function drift | **63 functions · 4 constants · no drift** |
| Campaign C1 manifest | **33/33 verified · 0 missing · 0 mismatched · 0 unlisted** |

`index.html` is untouched, so these could not have moved — they were re-run to prove it rather than
to assume it.

### 5.3 `tests/v131_evidence_verifier_tests.js` — **49/49 PASS, exit 0** (Decision 2)

Wired into `tests/run_all.sh`. **The canonical gate is now 18 suites, 996 fixtures, 996 passed,
0 failed** (947 + 49). Protected-function drift remains **0**.

| Required proof | Fixtures |
|---|---|
| Valid evidence verifies | V6, V17 |
| **Tampered evidence fails** | V7, V8, V9 |
| Duplicate physical copies do not become new evidence identities | V12–V17 |
| **packageId collisions are detected** | V18–V23 |
| Source files remain unchanged | V24, V27 |
| **Verification cannot mutate evidence** | V25, V26, V28, V29 |
| **Canonical hash recomputation matches the browser-generated hash** | **V10, V11 — on 121 real packages** |
| No second canonicalization implementation | V1–V5b |
| Classification is structural, not nominal (Decision 1) | V30–V45 |
| Reconciliation keys on `sourceTradeId` | V46–V48 |

**V5 is the strongest of these.** It takes the canonicalize function object the fixtures actually
execute, reads its own source back out of the running process, and finds that exact text inside
`index.html`. A copy living in the test file or in the verifier could not satisfy it.

**Why the fixtures run under Node.** The behaviour under test *is* filesystem and cryptographic
behaviour. JXA has neither `fs` nor `crypto`, and asserting those properties against stubs would
prove nothing about them. `tests/run_v131_evidence_verifier_tests.js` is a JXA shim that locates
Node, runs the fixtures, and relays their PASS/FAIL lines so `run_all.sh` counts them like any other
suite. **If Node cannot be found the shim FAILS loudly** — a suite that silently passes when it could
not run is worse than no suite.

Two shim defects surfaced during validation and were fixed, both caught by the shim's own guards
rather than by inspection: `doShellScript` returns CR-separated output, so an `\n`-only split
collapsed all 49 results into one line; and the wrong-directory path was verified to fail loudly.

---

## 6. Inventory results

### 6.1 Every location scanned

| Location | `.json` files | Evidence packages |
|---|---:|---:|
| `~/Desktop/MOGO-Evidence` | 74 | 67 |
| `~/Desktop/MOGO-Evidence-C1` | 33 | **0** |
| `~/Desktop/MOGO-Evidence-PILOT` | 175 | **0** |
| `~/Downloads` | 56 | 55 |
| **Total** | **338** | **122** |

`MOGO-Evidence-C1` holds 33 `C1-*-{HARVEST,PACKAGES,REJECTED}.json` files — a **copy of the Campaign
C1 artifacts**. The verifier correctly classified all 33 as `NOT_A_PACKAGE`: they are campaign output,
not evidence packages, and are not counted as such. `MOGO-Evidence-PILOT` contains a full Chrome
profile cold-copy; **no evidence package is hiding in it**, which is worth knowing.

### 6.2 Where the packages actually are — three directories

| Directory | Files | Unique identities |
|---|---:|---:|
| `~/Downloads` | 55 | 45 |
| `~/Desktop/MOGO-Evidence/MOGO-Evidence-Live-Paper-Prelaunch-2026-08-08` | 43 | 43 |
| `~/Desktop/MOGO-Evidence/alex_g_sr_v1-EUR_USD-90d-3d7c3dc1af7f` | 24 | 24 |

### 6.3 Canonical evidence identity

**Identity key: `sourceTradeId`.** It is immutable, it is present on all 122 packages, and **0
`sourceTradeId`s map to more than one `packageId`** — the key is sound across the whole corpus.

`packageId` is **not** a safe key, and the corpus quantifies the damage exactly:

| | |
|---|---|
| Distinct `sourceTradeId` (real packages) | **79** |
| Distinct `packageId` | **65** |
| **Identities lost if counting by `packageId`** | **14** |

**Counting this corpus by `packageId` would silently lose 14 real evidence packages.**

### 6.4 packageId collisions — 12

Every collision is a **different source trade** sharing a minted id, never one trade whose content
drifted. `evidenceAllocateSequence()` counts per `(strategy, yyyymmdd)` in **per-profile** IndexedDB
state, so a fresh or disposable profile re-mints from 1.

| packageId | distinct source trades | distinct hashes |
|---|---:|---:|
| `PKG\|alex_g_sr_v1\|20260408\|1` | **3** | 3 |
| `PKG\|alex_g_sr_v1\|20260513\|1` | **3** | 3 |
| `20260406\|1` · `20260420\|1` · `20260423\|1` · `20260424\|1` · `20260427\|1` · `20260429\|1` · `20260506\|1` · `20260507\|1` · `20260513\|2` · `20260702\|1` | 2 each | 2 each |

**The shipped guard already refuses these.** `evidenceEvaluateExportReimport()` compares
`sourceTradeId` as well as `packageId`, so a colliding foreign package cannot falsely confirm a
stored one. Production identity semantics are **unchanged by this step**, as instructed — measured
only.

### 6.5 Duplicate detection

| | |
|---|---:|
| Identities with more than one physical copy | **43** |
| …agreeing on `contentHash` | **43** |
| …**conflicting** on `contentHash` | **0** |

All 43 are benign: the copies differ only in their `export` block, which canonicalization excludes,
so **any one of them verifies correctly**. Physical files and evidence identities are reported as
separate quantities throughout — 122 files, 79 identities, 43 duplicates.

### 6.6 Hash verification

| Result | Count |
|---|---:|
| **VERIFIED** | **121** |
| **MISMATCH** | **0** |
| `NO_HASH` | 1 |
| Not canonicalizable | 0 |
| Unsupported algorithm | 0 |
| Unique identities with at least one verified copy | **78 of 79** |

### 6.7 Malformed and unverifiable files

**One malformed `.json`**, and it is **not evidence**:

```
~/Desktop/MOGO-Evidence-PILOT/00-PROFILE-COLD-COPY/full-profile/
    FirstPartySetsPreloaded/2025.7.24.0/sets.json
```

A Chrome component file in a copied browser profile. The verifier reports it and does **not** count
it as a problem, because an unparseable file only fails the run when it sits in a directory that
holds evidence. Conflating the two would make this gate cry wolf on every broad scan, and a gate
that cries wolf is one nobody reads. **0 unparseable files were found among evidence.**

**One package without a hash.** Its provenance is established in §6.8 — it is a synthetic test
artifact, and it is classified as such by structural rule, not by its name.

### 6.8 Artifact classification (Decision 1) — and a correction to my earlier finding

**Decision 1 required provenance to be established from evidence, not inferred from a filename.**
It was, and the result is broader than expected.

`NOCRYPTO` appears **nowhere in the repository**. Provenance therefore had to come from the
artifacts themselves. Measuring holding period across all 79 identities produced an absolute
separation with nothing in between:

| Population | n | Shortest holding period |
|---|---:|---|
| `REPLAY_RUN` | 76 | **3,600,000 ms** (exactly one H1 bar) |
| `LIVE_CLOSE` | 3 | **0 ms, 0 ms and 4 ms** |

Six orders of magnitude. A position cannot close before its own first bar has closed.

#### The deterministic rule

Two structural rules, both physical contradictions internal to the package. **Neither reads a
filename, a path, or any identifier string** — fixture V39 asserts that against the classifier's own
source, and V37/V38 prove a reassuring name cannot rescue an impossible artifact and a suspicious
name cannot condemn a plausible one.

- **SYN-1 `IMPOSSIBLE_HOLDING_PERIOD`** — `exit − entry` is shorter than one bar of the position's
  own timeframe (60,000 ms floor when no timeframe is recorded).
- **SYN-2 `EXCURSION_CONTRADICTION`** — the price moved between entry and exit, yet `maePips` and
  `mfePips` are **both exactly 0**. A `null` is a completeness gap, not a contradiction (V35).

`SYNTHETIC` requires **two or more** rules. Exactly one leaves the artifact **UNDETERMINED**, and an
UNDETERMINED artifact **stays in the counts** — an unproven suspicion must never quietly shrink a
population, because that is the direction that makes a backlog look smaller than it is.

#### Result — 2 synthetic, 1 undetermined, and a correction

| Identity | Class | Engine | Created | Why |
|---|---|---|---|---|
| `AGT\|NOCRYPTO\|1` | **SYNTHETIC** | 12.8.0 | 2026-07-31 | 0 ms hold on H1; 1.10 → 1.09 with zero excursion |
| `AGT\|MANUAL-B\|1785634676564` | **SYNTHETIC** | 12.8.4 | 2026-08-02 | 0 ms hold on H1; 1.10 → 1.11 with zero excursion |
| `1786021876135` (JVM) | **UNDETERMINED** | 12.19.0 | 2026-08-06 | 4 ms hold — one rule only, so retained in counts |

**I must correct my earlier Step 4A report.** It described `AGT|MANUAL-B|1785634676564` as
`VERIFIED (ALEX)` — a real closed paper trade. Its hash **is** valid, but **verified is not the same
as real**: it opened and closed in the same millisecond, moved a full 100 pips, and recorded zero
excursion. It is a test artifact. The earlier statement was wrong.

**The consequence is significant: there is no real forward-paper-trading evidence on disk at all.**
All 76 REAL identities are `REPLAY_RUN`. That is coherent — ALEX forward paper trading has never
been enabled — but it means the disk corpus contains zero examples of the very thing the preflight
exists to protect.

Corroborating detail for `AGT|NOCRYPTO|1`, none of it load-bearing for the classification: its
`completenessReport` carries the shipped text *"Web Crypto (crypto.subtle) is not available in this
browsing context"*; its `createdAt` of **2026-07-31** matches the date `docs/KNOWN_ISSUES.md` records
for the EXP-001 live proof; and its `export` block has the **old four-key pre-EXP-001 shape**,
consistent with engine 12.8.0. Both synthetic artifacts also carry round-number prices, balances and
sizes, and `AGT|MANUAL-B` carries placeholder zone and reaction ids (`zB`, `rB`) rather than
engine-minted ones.

#### Retention

**Both synthetic artifacts are preserved byte-for-byte and nothing was deleted** (V40). They are
excluded from the *real-evidence population* only, and every report states the exclusion explicitly
rather than silently applying it (V42, V43).

---

## 7. Comparison against the reported 222, and the exact remaining gap

| | |
|---|---|
| Operator-reported stored total | **222** |
| Provenance of that number | **OPERATOR_REPORTED** — this tool cannot verify the browser store |
| Unique identities found on disk | **79** |
| …of which SYNTHETIC (excluded) | 2 |
| …of which UNDETERMINED (retained) | 1 |
| **Real-evidence population on disk** | **77** |
| **Remaining gap** | **145** |
| Stored-but-not-found | **UNDETERMINABLE** — no manifest supplied |

**Three things this does not establish, stated plainly:**

1. **It does not establish that 143 packages are lost.** It establishes that 143 of the reported 222
   have no counterpart on this disk **that this scan found**. They may exist in an unscanned
   location; they may never have been written.
2. **It does not establish that the 79 are a subset of the 222.** Several are Campaign C1 replay-run
   packages that may predate the current store. Only a browser-exported manifest can settle this,
   which is exactly why the verifier supports `--manifest` and reports the field as
   `UNDETERMINABLE` rather than guessing.
3. **The disk contents must not be assumed complete.** The tool records this in its own output.

### 7.1 The prelaunch folder is not the evidence set — with numbers

| | |
|---|---:|
| Unique identities in `MOGO-Evidence-Live-Paper-Prelaunch-2026-08-08` | **43** |
| Unique identities that exist **only outside** it | **36** |
| Fraction of the reported 222 that folder covers | **~19%** |

Your instruction not to assume that folder is complete is confirmed twice over: it is missing 143
of the reported 222, **and** it is missing 36 packages that are sitting elsewhere on this same disk.

### 7.2 A signal about how the files were produced

Across the 79 unique identities, the `export` block **as written into each file**:

| `exportedAt` | `exportAttemptedAt` | Identities |
|---|---|---:|
| absent | **present** | 48 |
| absent | absent | 31 |
| **present** | — | **0** |

**Not one package on disk has ever been confirmed** — consistent with all 222 being reported
unexported, and consistent with defect **D-1** (the Import control being unreachable).

The 31 with no attempt record at all were written by something other than the download path — almost
certainly the receiver, during the C1 campaign. **Caveat: an `export` block in a file is a snapshot
from write time, not the current state of the browser store.** It tells us how the file was
produced; it does not tell us what IndexedDB holds now.

---

## 8. Did any evidence change?

**No.**

| Check | Result |
|---|---|
| Files fingerprinted before and after the run | **338** |
| Mutations detected (bytes, size or mtime) | **0** |
| Files in the four scanned locations, before and after | **338 → 338** |
| Campaign C1 + `docs/campaigns` vs pre-4A snapshot (42 files) | **byte-identical** |
| Campaign C1 manifest re-verification | **33/33 · 0 missing · 0 mismatched · 0 unlisted** |
| Browser storage | **not touched** — no browser was opened |
| The 222 stored packages | **not touched, not marked, not counted as confirmed** |
| `index.html` | **unmodified** |
| Tracked working tree | **clean** |
| `HEAD` | `c7527a4…` unchanged |

---

## 9. Did Campaign C1 remain byte-identical?

**Yes.** Verified two independent ways:

1. A 42-file SHA-256 manifest of `evidence/` + `docs/campaigns/` taken before Step 4A and re-computed
   after: `diff` clean. Roll-up hash
   `4ebea5cb72ecef7abc9dc751ff6d876496bc6e2f5dd1698b6a15e408edeaa47a`.
2. Independent re-hash of all 33 C1 artifacts against
   `docs/campaigns/C1/CAMPAIGN_C1_EVIDENCE_MANIFEST.md`: **33/33**, 13,575,486 bytes, exact.

The 33-file **copy** in `~/Desktop/MOGO-Evidence-C1` was scanned read-only, correctly classified as
non-evidence-package, and left byte-identical.

---

## 10. New defects discovered in Step 4A

Three, all quantitative refinements of what §4 of the Step 4 plan predicted:

| | Finding | Severity |
|---|---|---|
| **D-8** | **`packageId`-keyed counting undercounts this corpus by 14** (79 real identities behind 65 packageIds). Any reconciliation, dedup or progress counter keyed on `packageId` would silently drop 14 real packages — and would report a *smaller* backlog than actually exists, which is the dangerous direction | **High** |
| **D-9** | **The prelaunch folder is missing 36 identities that exist elsewhere on this disk.** "Collect the folder" is not a sufficient strategy; a multi-location scan is mandatory | **Medium** |
| **D-10** | **31 of 79 packages on disk carry no export-attempt record in their own file**, so the browser's `attempted` population and the disk population are **partially disjoint**. Reconciliation must be by content and identity, never by attempt bookkeeping | **Medium** |

| **D-11** | **Two synthetic test artifacts are indistinguishable from real evidence by hash alone.** Both verify perfectly — they are internally consistent — yet neither is a real trade. Hash verification proves integrity, never authenticity, exactly as `EVIDENCE_HASH_SCOPE` says. Any count of "real evidence" that keys on verification status alone will over-report | **Medium** |

No defect was found in the shipped verification logic. **`evidenceEvaluateExportReimport()` remains
correct and remains untouched.**

---

## 11. Recommendations for Step 4B

**Ordered, and each is a consequence of a measurement above.**

1. **Export the read-only browser manifest first.** Everything material is currently
   `UNDETERMINABLE`: whether the 79 are a subset of the 222, and which of the 222 are truly missing.
   `evidenceListPackages()` is already read-only and needs no code change. The verifier's
   `--manifest` path is built, self-tested, and waiting.
2. **Re-run this verifier with `--manifest`.** That converts "gap 143" into a named
   stored-but-not-found list keyed on `sourceTradeId` — the actual work list for 4C.
3. **Fix D-2 before any re-export.** Under the current code `Export all` clears `exportedAt` on
   every package it touches. With E-5 approved this is now unblocked. **Nothing should be re-exported
   until it lands**, or confirmation work will be destroyed by the next click.
4. **Key every counter on `sourceTradeId` (D-8).** Including the in-app unexported/confirmed counts.
   A `packageId`-keyed counter under-reports the backlog.
5. ~~Settle E-3~~ — **done under Decision 1.** Two artifacts classified SYNTHETIC by structural
   rule, one UNDETERMINED and retained. All three preserved unchanged.
6. ~~Add the fixture suite~~ — **done under Decision 2.** 49 fixtures, wired into `run_all.sh`,
   canonical gate now 996.
7. **When egress resumes, write to a dedicated empty directory** with an explicit `--out`, never the
   receiver's default `evidence/` (**D-6**).
8. **Do not enable ALEX forward paper trading.** Under E-4 the preflight is now a required
   fail-closed gate, and criteria 1–11 of the Step 4 plan are **not** met: coverage is 79 of 222,
   confirmed is 0, and stored-but-not-found is undeterminable.

---

## 12. Constraint compliance

| Constraint | Status |
|---|---|
| Reuse `mogo.evidence-canon.v1` exactly | ✅ extracted verbatim from `index.html`; provenance hashed in every report |
| No second canonicalization or trust path | ✅ only the SHA-256 primitive is substituted, disclosed and proven against 121 browser-computed hashes |
| Read actual exported files from disk | ✅ 338 files across 4 locations |
| Do not modify / rename / move / delete / rewrite them | ✅ 0 mutations over 338 files, fingerprint-proven |
| Do not modify browser storage | ✅ no browser opened |
| Do not mutate application evidence state | ✅ `index.html` untouched |
| Do not modify frozen Campaign C1 evidence | ✅ 42 files byte-identical; 33/33 re-verified |
| Do not write output into the C1 directory | ✅ structurally refused, and the refusal is self-tested |
| Duplicate physical files separate from unique identity | ✅ 122 files / 79 identities / 43 duplicates reported separately |
| Detect and report packageId collisions | ✅ 12 detected and enumerated |
| Use `sourceTradeId` for identity, don't change production semantics | ✅ measured only; no app change |
| Distinguish all nine required categories | ✅ §6 |
| Don't infer disk = all 222 | ✅ reported `UNDETERMINABLE`, in the tool's own output |
| Do not mark browser packages confirmed | ✅ the tool cannot write to the browser at all |
| Do not enable ALEX forward paper trading | ✅ untouched, OFF |

---

## 13. Gate

**Step 4A is committed** under the authorization granted, and **not pushed** — MOGO-011 governance
has treated commit and push as separate authorization gates at every step of this milestone
(Steps 1, 2 and 3 each required distinct push authorization), so I stopped after the commit.

Nothing tagged. Nothing pushed. ALEX forward paper trading OFF.

**Awaiting authorization to push Step 4A.**
