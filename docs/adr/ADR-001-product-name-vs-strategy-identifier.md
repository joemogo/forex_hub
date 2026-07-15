# ADR-001: Product name vs. strategy identifier

## Status

Accepted (established v7.0, still in force as of v11.0.1).

## Context

The application's original display name was "JVM Forex Hub" (also seen as "Forex Trading Hub").
Its original — and still only — built-in trading strategy has always been internally identified
as `JVM` throughout the codebase: `strategyLabel:'JVM'` on every journal record, the Journal
tab's strategy filter, and a large family of function names (`journalNoteOpenJVM`,
`buildJVMJournalOpenRecord`, `computeJVMExplanations`, etc.).

In v7.0, the product itself was rebranded to **MOGO**. This raised a real question: should the
`JVM` identifier be renamed too, to avoid confusion with the old product name?

## Decision

Rebrand the product's **display text only** — `<title>`, the nav wordmark, notification titles,
the Trade Inspector header, and the AI Assistant's self-description — to MOGO. **Do not** rename
`JVM` anywhere it functions as a stored value or code identifier: `strategyLabel:'JVM'`, the
Journal filter's `value="JVM"`, or any `*JVM`-suffixed/prefixed function name.

## Rationale

- `JVM` on an already-persisted journal record is stored data, not a display label. Renaming the
  identifier would either break every existing user's stored history, or require a migration
  layer solely to rename a string with no functional benefit.
- The rebrand's actual purpose (present a cohesive MOGO product identity) does not require the
  *internal* strategy identifier to match the product name — a product can be named differently
  from an internal component identifier it happens to contain, and often is.
- Keeping `JVM` as a stable internal identifier, separate from the product name, means future
  code changes never have to reason about "is this JVM the strategy or JVM the old product name"
  — there is exactly one meaning for the string going forward.

## Consequences

- **MOGO** is the product name — used in all user-facing branding.
- **JVM** is the internal identifier for the app's original ("current") strategy — used in stored
  data and code, never in product branding going forward.
- **ALEX** (`alex_g_sr_v1` internally) is the second, independently-specified strategy — see
  [ADR-002](ADR-002-isolated-strategy-and-feature-storage.md) for how it's kept isolated from
  JVM.
- Any future documentation, UI copy, or code comment should follow this same distinction rather
  than using "JVM" and "MOGO" interchangeably. See
  [PRODUCT_VISION.md](../PRODUCT_VISION.md#naming-mogo-vs-jvm-vs-alex).
