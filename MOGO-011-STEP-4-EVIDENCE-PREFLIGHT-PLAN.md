# MOGO-011 STEP 4 — EVIDENCE EXPORT & VERIFICATION PREFLIGHT

**Status:** **INVESTIGATION AND DESIGN ONLY — NOTHING IMPLEMENTED, NOTHING STAGED, NOTHING PUSHED**
**Date:** 2026-08-09
**Baseline:** `origin/mogo-main` = `HEAD` = `c7527a4b8c6dced08b6753667d8c76042fbfddac`
**Engine under investigation:** MOGO v12.19.0 (`index.html`), evidence layer MOGO-003 Phase 1 (v12.8.0)

> Every finding below was derived by reading the shipped source and by **read-only** analysis of the
> real exported files on this machine. No evidence was written, moved, renamed or deleted. No browser
> storage was touched. ALEX forward paper trading remains OFF.

---

## 0. Executive summary

The reported symptom — *"MOGO tells me to use Import package…, and there is no Import package
control"* — is **a real, precisely-located UI defect**, not a misreading of the UI. The control
exists in the shipped source at `index.html:14248` but is rendered only in Developer Mode, while the
banner that instructs the operator to use it is rendered unconditionally.

The investigation found **six further issues**, two of which are more serious than the reported one:

| | Finding | Severity |
|---|---|---|
| **D-1** | The **Import package… control is Developer-Mode-only**; the banner telling you to use it is not. Two independent gates hide it. | **High** — reported symptom |
| **D-2** | **A re-export silently demotes an already-confirmed package back to unconfirmed.** `Export all` wipes `exportedAt` on every package it touches. | **High** — destroys confirmation state |
| **D-3** | **No batch import exists.** The file input is single-file. Confirming 222 packages requires 222 manual file-picker interactions. | **High** — makes the gate impractical |
| **D-4** | **`packageId` is profile-local and collides across runs.** 12 real collisions observed on disk. `sourceTradeId` is the only collision-free identity. | **High** — identity integrity |
| **D-5** | The live-trading evidence gate is a **dismissible `confirm()` that deliberately fails open**. It cannot be a *required* preflight gate without a governance decision. | **Medium** — governance |
| **D-6** | The receiver's default output directory is `evidence/`, **the same directory holding the frozen Campaign C1 artifacts.** | **Medium** — contamination risk |
| **D-7** | **Only 65 distinct packages exist on disk against 222 stored.** The disk set is materially incomplete. | **High** — factual finding |

**Two reassurances, both verified in code rather than assumed:**

1. **Confirmation never deletes evidence.** There is no `.delete()` and no `.clear()` anywhere in the
   evidence layer. `evidenceUpdateExportState()` is the only write-back to a stored package and it
   writes only the `export` block.
2. **The verification logic itself is correct and well-tested.** `evidenceEvaluateExportReimport()`
   is pure, requires identity + SHA-256 + byte-exact canonical equality, has no operator override,
   and is covered by fixtures E1–E12. **It should not be changed.** Everything proposed below reuses
   it unmodified.

**The decisive feasibility result:** `mogo.evidence-canon.v1` was reimplemented outside the browser
and run against all 122 real exported files on this machine — **121 VERIFIED, 0 MISMATCH**, the
122nd having no hash by design. Batch verification without a browser is not a hope; it is
demonstrated.

---

## 1. Root cause of the reported symptom

### 1.1 The control exists

`index.html:14247-14248`, inside `renderEvidencePlatformDiagnostics()`:

```js
'<input type="file" id="evidenceImportInput" accept="application/json" style="display:none" onchange="evidenceHandleImportInput(this)">'+
'<button class="secondary" onclick="document.getElementById(\'evidenceImportInput\').click()">Import package…</button>'
```

### 1.2 Two independent gates hide it

**Gate 1 — the card blanks itself.** `index.html:14209`, the third line of the render function:

```js
if(typeof developerModeEnabled!=='undefined'&&!developerModeEnabled){ el.innerHTML=''; return; }
```

**Gate 2 — the wrapper is display:none.** `index.html:1354` ships with the style inline, and
`index.html:15578` only ever turns it on for Developer Mode:

```html
<div class="card" id="evidencePlatformDiagnosticsCardWrap" style="display:none">
```
```js
if(evidencePlatformWrap) evidencePlatformWrap.style.display=developerModeEnabled?'block':'none';
```

`developerModeEnabled` is `false` at `index.html:2205` and is only flipped by the Developer Mode
toggle at `index.html:15545`.

### 1.3 The instruction has no such gate

`evidenceBannerHtml()` (`index.html:14164-14186`) is rendered by `renderEvidenceExportBanner()`,
which has **no developer-mode check at all**. Its text at `index.html:14175`:

> `'To confirm: use <em>Import package…</em> in Diagnostics to re-import the downloaded file — MOGO verifies its hash '`

**Root cause, stated exactly:** the banner and the control it names are rendered by two different
functions with two different visibility policies. The banner is unconditional; the control is
Developer-Mode-only. An operator not in Developer Mode is instructed to use a control that is not
in the DOM.

### 1.4 Why browser Find returned 0/0

Gate 1 sets `el.innerHTML=''`. The string "Import package" is therefore **not present in the DOM at
all** — not merely hidden by CSS. `Ctrl-F` cannot find text that was never inserted. The operator's
`0/0` result is the correct and expected observation, and it independently corroborates Gate 1
rather than Gate 2 being the operative one.

