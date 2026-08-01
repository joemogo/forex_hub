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
