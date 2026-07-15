# ADR-002: Isolated strategy and feature storage

## Status

Accepted (established v3.4 for ALEX; reinforced by every subsequent feature — v6.0/v6.1 charts,
v8.0 Academy, v9.0–v11.0.1 paper-ledger work).

## Context

MOGO runs two independent trading strategies (JVM and ALEX) and several non-trading feature
areas (charting/drawings, the Training Academy, the AI Assistant) on top of one shared,
single-file application with no module system and one global JS scope. Without a firm rule,
it would be easy — and in a shared-scope codebase, easy to do *accidentally* — for one area's
code to read or write another area's state, especially under time pressure to "just reuse the
existing account object."

## Decision

Every strategy and every non-trading feature area gets:

1. Its own dedicated in-memory variable(s) (e.g. `paperAccount` vs. `alexGAccount`;
   `academyProgress`; `chartDrawings`).
2. Its own dedicated `localStorage` key(s) — never merged into another area's key. See
   [STORAGE_KEYS.md](../STORAGE_KEYS.md) for the current, complete list.
3. Its own save/load functions where warranted (ALEX has `saveAlexG()`/`loadAlexGSaved()`,
   fully separate from the JVM-side `save()`/`loadSaved()`).
4. A dedicated function-name namespace where it reduces ambiguity (`alexG*` for every ALEX
   function).

No function outside a given area's own namespace is permitted to read or write that area's state.
This is verified mechanically: every release that touches either strategy, or a feature area like
the Academy, includes a fixture asserting the other areas' state is byte-identical before and
after.

## Rationale

- **Blast radius containment.** A bug in ALEX's zone-detection engine cannot corrupt JVM's paper
  account, and vice versa — the two simply cannot touch each other's data, by construction, not
  by convention alone.
- **Independent evolution.** JVM and ALEX (and the Academy, and charting) can each gain new
  fields, functions, or entire subsystems without any risk of an unrelated area's fixtures
  breaking, because there is no shared mutable state to break.
- **Auditability.** A reviewer (human or the regression-baseline tool) can reason about one
  area's storage/state in complete isolation, without having to trace whether some other feature
  might also be touching the same key.
- Given the single-global-scope constraint (see [ARCHITECTURE.md](../ARCHITECTURE.md)), naming
  and storage-key isolation are the only enforcement mechanisms available — there's no module
  boundary to lean on instead.

## Consequences

- Some genuine duplication exists (e.g. `save()`/`loadSaved()` and `saveAlexG()`/
  `loadAlexGSaved()` are structurally similar but intentionally separate functions). This is
  accepted as the cost of the isolation guarantee, not treated as duplication to "clean up" by
  merging.
- Any new strategy or major feature area added in the future should follow this same pattern from
  the start: its own variable(s), its own storage key(s), its own save/load path, and an
  isolation fixture proving it doesn't leak into existing state.
- See [CODING_STANDARDS.md](../CODING_STANDARDS.md) rule 3 and
  [STORAGE_KEYS.md](../STORAGE_KEYS.md) rule 1 for the enforced version of this decision.