### 1.5 One correction to the reported wording

The report quotes the UI as saying MOGO *"only then clears the stored package."* The shipped string
(`index.html:14176`) is:

> `'and content against the stored package, and only then clears this warning.'`

It clears **the warning**, not the package. This matters: the code never deletes evidence, and the
UI never claims to. Worth stating plainly because the paraphrase describes a destructive behaviour
that does not exist.

---

## 2. Current evidence lifecycle

### 2.1 Storage

| Tier | Mechanism | Durability |
|---|---|---|
| (a) | `localStorage` | working buffer only |
| (b) | **IndexedDB** `mogo_evidence` v1, store `packages`, keyPath `packageId`, unique index `bySourceTradeId` | automatic; **does not survive clearing site data, device loss or disk loss** |
| (c) | File on disk | the only tier that survives a profile clear |

Tier (b) is the authoritative store. `evidencePutPackage()` uses `add()` — never `put()` — so a
duplicate `packageId` or `sourceTradeId` is **rejected rather than silently overwriting**
(`index.html:12382-12390`).

### 2.2 The four state words, defined by code

| Word | Persisted as | Set by | Meaning |
|---|---|---|---|
| **exported** | `export.exportedAt` (ISO string) | `evidenceBuildVerifiedExportState()` **only** (`index.html:14012`) | A durable disk artifact has been **read back and proven**. |
| **download attempted** | `export.exportAttemptedAt` + `exportAttemptCount` | `evidenceExportPackage()` (`index.html:13971-13979`) | An anchor-click was issued. Proves **nothing** about the disk. |
| **confirmed** | `export.exportVerified:true` + `exportVerificationMethod:'REIMPORT_VERIFIED'` | `evidenceImportPackageObject()` on the verified branch (`index.html:14076-14084`) | Identity, SHA-256 and canonical content all matched. |
| **cleared** | — | **nothing** | Only the *warning* clears. **No package is ever deleted.** |

### 2.3 The counting rule

`evidenceSummarizePackages()` (`index.html:12426-12436`) is pure and synchronous:

```js
if(!ex.exportedAt) unexported++;
if(!ex.exportedAt&&ex.exportAttemptedAt) attempted++;
```

So `unexported` keys **solely** on `exportedAt`, which only a verified re-import can set. The
operator's two numbers are consistent and honest: 222 unexported, and all 222 of those also
attempted.

### 2.4 The lifecycle as it exists today

```
captured → evidenceFinalizePackage (SHA-256 over canonical form) → IndexedDB add()
   └─ export.exportedAt = absent
        │
        ├─ evidenceExportPackage()  ── anchor-click download ──► export.exportAttemptedAt set
        │                                                        exportedAt STAYS null
        │                                                        exportAttemptCount++
        │
        └─ evidenceImportPackageObject(file)  ── all checks pass ──► exportedAt set
                                                                     exportVerified = true
                                                     (the stored package is NEVER deleted)
```

**The design is right.** EXP-001 already corrected the dangerous version of this, and the correction
holds. The gap is reachability and scale, not semantics.

---

## 3. Relevant files and functions

### 3.1 `index.html` — evidence layer

| Lines | Symbol | Role |
|---|---|---|
| 12120-12141 | `EVIDENCE_*` constants | Schema `mogo.evidence-package.v1`, canon `mogo.evidence-canon.v1`, `EVIDENCE_HASH_EXCLUDED_FIELDS`, `EVIDENCE_UNEXPORTED_BLOCKING_THRESHOLD=50` |
| 12165-12196 | `evidenceCanonValue` / `evidenceCanonicalize` | Deterministic canonical form. Excludes the 5 integrity fields **and the whole `export` block** |
| 12213-12249 | `evidenceContentHash` / `evidenceFinalizePackage` / `evidenceVerifyPackageHash` | SHA-256 over the canonical UTF-8 bytes. Never repairs a mismatch |
| 12262-12266 | `evidenceExportFilename` | `mogo-evidence-<strategy>-<packageId>-<hash12>.json` |
| 12317-12422 | IndexedDB layer | `add()`-only writes; unique `bySourceTradeId` |
| **12393-12403** | **`evidenceUpdateExportState`** | **The only write-back to a stored package.** Replaces `existing.export` wholesale |
| 12426-12445 | `evidenceSummarizePackages` / `evidenceCountUnexported` | The counting rule |
| **13941-13987** | **`evidenceExportPackage`** | Download + attempt marking. **Site of D-2** |
| **13992-14008** | **`evidenceEvaluateExportReimport`** | **Pure verification decision. Correct — do not change** |
| 14009-14020 | `evidenceBuildVerifiedExportState` | The only place `exportedAt` is stamped |
| 14021-14043 | `evidenceExportPending` / `evidenceExportAll` | Bulk export loops |
| 14050-14116 | `evidenceImportPackageObject` / `evidenceImportFile` | Import + the confirmation branch |
| 14153-14194 | `evidenceBannerHtml` / `renderEvidenceExportBanner` | **Ungated** banner |
| **14205-14251** | **`renderEvidencePlatformDiagnostics`** | **Dev-mode gated card. Site of D-1** |
| 14264-14272 | `evidenceHandleImportInput` | `input.files[0]` — **single file. Site of D-3** |
| 4948-4960 | `toggleAlexGLiveTrading` | The live-trading gate. **Site of D-5** |
| 8201-8207 | `downloadTextFile` | Anchor-click; returns nothing, reports nothing |
| 1354-1355, 15577-15578 | `evidencePlatformDiagnosticsCardWrap` | The second gate |

