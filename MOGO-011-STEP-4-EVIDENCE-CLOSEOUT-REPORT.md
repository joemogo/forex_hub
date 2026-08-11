# MOGO-011 STEP 4 — EVIDENCE CLOSEOUT REPORT

**Conclusion: CONDITIONAL PASS** *(final — reconciliation complete)*
**Date:** 2026-08-10 · **Repository HEAD:** `fb3658ecde31a46c88e5e40e69e05660914e70c9`
**ALEX forward paper trading: OFF · Evidence-export preflight: FAIL-CLOSED · Step 4C: not begun**

---

## 1. Verdict

**CONDITIONAL PASS.** The 222-package corpus is **preserved, located, enumerated and structurally
sound**. It is **not yet independently hash-verified package by package**, and the pipeline that was
supposed to produce that verification is defective in four named ways.

| Question | Answer |
|---|---|
| Is the corpus safe from loss? | **Yes** — byte-identical checkpoint, verified per-file |
| Is it located and identified? | **Yes** — 221 of 222 packageIds recovered offline (99.5%) |
| Does every package carry a hash? | **Yes** — 0 without a content hash, from two independent methods |
| Is every package independently re-hashed? | **No** — see §5. This is what makes it *conditional* |
| Is there real forward-paper evidence? | **No** — the corpus is replay evidence |
| Can the export pipeline be trusted today? | **No** — D-1, D-3, D-14 remain open (**D-2 is now fixed, §13**) |

**PASS was not available** because independent recomputation of each package's hash has not been
performed. **FAIL was not warranted** because nothing is lost, nothing is corrupted, and every
measurement that could be taken agrees with every other.

---

## 2. What the corpus actually is

Located at a **third origin** nobody had accounted for: `http://localhost:8751`, inside a
**disposable Chrome test profile** at
`/var/folders/…/T/mogo-browser-test-profiles/profile-20260805T230552Z-48568`.

That is the headline risk finding of this entire milestone. **222 evidence packages were accumulating
inside a temp-directory profile created by tooling whose stated purpose is to be thrown away**, in a
location macOS purges — and seven sibling profiles in that same directory are already empty, three of
them emptied within 36 hours of discovery.

| | |
|---|---|
| Origin | `http://localhost:8751` — secure context, Web Crypto available |
| Database | **`mogo_evidence_v1`** — a name that appears **nowhere in this repository's history** |
| Store | `http_localhost_8751.indexeddb.leveldb`, 4.1 MB + 72 KB blob sidecar |
| Banner | 222 packages · 222 unexported · 222 attempted · **0 unverifiable** |

---

## 3. Preservation — the part that is unambiguously done

**Checkpoint:** `~/MOGO-EVIDENCE-PRESERVED/20260810T005409Z` — 37 files, 8.0 MB.

Verified independently, not accepted on report:

- **Per-file SHA-256 across all 7 store files: all OK** (`000026.log`, `000028.ldb`, `000029.ldb`,
  `MANIFEST-000001`, `CURRENT`, `LOG`, `LOCK`).
- **IndexedDB tree hash MATCH** on both preserved profiles.
- The 48568 tree hash was **identical to a reading taken 13 minutes earlier**, proving the store was
  idle and the copy is not torn.
- The `.blob` sidecar was captured.

**The catastrophic-loss risk is eliminated.** This is the single most important outcome of Step 4.

**Residual risk:** the checkpoint sits on `/dev/disk1s1` — the same physical volume as the source. It
protects against temp-purge, not disk failure. An off-volume copy is recommended.

---

## 4. Offline reconstruction — method and result

`scripts/mogo_evidence_leveldb_extract.js` (new) reconstructs a manifest from the checkpoint with no
browser involved.

**Two earlier approaches failed, and the failures are instructive rather than incidental:**

1. **Whole-store token pairing under-reported silently.** V8 replaces any string it has already
   emitted with a back-reference, so field names vanish after first use. Records ran together and
   the store appeared to hold 30 identities instead of 221.
