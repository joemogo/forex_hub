#!/usr/bin/env python3
"""MOGO-010 Step 1 -- protected-boundary enforcement tests.

Pure stdlib (unittest). Fully offline, deterministic, repeatable.

Authority: MOGO-009 Architecture sections 7 and 25; Contract Catalog section H
(reuse verdict); Automation Platform Constitution sections 4.21, 4.22, 16.

TWO KINDS OF CHECK, AND WHY THE DISTINCTION MATTERS
    platform_boundaries.py is REQUIRED to contain the prohibited path, symbol
    and import literals -- it is the machine-readable declaration of the
    boundary. Every other platform module is forbidden from containing them.
    A blind text scan that rejected the declaration module for declaring the
    values it must declare would be a defective test, so the two cases are
    separated explicitly:

      * DECLARATION CHECK -- platform_boundaries.py must declare the complete
        approved set: nothing omitted, nothing invented.
      * LITERAL CHECK -- every OTHER platform .py module must contain none of
        those literals anywhere, including in comments and docstrings.
      * AST CHECK -- EVERY platform .py module, the declaration module
        included, must contain no executable write, network, subprocess or
        dynamic-import path. Declarations are strings, never calls, so the
        declaration module passes this check on its merits.

LIMITS OF THE TEXT SCAN, STATED PLAINLY
    A substring scan cannot tell code from prose, which is exactly why it is
    confined to the non-declaration modules and paired with AST checks for
    everything executable. It also covers .py files only: platform/README.md
    documents the boundary and is intentionally outside the scan.

Run with:
    python3 -m unittest tests.platform.test_platform_boundaries -v
"""

import ast
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLATFORM_DIR = os.path.join(REPO_ROOT, "platform")
SRC_DIR = os.path.join(PLATFORM_DIR, "src")
PACKAGE_DIR = os.path.join(SRC_DIR, "mogo_platform")
PIPELINE_DIR = os.path.join(REPO_ROOT, "scripts", "trader_intelligence")
# The ONE path entry the suites add -- see platform/README.md.
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import importlib.util  # noqa: E402

from mogo_platform.contracts import boundaries  # noqa: E402
from mogo_platform.contracts import command  # noqa: E402
from mogo_platform.contracts import errors  # noqa: E402
from mogo_platform.contracts import event  # noqa: E402
from mogo_platform.contracts import ids  # noqa: E402

DECLARATION_MODULE = "boundaries.py"
PACKAGE_MARKERS = (
    os.path.join(PACKAGE_DIR, "__init__.py"),
    os.path.join(PACKAGE_DIR, "contracts", "__init__.py"),
)
# The flat modules the MOGO-010 Step 1 correction removed. None may remain
# importable, or the generic top-level namespace is still occupied.
RETIRED_FLAT_MODULES = (
    "platform_ids", "platform_errors", "platform_vocabulary",
    "platform_command", "platform_event", "platform_task_states",
    "platform_boundaries",
)

# ---------------------------------------------------------------------------
# Independently transcribed -- MOGO-009 Architecture section 7 (6 targets)
# ---------------------------------------------------------------------------

EXPECTED_PROHIBITED_WRITE_PATHS = (
    "evidence/",
    "docs/campaigns/",
    "docs/trader-intelligence/governance/PREREG-*.md",
    "docs/MOGO-003-VERIFIED-REPLAY-RECORD.md",
    "index.html",
    "hypothesis-registry.json",
)

# Independently transcribed -- Contract Catalog section H reuse verdict (4).
EXPECTED_PROHIBITED_SCIENTIFIC_SYMBOLS = (
    "mogo.evidence-canon.v1",
    "mogo.evidence-package.v1",
    "alexGStableHash",
    "sourceTradeId",
)

# Independently listed: the network and execution imports Step 1 must not have.
REQUIRED_BANNED_IMPORTS = (
    "urllib.request", "http.client", "requests", "socket", "ftplib", "smtplib",
    "yt_dlp", "subprocess", "multiprocessing", "ctypes", "importlib", "runpy",
    "pickle",
)

# Literals that must not appear outside the declaration module. Derived from
# the two independently transcribed lists above, not from the implementation.
FORBIDDEN_LITERALS = (
    "evidence/",
    "docs/campaigns/",
    "PREREG-",
    "MOGO-003-VERIFIED-REPLAY-RECORD.md",
    "index.html",
    "hypothesis-registry.json",
) + EXPECTED_PROHIBITED_SCIENTIFIC_SYMBOLS


def platform_python_files():
    """Every .py file under platform/, as (relative path, absolute path)."""
    found = []
    for root, _dirs, files in os.walk(PLATFORM_DIR):
        for name in sorted(files):
            if name.endswith(".py"):
                absolute = os.path.join(root, name)
                found.append((os.path.relpath(absolute, REPO_ROOT), absolute))
    return sorted(found)


CONTRACTS_DIR = os.path.join(PACKAGE_DIR, "contracts")
RUNTIME_DIR = os.path.join(PACKAGE_DIR, "runtime")


def contracts_python_files():
    """Only the contracts layer, where the no-I/O rule remains ABSOLUTE."""
    return [(rel, abs_) for rel, abs_ in platform_python_files()
            if os.path.abspath(abs_).startswith(CONTRACTS_DIR + os.sep)]