### 3.2 Supporting

- `scripts/mogo_evidence_receiver.js` — write-only byte-verbatim HTTP receiver, port 8752, default
  out `<repo>/evidence/`. **`--selftest` re-run during this investigation: 9/9 PASS.**
- `tests/v128_evidence_platform_tests.js` — 2,767 lines. EXP-001 covered by X4, X5, X6, E1–E12.
- `docs/KNOWN_ISSUES.md:139` — **EXP-001, open defect**: a real export produced no file and no
  error; Chrome's `downloads` table held zero rows.
- `evidence/.gitignore` — `*` plus `!.gitignore`. **All evidence is git-ignored and local-only.**

---

## 4. The other findings, in detail

### 4.1 D-2 — a re-export silently demotes a confirmed package

`evidenceExportPackage()` builds a **fresh** export block on every call
(`index.html:13970-13979`):

```js
const prev=pkg.export||{};
const attemptState={
  exportedAt:null,                       // ← unconditional
  exportAttemptedAt:new Date().toISOString(),
  ...
  exportAttemptCount:(typeof prev.exportAttemptCount==='number'?prev.exportAttemptCount:0)+1
};
await evidenceUpdateExportState(pkg.packageId,attemptState);
```

`evidenceUpdateExportState()` then does `existing.export=exportState` — a **wholesale replacement**.

`prev` is read, but only `exportAttemptCount` is carried forward. A package that had been properly
confirmed (`exportedAt` set, `exportVerified:true`) is therefore **reset to unconfirmed** the moment
it is exported again.

**Reachability:** `evidenceExportPending()` filters on `!p.export||!p.export.exportedAt` and so skips
confirmed packages. **`evidenceExportAll()` does not** — it iterates every package
(`index.html:14036`). `Export all` is wired to a live button at `index.html:14245`, and the
storage-failure banner's `Export now` also calls `evidenceExportAll` (`index.html:14161`).

**Consequence:** confirmation work can be destroyed by a single later click. In a 222-package
backlog confirmed incrementally, this is the difference between finishing and never finishing.

**This is the reason the operator must not be told to "just press Export again."**

### 4.2 D-3 — no batch import

```js
'<input type="file" id="evidenceImportInput" accept="application/json" style="display:none" ...>'
```

No `multiple`. No `webkitdirectory`. `evidenceHandleImportInput()` reads `input.files[0]` and
discards the rest. Confirming 222 packages = **222 separate file-picker round trips**. This alone
makes the preflight gate impractical, independently of D-1.

### 4.3 D-4 — `packageId` collides; `sourceTradeId` does not

`evidenceAllocateSequence(strategyId, yyyymmdd)` (`index.html:12371-12381`) mints
`PKG|<strategy>|<yyyymmdd>|<n>` from a **per-profile IndexedDB counter**. A fresh or disposable
profile restarts at 1, so the same `packageId` is minted for a completely different trade.

**Measured on the real files, read-only:**

```
distinct packageIds with conflicting contentHash : 12
  of those, IDENTITY COLLISION (different trades) : 12
  of those, CONTENT DRIFT (same trade changed)    :  0
sourceTradeIds mapping to more than one packageId :  0
```

Example — `PKG|alex_g_sr_v1|20260406|1` exists on disk three times, as **EUR_USD from run
`3d7c3dc1af7f`** and as **AUD_USD from run `88d924c0be04`**.

**Two conclusions:**

1. **`sourceTradeId` is the stable, collision-free identity. `packageId` is not.** Any manifest,
   dedup key or reconciliation must key on `sourceTradeId` (with `identity.runId` as a
   disambiguator), never on `packageId` alone.
2. **The existing guard already holds.** `evidenceEvaluateExportReimport()` compares `sourceTradeId`
   as well as `packageId` (`index.html:13996-13997`) and returns `IDENTITY_MISMATCH`, which routes
   to `DUPLICATE_CONFLICTING_HASH` and refuses. **A colliding foreign package cannot falsely confirm
   a stored one.** This was verified by reading the decision ladder, not assumed.

   The cost is that genuine cross-profile *recovery* import is also blocked. That is the correct
   trade today and should be recorded rather than "fixed" in this step.

### 4.4 D-5 — the live-trading gate fails open by design

`index.html:4951-4959`:

```js
// Fails open -- an evidence surface must never be able to stop trading on its own.
const w=evidenceUnexportedBlockingWarning();
if(w&&!confirm('⚠ '+w+'\n\nTurn ON Live Alex Paper Trading anyway?')) return;
```

A dismissible confirm, wrapped in `try{}catch(e){}`. The mission requires a **required** preflight
gate. Converting fail-open to fail-closed **contradicts an explicit, documented design decision**
and is therefore a governance question (**Decision E-4**), not an implementation detail.

### 4.5 D-6 — receiver output collides with frozen Campaign C1 evidence

`scripts/mogo_evidence_receiver.js:65` defaults `--out` to `<repo>/evidence/` — which currently
holds the **33 frozen Campaign C1 artifacts**. Filenames do not collide (`C1-*` vs
`mogo-evidence-*`), so no overwrite would occur, but mixing a live export dump into a frozen
scientific artifact directory is exactly the kind of contamination the C1 manifest exists to detect.