2. **Field-name adjacency mis-assigned values.** `contentHash` appears twice in every package — once
   as the real field, once inside `completenessReport.missing[]` as
   `{field:'contentHash', reason:'UNAVAILABLE'}`. Naive pairing recorded a package's hash as the
   literal string `"reason"`.

**The working method:** split on the V8 record header (`0xFF <version> 0x6F`), which yields one
record per package, then identify each value **by its own grammar** rather than by an adjacent field
name that serialization may have removed. Every field carries a shape test; a failing value is
discarded rather than recorded, because a wrong hash in an evidence manifest is worse than a missing
one.

Covered by an 8-check selftest including the exact `"reason"` decoy, superseded-version dedup, and
refusal to read a live browser profile.

### Results

| | |
|---|---:|
| V8 record headers found | 283 |
| Records parsed | 280 |
| Superseded LevelDB versions collapsed | 31 |
| **Distinct packageIds recovered** | **221** |
| **Distinct content hashes recovered** | **221** |
| **Packages without a content hash** | **0** |
| Distinct `sourceTradeId` decoded | 28–56 — **under-decoded by the reader, see §5** |
| Capture basis | `REPLAY_RUN` 248 · `LIVE_CLOSE` 1 |

**221 of 222 — 99.5%.** Two fully independent methods (a whole-store token walk and per-record
extraction) arrived at 221 separately. **The live manifest has since resolved the one-package
difference**: it reports 222 unique `packageId` and 222 unique `sourceTradeId`, so there is no
collision in the store and the gap is a limitation of my reader — see §6.1.

**The 222 count is corroborated by the store's own manifest and independently reproduced to 99.5%
offline. It has not been forced.**

---

## 5. What remains unverified, stated precisely

| Not established | Why | Consequence |
|---|---|---|
| Independent recomputation of each package's `contentHash` | Requires full V8 deserialization of ~27 KB objects, not just string extraction | Hashes are **read**, not **re-derived**. Integrity is asserted by the store, not confirmed by us |
| Per-package `sourceTradeId` for all 222 | Only 28–56 decode offline; long unique IDs straddle LevelDB block boundaries. **The live manifest confirms all 222 exist and are unique** | Reconciliation keys on `contentHash`, which is a stronger identity anyway |
| Whether the 8751 build's canonicalization matches this repo | It reports database `mogo_evidence_v1`; **this repo has `mogo_evidence`** and no history of `_v1` | The running app is **not** the committed `index.html` |

**One strong mitigating measurement:** 43 content hashes appear in **both** the checkpoint and the
disk exports, and those disk packages were **independently re-hashed offline and verified 121/122 in
Step 4A** using the canonicalizer extracted from this repository's `index.html`. So the 8751 build's
canonicalization is **demonstrably compatible** with the committed one — on a 43-package sample. That
is real evidence, and it is not proof for all 222.

---

## 6. Twelve-point reconciliation — COMPLETE

**Identity key: `contentHash`.** This is deliberate and is *stronger* than matching on
`sourceTradeId`: the content hash covers the entire package — `sourceTradeId` is not an excluded
field — so a hash match asserts byte-identical canonical content, not merely a shared label.

| # | Point | Result |
|---:|---|---|
| 1 | Authoritative browser package count | **222** |
| 2 | Authoritative browser unique identities | **222** — 222 unique `sourceTradeId` = 222 unique `packageId` |
| 3 | Disk unique evidence identities | **78 hashes / 79 trade ids** |
| 4 | Identities present in **both** | **43** |
| 5 | **Browser identities missing from disk** | **178** |
| 6 | Disk identities absent from browser | **35** |
| 7 | Duplicate physical disk copies | **44** |
| 8 | `packageId` collisions | browser **0** · disk **12** · checkpoint **0** observed |
| 9 | `contentHash` mismatches | **0** — 121/122 recomputed and verified offline in Step 4A; 0 checkpoint-vs-disk conflicts |
| 10 | No-hash / synthetic / undetermined | browser **0 no-hash** · disk 1 no-hash, 2 SYNTHETIC, 1 UNDETERMINED |
| 11 | Export-attempt state discrepancies | **0** |
| 12 | Confirmation-state discrepancies | **0** — browser 0 confirmed, disk 0 confirmed |

