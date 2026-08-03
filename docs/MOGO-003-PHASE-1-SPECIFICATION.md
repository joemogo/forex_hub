# MOGO-003 Phase 1 — Durable Capture & Export
## Implementation Specification

**Milestone:** MOGO-003 Phase 1 · **Status:** SPECIFICATION ONLY — not implemented
**Date:** 2026-07-30 · **Revised:** 2026-07-30 (Engineering Authority rulings C1–C5 + minor corrections 1–5)
**HEAD:** `592ca97` (`mogo-002-complete`) · **Engine:** `APP_VERSION` 12.7.1 · **Target:** 12.8.0
**Parent:** [`MOGO-003-EVIDENCE-PLATFORM-ARCHITECTURE.md`](MOGO-003-EVIDENCE-PLATFORM-ARCHITECTURE.md)
**No production code modified. No strategy rule changed. No commit.**

**This document governs where it conflicts with the parent architecture** (parent §0 records the
supersession).

---

# 0A. Engineering Authority rulings incorporated — 2026-07-30

| Ruling | Decision | Where applied |
|---|---|---|
| **C1** | Content hash is **SHA-256** over deterministically canonicalised content. Asynchronous finalisation permitted. `alexGStableHash` may remain for internal non-security change detection but **must never be described or used as cryptographic tamper protection**. Integrity claims must not imply authenticity, identity verification, or protection from an attacker who can replace both package and hash | §5.1, §5.2, §5.3, §8, §9, §11 |
| **C2** | Tier (a) `localStorage` buffer · tier (b) IndexedDB automatic evidence store · tier (c) **successfully completed** disk export. **No claim that IndexedDB survives profile clearing, device loss, or disk loss** | §2.1, §2.4, parent §0/§6.1 |
| **C3** | Expanded Phase 1 scope **approved**. **File System Access API excluded** — Phase 1 must not depend on it. No replay, analytics, optimisation, or strategy-rule change authorised | §3.2, §12, §13 |
| **C4** | **Journal eviction dropped.** The guarded ALEX journal/ledger path is never capped, evicted, rewritten or bypassed. Caps apply only to `fxhub_alexg_setups` (1,000) and `fxhub_alexg_zones` (200/pair). No tier-(a) eviction before tier-(b) persistence. Tier-(b) packages never automatically deleted | §6, §6.1 |
| **C5** | Capture hooks **after** the `alexGCheckLivePositions` loop, adjacent to the existing save, in its own try/catch. Reports rather than swallows; structurally incapable of altering the protected close path; never prevents, repeats or alters a close; zero protected drift | §4.3, §4.4 |
| **Minor 1** | `packageId` sanitised before use in an export filename | §5.3, §8 |
| **Minor 2** | Sequence identifiers derived from persistent IndexedDB state, never process memory | §5.3 |
| **Minor 3** | `docs/STORAGE_KEYS.md` corrected — it currently states MOGO persists **all** state in `localStorage`, which this phase makes false | §4 |
| **Minor 4** | ADR treatment recommended and documented | §4, §15 |
| **Minor 5** | All existing modified and untracked files preserved; no unrelated cleanup | §4 |

---

# 0. Correction to the parent architecture

**The parent document's Phase 1 was under-specified, and the Engineering Authority's question exposes
it correctly.**

As originally scoped — *"loud write failure · capped buffers · whole-package JSON export"* — Phase 1
would have produced **manual backup capability, not durable evidence**. If the operator never clicked
Export and the browser profile were cleared, every trade would still be lost. That fails the milestone's
governing principle.

**This specification corrects that** by adding a genuinely automatic durability path (§3), and by
stating plainly what a browser can and cannot guarantee (§2.4).

---

# 1. Deliverable confirmation

| | |
|---|---|
| **File** | `docs/MOGO-003-EVIDENCE-PLATFORM-ARCHITECTURE.md` |
| **Absolute path** | `/Users/joemogollon/Desktop/Forex Hub/docs/MOGO-003-EVIDENCE-PLATFORM-ARCHITECTURE.md` |
| **Size** | 27,139 bytes · 489 lines |
| **Sections** | 15 of 15 present |
| **Git status** | `??` untracked — **not committed**, as directed |

---

# 2. Persistence model

## 2.1 The three tiers, precisely distinguished

*(Governing tier model, per ruling C2.)*

| | Tier | Medium | Holds | Automatic? | Survives reload | Survives **profile clear** | Survives **device / disk loss** |
|---|---|---|---|---|---|---|---|
| **a** | **Temporary working buffer** | `localStorage` (existing 31 keys, verified) | Live account, open positions, hot journal, engine cursors | ✅ | ✅ | ❌ **No** | ❌ **No** |
| **b** | **Automatic browser evidence store** | **IndexedDB** (new) | Complete evidence packages | ✅ **Fully — no user action, ever** | ✅ | ❌ **No** | ❌ **No** |
| **c** | **Durable artifact** | **Successfully completed export to a file on disk** | Self-contained, hash-verified evidence packages | 🟡 After one browser download grant | ✅ | ✅ **The only tier that does** | 🟡 **Only if the operator backs the file up off-device** |

⚠️ **Tier (c) counts only when the export completes successfully.** An attempted, failed, or cancelled
export produces no durable artifact and is never recorded as one.

⚠️ **IndexedDB is not a backup.** It does not survive browser-profile clearing, device loss, or disk
loss. **MOGO must never state or imply that it does.**

## 2.2 Why tier (b) is IndexedDB and not `localStorage`

| Constraint | `localStorage` | IndexedDB |
|---|---|---|
| Quota | ~5 MB **shared across all 31 keys** | Typically a large fraction of free disk |
| Failure mode | Throws; **currently swallowed by `catch(e){}`** | Async, catchable, reportable |
| Structured query | ❌ String blobs only | ✅ Indexed by key |
| Capacity at ~38 KB/trade (measured) | **~137 trades** | Effectively unbounded for this workload |

**The repository uses IndexedDB nowhere today** (0 references) — this is new surface, but it is
standard, synchronous-safe via promises, and requires no library.

## 2.3 Is the Evidence Package saved automatically or only by manual export?

**Both, at different tiers — and the distinction is the whole answer:**

- **Tier (b) IndexedDB write is fully automatic.** Every closed trade produces a package written
  without any user action. This is the default path and requires no interaction, ever.
