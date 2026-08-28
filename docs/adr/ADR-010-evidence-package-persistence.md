# ADR-010 — Evidence Package persistence

**Status:** Accepted · **Date:** 2026-07-31 · **Release:** v12.8.0 (MOGO-003 Phase 1)
**Authority:** Engineering Authority rulings C1–C5, minor corrections 1–5
**Supersedes nothing. Extends:** [ADR-002](ADR-002-isolated-strategy-and-feature-storage.md),
[ADR-003](ADR-003-paper-ledger-transaction-model.md)

---

## Context

MOGO-003's governing principle is: *"If MOGO cannot explain a trade six months later, then MOGO
failed to capture enough evidence when the trade occurred."*

Four measured facts about the persistence layer as of v12.7.1 made that principle unachievable:

| Finding | Evidence |
|---|---|
| 31 `localStorage` keys sharing one ~5 MB browser quota | Enumerated from `index.html` |
| Write failures silently swallowed | `saveAlexGRest()` and `save()` were both `try{…}catch(e){}` |
| Two persisted structures grew without bound | `alexGSetupState`, `alexGZoneState` — no cap anywhere |
| No quota detection at all | Zero occurrences of `QuotaExceeded` |

Capturing the evidence the July 2026 forensics proved necessary (~38 KB/trade with exit-path
candles) would exhaust the quota in roughly 137 trades — **and the failure would be silent.**

**An evidence platform whose storage can fail without telling anyone is worse than no platform,
because it produces confident conclusions from partial data.**

---

## Decision

### 1. Three tiers, with `localStorage` demoted to a working buffer

| Tier | Medium | Automatic? | Survives reload | Survives **site-data clear** | Survives **device / disk loss** |
|---|---|---|---|---|---|
| **(a)** | `localStorage` | ✅ | ✅ | ❌ | ❌ |
| **(b)** | **IndexedDB** (`mogo_evidence`) | ✅ **fully — no user action** | ✅ | ❌ | ❌ |
| **(c)** | **Completed file export** | 🟡 after one browser download grant | ✅ | ✅ | 🟡 only if backed up off-device |

**`localStorage` stops being the system of record.** It becomes a bounded buffer that flushes to
tier (b).

⚠️ **IndexedDB is chosen for quota, structure, and reportable failure — not for durability.** It is
destroyed together with `localStorage` when site data is cleared. **MOGO must never describe it as
a backup**, and the Diagnostics card and banner both state this limit in plain words.

**Why not a 32nd `localStorage` key:** the ~5 MB quota is shared across all keys and both
strategies; writes throw synchronously and were being swallowed; and there is no structured query.
IndexedDB is asynchronous (so failures are catchable and reportable), indexable, and effectively
unbounded for this workload. It requires no library.

### 2. Integrity is SHA-256, and the claim is scoped honestly

`contentHash` is SHA-256 (Web Crypto) over `mogo.evidence-canon.v1`, a canonical form defined
exactly: object keys sorted ascending by UTF-16 code unit (key order insignificant); **array order
preserved and significant** (a reordered decision chain is a different chain); `undefined` → explicit
`null`; non-finite numbers are a validation error; UTF-8; and the five integrity fields plus the
entire `export` block excluded, so marking a package exported can never change its hash.

**`alexGStableHash` is deliberately not used and is untouched.** It is a 64-bit FNV variant
producing 16 hex characters — fine for internal change detection, and not cryptographic. It remains
available for its existing `ruleSetHash`/`configurationHash` uses.

**The claim's limits are normative, not decorative.** `contentHash` detects **alteration**. It is
**not** authenticity, **not** identity verification, **not** a signature, and provides **no**
protection against an attacker who can modify a package and recompute its hash. A fixture asserts
that the corresponding vocabulary appears nowhere in the shipped layer.

**When Web Crypto is unavailable** (e.g. a `file://` origin, which is not a secure context) capture
still proceeds and the package is stored with `contentHash: null` and provenance `UNAVAILABLE`. It
**never** falls back to a weak digest — a weak hash in a field labelled SHA-256 would be a false
claim, which is worse than an honest absence. Such packages are counted and displayed separately and
are never reported as verified.

### 3. The evidence layer reads the ledger and never writes it

**This is ADR-003 restated as a boundary.** `alexGJournalEntries` is persisted only by
`saveAlexGAccountGuarded()` via `commitAlexGLedger()` — the atomic account+version+journal unit
established by the v11.0.1 / v12.3.2 corrections and the subject of INC-001.

