"""MOGO Automation Platform -- uniquely named package root.

AUTHORITY
    Automation Platform Constitution v1.0 (senior)
    ADR-012 (accepted 2026-08-07) -- approval 2, new top-level platform/
                                     bounded context
    MOGO-009 Architecture, sections 7 and 25 -- the platform/** boundary

WHY THIS NAME
    The bounded context directory is `platform/`, which collides with the
    Python standard-library module of the same name. A package marker at the
    repository-root `platform/` would shadow and BREAK stdlib `platform`
    process-wide. This package therefore lives at `platform/src/mogo_platform/`
    and carries a name that is not a standard-library name, verified against
    `sys.stdlib_module_names` rather than a hand-maintained list.

    `platform/__init__.py` MUST NEVER BE CREATED. That single file -- and only
    that file -- causes the collision. Nested markers such as this one cannot,
    because they are reached through a different sys.path entry and carry a
    different top-level name.

DELIBERATELY EMPTY OF CODE
    This module contains a docstring and nothing else: no import, no
    re-export, no registration, no side effect. Importing it does nothing
    observable. A re-export would create an import-time side effect and a
    second name for every symbol, both of which work against the MOGO-010
    Step 1 property that the platform is not executable.
"""