- **Tier (c) file write is automatic *after one user grant*, manual otherwise.** See §3.

## 2.4 ⚠️ The honest limit — what no browser can guarantee

**No browser-resident storage survives a profile clear.** Clearing site data removes `localStorage`
and IndexedDB together. Tier (b) solves quota, silent failure, capacity and structure — **it does not
solve profile clearing, and it does not solve device loss or disk loss either.**

**Nor does tier (c) solve device or disk loss on its own.** A file written to the downloads directory
lives on the same disk as the browser profile. It survives a *profile clear*; it does not survive the
*machine*. Off-device backup remains the operator's responsibility and **Phase 1 must not imply
otherwise.**

**Durability outside the browser profile therefore requires writing a real file, and every browser
requires a user gesture or grant to permit that.** Phase 1 can make file writing *automatic after a
single one-time grant*. **It cannot make it zero-interaction from a cold start, and no design can.**

**This is a platform constraint, not a design shortfall — but it must be stated rather than implied.**

---

# 3. How Phase 1 prevents loss when the profile is cleared

Three mechanisms, in descending order of strength.

## 3.1 Mechanism A — Auto-export after one-time grant *(primary)*

**Uses the existing, unprotected `downloadTextFile()` primitive** (`index.html`, already used by
`exportReplayDiagnosticsJSON`).

The first programmatic download prompts *"Allow this site to download multiple files?"*. **Once the
operator allows it, subsequent exports write to the downloads directory with no further
interaction.** The app is served from `http://localhost:8743` (per `.claude/launch.json`) — a secure
context, so this is available.

**Trigger policy:** on every trade close · on a rolling cadence when ≥ N new packages are pending ·
on `visibilitychange → hidden` (tab close / navigate away).

**Residual risk:** the operator declines the grant, or the browser later revokes it. **Mitigated by
Mechanism C.**

> **Implementation note — the grant is made explicit.** Automatic export is gated behind an
> operator opt-in (`evidenceAutoExportEnabled`, default **off**), offered directly in the
> unexported-evidence banner. A programmatic download is an outward-facing side effect, so MOGO asks
> once rather than beginning to write files unprompted. Once enabled, export runs automatically on
> trade close and on `visibilitychange → hidden` with no further interaction — which is exactly the
> *"automatic after ONE grant"* model this section describes, with the grant made visible instead of
> being buried in a browser permission prompt the operator may not connect to MOGO.

## 3.2 Mechanism B — File System Access API ❌ **EXCLUDED FROM PHASE 1 (ruling C3)**

`showDirectoryPicker()` would write to an operator-chosen folder. **It is excluded from Phase 1 and
must not be implemented, capability-detected, referenced in code, or depended upon in any way.**

Rationale, recorded for the phase that may reconsider it: Chromium-only (no Safari, no Firefox), may
require re-permission per session, and introduces a second export path that would have to be kept
consistent with Mechanism A's marking and verification rules. **`exportMechanism` retains the
`FS_ACCESS` enum value as a reserved, never-emitted token** so that a future phase can add it without
a schema change — **Phase 1 must never produce it.**

## 3.3 Mechanism C — Unexported-evidence warning *(safety net)*

**The mechanism that makes the other two honest.** MOGO tracks `lastExportedPackageId` and surfaces a
persistent, non-dismissible banner whenever unexported packages exist:

> ⚠️ **14 evidence packages have never been exported.** They exist only in this browser profile and
> will be lost if site data is cleared. **[Export now]**

Escalates to a blocking modal on: enabling live paper trading · a reset action · > 50 unexported
packages.

**This converts silent loss into a standing, visible, actionable state.** It is the single
highest-value item in Phase 1 relative to its cost.

## 3.4 Verdict

| Scenario | Outcome |
|---|---|
| Reload / crash / quota pressure | ✅ **Fully protected** by tier (b), automatically |
| Profile cleared, exports completed successfully | ✅ **Protected** — packages already on disk |
| Profile cleared, grant declined or exports failed, warning ignored | ❌ **Evidence lost** |
| Device loss / disk loss, no off-device backup | ❌ **Evidence lost — no tier protects against this** |

**Phase 1 makes loss require the operator to actively ignore a standing warning. It cannot make loss
impossible.**

---

# 4. Files created or modified

**This is the complete and bounded file-change list. Nothing outside it is touched.**

| # | File | Action | Notes |
|---|---|---|---|
| 1 | `index.html` | **MODIFY** | New evidence-platform block, additive |
| 2 | `tests/v128_evidence_platform_tests.js` | **CREATE** | Fixture suite |
| 3 | `tests/run_v128_evidence_platform_tests.js` | **CREATE** | Runner — auto-discovered by `tests/run_all.sh`'s `tests/run_*_tests.js` glob (verified) |
| 4 | `regression-baseline-tools.py` | **MODIFY** | `FIXTURE_COUNTS` entry only. **`PROTECTED_FUNCTIONS` and `PROTECTED_CONSTANTS` are not touched** |
| 5 | `docs/RELEASE_NOTES.md` | **MODIFY** | v12.8.0 entry |
| 6 | `docs/TESTING.md` | **MODIFY** | New suite; async/Web-Crypto harness limitation; browser-verification checklist |
| 7 | `docs/STORAGE_KEYS.md` | **MODIFY** | **Minor 3** — correct the opening claim that MOGO persists *all* state in `localStorage`; document the IndexedDB store and its non-durability |
| 8 | `docs/ARCHITECTURE.md` | **MODIFY** | Evidence-platform section. ⚠️ **This file has +28 uncommitted lines (Trader Intelligence section). Those lines must be preserved verbatim — append only** |
| 9 | `docs/adr/ADR-010-evidence-package-persistence.md` | **CREATE** | **Minor 4** — see §15 |
| 10 | `docs/MOGO-003-EVIDENCE-PLATFORM-ARCHITECTURE.md` | **MODIFY** *(done)* | Rulings C1–C5 reconciled |
| 11 | `docs/MOGO-003-PHASE-1-SPECIFICATION.md` | **MODIFY** *(done)* | This document |

**Estimated `index.html` change: ~500–650 added lines, 3 existing functions modified** (`saveAlexGRest`,
`save`, `saveAlexGAccountGuarded`) **plus 3 additive call-site insertions** (`alexGCheckLivePositions`,
`runDiagnostics`, `renderAlexGLivePanel`).