**Any batch egress must write to a dedicated, empty directory chosen explicitly via `--out`.**

### 4.6 D-7 — the disk set is materially incomplete

Read-only census of every `mogo-evidence-*.json` under `~/Desktop` and `~/Downloads`:

| | |
|---|---|
| Files found | **122** |
| Distinct `packageId` | **65** |
| Distinct `sourceTradeId` | **65** |
| `captureBasis` | `REPLAY_RUN` 118 · `LIVE_CLOSE` 4 |
| `contentHashProvenance` | `OBSERVED` 121 · `UNAVAILABLE` 1 |
| Files in `MOGO-Evidence-Live-Paper-Prelaunch-2026-08-08` | **43** |
| Files with a browser `" (n)"` duplicate suffix | **0** |

**65 distinct packages on disk against 222 stored.** Even taking every file in every folder, the
disk set covers at most ~29% of the backlog. The prelaunch folder alone holds 43.

This is consistent with **EXP-001**: the download path silently drops writes. It is **not** safe to
treat the prelaunch folder as a complete evidence set — as the task statement already anticipated.

The 122 files span **13 distinct replay runs**, several of which are Campaign C1 run IDs
(`f230a04976d4` = C1-01 GBP_USD, `88d924c0be04` = C1-03 AUD_USD, `4689c3d17f80` = C1-04 USD_JPY,
`ff5dd403ea8d` = C1-05, `ca6c0038a27b` = C1-06, `80a17b22e3f8` = C1-07, `3b36727d5694` = C1-08).
**The browser profile therefore holds evidence derived from frozen C1 runs.** Read-only export and
verification of those packages is safe; nothing in this plan mutates them.

---

## 5. Answers to the eight investigation objectives

| # | Objective | Answer |
|---|---|---|
| 1 | Where stored, lifecycle | IndexedDB `mogo_evidence` v1, store `packages`. §2 |
| 2 | Meaning of the four words | §2.2 — `exported` requires a verified read-back; `attempted` proves nothing; `cleared` refers to the warning, and **no package is ever deleted** |
| 3 | Does Import exist? | **Yes — implemented, complete, correct, and UNREACHABLE outside Developer Mode.** Not removed, not partial, not mislabeled. §1 |
| 4 | How hashes/contents are verified | SHA-256 over `mogo.evidence-canon.v1`, excluding the 5 integrity fields and the `export` block; re-import additionally requires byte-exact canonical equality and identity match. §2, §3 |
| 5 | Can confirmation occur without destroying the record? | **Yes — it already does.** No delete path exists; only the `export` block is rewritten, and it is excluded from the hash so integrity is never invalidated |
| 6 | Effect of repeated Export Now | Does **not** create new identities (`packageId` stable, `add()`-only, unique `sourceTradeId`). It **does** increment `exportAttemptCount` and — **defect D-2** — wipe `exportedAt` on already-confirmed packages. On disk: 0 browser `" (n)"` duplicates; 41 packageIds have multiple files, 29 agreeing on `contentHash` (benign, export block differs only) and 12 conflicting (**cross-run identity collisions, D-4**) |
| 7 | Can the 222 be enumerated/fingerprinted without mutation? | **Yes, three ways, all read-only.** (a) `evidenceListPackages()` in the console — available today, zero code change; (b) a proposed read-only manifest export — one file, one action; (c) the offline canonical verifier — **already prototyped and proven, 121/121** |
| 8 | Safest batch workflow | §6 |

---

## 6. Proposed architecture

### 6.1 Principle

**Do not invent a new trust path.** The existing verification decision is correct, pure and
well-tested. The fix is to let it run **once per package over a whole folder** instead of once per
manual file pick, and to add an **independent second opinion** outside the browser.

Every design below preserves: a download alone is never verification; confirmation is cryptographic;
the authoritative package is never destroyed.

### 6.2 The target lifecycle

```
stored
  → export_initiated        (operator action recorded)
  → bytes_written           (attempt only — never confirmation)
  → independently_verified  (SHA-256 + byte-exact canonical equality, against the STORED package)
  → export_confirmed        (exportedAt stamped; monotonic — never silently revoked)
  → archived                (durable, governed, RETENTION-PRESERVING label — never a delete)
```

### 6.3 Layer 1 — make the existing control reachable (fixes D-1)

Move the **Import package…** control and the unexported/attempted counters out of the Developer-Mode
card into an **operator-visible evidence panel**, rendered by the same ungated function that already
renders the banner. Developer Mode keeps the deep diagnostics; the operator gets the control the
banner names.

**Rule to encode as a test:** *no banner may name a control that its own visibility policy hides.*
A fixture should assert that every control named in `evidenceBannerHtml()` is rendered by a function
with no stricter visibility gate than the banner's.

### 6.4 Layer 2 — batch re-import (fixes D-3)

Add `multiple` and `webkitdirectory` to `#evidenceImportInput`, and iterate `input.files` in
`evidenceHandleImportInput()`.

**This is deliberately the least clever option available, and that is why it is the right one:**

- The app **genuinely reads the bytes back from disk** — the property EXP-001 exists to protect.
- `evidenceEvaluateExportReimport()` is called **unchanged**, once per file.
- **No new trust surface, no new protocol, no new crypto, no receipt to forge.**
- The operator performs **one** folder selection instead of 222 file picks.

