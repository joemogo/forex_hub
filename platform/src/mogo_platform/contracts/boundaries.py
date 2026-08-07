#!/usr/bin/env python3
"""MOGO Automation Platform -- Step 1 protected-boundary declarations.

AUTHORITY
    Automation Platform Constitution v1.0 (senior)  -- sections 4.21, 4.22, 16
    ADR-012 (accepted 2026-08-07)
    MOGO-009 Architecture, section 7   -- prohibited cross-context writes
    MOGO-009 Architecture, section 25  -- protected-boundary test
    MOGO-009 Contract Catalog, section H -- reuse verdict

THIS IS THE ONE DECLARATION MODULE
    This module is REQUIRED to contain the prohibited path, symbol and import
    literals, because it is the machine-readable declaration of the boundary.
    Every other platform module is forbidden from containing them.

    The boundary test enforces exactly that distinction:
      * this module must declare the complete approved set, with nothing
        omitted and nothing invented; and
      * no other platform module may contain those literals at all.

    A blind text scan that rejected this module for declaring the values it is
    required to declare would be a defective test, not an enforcement.

IMPLEMENTED NOW
    * The declarations themselves, as read-only data.
    * A pure reference detector used by the command and event validators, so
      the prohibited-reference rule has exactly one implementation.

EXPLICITLY DEFERRED -- absent from Step 1 entirely
    * Filesystem enforcement. Step 1 performs no I/O whatsoever, so there is
      no write to intercept. The static test is the enforcement.
    * Read-reference support. Architecture section 7 marks the hypothesis
      registry read-only, but a command or event envelope carries no read/write
      distinction, so Step 1 treats ANY reference to a declared path as
      prohibited -- the fail-closed reading. A later step that genuinely needs
      a governed read reference must introduce that form explicitly under
      governance rather than by relaxing this rule.
"""

from types import MappingProxyType

# ---------------------------------------------------------------------------
# MOGO-009 Architecture section 7 -- prohibited write targets (6)
# ---------------------------------------------------------------------------
# `declared` is the target exactly as the architecture writes it.
# `matchTokens` are the substrings that indicate a reference to that target in
# a string value. They exist because one declared target is a glob.


def _target(declared, match_tokens, note):
    return MappingProxyType({
        "declared": declared,
        "matchTokens": tuple(match_tokens),
        "note": note,
    })


PROHIBITED_WRITE_PATHS = (
    _target("evidence/", ("evidence/",),
            "Campaign C1 artifacts; frozen"),
    _target("docs/campaigns/", ("docs/campaigns/",),
            "campaign identity, manifest, certificate, adjudication; frozen"),
    _target("docs/trader-intelligence/governance/PREREG-*.md",
            ("docs/trader-intelligence/governance/PREREG-", "PREREG-"),
            "pre-registrations; immutable by their own section 10"),
    _target("docs/MOGO-003-VERIFIED-REPLAY-RECORD.md",
            ("MOGO-003-VERIFIED-REPLAY-RECORD.md",),
            "append-only verified replay register"),
    _target("index.html", ("index.html",),
            "protected trading engine; 63 protected functions, 4 constants"),
    _target("hypothesis-registry.json", ("hypothesis-registry.json",),
            "read-only; updates stay operator-driven"),
)

PROHIBITED_WRITE_PATH_DECLARATIONS = tuple(
    entry["declared"] for entry in PROHIBITED_WRITE_PATHS
)

# ---------------------------------------------------------------------------
# Contract Catalog section H -- reuse verdict: NOT reused (4)
# ---------------------------------------------------------------------------
# Importing any of these would couple automation to trading or to frozen
# scientific records, which is the coupling the charter prohibits. The first
# two are scientific schema/canonicalization identifiers; the last two are
# browser-only, trading-specific mechanisms.

PROHIBITED_SCIENTIFIC_SYMBOLS = (
    "mogo.evidence-canon.v1",
    "mogo.evidence-package.v1",
    "alexGStableHash",
    "sourceTradeId",
)

# ---------------------------------------------------------------------------
# Prohibited source trees -- MOGO-009 Architecture section 6.7
# ---------------------------------------------------------------------------
# The Phase I pipeline is reachable only through adapters, and no adapter
# exists in Step 1. Platform modules must therefore import nothing from it.