**Minor 5 — preservation rule:** the working tree carries 62 modified/untracked entries from MOGO-002
closeout and Trader Intelligence work. **Not one of them may be reverted, staged, cleaned, reformatted
or reorganised.** Phase 1 touches only the files listed above.

## 4.1 Functions to add (all new, all non-protected — 0 name collisions verified)

**Canonicalisation & integrity (C1):** `evidenceCanonicalize` · `evidenceContentHash` *(async)* ·
`evidenceFinalizePackage` *(async)* · `evidenceVerifyPackageHash` *(async)* · `evidenceHashAvailable`

**Store (tier b):** `evidenceOpenDb` · `evidencePutPackage` · `evidenceGetPackage` ·
`evidenceListPackages` · `evidenceCountUnexported` · `evidenceAllocateSequence` *(Minor 2)*

**Construction & validation:** `evidenceBuildPackageFromTrade` · `evidenceValidatePackage` ·
`evidenceComputeCompleteness`

**Export / import / backfill:** `evidenceSanitizeForFilename` *(Minor 1)* · `evidenceExportPending` ·
`evidenceExportAll` · `evidenceMarkExported` · `evidenceImportFile` ·
`evidenceBackfillFromLocalStorage`

**Failure & surfaces:** `evidenceRecordWriteFailure` · `evidenceClassifyStorageError` ·
`renderEvidencePlatformDiagnostics` · `renderEvidenceExportBanner`

*(`evidencePackageContentHash` from the previous draft is superseded by the
`evidenceCanonicalize` + `evidenceContentHash` pair, which separates the deterministic,
synchronously-testable step from the asynchronous digest.)*

## 4.2 Existing functions to modify

| Function | Protected? | Change |
|---|---|---|
| `saveAlexGRest` (`index.html:2837`) | ❌ No | **Replace `catch(e){}` with failure classification + recording.** ⚠️ **Must not throw** — `commitAlexGLedger` calls it *after* the guarded ledger write and its best-effort semantics are load-bearing (v11.0.1 / v12.3.2 correction) |
| `save` (JVM, `index.html:5422`) | ❌ No | Same, with the same non-throwing constraint relative to `commitPaperLedger` |
| `saveAlexGAccountGuarded` | ❌ No | Surface quota failure **distinctly from** version conflict. **Return shape `{ok:…}` unchanged** — every caller's rollback contract must keep working byte-for-byte |
| `runDiagnostics` | ❌ No | Add evidence-platform card (additive call) |
| `renderAlexGLivePanel` | ❌ No | Add unexported banner (additive call) |
| `alexGCheckLivePositions` (`index.html:4692`) | ❌ No | **One additive capture call after the loop** — see §4.4 |
| `alexGCloseLivePosition` | 🔒 **PROTECTED** | **NOT MODIFIED** — see §4.3 |

## 4.3 Protected functions

# ZERO protected functions modified.

All **63** protected functions and **4** protected constants stay byte-identical, verified by
`regression-baseline-tools.py`.

`alexGCloseLivePosition` is protected and is where a trade completes. **Package construction hooks the
non-protected caller instead** — the identical seam used successfully by MOGO-002.5 provenance
stamping, the v1.1 entry-day gate and the 002.8B suspension gate. Expected drift: **zero**.

## 4.4 The capture seam — binding constraints (ruling C5)

`alexGCheckLivePositions()` (`index.html:4692`, confirmed **not** protected) is an `async` function
whose entire per-position body is already wrapped in `try{ … }catch(e){}` (line 4728) and which calls
the protected `alexGCloseLivePosition` at three points inside that loop.

**Capture is therefore placed AFTER the loop, adjacent to the existing `saveAlexG()` call (line 4730),
never inside it.** Binding rules:

| # | Rule |
|---|---|
| **S1** | The capture call sits **after** the `for` loop closes, next to `saveAlexG()` / `renderAlexGLivePanel()` |
| **S2** | It is wrapped in **its own** `try/catch` that calls `evidenceRecordWriteFailure` — it **reports**, it never swallows. The existing line-4728 swallow is not reused and not relied upon |
| **S3** | It is **structurally incapable of altering the protected close path**: it runs after every close for the tick has already completed, reads only already-closed positions, and has no return value any caller inspects |
| **S4** | It **never prevents, repeats, or alters a position close.** It cannot re-enter `alexGCloseLivePosition`, cannot mutate `alexGAccount.openPositions`, and cannot write the journal/ledger |
| **S5** | It is **fire-and-forget** (architecture E3). A rejected promise is caught and recorded; it is never awaited in a way that could delay or block the trading tick |
| **S6** | Best-effort trading-engine behaviour is preserved exactly — an evidence failure degrades evidence only, never trading |
| **S7** | **Zero drift** in all 63 protected functions and 4 protected constants |
| **S8** | Capture is idempotent per `tradeId` — a re-run of the tick cannot create a duplicate package |

---

# 5. Evidence Package v1 schema