Output: a per-run reconciliation summary — verified / already-verified / identity-mismatch /
hash-mismatch / not-in-store / malformed — with counts and a downloadable report.

### 6.5 Layer 3 — reliable egress (mitigates EXP-001, fixes D-6)

Add an operator-selectable egress mechanism alongside the anchor-click download: **POST each package
to `http://127.0.0.1:<port>`**, the existing proven receiver. Unlike the download path it returns an
acknowledgement with a byte count, so a failure is **observable**.

- Mechanism recorded as a new `exportMechanism` value (governance decision **E-2** — Catalog §C
  currently permits only `MANUAL` and `AUTO_DOWNLOAD`, and fixture X6 asserts exactly that).
- **A receiver acknowledgement is still only an ATTEMPT.** Confirmation remains the Layer-2/4
  read-back. This must be stated in code comments and asserted by a fixture, or the receiver becomes
  exactly the false-confidence path EXP-001 was raised against.
- The receiver must be run with an explicit `--out` to a dedicated empty directory. **Never the
  default `evidence/`.**

### 6.6 Layer 4 — independent offline verification (the second opinion)

A repository-side verifier, `scripts/mogo_evidence_verify.js`, that:

1. reads a directory of exported packages;
2. reimplements `mogo.evidence-canon.v1` and recomputes SHA-256 per package;
3. compares against each package's own `contentHash`;
4. cross-checks against a manifest exported read-only from the browser;
5. reports `VERIFIED / MISMATCH / NO_HASH / MISSING / UNLISTED / COLLIDING_PACKAGE_ID`, keyed on
   **`sourceTradeId`**, never on `packageId` alone;
6. **writes nothing and exits non-zero on any failure.**

**This is already proven.** The prototype run during this investigation reproduced the browser's
hashes exactly:

```
files examined: 122
  VERIFIED                          121
  NO_HASH (unverifiable by design)    1
  MISMATCH                            0
```

A `--selftest` mode must ship with it, matching the receiver's precedent, and must include a
**negative control**: a deliberately mutated byte must produce `MISMATCH`. A verifier that has never
been shown to fail is not evidence that anything passed.

### 6.7 Layer 5 — read-only enumeration (objective 7)

An **Export manifest (read-only)** action producing one JSON file listing, per package:
`sourceTradeId`, `packageId`, `identity.runId`, `contentHash`, `contentHashProvenance`,
`captureBasis`, and the full `export` block. It **must not** write to IndexedDB — not even an
attempt marker. It is the input to Layer 4 and the only way to know what the 222 actually are.

**Available today with no code change**, and this should be the operator's *first* action:
`evidenceListPackages()` in the console is already read-only.

---

## 7. Treatment of the existing 222 packages

**Nothing about the 222 may be assumed. They must be enumerated before they are acted on.**

| Phase | Action | Mutates? |
|---|---|---|
| **P0** | Do not press Export again. Under **D-2**, `Export all` would wipe any confirmation already achieved | — |
| **P1** | Export a read-only manifest (§6.7) and record `total`, `unexported`, `attempted`, `unverifiable` | **No** |
| **P2** | Fingerprint the 122 files already on disk with the Layer-4 verifier | **No** |
| **P3** | Reconcile manifest against disk. Expect ~65 of 222 present. Produce the exact missing list, keyed on `sourceTradeId` | **No** |
| **P4** | Re-export **only the missing** via the receiver (Layer 3) into a dedicated empty directory | Writes `exportAttemptedAt` only |
| **P5** | Batch re-import the whole directory (Layer 2). Only packages that pass every check are confirmed | Writes `export` block only |
| **P6** | Re-run P1 + P2. The preflight passes only when confirmed == total and the verifier is clean | **No** |

**Explicitly forbidden:** marking any package verified because a file with a matching name exists;
because a download was attempted; because the count "looks right"; or by any operator override.
There is no override in the code today and none may be added.

**The 1 package with `contentHashProvenance: UNAVAILABLE`** can never be cryptographically confirmed
— it was captured without Web Crypto. It must be reported as a **permanent, named exception**, not
counted as passing and not silently dropped. This needs governance decision **E-3**.

---

## 8. Duplicate-download handling

**Established by measurement, not assumption:**

- Repeated export **cannot** create a new evidence identity: `packageId` is stable per package,
  `evidencePutPackage()` uses `add()`, and `bySourceTradeId` is a unique index.
- 41 packageIds have more than one file on disk. **29 agree on `contentHash`** — the files differ
  only in their `export` block, which is excluded from canonicalization, so **any one of them
  verifies correctly**. This is benign and needs no handling beyond de-duplication for reporting.
- **12 conflict** — all 12 are cross-run identity collisions (**D-4**), not content drift. They must
  be refused, and today they are.
- **0 files carry a browser `" (n)"` duplicate suffix**, so Chrome did not in fact write repeat
  downloads on this machine.

**Rules to encode:**

1. De-duplicate by `(sourceTradeId, contentHash)`, never by filename and never by `packageId` alone.
2. A duplicate that agrees on `contentHash` is **one** package — it must not increment any confirmed
   count twice. **A fixture must assert that importing the same package twice leaves the confirmed
   count unchanged.**
3. A duplicate that disagrees is a **collision or a corruption** and must be reported by name and
   refused, never resolved by picking one.

---

## 9. Retention semantics

**Current behaviour is already correct and must be preserved.** Ruling C4 — packages in tier (b) are
**never** automatically deleted. There is no delete path in the evidence layer.

