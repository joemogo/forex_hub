# MOGO-011 — STEP 4B COMMIT/PUSH AND MULTI-ORIGIN EVIDENCE RECONCILIATION

**Status:** **4A AND 4B COMMITTED AND PUSHED · MULTI-ORIGIN INVESTIGATION COMPLETE · STOPPED AT THE AUTHORIZATION GATE**
**Date:** 2026-08-09 · **Step 4C NOT authorized and NOT started** · **ALEX forward paper trading OFF**
**Preflight status: FAIL-CLOSED**

---

## 1. Step 4A commit

```
f139b8b90526388398ca12ce5489981bc42d3dc3
```
`MOGO-011 Step 4A: read-only offline evidence inventory and verifier` · parent `c7527a4…` · 3 files

## 2. Step 4B commit

```
ce94424bdb0f4fb6a7a10f45c1738623e25f06de
```
`MOGO-011 Step 4B: read-only browser evidence manifest and reconciliation` · parent `f139b8b…` · 3 files
(2 modified, 1 created — the already-validated boundary only)

## 3. Remote HEAD after push

```
ce94424bdb0f4fb6a7a10f45c1738623e25f06de   refs/heads/mogo-main
```

Read back from the server with `git ls-remote`, not from the local tracking ref. Push transcript
`c7527a4..ce94424` — the `..` form is a **fast-forward**; a forced update prints `+ … (forced update)`.
**Local HEAD = remote HEAD, 0 ahead / 0 behind.** Both commits confirmed present on `origin/mogo-main`.
**No tag was created** — the 26 tags on the remote are pre-existing and none points at either commit.

## 4. Integrity and regression results

| Gate | Pre-commit | Post-push |
|---|---|---|
| Canonical gate `tests/run_all.sh` | **18 suites · 1020 fixtures · 1020 passed · 0 failed** | **1020/1020** |
| Protected-function drift | **63 functions · 4 constants · 0 drift** | **0 drift** |
| `v131` verifier fixtures | **73/73** | — |
| `mogo_evidence_verify --selftest` | **43/43** | — |
| `mogo_evidence_store_scan --selftest` | **12/12** | — |
| Campaign C1 | **33/33 · 0 missing · 0 mismatched · 0 unlisted** | **33/33** |
| C1 + `docs/campaigns` (42 files) | byte-identical | **byte-identical** |
| `index.html` | **unmodified** | **unmodified** |

---

## 5. Browser profiles and origins discovered

### 5.1 Chrome profiles

| Profile directory | Display name | Account | Live? |
|---|---|---|---|
| `Default` | Person 1 | jvmbiz25@gmail.com | yes — **no MOGO store** |
| `Profile 1` | students.sheltonpublicschools.org | — | yes — **no MOGO store** |
| **`Profile 2`** | **Joe** | **joemogollon025@gmail.com** | **yes — holds BOTH MOGO origins** |
| `Profile 2 copy` | *(not registered in Local State)* | — | backup copy of Profile 2 |
| `Profile 2 Safety Copy 2026-07-31` | *(not registered)* | — | backup copy of Profile 2 |
| `Profile 2 Recovered Data 2026-07-31` | *(not registered)* | — | **no MOGO store** |

**Only one live profile carries MOGO evidence: `Profile 2` ("Joe").** Both origins live inside it.

### 5.2 Evidence stores, both origins

| Origin | Store path (within each profile) | Size | Last written |
|---|---|---:|---|
| `http://localhost:8744` | `IndexedDB/http_localhost_8744.indexeddb.leveldb` | 52 KB | **2026-07-31 10:48** |
| `http://10.143.1.187:8744` | `IndexedDB/http_10.143.1.187_8744.indexeddb.leveldb` | 24 KB | **2026-07-31 10:43** |

Both are present, identically, in `Profile 2` and in the two backup copies.

**Every MOGO store on this machine was last written 2026-07-31** — before the Campaign C1 runs
(2026-08-06) and before the export attempts (2026-08-09).

### 5.3 How they were read

**No live store was opened.** Each directory was **copied**, and only the copies were scanned.
`scripts/mogo_evidence_store_scan.js` **refuses by construction** to scan a path inside a live
browser profile, and never opens a LevelDB database at all — opening one would replay its log,
compact, and rewrite the very files under examination. It decodes V8 string tokens from the bytes,
which is why it can run safely while Chrome is open.

**Verification that nothing moved:** both live stores still carry their original mtimes
(`10:48` and `10:43` on 2026-07-31), unchanged before and after the investigation.

---

## 6. Evidence count per origin

Each manifest is produced **independently**, and **origin provenance is stamped on every row**.

### `http://localhost:8744`

| | |
|---|---|
| Distinct packages | **1** |
| `packageId` | `PKG\|alex_g_sr_v1\|20260731\|1` |
| `sourceTradeId` | `AGT\|REALEXPORT\|1` |
| `contentHash` | `66a2f44abffa4f20…` (present) |
| Stored LevelDB versions of that one record | **7** — successive rewrites, uncompacted |