```jsonc
{
  "packageSchemaVersion": "mogo.evidence-package.v1",
  "packageId":   "PKG|<strategyId>|<YYYYMMDD>|<seq>",   // seq from IndexedDB, never memory (§5.3)

  // --- Integrity block (ruling C1). See §5.1 canonicalisation, §5.2 claim scope. ---
  "contentHash":           "<64 lowercase hex chars — SHA-256 of the canonical form>",
  "contentHashAlgorithm":  "SHA-256",
  "contentHashCanonicalization": "mogo.evidence-canon.v1",
  "contentHashProvenance": "OBSERVED",   // OBSERVED when computed; UNAVAILABLE if Web Crypto absent
  "contentHashScope":      "INTEGRITY_ONLY_NOT_AUTHENTICITY",

  "createdAt":   "2026-07-30T14:23:08.051Z",

  "identity": {
    "strategyId": "alex_g_sr_v1",
    "strategyVersion": "alex_g_sr_v1_1",
    "implementationVersion": "alex_g_sr_v1.impl.1",
    "engineVersion": "12.7.1",
    "commitHash": null,              // null + reason until build-time injection exists
    "commitHashProvenance": "UNAVAILABLE",
    "mode": "LIVE_PAPER",            // LIVE_PAPER | REPLAY
    "runId": null                    // REPLAY only
  },

  "configSnapshot": { /* verbatim snapshotAlexGConfig() output */ },
  "configHash": "<sha256>",

  "objects": {
    "candidates":     [ /* Candidate */ ],
    "decisions":      [ /* Decision — from the existing decision-event bus */ ],
    "qualifiedSetups":[ /* QualifiedSetup */ ],
    "positions":      [ /* Position */ ],
    "outcomes":       [ /* Outcome */ ],
    "marketContexts": [ /* Phase 3 — empty array in Phase 1 */ ]
  },

  "objectCounts": { "candidates": 0, "decisions": 0, "qualifiedSetups": 0,
                    "positions": 0, "outcomes": 0, "marketContexts": 0 },

  "completenessReport": {
    "level": "PARTIAL",              // COMPLETE | PARTIAL | MINIMAL | UNKNOWN
    "missing": [
      { "field": "marketContexts",  "reason": "FUTURE_WORK",
        "detail": "Candle capture is MOGO-003 Phase 3." },
      { "field": "identity.commitHash", "reason": "UNAVAILABLE",
        "detail": "No build-time commit injection exists at 12.7.1." },
      // v12.12.0 (Unit C1): this entry is now CONDITIONAL. A package that actually carries
      // verified excursion timing omits it; every other package still declares it exactly here,
      // in this array position. Phase 1's own scope is unchanged.
      { "field": "outcomes[].timeToMFE", "reason": "FUTURE_WORK",
        "detail": "Excursion timing is Phase 5." }
    ]
  },

  // --- Excluded from the hash (§5.1). Mutable after finalisation. ---
  "export": {
    "exportedAt": null,
    "exportMechanism": null,         // AUTO_DOWNLOAD | MANUAL. FS_ACCESS reserved, never emitted in P1
    "exportFilename": null,
    "exportVerified": null           // true only after the written bytes re-hash to contentHash
  }
}
```

**Phase 1 deliberately emits `PARTIAL`.** A package that claimed `COMPLETE` while lacking market
context would be dishonest — and `completenessReport` is what makes the honesty machine-readable.

**Reuses existing primitives, does not reinvent them:** `snapshotAlexGConfig` (`index.html:2732`), the
decision-event schema, and the `EVIDENCE_FIELD_PROVENANCE` vocabulary (`index.html:11042`).

⚠️ **`alexGStableHash` (`index.html:2637`) is NOT used for `contentHash`.** It is a 64-bit FNV-variant
producing 16 hex characters — **not a cryptographic hash.** It remains in place, unmodified, for its
existing internal change-detection uses (`ruleSetHash`, `configurationHash`) and **must never be
described, documented, or used as tamper protection** (ruling C1).

## 5.1 Canonicalisation — `mogo.evidence-canon.v1`

**The hash is only as trustworthy as the determinism of what it hashes.** Canonical form is defined
exactly, once, and is independently testable without any async machinery:

| # | Rule |
|---|---|
| **K1** | Start from the package object |
| **K2** | **Delete `contentHash`, `contentHashAlgorithm`, `contentHashCanonicalization`, `contentHashProvenance`, `contentHashScope`, and the entire `export` block.** A package's hash must not change when it is later marked exported |
| **K3** | **Object keys sorted ascending by UTF-16 code unit**, then emitted as `{"k":v,…}`. Object key order is therefore insignificant |
| **K4** | **Array order is preserved and IS significant.** Arrays are ordered evidence — a reordered decision chain is a different chain |
| **K5** | `undefined` → `null`. Absence is always explicit, never omitted (architecture §3.1 rule 2) |
| **K6** | Numbers, strings and booleans via standard JSON encoding. `NaN` / `±Infinity` are a **validation error**, never silently coerced |
| **K7** | The canonical string is encoded **UTF-8** before digesting |
| **K8** | No whitespace, no trailing separators, no BOM |

**Note on wording:** the previous draft described `alexGStableHash` as "order-independent". That is
imprecise — its `canon` step is **key-order-independent and array-order-significant**, exactly as K3/K4
above. `evidenceCanonicalize` implements this rule set as its own independently-testable function
rather than borrowing it, so the canonical form can never drift with an unrelated change to
`alexGStableHash`.

## 5.2 What the integrity claim does and does not mean *(ruling C1 — required wording)*

**`contentHash` detects alteration of a package relative to its recorded hash.** It protects against
corruption, truncation, partial writes, storage faults, and accidental or casual modification.

**It is NOT any of the following, and MOGO must never present it as such:**

- ❌ **Not authenticity.** It does not prove who produced the package.
- ❌ **Not identity verification.** It binds no operator, machine, or installation.
- ❌ **Not a digital signature.** There is no key, therefore no signer.
- ❌ **Not protection against a capable attacker.** Anyone who can modify a package can recompute
  SHA-256 over the modified content and replace the stored hash. **Against a deliberate adversary with
  write access to both, this provides no protection at all.**

**This wording is normative.** The Diagnostics card, the release notes and any user-facing string must
describe verification as *"content integrity verified"* — **never** as *"verified authentic"*,
*"signed"*, or *"tamper-proof"*. A fixture asserts this vocabulary (§11 group 2).

*(The parent architecture §4.7 previously said "Signed, self-contained evidence packages". Nothing in
Phase 1 is signed; that word is withdrawn.)*

## 5.3 Identifiers *(Minor 1 and Minor 2)*

**Sequence allocation — persistent, never process memory.** `evidenceAllocateSequence(strategyId,
yyyymmdd)` reads and increments a counter in an IndexedDB `meta` object store inside a **committed
`readwrite` transaction**.

- ✅ Survives reload, tab close, and crash — a fresh session never restarts at `1`.
- ✅ Two tabs cannot collide: IndexedDB serialises overlapping `readwrite` transactions on the same store.
- ✅ The package is then inserted with `add()`, **never `put()`**, so a duplicate `packageId` or a
  duplicate `sourceTradeId` is rejected rather than silently overwriting a stored package.
- ❌ **An in-memory counter is explicitly forbidden** — it would silently mint duplicate `packageId`s
  after every reload.