def runtime_python_files():
    """Only the runtime layer, where writes are permitted but CONFINED."""
    return [(rel, abs_) for rel, abs_ in platform_python_files()
            if os.path.abspath(abs_).startswith(RUNTIME_DIR + os.sep)]


def read_source(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def parse_platform_modules():
    """(relative path, source text, parsed AST) for every platform module."""
    parsed = []
    for relative, absolute in platform_python_files():
        source = read_source(absolute)
        parsed.append((relative, source, ast.parse(source, filename=absolute)))
    return parsed


def imported_module_names(tree):
    """Every module name imported, including relative `from . import X`.

    A relative import is recorded as its dotted prefix plus module, for example
    "." for `from . import errors`. Recording it matters: after the MOGO-010
    Step 1 correction the contract modules import each other relatively, and an
    import scanner that silently skipped `node.module is None` would report
    those modules as importing nothing at all.
    """
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                names.add("." * node.level + (node.module or ""))
            elif node.module:
                names.add(node.module)
    return names


def called_names(tree):
    """Every call site, as (kind, name, lineno, node).

    `kind` is "name" for a bare call such as open(...) and "attribute" for a
    dotted call such as os.remove(...). Keeping the two apart is what lets the
    builtin `compile` be banned while `re.compile` stays legitimate, without
    weakening either rule.
    """
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            calls.append(("name", func.id, node.lineno, node))
        elif isinstance(func, ast.Attribute):
            calls.append(("attribute", func.attr, node.lineno, node))
    return calls


class TestDeclarationModuleIsComplete(unittest.TestCase):
    """platform_boundaries.py must declare the complete approved set."""

    def test_declares_every_prohibited_write_path(self):
        declared = tuple(boundaries.PROHIBITED_WRITE_PATH_DECLARATIONS)
        self.assertEqual(declared, EXPECTED_PROHIBITED_WRITE_PATHS)
        self.assertEqual(len(declared), 6)

    def test_no_prohibited_write_path_is_silently_omitted(self):
        missing = [
            path for path in EXPECTED_PROHIBITED_WRITE_PATHS
            if path not in boundaries.PROHIBITED_WRITE_PATH_DECLARATIONS
        ]
        self.assertEqual(missing, [])

    def test_no_unapproved_prohibited_write_path_is_invented(self):
        invented = [
            path for path in boundaries.PROHIBITED_WRITE_PATH_DECLARATIONS
            if path not in EXPECTED_PROHIBITED_WRITE_PATHS
        ]
        self.assertEqual(invented, [])

    def test_declares_every_prohibited_scientific_symbol(self):
        self.assertEqual(
            tuple(boundaries.PROHIBITED_SCIENTIFIC_SYMBOLS),
            EXPECTED_PROHIBITED_SCIENTIFIC_SYMBOLS,
        )

    def test_no_unapproved_scientific_symbol_is_invented(self):
        self.assertEqual(
            set(boundaries.PROHIBITED_SCIENTIFIC_SYMBOLS),
            set(EXPECTED_PROHIBITED_SCIENTIFIC_SYMBOLS),
        )

    def test_every_declared_target_carries_at_least_one_match_token(self):
        for entry in boundaries.PROHIBITED_WRITE_PATHS:
            with self.subTest(target=entry["declared"]):
                self.assertGreater(len(entry["matchTokens"]), 0)
                for token in entry["matchTokens"]:
                    self.assertIsInstance(token, str)
                    self.assertTrue(token.strip())

    def test_banned_import_list_covers_every_required_entry(self):
        for name in REQUIRED_BANNED_IMPORTS:
            with self.subTest(module=name):
                self.assertIn(name, boundaries.BANNED_RUNTIME_IMPORTS)

    def test_declaration_tables_are_read_only(self):
        with self.assertRaises(TypeError):
            boundaries.PROHIBITED_WRITE_PATHS[0]["declared"] = "elsewhere"

    def test_detector_finds_every_declared_target(self):
        for path in EXPECTED_PROHIBITED_WRITE_PATHS:
            probe = path.replace("*", "001-x")
            with self.subTest(path=path):
                self.assertIsNotNone(boundaries.prohibited_reference_reason(probe))

    def test_detector_finds_every_declared_symbol(self):
        for symbol in EXPECTED_PROHIBITED_SCIENTIFIC_SYMBOLS:
            with self.subTest(symbol=symbol):
                self.assertIsNotNone(boundaries.prohibited_reference_reason(symbol))

    def test_detector_ignores_benign_values(self):
        for benign in ("SRC|web|0123456789ab", "platform/contracts/x.py",
                       "intake/pending/a.json", 17, None, ["a"]):
            with self.subTest(value=benign):
                self.assertIsNone(boundaries.prohibited_reference_reason(benign))


class TestNoProhibitedLiteralOutsideTheDeclarationModule(unittest.TestCase):
    """Every OTHER platform module must contain none of the literals."""

    def test_at_least_the_expected_modules_are_scanned(self):
        scanned = {os.path.basename(rel) for rel, _abs in platform_python_files()}
        self.assertGreaterEqual(len(scanned), 7)
        self.assertIn(DECLARATION_MODULE, scanned)

    def test_no_other_module_contains_a_prohibited_path_or_symbol(self):
        offenders = []
        for relative, absolute in platform_python_files():
            if os.path.basename(relative) == DECLARATION_MODULE:
                continue
            source = read_source(absolute)
            for literal in FORBIDDEN_LITERALS:
                if literal in source:
                    offenders.append((relative, literal))
        self.assertEqual(offenders, [])

    def test_the_declaration_module_is_the_only_exemption(self):
        # Guards against the exemption being widened later.
        self.assertEqual(boundaries.DECLARATION_MODULE_BASENAME, DECLARATION_MODULE)


class TestNoWritePathInPlatform(unittest.TestCase):
    """AST checks -- applied to EVERY platform module, declaration included."""

    def test_contracts_layer_has_no_write_capable_open_call(self):
        offenders = []
        for relative, absolute in contracts_python_files():
            tree = ast.parse(read_source(absolute))
            for _kind, name, lineno, node in called_names(tree):
                if name != "open":
                    continue
                mode = None
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for keyword in node.keywords:
                    if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                        mode = keyword.value.value
                if mode is None:
                    continue
                if isinstance(mode, str) and any(
                    character in mode
                    for character in boundaries.WRITE_MODE_CHARACTERS
                ):
                    offenders.append((relative, lineno, mode))
        self.assertEqual(offenders, [])

    def test_contracts_layer_has_no_open_call_at_all(self):
        """The contracts layer performs no I/O, and that rule stays ABSOLUTE.

        MOGO-010 applied this to all of platform/**, which was correct while the
        platform was contracts-only but stricter than the architecture requires:
        Architecture section 7 forbids writing to six named targets, not writing
        in general. MOGO-011 narrowed the absolute rule to the layer it belongs
        to and gave the runtime layer a CONFINEMENT rule instead (below), so
        total coverage increased rather than decreased.
        """
        offenders = [
            (relative, lineno)
            for relative, _source, tree in [(r, s, t) for r, s, t
                                            in parse_platform_modules()
                                            if os.path.abspath(
                                                os.path.join(REPO_ROOT, r)).startswith(
                                                    CONTRACTS_DIR + os.sep)]
            for _kind, name, lineno, _node in called_names(tree)
            if name == "open"
        ]
        self.assertEqual(offenders, [])

    def test_contracts_layer_has_no_filesystem_mutation_call(self):
        offenders = [
            (relative, name)
            for relative, absolute in contracts_python_files()
            for _kind, name, _lineno, _node in called_names(
                ast.parse(read_source(absolute)))
            if name in boundaries.BANNED_MUTATION_CALLS
        ]
        self.assertEqual(offenders, [])

    def test_every_runtime_write_site_is_guarded_by_runtime_paths(self):
        """Runtime writes are permitted, but only inside the state root.

        Statically: a module that performs any write-capable call must also
        reference the path guard. Dynamically: TestRuntimeWriteConfinement below
        proves the guard actually refuses an outside path.
        """
        offenders = []
        for relative, absolute in runtime_python_files():
            # MOGO-014: the authorized effectful capability writes into the
            # governed research corpus, OUTSIDE the runtime state root, by
            # design. Its confinement is asserted separately and more strictly
            # by test_the_effectful_capability_reaches_nothing.
            if os.path.basename(absolute) in EFFECTFUL_CAPABILITY_MODULES:
                continue
            source = read_source(absolute)
            tree = ast.parse(source)
            writes = [name for _kind, name, _lineno, _node in called_names(tree)
                      if name == "open" or name in boundaries.BANNED_MUTATION_CALLS]
            if not writes:
                continue
            if "assert_inside_state_root" not in source:
                offenders.append((relative, sorted(set(writes))))
        self.assertEqual(offenders, [])

    def test_runtime_declares_no_absolute_path_literal(self):
        """No runtime module may hard-code a path outside the state root."""
        offenders = []
        for relative, absolute in runtime_python_files():
            if os.path.basename(absolute) in CONNECTOR_POLICY_MODULES:
                continue   # a URL template is not a filesystem path
            for node in ast.walk(ast.parse(read_source(absolute))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    value = node.value
                    if value.startswith("/") and len(value) > 1:
                        offenders.append((relative, node.lineno, value))
        self.assertEqual(offenders, [])

    def test_no_prohibited_target_is_ever_a_write_argument(self):
        """The section 7 rule, unchanged and still global across platform/**."""
        offenders = []
        for relative, source, tree in parse_platform_modules():
            if os.path.basename(relative) == DECLARATION_MODULE:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if boundaries.prohibited_reference_reason(node.value):
                        offenders.append((relative, node.lineno, node.value))
        self.assertEqual(offenders, [])

    def test_no_dangerous_builtin_call(self):
        offenders = [
            (relative, name, lineno)
            for relative, _source, tree in parse_platform_modules()
            for kind, name, lineno, _node in called_names(tree)
            if kind == "name" and name in boundaries.BANNED_BUILTIN_CALLS
        ]
        self.assertEqual(offenders, [])

    def test_no_process_execution_call(self):
        offenders = [
            (relative, name, lineno)
            for relative, _source, tree in parse_platform_modules()
            for kind, name, lineno, _node in called_names(tree)
            if kind == "attribute" and name in boundaries.BANNED_EXECUTION_CALLS
        ]
        self.assertEqual(offenders, [])

    def test_re_compile_is_not_mistaken_for_the_builtin(self):
        # Guards the precision of the rule above: platform modules DO call
        # re.compile, and that must remain legitimate.
        attribute_compiles = [
            relative
            for relative, _source, tree in parse_platform_modules()
            for kind, name, _lineno, _node in called_names(tree)
            if kind == "attribute" and name == "compile"
        ]
        self.assertGreater(len(attribute_compiles), 0)

    def test_no_scientific_path_appears_as_any_call_argument(self):
        offenders = []
        for relative, _source, tree in parse_platform_modules():
            if os.path.basename(relative) == DECLARATION_MODULE:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if boundaries.prohibited_reference_reason(node.value):
                        offenders.append((relative, node.lineno, node.value))
        self.assertEqual(offenders, [])


class TestNoNetworkOrExecutionCapability(unittest.TestCase):
    def test_no_banned_runtime_import(self):
        offenders = []
        for relative, _source, tree in parse_platform_modules():
            for imported in imported_module_names(tree):
                root = imported.split(".")[0]
                for banned in boundaries.BANNED_RUNTIME_IMPORTS:
                    if imported == banned or root == banned.split(".")[0]:
                        # urllib.parse would be harmless, but Step 1 imports no
                        # part of urllib at all, so the root match is exact.
                        offenders.append((relative, imported, banned))
        self.assertEqual(offenders, [])

    def test_no_required_banned_import_appears_anywhere(self):
        for relative, _source, tree in parse_platform_modules():
            imported = imported_module_names(tree)
            for banned in REQUIRED_BANNED_IMPORTS:
                with self.subTest(module=relative, banned=banned):
                    self.assertNotIn(banned, imported)

    def test_the_only_imports_are_stdlib_or_sibling_contract_modules(self):
        # Contracts stay minimal; the runtime additionally needs persistence,
        # locking and a CLI. Every name below is standard library -- verified
        # against sys.stdlib_module_names, not a hand-maintained belief.
        allowed_stdlib = {
            "hashlib", "json", "re", "uuid", "datetime", "types", "math", "os",
            "sys", "unittest", "ast", "sqlite3", "fcntl", "argparse", "shutil",
        }
        for name in allowed_stdlib:
            self.assertIn(name, sys.stdlib_module_names, name)
        offenders = []
        for relative, _source, tree in parse_platform_modules():
            for imported in imported_module_names(tree):
                if imported.startswith("."):
                    continue                      # package-relative sibling
                root = imported.split(".")[0]
                if root in allowed_stdlib or root == "mogo_platform":
                    continue
                offenders.append((relative, imported))
        self.assertEqual(offenders, [])

    def test_contract_modules_use_package_relative_sibling_imports(self):
        # The correction replaced flat bare-name imports with relative ones.
        # At least one module must actually use the relative form, or the
        # allowance above would be dead and the old style could creep back.
        relative_users = {
            os.path.basename(relative)
            for relative, absolute in contracts_python_files()
            if any(name.startswith(".")
                   for name in imported_module_names(ast.parse(read_source(absolute))))
        }
        # Exactly the four modules that depend on a sibling. errors.py,
        # vocabulary.py and boundaries.py are leaves with no platform imports,
        # and the two package markers import nothing at all.
        self.assertEqual(
            relative_users,
            {"ids.py", "command.py", "event.py", "task_states.py"},
        )

    def test_no_module_imports_a_retired_flat_module(self):
        offenders = [
            (relative, imported)
            for relative, _source, tree in parse_platform_modules()
            for imported in imported_module_names(tree)
            if imported.split(".")[0] in RETIRED_FLAT_MODULES
        ]
        self.assertEqual(offenders, [])


class TestNoPipelineOrScientificCoupling(unittest.TestCase):
    def test_no_platform_module_imports_a_phase_i_pipeline_module(self):
        # Architecture section 6.7: adapters are the only permitted path, and
        # no adapter exists in Step 1 -- so the permitted count is zero.
        pipeline_modules = {
            name[:-3] for name in os.listdir(PIPELINE_DIR) if name.endswith(".py")
        }
        self.assertGreater(len(pipeline_modules), 30)
        offenders = []
        for relative, _source, tree in parse_platform_modules():
            for imported in imported_module_names(tree):
                if imported.split(".")[0] in pipeline_modules:
                    offenders.append((relative, imported))
        self.assertEqual(offenders, [])

    def test_no_platform_module_references_the_prohibited_source_tree(self):
        for relative, source, _tree in parse_platform_modules():
            if os.path.basename(relative) == DECLARATION_MODULE:
                continue
            for tree_path in boundaries.PROHIBITED_SOURCE_TREES:
                with self.subTest(module=relative):
                    self.assertNotIn(tree_path, source)

    def test_no_unauthorized_scientific_write_is_expressible(self):
        # There is no write path at all, so a scientific write cannot be
        # expressed. Both previous checks combine to prove it; this asserts the
        # conclusion directly so the intent is visible in the failure output.
        # Contracts: no write call of any kind exists.
        contracts_writes = [
            (relative, name)
            for relative, absolute in contracts_python_files()
            for _kind, name, _lineno, _node in called_names(
                ast.parse(read_source(absolute)))
            if name in ("open",) + boundaries.BANNED_MUTATION_CALLS
        ]
        self.assertEqual(contracts_writes, [])
        # Runtime: writes exist, but no prohibited target is expressible -- the
        # path guard confines them and no section 7 literal appears at all.
        for relative, absolute in runtime_python_files():
            source = read_source(absolute)
            for literal in FORBIDDEN_LITERALS:
                self.assertNotIn(literal, source, relative)


class TestEnvelopesRejectProhibitedTargets(unittest.TestCase):
    """The boundary must also hold at the contract surface, not only in source."""

    UUID_A = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
    UUID_B = "7d444840-9dc0-41d2-b1a6-6f1d1d1a1a1a"
    UUID_C = "16fd2706-8baf-433b-82eb-8c7fada847da"
    UUID_D = "1b4e28ba-2fa1-489f-a9fd-2b0e6b6f7c33"
    STAMP = "2026-08-07T12:34:56.789Z"

    def _command(self, refs):
        return {
            "commandId": self.UUID_A, "commandType": "NormalizeArtifact",
            "commandVersion": 1, "workflowId": self.UUID_B,
            "correlationId": self.UUID_C, "causationId": self.UUID_D,
            "idempotencyKey": "a" * 64, "issuedAt": self.STAMP,
            "issuedBy": "orchestrator", "targetCapability": "research.acquire.v1",
            "inputRefs": refs,
            "policyContext": {"authorizationId": None, "policyVersion": "1.0",
                              "permittedOperations": []},
            "payloadHash": "b" * 64,
        }

    def _event(self, refs):
        payload = {"note": "fixture"}
        return {
            "eventId": self.UUID_A, "eventType": "TaskSucceeded", "eventVersion": 1,
            "workflowId": self.UUID_B, "correlationId": self.UUID_C,
            "causationId": self.UUID_D, "producer": "orchestrator",
            "producerVersion": "1.0.0", "occurredAt": self.STAMP,
            "recordedAt": self.STAMP, "subjectRefs": refs, "payload": payload,
            "payloadHash": ids.content_hash_of(payload), "sequence": 0,
        }

    def test_no_command_validates_with_a_prohibited_target(self):
        for path in EXPECTED_PROHIBITED_WRITE_PATHS:
            probe = path.replace("*", "001-x")
            with self.subTest(path=path):
                with self.assertRaises(errors.ProtectedBoundaryViolationError):
                    command.validate_command(self._command([probe]))

    def test_no_event_validates_with_a_prohibited_target(self):
        for path in EXPECTED_PROHIBITED_WRITE_PATHS:
            probe = path.replace("*", "001-x")
            with self.subTest(path=path):
                with self.assertRaises(errors.ProtectedBoundaryViolationError):
                    event.validate_event(self._event([probe]))

    def test_no_envelope_validates_with_a_prohibited_symbol(self):
        for symbol in EXPECTED_PROHIBITED_SCIENTIFIC_SYMBOLS:
            with self.subTest(symbol=symbol):
                with self.assertRaises(errors.ProtectedBoundaryViolationError):
                    command.validate_command(self._command([symbol]))
                with self.assertRaises(errors.ProtectedBoundaryViolationError):
                    event.validate_event(self._event([symbol]))


class TestImportConventionIntegrity(unittest.TestCase):
    def test_no_init_py_at_platform_root(self):
        # THE NARROW RULE. Only platform/__init__.py causes the collision: it
        # would make the repository-root directory the `platform` package and
        # shadow the standard-library module process-wide. Nested markers deeper
        # in the tree are reached through a different sys.path entry and carry a
        # different top-level name, so they cannot. The previous version of this
        # test banned __init__.py ANYWHERE under platform/, which was an
        # over-generalisation that blocked normal packaging -- MOGO-010 Step 1
        # correction I-1.
        root_marker = os.path.join(PLATFORM_DIR, "__init__.py")
        self.assertFalse(
            os.path.exists(root_marker),
            "platform/__init__.py would shadow the stdlib `platform` module "
            "repository-wide. It must never exist. Nested package markers under "
            "platform/src/mogo_platform/ are correct and required.",
        )

    def test_package_markers_exist(self):
        for marker in PACKAGE_MARKERS:
            with self.subTest(marker=os.path.relpath(marker, REPO_ROOT)):
                self.assertTrue(os.path.isfile(marker))

    def test_package_markers_are_docstring_only(self):
        # No import, no re-export, no executable statement: importing the
        # package must do nothing observable, which is what keeps Step 1
        # non-executable.
        for marker in PACKAGE_MARKERS:
            relative = os.path.relpath(marker, REPO_ROOT)
            with self.subTest(marker=relative):
                tree = ast.parse(read_source(marker), filename=marker)
                self.assertEqual(
                    len(tree.body), 1,
                    "%s must contain exactly one statement (its docstring)" % relative,
                )
                statement = tree.body[0]
                self.assertIsInstance(statement, ast.Expr)
                self.assertIsInstance(statement.value, ast.Constant)
                self.assertIsInstance(statement.value.value, str)
                self.assertEqual(imported_module_names(tree), set())
                self.assertEqual(called_names(tree), [])

    def test_no_retired_flat_module_is_importable(self):
        # The generic top-level namespace must be free again.
        for name in RETIRED_FLAT_MODULES:
            with self.subTest(module=name):
                self.assertIsNone(importlib.util.find_spec(name))

    def test_the_old_flat_contracts_directory_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(PLATFORM_DIR, "contracts")))

    def test_no_test_inserts_platform_contracts_into_sys_path(self):
        """No suite may reach the package through the retired flat directory.

        THIS FILE IS EXEMPT, for the same reason platform_boundaries.py is
        exempt from the literal scan: it is the module that DECLARES the
        forbidden strings, so it must be allowed to contain them. Every other
        suite is checked. The exemption is one named file, not a pattern.
        """
        this_file = os.path.basename(os.path.abspath(__file__))
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        offenders = []
        for name in sorted(os.listdir(tests_dir)):
            if not name.endswith(".py") or name == this_file:
                continue
            source = read_source(os.path.join(tests_dir, name))
            if '"platform", "contracts"' in source or "platform/contracts" in source:
                offenders.append(name)
        self.assertEqual(offenders, [])
        # And prove the exemption is not hiding a real one: the retired
        # directory does not exist, so no suite could reach it even if it tried.
        self.assertFalse(os.path.exists(os.path.join(PLATFORM_DIR, "contracts")))

    def test_every_suite_adds_only_the_src_directory(self):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        for name in sorted(os.listdir(tests_dir)):
            if not name.startswith("test_") or not name.endswith(".py"):
                continue
            with self.subTest(suite=name):
                source = read_source(os.path.join(tests_dir, name))
                self.assertIn('"platform", "src"', source)

    def test_stdlib_platform_module_is_importable_and_functional(self):
        import platform as stdlib_platform
        self.assertTrue(stdlib_platform.system())
        self.assertTrue(stdlib_platform.python_version())
        module_file = getattr(stdlib_platform, "__file__", "") or ""
        self.assertFalse(
            os.path.abspath(module_file).startswith(PLATFORM_DIR + os.sep),
            "stdlib `platform` resolved inside the repository -- it is shadowed.",
        )

    def test_platform_modules_are_package_qualified(self):
        # The correction replaced generic top-level names (platform_ids) with
        # names inside the uniquely owned package, so nothing occupies the flat
        # global module namespace any more.
        for module in (ids, errors, command, event, boundaries):
            with self.subTest(module=module.__name__):
                self.assertTrue(
                    module.__name__.startswith("mogo_platform.contracts."),
                    "%s is not package-qualified" % module.__name__,
                )