**Nothing in the evidence layer writes, caps, evicts, reorders or rewrites the journal or ledger.**
Capture, backfill and import are all read-only with respect to trading state. Buffer caps apply only
to `fxhub_alexg_setups` (1,000) and `fxhub_alexg_zones` (200 per pair) — the two genuinely unbounded
stores. The journal is not the store that exhausts quota, so capping it would have added risk to the
one code path in MOGO that must stay boring, for no benefit.

### 4. Eviction can never outrun capture

**No tier-(a) record is evicted until its corresponding evidence is committed to tier (b), and no
tier-(b) package is ever automatically deleted.**

A setup or zone belonging to an open position, or to a closed trade whose package is not yet
committed, is skipped. **If tier (b) is unavailable at all, eviction does not run** — an over-full
buffer is recoverable; a deleted record is not.

### 5. Identity comes from persistent state

Package sequence numbers are allocated from an IndexedDB `meta` store, never process memory — an
in-memory counter would mint duplicate `packageId`s after every reload.

**Disclosed engineering limit:** allocation and the package write cannot share one transaction,
because the SHA-256 digest between them is asynchronous and an IndexedDB transaction auto-commits as
soon as the microtask queue drains with no pending request. Allocation is therefore its own
committed `readwrite` transaction, and the package is then inserted with `add()` (never `put()`). A
failed write burns a sequence number rather than reusing one — harmless for an identifier, and
strictly safer than the alternative.

---

## Consequences

**Accepted:**

- A second storage medium to reason about. Mitigated by keeping the async surface deliberately thin:
  every decision worth testing lives in a pure, synchronously-testable function.
- The SHA-256 digest and the IndexedDB layer cannot be covered by the offline JXA harness, which has
  neither `crypto.subtle` nor `indexedDB`. Both are browser-verified, and the split is disclosed in
  [TESTING.md](../TESTING.md) rather than glossed. This is the same offline/live split already
  documented for `alexGCloseLivePosition`.
- A burned sequence number on a failed write (above).

**Gained:**

- Evidence capture is automatic and requires no user action.
- No persistence path can fail silently — the defect that made silent loss the default is closed.
- Storage growth is bounded and measured.
- Existing history is adoptable read-only, without fabricating a single value.

**Rejected:**

- **File System Access API** — Chromium-only, needs re-permission per session, and would add a
  second export path to keep consistent with the marking and verification rules. Excluded from
  Phase 1 by ruling C3; `FS_ACCESS` remains a reserved, never-emitted enum value so a later phase can
  add it without a schema change.
- **Committing evidence packages to the repository** — packages may contain broker market data with
  its own licensing terms (MOGO-002 §12.1).
- **Claiming any browser-resident durability guarantee** — see the tier table.

---

## Relationship to existing ADRs

| ADR | Relationship |
|---|---|
| **ADR-002** (isolated strategy/feature storage) | **Extended, not overridden.** Its one-owner-per-key principle now applies across two media: each object store has exactly one owning writer, and no store is ever rebuilt from another's data. |
| **ADR-003** (paper ledger transaction model) | **Reinforced.** The evidence layer is a strict reader of the ledger; the guarded commit path is untouched. |
| **ADR-004** (read-only analytics principle) | **Consistent.** Evidence packages record captured facts; `realizedR` and other derived values stay computed at read time, never cached into the record. |

---

## Amendment A4 — encrypted operator-local backup, and why the packages stay out of Git

**Status: Accepted (operator ruling, 2026-08-28).** Supersedes the withdrawn amendment A3
proposal. Mechanism implemented and tested; **no backup has been created**.

### The rejection above stands, and now has a measured reason

The original "Rejected" list declined to commit evidence packages because they "may contain
broker market data with its own licensing terms". That is no longer a *may*:

| Measure | Value |
|---|---|
| Packages carrying a `marketContexts` entry | 221 of 268 |
| OANDA-derived OHLC bars embedded | **18,397** |
| Instruments | 11 |

**Operator ruling:** OANDA's current API licence limits use to **Internal Use** and prohibits
transmitting, publishing, disseminating or otherwise providing OANDA Trading System Rates to
third parties. Pushing these artifacts to GitHub would be exactly that. They are therefore
excluded from Git permanently, not pending a better mechanism.

A3 — force-adding the artifacts with `git add -f` — was implemented, tested, staged, and then
**withdrawn and fully unwound** under this ruling. Nothing OANDA-derived was ever committed.

### What Git keeps instead

`docs/trader-intelligence/evidence/ledger-preservation/ARTIFACT_INDEX.json`: per artifact, the
repository-relative path, whole-file SHA-256, byte size, package count and the list of package
`contentHash` values. Plus the hash algorithms and the canonicalization identifier.