> ⚠️ **Disclosed deviation from this section's original wording, recorded at implementation.**
> An earlier draft required allocation and the package write to share **one** transaction. That is
> **not achievable**: the SHA-256 digest sits between them and is asynchronous, and an IndexedDB
> transaction auto-commits as soon as the microtask queue drains with no pending request. Allocation
> is therefore its own committed transaction, and the package is added afterwards.
>
> **Consequence:** if the later write fails, a sequence number is **burned**. This is harmless — a
> sequence number is an identifier, not a count — and is strictly safer than reusing one. No
> invariant is weakened: IDs remain unique, no package is silently overwritten, and no evidence is
> lost. Flagged for Engineering Authority acknowledgement rather than left as an undocumented gap.

**`packageId` keeps the `|` delimiter**, matching the existing repository convention
(`alexGSetupId` → `AGS|…`, `alexGTradeId`, `alexGZoneId`). `|` cannot occur in any component, so the
ID stays unambiguously parseable.

**`evidenceSanitizeForFilename(s)` is applied to every component before it reaches a filename:**
replace every character outside `[A-Za-z0-9._-]` with `_`, collapse runs of `_`, strip leading/trailing
`.`/`-`/`_`, reject the empty result, and truncate to 64 characters. **A raw `packageId` must never be
concatenated into a filename** (Minor 1).

## 5.4 When Web Crypto is unavailable — the honest degraded path

`crypto.subtle` requires a secure context. `http://localhost:8743` (per `.claude/launch.json`) **is**
one. But `index.html` can also be opened directly from disk over `file://`, where `crypto.subtle` is
`undefined`. `evidenceHashAvailable()` detects this once.

**Policy — evidence preservation wins, but the claim degrades honestly:**

| Behaviour | Rule |
|---|---|
| Capture | ✅ **Still proceeds.** The package is built and written to tier (b). Losing evidence to protect a hash would invert the milestone's purpose |
| `contentHash` | `null`, with `contentHashProvenance: "UNAVAILABLE"` and a `completenessReport.missing` entry |
| Fallback | ❌ **Never falls back to `alexGStableHash`.** A weak hash in a field labelled SHA-256 would be a false integrity claim |
| Export | Permitted, but the artifact carries the `UNAVAILABLE` marker and the banner reports the count of unverifiable packages |
| Import | Such a package is accepted **read-only and flagged `UNVERIFIED`** — never silently trusted, and never treated as "verified" |
| Surface | 🔴 Diagnostics: *"Package integrity hashing unavailable in this context — packages are being stored without verification."* |

---

# 6. Buffer limits and eviction

**Revised per ruling C4 — journal eviction is dropped from Phase 1.**

| Store | Tier | Limit | Eviction | Today |
|---|---|---|---|---|
| `fxhub_alexg_account` | a | 🔒 **No cap — the live ledger** | **Never** | uncapped |
| `fxhub_alexg_journal` | a | 🔒 **No cap — OUT OF SCOPE (C4)** | **Never. Not capped, evicted, rewritten or bypassed** | uncapped |
| `fxhub_alexg_setups` | a | **1,000 records** | Oldest first, **gated on tier-(b) persistence** | ⚠️ **unbounded today (R8)** |
| `fxhub_alexg_zones` | a | **200 zones per pair** | Oldest by `formedAt`, **gated on tier-(b) persistence** | ⚠️ **unbounded today (R8)** |
| `decisionEventLog` | memory | 500 *(existing, unchanged)* | Existing oldest-first behaviour, **not modified in Phase 1** | transient |
| IndexedDB `packages` | b | **No cap** | 🔒 **Never automatic, under any condition** | n/a |

## 6.1 The eviction safety rule

> **No tier-(a) record may be evicted until its corresponding evidence has been successfully persisted
> to tier (b), and no tier-(b) Evidence Package may be automatically deleted at all.**

"Successfully persisted" means the IndexedDB write transaction has **committed**, not that it was
issued. If tier (b) is unavailable, **eviction does not run** — the buffer is allowed to exceed its cap
and the condition is reported, because an over-full buffer is recoverable and a deleted record is not.

Eviction that outruns capture is exactly the silent loss this milestone exists to end.

## 6.2 Why the journal is excluded *(ruling C4, rationale recorded)*

`alexGJournalEntries` is persisted **only** by `saveAlexGAccountGuarded()` via `commitAlexGLedger()` —
the atomic account+version+journal unit established by the v11.0.1 / v12.3.2 ledger corrections and the
subject of INC-001. Capping it would mean mutating ledger state through the guarded path, mixing an
evidence-retention concern into the one code path in MOGO that must stay boring.

**It is also unnecessary:** the journal is not the store that exhausts quota. `fxhub_alexg_setups` and
`fxhub_alexg_zones` are the two genuinely unbounded stores (verified — filtered per pair at
`index.html:3959` / `4420`, capped nowhere), and they are the two Phase 1 bounds.

**Phase 1 introduces no code path that writes, caps, evicts, reorders or rewrites the ALEX
journal/ledger.** A fixture asserts this directly (§11 group 5).

---

# 7. Write-failure detection and user-visible behaviour

## 7.1 Current behaviour — the defect being fixed

```js
function saveAlexGRest(){
  try{
    localStorage.setItem('fxhub_alexg_auto',  JSON.stringify(alexGAutoTrading));
    localStorage.setItem('fxhub_alexg_zones', JSON.stringify(alexGZoneState));
    localStorage.setItem('fxhub_alexg_setups',JSON.stringify(alexGSetupState));
  }catch(e){}                                  // ← evidence can vanish silently
}
```

## 7.2 Required behaviour

Every persistence path must, on failure: classify the error (`QuotaExceededError` vs other) · record
to the existing `alexGEngineErrors` / `paperEngineErrors` channels *(already surfaced in Diagnostics —
reuse, do not invent)* · emit a `DATA_UNAVAILABLE` decision event · set a **persistent** banner ·
**mark affected evidence `PARTIAL` with reason `UNAVAILABLE`, never omit it silently**.

## 7.3 User-visible surfaces

| Condition | Surface |
|---|---|
| Quota exceeded | 🔴 Persistent banner: *"Storage full — evidence is not being saved. Export now."* |
| Any write failure | Diagnostics error card (existing channel) |
| Unexported packages exist | ⚠️ Standing banner with count + **[Export now]** |
| > 50 unexported | Blocking modal on live-trading enable |
| IndexedDB unavailable | 🔴 *"Durable evidence storage unavailable — running in buffer-only mode."* |

**No failure may be silent. That is the phase's defining requirement.**

---

# 8. Export behaviour