**Coverage:** 221 of 222 hashes recovered from the checkpoint (**99.5%**). Union by content identity
across browser and disk: **256**.

**The finding that matters: 178 packages exist only inside that temp-profile database.** Before the
checkpoint they existed in exactly one place, on volatile storage, with no backup.

The 35 disk-only hashes are prior-run and prior-profile evidence the current store never held. This
corrects Step 4B's "zero overlap" reading, which was measured against the `8744` stores — a different
origin, and the wrong one.

### 6.1 The one-package ambiguity is now resolved

The live manifest reports **222 unique `packageId` and 222 unique `sourceTradeId`**, so there is **no
collision inside the 8751 store**. The single-package gap in my offline extraction (221 of 222) is
therefore a **limitation of my reader**, not a property of the corpus: long `sourceTradeId` strings
straddle LevelDB block boundaries, and recovering them would require a full SST block parser.

Both readings I previously left open are now settled — and the answer is the benign one.

---

## 7. Is there genuine forward-paper-trading evidence?

**No.** The corpus is `REPLAY_RUN` by an overwhelming margin (248 vs 1 decoded; 277 vs 3 by raw token
count). Step 4A classified the only three `LIVE_CLOSE` artifacts on disk as **2 SYNTHETIC** (
structurally impossible: same-millisecond open and close, price movement with zero excursion) and
**1 UNDETERMINED**.

**The preflight has never been exercised against the class of evidence it exists to protect.** That
is coherent — ALEX forward paper trading has never been enabled — but it means passing this preflight
would prove nothing about forward-paper evidence.

---

## 8. Open defects blocking an unconditional PASS

| | Defect | Status |
|---|---|---|
| **D-1** | The **Import package… control is Developer-Mode-only**, while the banner instructing its use is not. This is why 0 of 222 are confirmed | open |
| **D-2** | A re-export silently demoted a confirmed package | ✅ **REMEDIATED — see §13** |
| **D-3** | **No batch import** — single-file input. 222 packages = 222 manual picks | open |
| **D-8** | `packageId`-keyed counting under-reports — proven again here | open |
| **D-12** | Evidence fragmented across **three** origins with separate stores and separate sequence counters | open |
| **D-14** | `http://10.143.1.187:8744` is not a secure context and **cannot hash evidence at all** | open — **does not affect 8751** |
| **D-15** *(new)* | **The authoritative corpus lived only in a disposable temp-directory profile** with no backup | **mitigated** by the checkpoint; the practice is not fixed |
| **D-16** *(new)* | **The running build is not the committed `index.html`** (`mogo_evidence_v1`). An evidence engine whose source is not in version control cannot be audited | open |

---

## 9. Minimum engineering work for a clean automated forward-paper evidence pipeline

Ordered. Each is small; the value is in the sequence.

**M-1 — ✅ DONE. See §13.** `exportedAt` is now monotonic at the store layer. *The prohibition on
running an export is lifted by this fix alone; the remaining blockers are D-1 (unreachable Import
control) and D-3 (no batch import), which make confirmation impractical rather than unsafe.*

**M-2 — Make the confirmation control reachable (D-1).** Move *Import package…* and the
unexported/attempted counters out of the Developer-Mode card into the operator-visible surface
rendered by the same ungated function as the banner. Add the fixture: *no banner may name a control
its own visibility policy hides.*

**M-3 — Batch re-import (D-3).** Add `multiple` + `webkitdirectory` to the file input and iterate
`input.files`, calling the **unchanged** `evidenceEvaluateExportReimport()` once per file. One folder
selection replaces 222. No new trust surface, no new crypto, no receipt to forge — the app still
reads the bytes back from disk itself.