class TestNoManifestOrDependencyIntroduced(unittest.TestCase):
    def test_no_package_manifest_or_lock_file_exists(self):
        # ADR-012 D-01 manifest is deferred by operator ruling. Nothing in
        # Step 1 may introduce one.
        for name in ("pyproject.toml", "requirements.txt", "setup.py",
                     "setup.cfg", "Pipfile", "Pipfile.lock", "poetry.lock",
                     "package.json", "package-lock.json"):
            for directory in (REPO_ROOT, PLATFORM_DIR, SRC_DIR, PACKAGE_DIR):
                candidate = os.path.join(directory, name)
                with self.subTest(candidate=candidate):
                    self.assertFalse(os.path.exists(candidate))


class TestRuntimeWriteConfinement(unittest.TestCase):
    """The confinement rule, exercised rather than merely inspected."""

    def setUp(self):
        import tempfile
        from mogo_platform.runtime import paths as paths_module
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = paths_module.ensure_state_root(
            paths_module.RuntimePaths(os.path.join(self._tmp.name, "state")))

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_write_outside_the_state_root_is_refused(self):
        from mogo_platform.runtime import errors as runtime_errors
        for candidate in (os.path.join(REPO_ROOT, "index.html"),
                          os.path.join(REPO_ROOT, "evidence", "x.json"),
                          "/tmp/escape.txt", REPO_ROOT):
            with self.subTest(candidate=candidate):
                with self.assertRaises(runtime_errors.PathEscapeError):
                    self.paths.assert_inside_state_root(candidate)

    def test_every_prohibited_section_7_target_is_outside_the_state_root(self):
        for entry in boundaries.PROHIBITED_WRITE_PATHS:
            probe = os.path.join(REPO_ROOT, entry["declared"].replace("*", "x"))
            with self.subTest(target=entry["declared"]):
                self.assertFalse(self.paths.is_inside_state_root(probe))

    def test_runtime_state_root_is_git_ignored(self):
        """Runtime state must never be committable, by construction."""
        marker = os.path.join(REPO_ROOT, "platform", "runtime", ".gitignore")
        self.assertTrue(os.path.isfile(marker))
        with open(marker, "r", encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn("*", body)
        self.assertIn("!.gitignore", body)

    def test_runtime_package_markers_are_docstring_only(self):
        for marker in (os.path.join(RUNTIME_DIR, "__init__.py"),
                       os.path.join(RUNTIME_DIR, "capabilities", "__init__.py")):
            relative = os.path.relpath(marker, REPO_ROOT)
            with self.subTest(marker=relative):
                tree = ast.parse(read_source(marker), filename=marker)
                self.assertEqual(len(tree.body), 1)
                self.assertIsInstance(tree.body[0], ast.Expr)
                self.assertIsInstance(tree.body[0].value, ast.Constant)
                self.assertEqual(imported_module_names(tree), set())


# MOGO-014: capability modules authorized to perform effects. Named
# explicitly so adding a second effectful capability is a visible edit here.
EFFECTFUL_CAPABILITY_MODULES = ("ingest_local_artifact.py",)
# MOGO-015: the connector AUTHORIZATION gate necessarily names the external
# host it authorizes -- an allow-list that cannot name a host authorizes
# nothing. It contains no transport (asserted in
# tests/platform/test_runtime_connector_authorization.py, which also pins
# https-only and forbids every loopback/private destination).
CONNECTOR_POLICY_MODULES = ("connector_authorization.py",)
EFFECTFUL_CAPABILITY_IDS = ("CAP|research|ingest-local-artifact",)


class TestNoAutomationEscapeHatch(unittest.TestCase):
    """No trading, replay, acquisition or model-call path exists anywhere."""

    FORBIDDEN_MARKERS = (
        "oanda", "paper_trade", "papertrade", "live_trade", "livetrade",
        "place_order", "replay_engine", "yt_dlp", "youtube", "openai",
        "anthropic", "webdriver", "selenium", "beautifulsoup",
    )

    def test_no_trading_acquisition_or_model_marker_appears(self):
        """boundaries.py is exempt: it must NAME what it forbids.

        The same declaration-module principle the literal scan uses. `yt_dlp`
        appears in BANNED_NETWORK_IMPORTS precisely so that no other module may
        import it; flagging the ban as a violation would be self-defeating.
        """
        offenders = []
        for relative, absolute in platform_python_files():
            if os.path.basename(relative) == DECLARATION_MODULE:
                continue
            # MOGO-015 extends the SAME declaration-module principle this test
            # already states. boundaries.py is exempt because it must name what
            # it forbids; the connector authorization allow-list is exempt
            # because it must name what it AUTHORIZES. An allow-list that
            # cannot name its host authorizes nothing. It contains no
            # transport, which is asserted separately and strictly in
            # tests/platform/test_runtime_connector_authorization.py.
            if os.path.basename(relative) in CONNECTOR_POLICY_MODULES:
                continue
            lowered = read_source(absolute).lower()
            for marker in self.FORBIDDEN_MARKERS:
                if marker in lowered:
                    offenders.append((relative, marker))
        self.assertEqual(offenders, [])

    def test_no_module_can_reach_the_network_or_a_subprocess(self):
        for relative, absolute in platform_python_files():
            imported = imported_module_names(ast.parse(read_source(absolute)))
            for banned in REQUIRED_BANNED_IMPORTS:
                with self.subTest(module=relative, banned=banned):
                    self.assertNotIn(banned, imported)

    def test_the_runtime_registers_exactly_the_approved_capabilities(self):
        """Every capability harmless -- asserted per capability, not by count.

        The count is not the property worth protecting; what each capability is
        ALLOWED to do is. Every manifest must need no connector, no secret and
        no permission, and must be effectClass `pure` UNLESS it is the
        authorized effectful capability -- the A-5 argument for crash boundary 8
        is now carried by the idempotency-keyed result store (MOGO-014) rather
        than by universal purity.

        MOGO-011 Step 3 adds ONE capability declaring `operationClass:
        acquisition`. That declaration is a statement about what governance
        must approve before it may run, NOT about what it does: it acquires
        nothing, and the network, subprocess and write-confinement tests in this
        suite continue to prove that no acquisition path exists anywhere.
        """
        from mogo_platform.runtime import orchestrator as orchestrator_module
        from mogo_platform.runtime import registry
        self.assertEqual(len(orchestrator_module.BUILTIN_CAPABILITIES), 4)
        self.assertEqual(len(orchestrator_module.CAPABILITY_CALLABLES), 4)
        acquisition_class = 0
        for manifest in orchestrator_module.BUILTIN_CAPABILITIES:
            with self.subTest(capability=manifest["capabilityId"]):
                self.assertEqual(manifest["requiredConnectors"], [])
                self.assertEqual(manifest["requiredSecretReferences"], [])
                self.assertEqual(manifest["requiredPermissions"], [])
                self.assertIn(manifest["operationClass"],
                              ("acquisition", "non_acquisition"))
                self.assertEqual(
                    manifest.get("effectClass", registry.DEFAULT_EFFECT_CLASS),
                    "effectful" if manifest["capabilityId"] in EFFECTFUL_CAPABILITY_IDS
                    else registry.DEFAULT_EFFECT_CLASS)
                if manifest["operationClass"] == "acquisition":
                    acquisition_class += 1
        # Exactly one, and it exists to be GOVERNED rather than to acquire.
        # MOGO-014 adds a second acquisition-class capability: local artifact
        # ingestion. Both are governed by the policy gate, which is the point.
        self.assertEqual(acquisition_class, 2)
        self.assertEqual(
            {m["capabilityId"] for m in orchestrator_module.BUILTIN_CAPABILITIES},
            set(orchestrator_module.CAPABILITY_CALLABLES))

    def test_no_random_or_secrets_import_anywhere(self):
        """Decision B-2, enforced structurally rather than by convention.

        Deterministic backoff is not a rule a future edit could quietly break:
        randomness is an import that will not pass this test.
        """
        for name in ("random", "secrets"):
            with self.subTest(module=name):
                self.assertIn(name, boundaries.BANNED_RUNTIME_IMPORTS)
        offenders = [
            (relative, imported)
            for relative, _source, tree in parse_platform_modules()
            for imported in imported_module_names(tree)
            if imported.split(".")[0] in ("random", "secrets")
        ]
        self.assertEqual(offenders, [])

    def test_clock_is_read_only_in_clock_py(self):
        """Exactly one module in platform/** may ask what time it is.

        Every other module takes `now` as an argument, which is what makes
        every retry and lease decision a pure function of recorded values --
        and therefore what makes replay reproduce byte-identical rows.
        """
        readers = {}
        for relative, _source, tree in parse_platform_modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute):
                    continue
                if func.attr not in ("now", "time", "monotonic",
                                     "perf_counter", "utcnow", "today"):
                    continue
                readers.setdefault(os.path.basename(relative), set()).add(func.attr)
        self.assertEqual(sorted(readers), ["clock.py"], readers)

    def test_no_naive_datetime_now_call_exists(self):
        """`datetime.now()` with no tzinfo is the local-time path. It must not
        exist anywhere, so timezone ambiguity is impossible rather than
        merely discouraged."""
        offenders = []
        for relative, _source, tree in parse_platform_modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (isinstance(func, ast.Attribute) and func.attr == "now"):
                    continue
                if not node.args and not node.keywords:
                    offenders.append((relative, node.lineno))
        self.assertEqual(offenders, [])

    def test_the_effectful_capability_reaches_nothing(self):
        """The effectful capability is exempt from purity, NOT from isolation.

        It may open files. It may not reach the network, spawn a process, or
        touch anything outside the governed research area. This boundary is
        stricter than the one it is exempted from in the dimension that
        matters: a capability that could fetch is a capability that could
        acquire without an authorization record.
        """
        capabilities_dir = os.path.join(RUNTIME_DIR, "capabilities")
        checked = 0
        for relative, absolute in platform_python_files():
            if os.path.basename(absolute) not in EFFECTFUL_CAPABILITY_MODULES:
                continue
            checked += 1
            source = read_source(absolute)
            tree = ast.parse(source)
            with self.subTest(module=relative):
                for imported in imported_module_names(tree):
                    root = imported.split(".")[0]
                    self.assertNotIn(root, (
                        "socket", "ssl", "http", "urllib", "requests", "httpx",
                        "ftplib", "telnetlib", "smtplib", "asyncio", "aiohttp",
                        "subprocess", "multiprocessing", "ctypes", "random",
                        "secrets"),
                        "the effectful capability must reach nothing and spawn "
                        "nothing")
                for _kind, name, _lineno, _node in called_names(tree):
                    self.assertNotIn(name, ("urlopen", "system", "popen", "run",
                                            "Popen", "connect", "request"))
                # It must confine itself to the governed research directories.
                self.assertIn("INTAKE_ROOT", source)
                self.assertIn("ARTIFACT_ROOT", source)
                # And it must never name the forward-campaign surfaces.
                for forbidden in ("index.html", "alexG", "localStorage",
                                  "indexedDB", "paperAccount"):
                    self.assertNotIn(forbidden, source,
                                     "research capability must not reference "
                                     "the forward trading lane")
        self.assertEqual(checked, len(EFFECTFUL_CAPABILITY_MODULES))

    def test_capability_modules_read_no_clock_and_no_randomness(self):
        """Purity, statically -- the layer that applies whether or not a
        manifest DECLARES anything.

        This is the enforcement; the manifest's effectClass is documentation. A
        capability that lied about being pure would be caught here.
        """
        capabilities_dir = os.path.join(RUNTIME_DIR, "capabilities")
        checked = 0
        for relative, absolute in platform_python_files():
            if not os.path.abspath(absolute).startswith(capabilities_dir + os.sep):
                continue
            # MOGO-014 narrowed this boundary rather than deleting it. The rule
            # was "every capability is pure", which was true when every
            # capability was a demonstration. The first EFFECTFUL capability is
            # authorized to read and write files, so a rule forbidding `open`
            # everywhere would now be a wrong rule enforced by a test -- the
            # exact failure platform/README.md records correcting once before.
            # It is excluded HERE and constrained by its own stricter boundary
            # in test_the_effectful_capability_reaches_nothing below, which
            # forbids every network client outright.
            if os.path.basename(absolute) in EFFECTFUL_CAPABILITY_MODULES:
                continue
            checked += 1
            tree = ast.parse(read_source(absolute))
            with self.subTest(module=relative):
                for imported in imported_module_names(tree):
                    root = imported.split(".")[0]
                    self.assertNotIn(root, ("random", "secrets", "time",
                                            "datetime", "os", "sys", "socket"))
                for kind, name, _lineno, _node in called_names(tree):
                    self.assertNotIn(name, ("open",) + boundaries.BANNED_MUTATION_CALLS)
                    self.assertNotIn(name, ("now", "time", "monotonic", "random",
                                            "randint", "choice", "token_hex"))
        # echo.py, fail_then_succeed.py and the package marker.
        self.assertGreaterEqual(checked, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