| | |
|---|---|
| **Format** | One JSON file per package, or a bundle |
| **Filename** | `mogo-evidence-<san(strategyId)>-<san(packageId)>-<contentHash12>.json`, where `san()` is `evidenceSanitizeForFilename` (§5.3, **Minor 1**) and `contentHash12` is the first 12 hex characters |
| **Mechanism** | `downloadTextFile()` (`index.html:7879`, non-protected, already used by `exportReplayDiagnosticsJSON`). **`AUTO_DOWNLOAD` or `MANUAL` only — never `FS_ACCESS`** (C3) |
| **Trigger** | Auto on trade close (grant permitting) · cadence when ≥ N pending · `visibilitychange → hidden` (no such listener exists today — new, additive) · manual button |
| **Idempotence** | `contentHash` in the filename makes re-export detectable and harmless |
| **Verification** | **Re-canonicalise and re-digest the exact bytes about to be written and compare to `contentHash`.** Mismatch **aborts** the export and reports — it never writes and never marks |
| **Marking** | A download records an **attempt only** — see §8.1. `exportedAt` is set **only** by a verified re-import |

⚠️ **A package is never marked exported on a failed, aborted, or cancelled download.** Optimistic
marking would recreate silent loss in a new place — and would make the unexported-evidence banner lie,
which is worse than having no banner.

## 8.1 EXP-001 — a browser download is an attempt, not a durability proof *(corrected)*

**Found by literal browser verification, not by reasoning.** The original design marked a package
exported whenever `downloadTextFile()` returned without throwing. It cannot throw on refusal:

```js
a.href=url; a.download=filename; document.body.appendChild(a); a.click();
```

Verified in-browser — it **returns nothing, has no error handling, and cannot report whether the
browser accepted, blocked, cancelled or failed the write.** Chrome silently refused two real
downloads while the app reported `ok:true`, set `exportVerified:true`, and cleared the standing
warning, **with no file anywhere on disk.** The original fixture missed this because its stub
*threw*; the real API never does.

**Corrected contract:**

| Stage | State recorded | Warning |
|---|---|---|
| Download attempted | `exportAttemptedAt`, `exportMechanism`, `exportFilename`, `exportAttemptCount`. **`exportedAt: null`, `exportVerified: false`** | ❌ **Does not clear** |
| Operator re-imports the written file | All five conditions below must hold | ✅ **Clears** |

**All five are required — there is no shortcut:**

1. The bytes **parse**.
2. The package **validates** against schema v1.
3. The **identity matches** the stored package (`packageId` **and** `sourceTradeId`).
4. The **SHA-256 content hash verifies**.
5. The **exact canonical content is byte-identical** to the stored Evidence Package.

Only then are `exportedAt`, `exportVerified: true` and
`exportVerificationMethod: 'REIMPORT_VERIFIED'` recorded.

**MOGO only ever claims evidence is on disk when it has actually read it back off disk.**

**Explicitly excluded:** the File System Access API (ruling C3), and **any operator-confirmation
shortcut** — an operator saying *"yes, it downloaded"* is not evidence; the bytes are. The decision
function `evidenceEvaluateExportReimport()` is pure and consults neither `confirm()` nor `prompt()`.
An `UNVERIFIABLE` hash (no Web Crypto) can never confirm an export; it degrades to an explicit
`DUPLICATE_IDENTICAL_UNVERIFIABLE` no-op.

⚠️ **Unverifiable packages** (`contentHashProvenance: "UNAVAILABLE"`, §5.4) may be exported, but are
counted and displayed separately from verified ones. They are never reported as verified.

---

# 9. Import and recovery

**Included in Phase 1** — an export path without an import path is a one-way door.

`evidenceImportFile(file)`: parse → validate against v1 schema → **canonicalise per §5.1 and recompute
SHA-256, compare to the package's own `contentHash`** → reject on mismatch (**never repair**) → insert
into IndexedDB, keyed by `packageId`.

| Rule | Behaviour |
|---|---|
| `contentHash` mismatch | ❌ **Reject and report — the package is altered.** Never repaired, never re-hashed, never imported |
| `contentHash` absent / `UNAVAILABLE` | 🟡 Import **flagged `UNVERIFIED`** — never counted or displayed as verified (§5.4) |
| `contentHashAlgorithm` ≠ `SHA-256` | ❌ Reject — an unrecognised algorithm cannot be verified |
| Duplicate `packageId`, identical hash **and identical canonical content** | ✅ **This is the EXP-001 export-verification event** (§8.1) — the stored package is marked exported and the warning clears |
| Duplicate `packageId`, identical hash but hash **unverifiable** | **Explicit no-op** (`DUPLICATE_IDENTICAL_UNVERIFIABLE`) — never an export confirmation |
| Duplicate `packageId`, **different hash** | ❌ **Reject and report** — never overwrite |
| Unknown fields | ✅ Preserved (forward compatibility), and **included in the canonical form**, so they are covered by the hash |
| Newer `packageSchemaVersion` | Import read-only with a warning |

**Sequence isolation:** an imported `packageId` **never advances** the tier-(b) sequence counter
(§5.3). Import is recovery, not production — a recovered package must not influence the IDs of
packages this installation goes on to create.

**Import never touches `alexGAccount`, `alexGJournalEntries`, or any live trading state.** It populates
the evidence store only. **Recovery is for analysis, not for resurrecting a live account** — that
distinction prevents an import from corrupting a running ledger.

---

# 10. Backward compatibility with existing history

**Existing localStorage trade history must be adoptable without rewriting a single record.**

`evidenceBackfillFromLocalStorage()` — one-time, idempotent, **read-only over existing stores**:

1. Read `fxhub_alexg_journal` + `fxhub_alexg_account.closedPositions`.
2. Build one package per closed trade from **only the fields actually present**.
3. Mark `completenessReport.level = "MINIMAL"`, with `reason: "UNSAFE_TO_RECONSTRUCT"` for every field
   that did not exist at the time.
4. Set `identity.strategyVersion` from `strategyProvenance` when present; otherwise
   `"alex_g_sr_v1 (inferred, unstamped)"` with provenance `DERIVED`.
5. **Never** back-fill, infer, or fabricate a missing value.