**M-4 — Deterministic egress that reports success (EXP-001).** Add receiver POST alongside the
anchor-click download, which returns an acknowledgement with a byte count so a failure is
*observable*. A receiver ack remains an **attempt**, never a confirmation. Requires governance
decision **E-2** (a third `exportMechanism`).

**M-5 — Multi-origin provenance as a first-class field (D-12).** Every manifest row, every
confirmation record and every export filename carries its origin. Counters key on `sourceTradeId`,
never `packageId` (D-8).

**M-6 — Get the evidence engine into version control (D-16).** Reconcile the 8751 build with
`index.html`, or record explicitly which build produced which packages. An evidence engine outside
version control cannot be audited, and its canonicalization cannot be verified.

**M-7 — Stop capturing real evidence in disposable profiles (D-15).** Either designate a durable
origin and profile for evidence-bearing runs, or have `browser_test_profile.sh` refuse to run against
a build that captures evidence. Automatic checkpointing of the evidence store belongs here too.

**M-8 — Wire the preflight to the real gate (E-4, approved).** Fail-closed, keyed on
`sourceTradeId`, requiring: manifest ⟷ disk reconciliation clean, every package hash-verified by
independent recomputation, named exceptions only, and Campaign C1 intact.

**Only after M-1 … M-8** can forward paper trading be enabled — and enabling it remains a separate,
explicit authorization regardless.

---

## 10. Tooling produced (all read-only w.r.t. evidence)

| Tool | Status |
|---|---|
| `scripts/mogo_evidence_verify.js` | committed `f139b8b` / `ce94424` — offline verifier + 12-point reconciliation |
| `scripts/mogo_evidence_browser_manifest.js` | committed `ce94424` — in-page read-only manifest exporter |
| `scripts/mogo_evidence_store_scan.js` | committed `fb3658e` — forensic multi-origin scanner |
| **`scripts/mogo_evidence_leveldb_extract.js`** | **new, uncommitted** — offline checkpoint manifest extractor, 8/8 selftest |
| `tests/v131_evidence_verifier_tests.js` | committed — 73 fixtures, in the canonical gate |

Canonical gate at last run: **18 suites, 1020 fixtures, 1020 passed, 0 failed.** Protected-function
drift **0**. Campaign C1 **33/33 byte-identical**.

---

## 11. Two process failures worth recording

**The clipboard retrieval failed twice, and both causes were mine.** Step A placed the manifest on
the clipboard; Step B then required copying a Bash command *to the clipboard* to paste into Terminal
— destroying it. The saved file contained my own command text. Separately, when converting that block
to a heredoc I dropped the `|| { echo FATAL; exit 1; }`, so the JSON parse failure never aborted and
`=== MANIFEST SAVED OK ===` printed over a broken result.

**Silence was again indistinguishable from success** — the same defect class as EXP-001, reproduced
in the tooling built to investigate EXP-001. Every instrument since fingerprints its own output and
fails loudly.

---

## 12. State at closeout

Repository `fb3658ecde31a46c88e5e40e69e05660914e70c9`, clean, synchronized with `origin/mogo-main`.
Live browser stores unmodified. Checkpoint verified byte-identical. Campaign C1 33/33.

Nothing exported through MOGO, imported, confirmed, deleted, or cleared. No browser storage mutated.
ALEX forward paper trading **OFF**. Preflight **FAIL-CLOSED**. **Step 4C not begun.**


---

## 13. M-1 remediation — D-2 closed at source (2026-08-10)

**Status: implemented, mutation-verified, full regression green. Uncommitted, awaiting authorization.**

### 13.1 The fix, and why it is at this layer

The defect was **not** in `evidenceExportPackage`. That function proposing `exportedAt:null` on every
attempt is *correct* and must stay — a browser download can never prove disk persistence (EXP-001).

The defect was that `evidenceUpdateExportState` **replaced the export block wholesale**, so a
proposal containing `null` erased a confirmation a verified re-import had already earned. Fixing only
the export path would have left the hazard open to every present and future caller. Fixing the store
layer eliminates the entire class.