**A SHA-256 is not rates.** It cannot reconstruct a candle, a price, or an instrument. So the
verification chain is public while the data is entirely operator-local — that split is the
whole design, and it is what makes the constraint survivable rather than merely obeyed.

The index is enforced clean by test, not by care: no floats at any depth (a price would be
one), no forbidden field names, no drive name, no path, no backup status, no per-artifact
timestamps. Mutating a byte size to a float, adding an `instrument` key, or leaking the volume
name each fail the suite.

### The backup mechanism

`scripts/backup_source_artifacts.sh`, three explicit modes — `--backup`, `--verify`,
`--restore` — each requiring an exact `--dest`, an explicit `--confirm`, a terminal on stdin,
and a typed `YES` at the prompt. It is interactive by construction: **the terminal requirement
is what prevents it running from a hook or a timer**, rather than a comment asking nobody to.

- **No plaintext archive is ever written.** The obvious design — tar, then encrypt — writes a
  complete unencrypted copy of every candle to disk first. This creates an *empty* AES-256
  encrypted image with `hdiutil`, attaches it, and copies the literal paths in. Plaintext
  exists only inside the attached encrypted volume, which is unavoidable for any encryption.
- **The passphrase reaches `hdiutil` on stdin via `-stdinpass` and goes nowhere else.** Never
  argv (`ps` would show it to every process on the machine — `--password` is refused with that
  explanation), never an environment variable, never a file, never a receipt, never shell
  history, and **never the Keychain**. Losing it loses the archive; that is the trade.
- Built-in macOS tooling only. `age` and `gpg` are not installed and nothing was installed.
- Fails closed on any hash, space, destination, canonicalization, mount or receipt failure.
- Refuses Time Machine's managed directories, the volume root, symlinks, globs, `..`,
  relative paths, read-only volumes and unmounted volumes.
- Removes a **partial** image left by a failure; never deletes a **completed** backup.
- Makes no network call and never invokes git.

### MOGOTH improves resilience. It is not an independent offline copy.

The connected volume is a **Seagate BUP Slim BK, 2 TB, USB, APFS, FileVault-encrypted**,
mounted at `/Volumes/MOGOTH` — and it is **also the configured Time Machine destination**.

That means the encrypted archive would share **one physical device** with the system backup.
One drive failure loses both. It is also a portable hard disk rather than an SSD, and it lives
attached to the machine, so it protects against accidental deletion and repository loss but not
against theft, fire, or a controller failure. The script prints this warning on every run
against a Time Machine volume rather than leaving it in a document nobody re-reads.

**Recommended next step, not yet authorised:** a *second* encrypted device, written by the same
tool with the same verification, then **physically disconnected and stored separately**. Only
at that point is the source evidence genuinely durable. Until then, the honest description is
"a second copy on the same desk", and it should be described that way.

### Known provenance debt — recorded, not repaired

Two items are deliberately left alone.

1. **The 2026-08-18 dangling declaration.** `EVSRC|MOGO|20260818|015` declares
   `repositoryPath: "evidence/FWD-20260818T153216Z-PACKAGES.json"`, and that file does not
   exist. Its exact bytes survive as `evidence/FWD-20260818T153243Z-PACKAGES.json`, a
   **verified byte-identical duplicate** (both 5,619 B, both SHA-256 `f31505ff876a4c40…`, the
   value the record already declares). A restoration was made under A3 and **removed again**
   during the unwind, because restoring it duplicates a package across two capture files and
   breaks the corpus invariant that a package appears in exactly one — enforced by
   `test_content_hash_is_unique_across_every_package`, which failed with it present and passes
   with it absent. The invariant was **not** weakened to accommodate the restoration. The
   artifact is consequently absent from `ARTIFACT_INDEX.json`, which lists 17, not 18.
   `TOBS|MOGO|20260818|001` therefore rests on a witness reachable only by contentHash search,
   and `EVF0002` continues to report it. That is the honest state.

2. **The 48 `storageLocationType: "repository"` declarations are now known to be wrong.** Under
   this ruling the artifacts will never be in version control, so `external` is the truthful
   value. **They are not edited.** `SPEC-provenance.md` **P11** governs — *"Records are
   immutable; corrections supersede rather than edit"* — and `evidence-source.schema.json` has
   `additionalProperties: false` with no `supersedes*` property, so the correction cannot
   currently be expressed. Three routes remain open, in increasing cost: record the debt and
   report it as an advisory validator finding; add a `supersededBySourceId` property and mint
   replacement records; or append a `corrected` lifecycle event per source, which the lifecycle
   schema already supports. None is taken here.
