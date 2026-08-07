"""MOGO Automation Platform -- Step 1 contract definitions.

AUTHORITY
    Automation Platform Constitution v1.0 (senior)
    ADR-012 (accepted 2026-08-07)
    MOGO-009 Contract Catalog, sections A, B, H, I, J, K, L, M, O
    MOGO-009 Architecture, sections 7, 10, 11, 17, 18.1, 25

CONTENTS -- contract definitions only, nothing executable
    ids           identifier model, canonicalization, idempotency keys, and
                  the JSON-shape validator every envelope passes through
    errors        exception hierarchy, canonical raisers, inert error classes
    vocabulary    closed command / event / licensing / lifecycle vocabularies
    command       command envelope contract (Catalog section A)
    event         operational event envelope contract (Catalog section B)
    task_states   task states and transition legality (Catalog section L)
    boundaries    protected-boundary declarations (Architecture section 7)

DELIBERATELY EMPTY OF CODE
    Docstring only: no import, no re-export, no registration, no side effect.
    Importing this package does nothing observable. Callers import the modules
    they need explicitly, for example:

        from mogo_platform.contracts import ids, event

    so that no symbol acquires a second name and no module is loaded merely
    because a sibling was.
"""