**One new pure function, one changed line.** `evidenceMergeExportState(prev, next)` enforces:

- a previously earned `exportedAt` survives any proposal that does not carry one, along with
  `exportVerified` and `exportVerificationMethod`;
- `exportAttemptCount` never decreases;
- `exportAttemptedAt` still advances, so attempt history is recorded rather than suppressed;
- a verified re-import may still **set** `exportedAt` — advancing is always allowed.

Pure and synchronous, so the rule is executable offline without IndexedDB, matching the established
pattern of `evidenceEvaluateExportReimport`.

**Confirmation advances; it never silently retreats.** Revoking one would require its own explicit
audited operation. None exists, and an export attempt is emphatically not one.

### 13.2 Scope

| File | Change |
|---|---|
| `index.html` | +36 / −1 — one new pure function, one call site |
| `tests/v128_evidence_platform_tests.js` | +11 fixtures (M1–M11); D2 assertion re-expressed |
| `tests/run_v128_evidence_platform_tests.js` | +1 line exporting the pure function |

`evidenceExportPackage` untouched. Schema untouched. Canonicalization untouched. No migration: the
merge reads whatever shape a stored package already has and tolerates absent or malformed prior
state without throwing or fabricating.

### 13.3 One pre-existing test had to change, and it was strengthened

Fixture **D2** asserted the literal `existing.export=exportState` — pinning the wholesale assignment
that *was* the defect. Its own comment states the intent: *"The only write-back permitted on an
existing package is recording an export outcome."*

That intent is now asserted **directly and independently of how the value is computed**: the fixture
extracts every `existing.<field> =` assignment and requires the set to be exactly `{export}`. This is
strictly stronger than the string it replaced — it would catch a write to any other field, which the
literal never could.

**E-5 was not needed.** Fixture X4 pins `exportedAt:null` inside `evidenceExportPackage`, and that
function is unchanged, so X4 passes untouched.

### 13.4 Mutation verification — including a lesson the first pass taught

Reverting the call site to the original defect left **M1–M8 and M11 all green** and only M9 red.
Those fixtures exercise the merge contract directly, so they pass even when the store stops *calling*
the merge — the same trap Step 3's M14 exposed: *a test that passes because a different guard fired
is not evidence of the guard it names.*

M9 was therefore rewritten to pin the wiring itself — the assigned value must **be** the merge, with
prior state first. Three mutations, all **DETECTED**:

| Mutation | Result |
|---|---|
| A — `existing.export=exportState` (the original defect) | **DETECTED** |
| B — `Object.assign({},exportState)` (a copy that still discards prior state) | **DETECTED** |
| C — `evidenceMergeExportState(exportState,existing.export)` (arguments reversed, proposal wins) | **DETECTED** |

`index.html` restored byte-identical after every mutation
(`71a8a45547bb5a2dcf75a923448fd1a3c8716de63d7c601c303045c525f38b99`).

**Disclosed limitation:** M9 asserts from source text because the offline harness provides no
IndexedDB. This is the same offline/live split the suite already documents for its async layer, and
it is the reason the behavioural fixtures alone are not sufficient.

### 13.5 Validation

| Gate | Result |
|---|---|
| `tests/run_v128_evidence_platform_tests.js` | **238/238** (227 → 238) |
| **Canonical gate `tests/run_all.sh`** | **18 suites · 1031 fixtures · 1031 passed · 0 failed** (1020 → 1031) |
| Protected-function drift | **63 functions · 4 constants · 0 drift** |
| Campaign C1 | **33/33** · 42 files byte-identical |
| Mutation protocol | **3 applied · 3 detected · 0 survivors** |

### 13.6 What was not touched

The 222-package corpus was not exported, imported, confirmed, deleted, cleared or mutated. No browser
storage was touched. The preservation checkpoint is unchanged. ALEX forward paper trading remains
**OFF**, the preflight remains **FAIL-CLOSED**, and Step 4C has not begun.

**This fix changes no stored data.** It changes only what a *future* write is permitted to do.