### `http://10.143.1.187:8744`

| | |
|---|---|
| Distinct `sourceTradeId` | **1** — `AGT\|INSECURE\|1` |
| Distinct `packageId` observed | **4** — `…\|20260731\|1`, `\|12`, `\|18`, `\|19` |
| `contentHash` present | **0 — none at all** |
| `createdAt` | 2026-07-31T14:43:30.112Z · engine 12.8.0 |

**Two things follow from that store, and both matter.**

The **sequence counter reached at least 19** on 2026-07-31, so **at least 19 packages were minted at
this origin** — yet only one identity survives in the store. The rest are gone.

And **not one package at this origin has a content hash.** §9 explains why, and it is structural.

---

## 7. Union count by sourceTradeId / content identity

| Population | Identities |
|---|---:|
| `http://localhost:8744` | 1 |
| `http://10.143.1.187:8744` | 1 |
| **Union of both browser origins** | **2** |
| Disk exports (Step 4A) | 79 |
| Overlap between browser and disk | **0** |
| **UNION — browser ∪ disk, by `sourceTradeId`** | **81** |

Reconciled on `sourceTradeId` + `contentHash`. **`packageId` is never used alone as identity.**

Cross-checked individually:

| Identity | In browser | On disk |
|---|---|---|
| `AGT\|REALEXPORT\|1` | localhost | **not found** |
| `AGT\|INSECURE\|1` | 10.143.1.187 | **not found** |
| `AGT\|NOCRYPTO\|1` | **neither store** | present (`…-unverified.json`) |

So each population holds identities the other lacks — in both directions.

---

## 8. Duplicate and collision analysis

| Check | Result |
|---|---:|
| Packages present in **both** origins | **0** |
| Unique to `localhost:8744` | **1** |
| Unique to `10.143.1.187:8744` | **1** |
| **Cross-origin `packageId` collisions** | **0** *(see below)* |
| `sourceTradeId` collisions | **0** |
| contentHash matches across origins | 0 — no identity is in both |
| contentHash mismatches across origins | **0** |
| Duplicate physical disk copies (Step 4A) | 43, all agreeing on `contentHash` |
| Disk `packageId` collisions (Step 4A) | **12**, involving 26 distinct trades |

**Zero cross-origin collisions *in the surviving records* is not evidence that the hazard is absent.**
Both origins independently minted `PKG|alex_g_sr_v1|20260731|1` for **different** evidence —
`AGT|REALEXPORT|1` at localhost and a different package at the LAN origin. The collision is real; it
does not register as a *sourceTradeId* conflict only because so little survives at the LAN origin.
The 12 collisions found on disk in Step 4A are the same mechanism at full scale.

---

## 9. Is the 222 count independently reproducible?

## **No. Emphatically not — and I am not forcing the result to 222.**

| | |
|---|---:|
| Reported by the UI banner | 222 |
| **Independently derived from browser state** | **2** |
| Independently derived from disk | 79 (77 after excluding 2 synthetic) |
| **Union, browser ∪ disk** | **81** |
| **Unaccounted against 222** | **141** |

Three independent measurements agree that the 222-package store is **not on this machine**:

1. **Arithmetic.** 222 packages at the observed mean of 40,556 bytes require **≈ 8.6 MB**. Every
   MOGO-origin store here totals **0.22 MB** — off by ~39×.
2. **Content.** Both stores hold only 2026-07-31 records; the C1 runs and the export attempts are
   days later.
3. **Identity.** The two surviving browser identities appear nowhere on disk, and the 79 disk
   identities appear in neither store.

MOGO is served over the LAN (`http://10.143.1.187:8744`), so the operator's live browser is almost
certainly **on another device**. The 222 remains **OPERATOR_REPORTED and unverified**.

---

## 10. Does any genuine forward-paper-trading evidence exist?

## **No.**

Across all 81 identities in the union:

| Classification | Count | What it is |
|---|---:|---|
| **REAL** | **76** | **every one is `REPLAY_RUN`** — backtest replay, not forward trading |
| SYNTHETIC | 2 | `AGT\|NOCRYPTO\|1`, `AGT\|MANUAL-B\|…` — structurally impossible trades |
| UNDETERMINED | 1 | `1786021876135` (JVM) — 4 ms holding period, one rule only, retained in counts |
| UNCLASSIFIED | 2 | `AGT\|REALEXPORT\|1`, `AGT\|INSECURE\|1` — browser-only; the forensic extraction cannot recover the timestamps the classifier needs, so they are **not** classified |

**Not one `LIVE_CLOSE` package survives classification as real.** That is coherent — ALEX forward
paper trading has never been enabled — but it means the evidence population contains **zero examples
of the very thing the preflight exists to protect**, and the preflight has never been exercised
against real forward-trading evidence.