Proposed, to be ratified as decision **E-1**:

| State | Meaning | Deletes anything? |
|---|---|---|
| `stored` | in IndexedDB | no |
| `export_attempted` | bytes issued | no |
| `export_confirmed` | read back and cryptographically verified | no |
| `archived` | confirmed **and** the operator has recorded a durable off-device copy | **no — a label only** |

**Deletion remains out of scope for Step 4 and is not designed here.** If a retention policy is ever
wanted it must be a separate, explicitly governed decision with its own preconditions — at minimum:
two independent verified copies, a recorded archival location, and an audited operator authorization
per package. **Confirmation must never become a trigger for deletion.**

**`exportedAt` must become monotonic** (fixes D-2): once set, a subsequent export attempt may
increment `exportAttemptCount` and update `exportAttemptedAt`, but **must not clear `exportedAt` or
`exportVerified`.** Revocation, if ever needed, must be its own explicit, audited operation.

---

## 10. Required tests

All new fixtures go in a **new** suite, `tests/run_v131_evidence_export_preflight_tests.js`. Note
that `tests/run_all.sh` discovers suites by the glob `tests/run_*_tests.js`
(`tests/run_all.sh:44-45`), so **a new suite is picked up without modifying `run_all.sh`** — ADR-012
D-12 is not touched.

**Existing fixtures are not to be weakened.** One assertion needs re-expression, discussed in §12.

| Group | Fixture | Asserts |
|---|---|---|
| **UI reachability (D-1)** | every control named in `evidenceBannerHtml()` is rendered by a function with no stricter visibility gate than the banner's | the reported defect cannot recur |
| | the Import control is reachable with `developerModeEnabled === false` | |
| **Monotonic confirmation (D-2)** | re-exporting a confirmed package preserves `exportedAt` and `exportVerified` | confirmation is never silently revoked |
| | `evidenceExportAll` over a confirmed package does not reduce the confirmed count | |
| | `exportAttemptCount` still increments | attempt history is not lost |
| **Batch import (D-3)** | N files produce N independent decisions | |
| | one malformed file does not abort the batch | |
| | the batch summary counts each `(sourceTradeId, contentHash)` exactly once | |
| | importing the same package twice leaves the confirmed count unchanged | idempotence |
| **Identity (D-4)** | a colliding `packageId` with a different `sourceTradeId` is **refused** | uses the real decision function |
| | dedup keys on `sourceTradeId`, never `packageId` | |
| **Verifier (Layer 4)** | recomputed hash matches a real fixture package | |
| | **negative control:** one mutated byte ⇒ `MISMATCH` | the verifier can actually fail |
| | a `NO_HASH` package is reported as an exception, never as passing | |
| | the verifier writes nothing | read-only |
| **Egress honesty** | a receiver acknowledgement never sets `exportedAt` | EXP-001 cannot regress |
| **Preflight gate** | the PASS criteria of §14 evaluate false when any one is unmet | |

**Mutation protocol.** Following Steps 1–3, every new guard must be mutation-tested: at minimum
*"let a download confirm an export"*, *"let a re-export clear `exportedAt`"*, *"accept a colliding
packageId"*, *"count a duplicate twice"*, and *"let the verifier pass a mutated byte."* Each must be
**detected**.

---

## 11. Migration and backward compatibility

| Concern | Assessment |
|---|---|
| **Package schema** | **Unchanged.** `mogo.evidence-package.v1` stays. No re-hash, no re-canonicalization, no field added to the hashed surface |
| **Canonicalization** | **Unchanged.** `mogo.evidence-canon.v1` is frozen. Changing it would invalidate every hash ever produced |
| **`export` block** | Additive only, and excluded from the hash — existing packages stay valid with no migration |
| **Already-confirmed packages** | Preserved by the monotonic rule. **No back-fill and no re-verification is required** |
| **IndexedDB version** | **No bump needed** — no new store, no new index. If one is later required it must migrate on open, following the platform's v1→v2→v3 precedent |
| **Existing files on disk** | All 122 remain verifiable — proven, 121/121 with hashes |
| **Protected-function drift** | **Zero.** No `evidence*` function is in `regression-baseline.json`'s 63 protected functions — checked directly |
| **`knownGoodHtmlSha1`** | Hashes `index-v2.9-KNOWN-GOOD.html`, **not** the live `index.html` — editing `index.html` cannot break it |
| **Canonical gate count** | 947 will rise by the new fixture count. Expected and governed |
| **`tests/run_all.sh`** | **Not modified.** ADR-012 D-12 intact |
| **Older engines** | An older MOGO reading a package with a richer `export` block ignores unknown keys; the import path already preserves unknown fields verbatim (`index.html:14096`) |

---

## 12. Governance decisions required before implementation

| | Decision | Why it cannot be made unilaterally |
|---|---|---|
| **E-1** | Adopt the six-state lifecycle with `archived` as a **non-deleting label**, and make `exportedAt` **monotonic** | Changes the meaning of a persisted governance field |
| **E-2** | Permit a third `exportMechanism` (`RECEIVER_POST`) | Catalog §C currently permits exactly two, and fixture X6 asserts it. Adding one is a vocabulary extension |
| **E-3** | How to treat the package with no `contentHash` | It can never be cryptographically confirmed. Either the preflight tolerates a **named permanent exception**, or it can never pass |
| **E-4** | Whether the live-trading preflight becomes **fail-closed** | Directly contradicts the documented *"an evidence surface must never be able to stop trading on its own"* at `index.html:4953` |
| **E-5** | Re-express fixture X4 | X4 asserts the literal string `exportedAt:null` appears in `evidenceExportPackage`. The D-2 fix requires preserving a prior verified stamp, which changes that literal. **X4's stated intent — "a download never *stamps* exportedAt" — is preserved; only its textual form changes.** This must be ratified explicitly so it is never mistaken for weakening a test |