PROHIBITED_SOURCE_TREES = (
    "scripts/trader_intelligence",
)

# ---------------------------------------------------------------------------
# Banned runtime imports
# ---------------------------------------------------------------------------
# Network capability first: this list follows the proven precedent already
# enforced for the acquisition scripts (TestNoNetworkImports). Subprocess and
# dynamic-import machinery are added because Step 1 must expose no executable
# automation path of any kind.

BANNED_NETWORK_IMPORTS = (
    "urllib.request",
    "urllib.error",
    "http.client",
    "requests",
    "socket",
    "ssl",
    "yt_dlp",
    "ftplib",
    "smtplib",
    "telnetlib",
    "xmlrpc.client",
    "asyncio",
)

BANNED_EXECUTION_IMPORTS = (
    "subprocess",
    "multiprocessing",
    "ctypes",
    "importlib",
    "runpy",
    "pickle",
    "shelve",
)

BANNED_RUNTIME_IMPORTS = BANNED_NETWORK_IMPORTS + BANNED_EXECUTION_IMPORTS

# ---------------------------------------------------------------------------
# Banned mutation call names (matched on the called attribute or name)
# ---------------------------------------------------------------------------

BANNED_MUTATION_CALLS = (
    "remove", "unlink", "rename", "replace", "rmtree", "move",
    "mkdir", "makedirs", "rmdir", "removedirs",
    "write_text", "write_bytes", "truncate", "chmod", "chown",
    "copy", "copy2", "copyfile", "copytree",
)

# Dangerous BUILTINS, matched only when called as a bare name. `compile` is
# listed here and not among the attribute calls on purpose: the builtin
# compiles source code, whereas `re.compile` merely builds a pattern object.
# Matching on the bare name keeps the check precise instead of forcing the
# rule to be weakened later to accommodate a false positive.
BANNED_BUILTIN_CALLS = (
    "eval", "exec", "compile", "__import__", "globals", "locals", "setattr",
    "delattr",
)

# Dangerous process/execution calls, matched as attributes (for example
# os.system, os.popen, subprocess.Popen).
BANNED_EXECUTION_CALLS = (
    "system", "popen", "Popen", "execv", "execve", "execl", "spawnv",
    "spawnl", "fork", "check_output", "check_call",
)

# Modes that make an `open()` call write-capable.
WRITE_MODE_CHARACTERS = ("w", "a", "x", "+")

# The single module permitted to contain the literals declared above.
DECLARATION_MODULE_BASENAME = "boundaries.py"


# ---------------------------------------------------------------------------
# Reference detection -- one implementation, used by every validator
# ---------------------------------------------------------------------------


def prohibited_reference_reason(value):
    """Return why `value` is a prohibited reference, or None if it is not.

    `value` is inspected only when it is a string. Detection is substring
    based and deliberately generous: over-rejection fails closed, which is the
    behaviour the Constitution requires where a boundary is at stake.
    """
    if not isinstance(value, str):
        return None
    for entry in PROHIBITED_WRITE_PATHS:
        for token in entry["matchTokens"]:
            if token in value:
                return "references prohibited path %s" % (entry["declared"],)
    for symbol in PROHIBITED_SCIENTIFIC_SYMBOLS:
        if symbol in value:
            return "references prohibited scientific symbol %s" % (symbol,)
    return None


def find_prohibited_references(obj, path="$"):
    """Walk a JSON-shaped value and collect every prohibited reference.

    Returns a list of (json_path, value, reason) triples -- empty when clean.
    Mapping keys are inspected as well as values, so a prohibited target
    cannot be smuggled in as a key.
    """
    found = []
    if isinstance(obj, str):
        reason = prohibited_reference_reason(obj)
        if reason is not None:
            found.append((path, obj, reason))
        return found
    if isinstance(obj, (list, tuple)):
        for index, item in enumerate(obj):
            found.extend(find_prohibited_references(item, "%s[%d]" % (path, index)))
        return found
    if hasattr(obj, "keys"):
        for key in obj.keys():
            child = "%s.%s" % (path, key)
            reason = prohibited_reference_reason(key)
            if reason is not None:
                found.append((child + " (key)", key, reason))
            found.extend(find_prohibited_references(obj[key], child))
        return found
    return found