**Guarantees:** no existing record is modified, moved or deleted · **the journal and ledger are opened
read-only and never written by any backfill path (C4)** · pre-v1.1 trades stay honestly unversioned
(matching `alexGClassifyTradeProvenance`, `index.html:2694`) · running it twice changes nothing ·
backfilled packages are canonicalised and hashed exactly like live ones, so a `MINIMAL` package is
still integrity-verifiable.

**This backfill would immediately place the two July Break & Retest trades under version control as
`MINIMAL` packages** — not solving the forensics, but ending the "one browser profile, no backup"
exposure.

---

# 11. Validation and test requirements

## 11.1 New suite — `tests/run_v128_evidence_platform_tests.js`, **62 fixtures**

| # | Group | Fixtures | Coverage |
|---|---|---|---|
| **1** | **Canonicalisation** (§5.1) | **7** | Deterministic across repeated calls; **key-order independent** (K3); **array order significant** (K4); `undefined`→`null` (K5); `NaN`/`Infinity` rejected (K6); **excludes all five integrity fields and the whole `export` block** (K2); nested + Unicode stable |
| **2** | **Integrity — sync-testable parts** (§5.2, §5.4) | **6** | Hex output shape (64 lowercase); mutation of any content field changes the canonical string; mutating **only** `export` does **not**; `evidenceHashAvailable()` false ⇒ `contentHash:null` + `UNAVAILABLE`; **never falls back to `alexGStableHash`**; **user-facing integrity vocabulary contains no "signed"/"authentic"/"tamper-proof"** |
| **3** | **Schema & validation** | **8** | v1 validates; unknown fields preserved; `completenessReport` mandatory; `PARTIAL` correctly asserted in Phase 1; `objectCounts` match `objects`; `marketContexts` empty + `FUTURE_WORK`; `commitHash` `null` + `UNAVAILABLE`; invalid packages rejected with a reason |
| **4** | **Write-failure detection** (§7) | **7** | Simulated `QuotaExceededError` → recorded, banner set, `DATA_UNAVAILABLE` emitted, **never silent**; non-quota errors distinguished; **`saveAlexGRest`/`save` never throw**; `saveAlexGAccountGuarded` return shape unchanged |
| **5** | **Buffer caps & eviction** (§6) | **7** | `fxhub_alexg_setups` capped at 1,000; `fxhub_alexg_zones` at 200/pair; **eviction blocked until tier-(b) commit**; **tier-(b) never auto-deletes**; account ledger never evicted; **`fxhub_alexg_journal` never capped, evicted or rewritten (C4)**; tier-(b) unavailable ⇒ eviction does not run |
| **6** | **Export** (§8) | **6** | Filename shape; **`packageId` sanitised — no raw `\|` reaches a filename**; **not marked exported on failure/cancel**; idempotent re-export; `exportMechanism` never `FS_ACCESS`; unverifiable packages counted separately |
| **7** | **Import & recovery** (§9) | **7** | Round-trip; **hash mismatch rejected, never repaired**; duplicate-different-hash rejected; unknown algorithm rejected; `UNAVAILABLE` imported as `UNVERIFIED`; **live trading state untouched**; **import does not advance the sequence counter** |
| **8** | **Backfill** (§10) | **6** | Idempotent; **no existing record mutated, moved or deleted**; unstamped trades stay unstamped; `MINIMAL` level; `UNSAFE_TO_RECONSTRUCT` reasons present; nothing fabricated |
| **9** | **Seam & protected-path safety** (§4.4) | **6** | `alexGCheckLivePositions` confirmed **not** protected (cross-checked against `BASELINE_ALEX_FUNCTIONS`); capture is after the loop; a **throwing** capture cannot alter close outcomes (S3/S4); capture never re-enters `alexGCloseLivePosition`; capture never writes the journal/ledger; idempotent per `tradeId` (S8) |
| **10** | **Store contract — sync-testable parts** | **2** | `evidenceAllocateSequence` allocates from persistent state, not memory, against a deterministic mock; sequence and package write share one transaction (abort ⇒ neither) |
| | **Total new** | **62** | |

## 11.2 Expected fixture total

| | |
|---|---|
| Current verified baseline | **679 / 679 PASS**, 14 suites, 0 execution errors, **0 drift** |
| New in v12.8.0 | **+62** |
| **Expected total after Phase 1** | **741 / 741 PASS**, 15 suites, **0 drift (63 functions / 4 constants)** |

*(`regression-baseline-tools.py`'s `FIXTURE_COUNTS` totals 847 across 31 entries. That is the
**historical superset** including the 22 disclosed scratchpad-only suites, not the repository baseline.
The release report must not conflate the two numbers: the repository-owned figure is 679 → 741.)*

## 11.3 ⚠️ Disclosed harness limitations *(must appear in the release report, not glossed)*

The offline JXA runner cannot resolve genuine `async` chains, **and `osascript` provides no
`crypto.subtle` and no IndexedDB.** Two consequences, both stated plainly:

| Layer | Offline-testable? | How it is verified |
|---|---|---|
| Canonicalisation (§5.1) | ✅ **Fully** — pure and synchronous | 7 fixtures |
| SHA-256 digest itself | ❌ **No `crypto.subtle` in JXA** | **Browser-verified against published NIST SHA-256 test vectors**, recorded in the release report |
| IndexedDB read/write | ❌ Async, absent from the harness | Browser-verified; the offline suite covers the pure layers via a deterministic mock |
| Package construction, validation, eviction, backfill, filename sanitisation | ✅ **Fully** | 44 fixtures |

This is the same documented offline/live split already used for `alexGCloseLivePosition` and
`closePaperPosition`. **The async layer is kept deliberately thin so the untestable surface stays
small** — every decision worth testing lives in a pure function.

## 11.4 Browser-verification checklist *(required before the phase is declared done)*

1. NIST SHA-256 known-answer vectors match `evidenceContentHash`.
2. A live paper trade close produces a tier-(b) package with **no user action**.
3. A forced `QuotaExceededError` is visible in Diagnostics within one render cycle.
4. Export writes a file; its bytes re-hash to `contentHash`; the package is marked only then.
5. A **cancelled** export leaves the package unmarked and the banner count unchanged.
6. A hand-edited exported file is **rejected** on import.
7. Reload → sequence counter continues, no duplicate `packageId`.
8. `file://` open → integrity-unavailable banner, capture still succeeds, nothing claims verification.
9. Backfill run twice changes nothing.
10. Journal/ledger byte-identical before and after a full session (C4).