**E-4 and E-5 are the two that matter.** E-5 in particular must be approved in the open: a
source-text assertion being rewritten as part of fixing the behaviour it guards is exactly the
pattern that should attract scrutiny.

---

## 13. Risk analysis

| | Risk | Severity | Mitigation |
|---|---|---|---|
| **R-1** | A batch path marks packages confirmed **without** genuinely reading bytes back | **Critical** | Layer 2 reuses `evidenceEvaluateExportReimport()` unchanged; no override exists or may be added; mutation-tested |
| **R-2** | The D-2 fix is mis-implemented and lets a download stamp `exportedAt` | **Critical** | Only `evidenceBuildVerifiedExportState()` may stamp it — already asserted by E3; extend to the re-export path |
| **R-3** | Batch egress writes into `evidence/` and contaminates frozen C1 | **High** | Mandatory explicit `--out`; C1 manifest re-verified before and after every phase |
| **R-4** | Cross-run `packageId` collision falsely confirms a package | **High** | Already refused via `sourceTradeId`; add explicit fixtures so it stays that way |
| **R-5** | The offline verifier has a canonicalization bug and passes bad data | **High** | Negative-control fixture; cross-checked against 121 real packages; browser remains the authority |
| **R-6** | The operator treats the 43-file prelaunch folder as complete | **High** | §4.6 quantifies the shortfall; P3 produces the explicit missing list |
| **R-7** | Fixing D-1 exposes evidence controls to an operator who then misuses them | Low | Controls are read-only or additive; no delete path exists |
| **R-8** | EXP-001 silently drops writes again during P4 | **High** | Receiver acknowledges per package with a byte count; P6 re-verifies independently |
| **R-9** | Making the gate fail-closed strands the operator with no way to trade | Medium | E-4; if approved, pair with a documented, audited override that is **recorded**, not silent |
| **R-10** | Scope creep into a deletion/retention feature | Medium | §9 puts deletion explicitly out of scope |

**Carried from MOGO-011:** risk **A-5** is untouched by this plan. Nothing here registers an
effectful capability on the automation platform. The receiver is operator-run tooling, not a
platform capability, and **no connector is created**.

---

## 14. Criteria to declare the evidence-export preflight PASS

All of the following must hold **simultaneously**, evidenced by artifacts, not by assertion:

1. **Enumeration** — a read-only manifest exists, and `total` equals the reported stored count.
2. **Coverage** — every package in the manifest has a corresponding file, reconciled by
   `sourceTradeId`. Zero missing.
3. **Independent verification** — the offline verifier reports `VERIFIED` for every package with a
   hash, `MISMATCH` = 0, `UNLISTED` = 0, `COLLIDING_PACKAGE_ID` = 0.
4. **In-app confirmation** — `evidenceUnexportedCount` = 0 and `evidenceAttemptedUnverifiedCount` = 0,
   every one reached through `REIMPORT_VERIFIED`.
5. **Named exceptions** — the `UNAVAILABLE`-hash package is listed by name with its governance
   disposition under E-3. **Zero unexplained exceptions.**
6. **Non-destruction** — stored package count before = after. No package deleted, no `contentHash`
   altered. Proven by manifest diff.
7. **Frozen evidence intact** — Campaign C1 re-verifies **33/33**, 0 mismatched, 0 unlisted.
8. **Regression clean** — platform 740/740 (or higher), canonical gate green, **protected-function
   drift 0**.
9. **Mutation protocol** — every new guard mutation-tested, 0 survivors.
10. **Verifier negative control** — a deliberately mutated byte produces `MISMATCH`, demonstrated in
    the run log.
11. **Reproducibility** — a second independent verifier run reproduces the first exactly.

**Only when 1–11 hold may the ALEX forward-paper-trading preflight be declared PASS** — and enabling
it still requires separate, explicit owner authorization.

---

## 15. Exact implementation boundary

**In scope (proposed, not yet authorized):**

| File | Change |
|---|---|
| `index.html` | Un-gate the import control (D-1); monotonic `exportedAt` (D-2); `multiple`+`webkitdirectory` batch import (D-3); read-only manifest export; optional receiver egress (**pending E-2**) |
| `tests/run_v131_evidence_export_preflight_tests.js` | **New** runner |
| `tests/v131_evidence_export_preflight_tests.js` | **New** fixtures |
| `tests/v128_evidence_platform_tests.js` | **X4 only**, re-expressed — **pending E-5** |
| `scripts/mogo_evidence_verify.js` | **New** offline verifier with `--selftest` |
| `docs/KNOWN_ISSUES.md` | Record D-1…D-7; update EXP-001 with the receiver mitigation |
| `docs/MOGO-003-PHASE-1-SPECIFICATION.md` | Amend the lifecycle section (**pending E-1**) |

**Explicitly out of scope:**