I have deliberately left the two browser-only artifacts **UNCLASSIFIED** rather than inferring from
their names. Their names suggest test artifacts; names are not evidence, and Decision 1 requires
structural proof I do not have for them.

---

## 11. New defect

### D-14 — the LAN origin is not a secure context, so it **cannot hash evidence at all** (High)

`crypto.subtle` requires a secure context. `http://localhost` is one **by specification**;
`http://10.143.1.187` is **not**. `index.html:12199` already records the rule.

**Confirmed by measurement:** the LAN-origin store contains **zero content hashes**, while the
localhost store's single package has one. The trade identifier at that origin is literally
`AGT|INSECURE|1`.

**The consequence is severe.** Any evidence captured while MOGO is reached by IP address is stored
with `contentHashProvenance: UNAVAILABLE` and **can never be cryptographically verified — not now,
not later, not by any tool.** `evidenceFinalizePackage()` degrades honestly rather than faking a
digest, which is right, but the evidence is permanently unverifiable.

**If the operator's 222 packages were captured over the LAN origin, a large fraction of them may be
unhashable, and the export preflight can never pass for those.** This must be established before any
repair work: it decides whether Step 4C is a recovery exercise or a re-capture exercise.

It also explains `AGT|NOCRYPTO|1` (Step 4A) and `AGT|INSECURE|1` as the same phenomenon under test,
and it compounds D-12: the two origins differ not only in *storage* but in *cryptographic capability*.

---

## 12. Remaining blockers for Step 4C

| | Blocker | Why it blocks |
|---|---|---|
| **B-1** | **The authoritative store is on another device** | Nothing here can enumerate the 222. `scripts/mogo_evidence_browser_manifest.js` must be run on the device that actually holds it |
| **B-2** | **D-14 — hashability of the real population is unknown** | If captured over the LAN origin, those packages have no hash and can never satisfy a cryptographic preflight |
| **B-3** | **D-12 — evidence is split across two origins** | Both must be manifested and reconciled, or 4C confirms one fragment and silently leaves the other |
| **B-4** | **D-2 — re-export demotes confirmations** | `Export all` clears `exportedAt`. E-5 approved the fix; **it is not implemented**. No re-export may occur until it lands |
| **B-5** | **D-8 — `packageId`-keyed counting under-reports** | Every counter, including the in-app one, must key on `sourceTradeId` |
| **B-6** | **No real forward-paper evidence exists to test against** | The preflight has never been exercised on the class of evidence it governs |

---

## 13. Recommended next action

**One action unblocks everything else, and it is read-only:**

> **Run `scripts/mogo_evidence_browser_manifest.js` in the MOGO tab on the device that actually holds
> the 222 packages — once per origin — and save each printed JSON.**

Then, locally and still without touching anything:

```
node scripts/mogo_evidence_verify.js --scan <DIR> --manifest <MANIFEST> --expected-total <N>
```

which produces the twelve-point reconciliation and the named stored-but-not-found work list.

**That single capture also settles B-2 immediately:** the manifest's `contentHashProvenance` and
`withoutContentHash` counts will show, per origin, how much of the real population is hashable at
all. **Until that is known, no repair plan can be designed honestly** — a recovery plan and a
re-capture plan are different pieces of work, and which one applies is currently unknown.

**Do not export anything first.** Under D-2, `Export all` would clear `exportedAt` on every package
it touches. The manifest is read-only and safe; the export is not.

### On the architectural requirement

Recorded and preserved, **not implemented**: the production solution must eliminate hundreds of
manual downloads and imports. The Step 4 plan's design stands — batch re-import via
`multiple`+`webkitdirectory` reusing the unchanged `evidenceEvaluateExportReimport()`, receiver-based
egress with observable acknowledgement, and independent offline verification — and multi-origin
provenance must now be a first-class field in every manifest and every confirmation record, not an
afterthought. Nothing in that design has been built.

---

## 14. Gate

Nothing repaired. No bulk export. No package confirmed. No automatic confirmation. No browser opened,
no browser storage altered — both live stores retain their original 2026-07-31 mtimes. No duplicate
deleted. No frozen Campaign C1 artifact touched (33/33, 42 files byte-identical). **Step 4C not
started. ALEX forward paper trading OFF. The evidence-export preflight remains FAIL-CLOSED.**

### Uncommitted work awaiting authorization

| File | State |
|---|---|
| `scripts/mogo_evidence_store_scan.js` | **new, untracked** — the forensic multi-origin scanner (12/12 selftest) |
| `MOGO-011-STEP-4B-REPORT.md` | new, untracked — governance document |
| `MOGO-011-STEP-4B-MULTI-ORIGIN-REPORT.md` | new, untracked — this report |
| `MOGO-011-STEP-4A-REPORT.md`, `MOGO-011-STEP-4A-INVENTORY.json` | new, untracked |

`HEAD` = `origin/mogo-main` = `ce94424bdb0f4fb6a7a10f45c1738623e25f06de`, 0 ahead / 0 behind.