---

# 12. Definition of Done — Phase 1

1. Every closed trade automatically produces a v1 package in IndexedDB, with **no user action**.
2. **No persistence path can fail silently** — quota failure is visible in ≤ 1 render cycle.
3. Unexported packages surface a standing, accurate count.
4. A download records an **attempt only** and **never clears the unexported warning**; a package is
   marked exported **only** after a re-import satisfies all five conditions in §8.1 (EXP-001).
5. Import round-trips and **rejects altered packages, never repairing them**.
6. Backfill adopts existing history without modifying one record and without fabricating one value.
7. Buffer caps enforced on `fxhub_alexg_setups` / `fxhub_alexg_zones` only; **eviction cannot outrun
   capture**; **tier-(b) packages are never automatically deleted**.
8. `completenessReport` honestly reports Phase 1 as `PARTIAL`.
9. **Zero protected-function drift** (63 functions / 4 constants); **regression green at 741/741**.
10. Demonstrated on **ALEX and one other strategy** with no schema change.
11. The async / Web-Crypto / IndexedDB harness limitations are disclosed (§11.3).
12. **The ALEX journal/ledger is byte-identical in behaviour** — not capped, evicted, rewritten or
    bypassed (C4), asserted by fixture.
13. **No integrity claim overstates itself** — no user-facing or documentation string describes a
    package as signed, authentic, or tamper-proof (C1, §5.2).
14. **No File System Access API code exists** anywhere in the change (C3).
15. All 62 pre-existing modified/untracked working-tree entries are **preserved untouched** (Minor 5).
16. `docs/STORAGE_KEYS.md` no longer claims all MOGO state lives in `localStorage` (Minor 3), and
    **ADR-010** records the persistence decision (Minor 4).

---

# 13. Explicit exclusions

**Not in Phase 1:** market context / candle capture (P3) · decision-chain durability beyond what the
bus already emits (P2) · replay run identity, date range, dataset hash (P4) · `timeToMFE`/`timeToMAE`
(P5) · **any analytics or metric computation** · **any replay implementation** · **any strategy
optimisation** · **the B1 resistance-role defect** (protected code, separate authorisation) ·
transaction-cost modelling · **any strategy rule, entry, exit, stop, target or sizing change** ·
commit-hash injection (recorded `null` + `UNAVAILABLE` until a build step exists).

> **Status note, 2026-08-03 — Phase 1's exclusions above are unchanged and remain historically
> accurate.** Recording only what has since shipped in later units: replay run identity, absolute
> date range and dataset hash landed in **v12.9.0**; `timeToMFE`/`timeToMAE` landed in **v12.12.0
> (Unit C1)**, replay capture path only, with browser verification still pending. Market context /
> candle capture (P3) is **partially delivered**: Unit C2-M1 (v12.13.0) captures a bounded
> own-timeframe window plus evidence lineage for captured replay trades, while the content-addressed
> candle store, higher-timeframe context (Unit C2-M2) and untraded-candidate context remain
> **unimplemented**. Decision-chain durability (P2) remains **unimplemented**.

**Excluded by explicit Engineering Authority ruling:**

| Excluded | Ruling |
|---|---|
| **File System Access API** — not implemented, not capability-detected, not referenced. Phase 1 must not depend on it | **C3** |
| **Journal / ledger capping, eviction, rewriting or bypass** — the guarded ALEX path is not touched | **C4** |
| **`alexGStableHash` as tamper protection** — it may remain for internal change detection only, never described or used as cryptographic protection | **C1** |
| **Any claim that IndexedDB survives profile clearing, device loss, or disk loss** | **C2** |
| **Any modification to a protected function or constant** | **C5** |

---

# 14. Answer to the Authority's question

> **Does Phase 1 alone make evidence durable automatically, or merely make manual backup possible?**

**Both, and the boundary is precise:**

| | Automatic? |
|---|---|
| **Durable against reload, crash, quota pressure** (tier b) | ✅ **YES — fully automatic, no user action ever** |
| **Durable against browser-profile clearing** (tier c) | 🟡 **Automatic after ONE browser download grant.** Manual if declined |
| **Zero-interaction durability from a cold start** | ❌ **Impossible in any browser** — a file write always requires a gesture or grant |
| **Durable against device loss or disk loss** | ❌ **No tier provides this.** The exported file sits on the same disk as the profile. Off-device backup is the operator's responsibility, and Phase 1 says so rather than implying otherwise (C2) |

**Phase 1 as originally scoped in the parent document made only manual backup possible. That was a
genuine gap, and this specification closes it** — through IndexedDB (automatic), auto-export after one
grant (automatic thereafter), and a standing unexported-evidence warning that makes loss require the
operator to actively ignore it.

**MOGO cannot make evidence loss impossible. Phase 1 makes it loud, visible, and deliberate.**

---

---

# 15. ADR treatment *(Minor 4)*

**Recommendation: create `docs/adr/ADR-010-evidence-package-persistence.md`.**

The repository holds nine ADRs, and the two most directly implicated both stop at `localStorage`:

- **ADR-002 — Isolated strategy and feature storage.** Establishes "each key belongs to exactly one
  owning variable and is written by exactly one save path." **Phase 1 introduces a second storage
  medium**, which that ADR does not contemplate. The isolation principle should be extended to
  IndexedDB, not silently assumed to carry over.
- **ADR-003 — Paper ledger transaction model.** Defines the guarded, atomic ledger path. **ADR-010 must
  state explicitly that the evidence platform reads from the ledger and never writes to it** — the
  written form of ruling C4.

**ADR-010 should record, at minimum:** the three-tier model and its exact durability limits (C2); why
IndexedDB rather than `localStorage`; that the evidence store is **read-only with respect to all
trading state**; the SHA-256 integrity decision **and the explicit scope limits of that claim** (C1,
§5.2); that tier-(b) packages are never automatically deleted; and that eviction is gated on tier-(b)
persistence.

**Amending ADR-002 in place is the weaker option** — the persistence decision is substantial enough to
deserve its own record, and ADR-002 remains true within its own scope.

---

*Specification only, revised 2026-07-30 to incorporate Engineering Authority rulings C1–C5 and minor
corrections 1–5. No production code modified; no strategy rule changed; no commit created.
**Awaiting final Engineering Authority authorisation to implement Phase 1.***