`tests/run_all.sh` (ADR-012 D-12) · `regression-baseline.json` · the 63 protected functions · the
canonicalization `mogo.evidence-canon.v1` · the package schema · `evidenceEvaluateExportReimport()`
· `scripts/mogo_evidence_receiver.js`'s write path · **any deletion or retention mechanism** ·
`evidence/**` · `docs/campaigns/**` · the MOGO-011 automation platform · **anything that enables
ALEX forward paper trading**.

**Proposed sequencing** — each with its own validation and approval gate:

| Step | Content | Rationale |
|---|---|---|
| **4a** | Offline verifier + fixtures | **Zero risk to the app.** Establishes ground truth before anything is changed |
| **4b** | Read-only manifest export + enumerate the 222 | Still non-mutating. Turns 222 from a number into a list |
| **4c** | D-1 and D-2 fixes + fixtures | The two defects that matter, smallest possible surface |
| **4d** | Batch re-import (D-3) | Only after 4c, so a batch cannot demote anything |
| **4e** | Receiver egress (**pending E-2**) | Only if P3 shows a material shortfall — which it does |
| **4f** | Preflight gate semantics (**pending E-4**) | Last, because it depends on everything above |

---

## 16. Rollback strategy

| Layer | Rollback |
|---|---|
| **Offline verifier / manifest** | Delete the script. **Nothing to undo — it never wrote anything** |
| **UI un-gating (D-1)** | Revert the commit. Purely presentational; no persisted state touched |
| **Monotonic `exportedAt` (D-2)** | Revert. **Strictly additive to durability** — it only *preserves* a stamp that would otherwise be cleared, so a rollback cannot resurrect a false confirmation. Any package confirmed under the new rule was confirmed by the unchanged decision function |
| **Batch import (D-3)** | Revert. Every confirmation it produced was produced by the same per-package decision as a manual import, so confirmations remain valid after rollback |
| **Receiver egress (E-2)** | Revert. Attempt markers remain, which is honest — an attempt did occur |
| **Preflight gate (E-4)** | Revert restores fail-open. Must be called out explicitly in the release notes: **a rollback re-opens the gate** |

**Git-level:** each sub-step is its own commit on `main`, parented on the previous, pushed
fast-forward to `origin/mogo-main`. Rollback is `git revert` — **never** a force push, never a
history rewrite, matching Steps 1–3.

**Evidence-level:** no step deletes or mutates a package, so **there is no evidence-level rollback to
perform.** This is a deliberate property of the design, not a convenience: the only persisted
mutation any step makes is to the `export` block, which is excluded from the content hash and
therefore cannot invalidate a package's integrity.

---

## 17. What was verified during this investigation

| | Method | Result |
|---|---|---|
| Import control exists but is dev-gated | Read `index.html:14205-14251`, `1354`, `15578`, `2205` | **Confirmed** |
| Ctrl-F 0/0 explained | `el.innerHTML=''` at `14209` removes the text from the DOM | **Confirmed** |
| No deletion path | Grepped every `EVIDENCE_STORE_PACKAGES` use; no `.delete(`/`.clear(` | **Confirmed** |
| Re-export demotes a confirmation | Read `13970-13980` + `12393-12403` | **Confirmed** |
| Single-file import only | Read `14247`, `14264-14266` | **Confirmed** |
| `packageId` collides, `sourceTradeId` does not | Read-only analysis of 122 real files | **12 collisions, 0 drift, 0 trade→multi-package** |
| Disk set incomplete | Read-only census, `~/Desktop` + `~/Downloads` | **65 distinct vs 222 stored** |
| Canonicalization is reimplementable offline | Python prototype vs recorded hashes | **121 VERIFIED / 0 MISMATCH / 1 no-hash** |
| Receiver preserves bytes | `node scripts/mogo_evidence_receiver.js --selftest` | **9/9 PASS** |
| No evidence function is protected | Parsed `regression-baseline.json` | **Confirmed — drift risk 0** |
| `knownGoodHtmlSha1` is not `index.html` | Read `regression-baseline-tools.py:32,196-204` | **Confirmed** |
| New suites need no `run_all.sh` change | Read `tests/run_all.sh:44-45` | **Confirmed — glob discovery** |
| Frozen C1 intact | 33/33 SHA-256 re-verified after all analysis | **Unchanged** |

**Nothing was written, moved, renamed or deleted. `git status` for tracked files is clean, `HEAD` is
unchanged at `c7527a4`, and Campaign C1 re-verifies 33/33.**

---

## 18. State and next action

`HEAD` = `origin/mogo-main` = `c7527a4b8c6dced08b6753667d8c76042fbfddac`, 0 ahead / 0 behind.
Nothing staged, nothing committed, nothing tagged, nothing pushed. ALEX forward paper trading **OFF**.

**Next action: owner review of this plan, and rulings on E-1 … E-5.**

The two worth deciding first, because everything else depends on them:

1. **E-4 — does the evidence gate become fail-closed?** The mission says the preflight is *required*;
   the code says an evidence surface must never stop trading. Both cannot stand.
2. **E-5 — may fixture X4 be re-expressed?** The D-2 fix cannot land while a fixture asserts the
   literal text that causes the defect. The fixture's *intent* is right and is preserved; its
   *wording* is what must change, and that should be approved rather than assumed.

**Recommended first implementation step regardless: 4a**, the offline verifier. It touches no
application code, writes nothing, and converts "222 packages, state unknown" into a verified,
enumerated list — which every later decision depends on.
