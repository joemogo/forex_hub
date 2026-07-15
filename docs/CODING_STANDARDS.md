# Coding Standards

These are the conventions this codebase is actually held to, based on how every release to date
has been built and verified. Some are hard rules (violating them should block a release); others
are strong conventions. Both are documented here so they survive beyond any one contributor's
memory of "how we do things."

## Hard rules

### 1. Trading methodology is frozen

Both JVM's and ALEX's entry/stop/target/direction/qualification/exit logic must never be altered
in place. The 63 functions and 4 constants in `PROTECTED_FUNCTIONS`/`PROTECTED_CONSTANTS`
(`regression-baseline-tools.py`) define exactly what this covers. A release may only **extend**
this logic via new, clearly-disclosed, additive fields or functions — never by changing what an
existing function computes for a given input.

If a change requires touching a protected function's actual math, that is a **methodology
change**, not a routine release, and must be called out and confirmed explicitly before
proceeding — it is never bundled silently into a reliability/UI/performance release. (Adding
logging, a version guard, or a snapshot/rollback wrapper *around* unchanged math is not a
methodology change, but must still be disclosed as a protected-function diff — see
[TESTING.md](TESTING.md).)

### 2. `index-v2.9-KNOWN-GOOD.html` is never modified

This file is a frozen, byte-for-byte integrity reference. Its SHA-1 hash is checked by
`regression-baseline-tools.py` on every run. Never edit, rename, or delete it.

### 3. JVM and ALEX never read or write each other's state

No function outside the `alexG*` namespace reads or writes `alexGAccount`,
`alexGJournalEntries`, `alexGZoneState`, `alexGSetupState`, or their storage keys, and vice
versa. Every release that touches either strategy includes a fixture proving the other strategy's
state is byte-identical before and after. See [ARCHITECTURE.md](ARCHITECTURE.md).

### 4. Never fabricate data

If a value can't be honestly computed from real, stored data, show an honest "Not Evaluated" /
empty-state / "insufficient sample" message — never a placeholder number, a guessed timestamp, or
an invented event. This applies to journal fields, compliance checks, statistics, and chart
overlays alike. See [ADR-004](adr/ADR-004-read-only-analytics-principle.md).

### 5. Paper-account persistence goes through `commitPaperLedger()` only

General `save()` must never write `paperAccount`/`fxhub_paper`/`fxhub_paper_version`. Any new
code that mutates `paperAccount` must snapshot before mutating and roll back on a rejected
commit. See [ARCHITECTURE.md](ARCHITECTURE.md#the-paper-ledger-transaction-model-v1101) and
[ADR-003](adr/ADR-003-paper-ledger-transaction-model.md).

### 6. Escape all dynamically-inserted text

Anything derived from an API response, user input, or stored free text that gets inserted via
`innerHTML` must go through `escapeHtml()`. A real stored-XSS defect from skipping this was found
and fixed in v2.6 — don't reintroduce it.

### 7. Browser testing must never contaminate production paper-trading data

Prefer, in order: unit fixtures, regression fixtures, mock data, temporary in-memory state, and
only then a real paper trade — and only when explicitly authorized. Any real paper trade created
during testing must be tagged Developer Test, excluded from analytics/performance statistics, and
removable through Diagnostics. The default assumption is that verification leaves the user's
paper-trading history unchanged. See the full Browser Testing Policy in
[TESTING.md](TESTING.md#browser-testing-policy) and [INCIDENTS.md](INCIDENTS.md#inc-001) for why
this is a hard rule, not a preference.

## Strong conventions

- **Additive over invasive.** Prefer adding a new field, function, or isolated store over
  modifying an existing one's shape or behavior, especially near trading state. Several releases
  (v9.0's `paperResetHistory`, v10.0's `tradeNotes`, v11.0's `paperReconciliationAudit`) added an
  entirely new, isolated store rather than extending an existing one, specifically to avoid any
  risk to already-working code.
- **One concern, one storage key.** See [STORAGE_KEYS.md](STORAGE_KEYS.md).
- **Read-side projections don't own data.** `getUnifiedJournalRecords()` and
  `classifyJvmJournalRecord()` are examples of pure, read-only functions that compute a view over
  existing stores — they never persist anything themselves and are safe to call as often as
  needed.
- **Every release gets a fixture suite.** New behavior ships with new fixtures proving it, named
  by version, plus a full run of every prior suite. See [TESTING.md](TESTING.md).
- **Disclose what you touched, not just what you added.** Every release's changelog entry
  (`APP_VERSION_LOG` in-code, summarized in [RELEASE_NOTES.md](RELEASE_NOTES.md)) explicitly
  lists every existing function it touched, even a one-line change, and states plainly when zero
  trading-logic functions were touched.
- **A rejected/blocked action is a visible failure, not a silent no-op.** See
  [UI_GUIDELINES.md](UI_GUIDELINES.md#blockingerror-banners).
- **Root-cause before patching.** When investigating a defect, reproduce the actual mechanism
  (live, through the real code path) before writing a fix — see
  [INCIDENTS.md](INCIDENTS.md) for why this mattered concretely (a first fix addressed a real but
  incomplete cause; a second release found and corrected the more precise one).

## Documentation obligations

Every release that changes behavior must update:

- `RELEASE_NOTES.md` (a new summarized entry)
- `TESTING.md` (if fixture counts or the testing process changed)
- `KNOWN_ISSUES.md` (if a limitation was closed or a new one introduced)
- Any ADR or `ARCHITECTURE.md` section the change actually affects

The in-code `APP_VERSION_LOG` remains the verbatim, unabridged source of record for every release
and is never rewritten by documentation work — see [README.md](../README.md).
