#!/usr/bin/env python3
"""Encrypted source-evidence backup (ADR-010 amendment A4).

THE TWO PROPERTIES UNDER TEST

  1. ARTIFACT_INDEX.json is safe to commit. It carries hashes, sizes and counts, and
     nothing that is OANDA Trading System Rates -- no candles, no OHLC, no prices.
     Committing it must never become a route by which restricted data reaches GitHub.

  2. The backup tool refuses everything it cannot prove, and the passphrase never
     leaves the terminal. In particular it never reaches argv, where `ps` would show
     it to every process on the machine.

BEHAVIOURAL VERSUS STRUCTURAL, STATED PLAINLY

    This phase is authorised to implement the mechanism but NOT to create an encrypted
    image or copy any OANDA data. Tests that would require a real image -- corruption
    detection, restore-refuses-overwrite, insufficient space, partial-image cleanup --
    therefore assert the GUARD EXISTS AND IS REACHED, not that it fires against a real
    archive. Each is named `_structural_` so the distinction cannot be lost by reading
    a green run, and the report says so.

    A structural test is weaker evidence than a behavioural one. Marking it as such is
    the point: the alternative is a suite that looks complete and is not.

VACUITY

    Every loop asserts its filter is non-empty first, and counts are derived at run
    time and compared against other derived quantities. `17` and `267` are true today
    and false after the next close; pinning them would be the oracle defect CLAUDE.md
    names as this project's most common failure.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "trader_intelligence"))

INDEX_PATH = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                          "ledger-preservation", "ARTIFACT_INDEX.json")
SCRIPT = os.path.join(REPO_ROOT, "scripts", "backup_source_artifacts.sh")


def _index():
    with open(INDEX_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _script_source():
    with open(SCRIPT, "r", encoding="utf-8") as handle:
        return handle.read()


def _code_lines():
    """Script source with comment-only lines removed.

    A scan that counts comment text finds `git` in "never invoke git" and calls the
    tool unsafe for documenting its own safety. The first draft of this test did
    exactly that.
    """
    out = []
    for line in _script_source().split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        out.append(line)
    return out


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _run(*args):
    return subprocess.run(["bash", SCRIPT, *args], capture_output=True, text=True,
                          cwd=REPO_ROOT, stdin=subprocess.DEVNULL)


class TestIndexIsSafeToCommit(unittest.TestCase):
    """1: the index carries no restricted market data."""

    #: Field names that would indicate market data rather than an identifier.
    FORBIDDEN_KEYS = ("candle", "candles", "ohlc", "open", "high", "low", "close",
                      "price", "bid", "ask", "mid", "volume", "instrument", "account",
                      "balance", "apikey", "api_key", "token", "secret", "password",
                      "credential", "backupstate", "backedup", "verifiedat",
                      "destination", "label", "volume", "mountpoint")

    def test_1a_artifact_records_carry_only_the_permitted_fields(self):
        index = _index()
        artifacts = index["artifacts"]
        self.assertTrue(artifacts, "index declares no artifacts; every check below is vacuous")
        permitted = {"path", "sha256", "bytes", "packageCount", "packageContentHashes"}
        for artifact in artifacts:
            self.assertEqual(set(artifact), permitted,
                             "artifact record carries unexpected fields: %s"
                             % sorted(set(artifact) - permitted))

    def test_1b_no_forbidden_key_names_anywhere_in_the_data(self):
        """Scans KEYS and string VALUES, but not the `notice` prose.

        The notice says "no candles, no OHLC values and no prices" -- scanning it
        would flag the sentence that promises the absence, which is the wrong result
        for the right words.
        """
        index = dict(_index())
        index.pop("notice", None)
        scanned = []

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    scanned.append(key)
                    self.assertNotIn(key.lower(), self.FORBIDDEN_KEYS,
                                     "forbidden key %r at %s" % (key, path))
                    walk(value, path + "/" + key)
            elif isinstance(node, list):
                for item in node:
                    walk(item, path + "/[]")

        walk(index)
        self.assertTrue(scanned, "walked nothing; vacuous")

    def test_1c_every_number_is_a_size_or_a_count_and_none_is_a_float(self):
        """An OHLC value is a float. There are no floats here, at any depth."""
        index = _index()
        numbers = []

        def walk(node):
            if isinstance(node, dict):
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, bool):
                pass
            elif isinstance(node, (int, float)):
                numbers.append(node)

        walk(index)
        self.assertTrue(numbers, "index contains no numbers at all; vacuous")
        self.assertEqual([n for n in numbers if isinstance(n, float)], [],
                         "a float in the index -- a price would look exactly like this")
        allowed = {a["bytes"] for a in index["artifacts"]}
        allowed |= {a["packageCount"] for a in index["artifacts"]}
        self.assertTrue(set(numbers) <= allowed,
                        "a number that is neither a byte size nor a package count: %s"
                        % sorted(set(numbers) - allowed))

    def test_1d_no_drive_name_path_or_backup_status(self):
        raw = json.dumps(_index())
        self.assertTrue(raw, "empty index; vacuous")
        for needle in ("MOGOTH", "/Volumes", ".dmg", "backupState", "lastBackup",
                       "verifiedAt", "Seagate"):
            self.assertNotIn(needle, raw,
                             "%r must not appear in a committed index" % needle)

    def test_1e_the_index_states_the_licensing_restriction(self):
        notice = _index().get("notice", "")
        self.assertTrue(notice, "index carries no notice")
        for phrase in ("OANDA", "Internal Use", "excluded"):
            self.assertIn(phrase, notice,
                          "the notice must state why the artifacts are not in Git")

    def test_1f_hashes_are_well_formed_and_hash_algorithms_are_declared(self):
        index = _index()
        self.assertEqual(index["fileHashAlgorithm"], "sha256")
        self.assertEqual(index["packageHashAlgorithm"], "sha256")
        self.assertEqual(index["packageHashCanonicalization"], "mogo.evidence-canon.v1")
        artifacts = index["artifacts"]
        self.assertTrue(artifacts, "no artifacts; vacuous")
        hex64 = re.compile(r"^[0-9a-f]{64}$")
        for artifact in artifacts:
            self.assertRegex(artifact["sha256"], hex64)
            self.assertTrue(artifact["packageContentHashes"], "artifact declares no packages")
            for package_hash in artifact["packageContentHashes"]:
                self.assertRegex(package_hash, hex64)


class TestIndexMatchesReality(unittest.TestCase):
    """2-3: the index describes the artifacts that actually exist."""

    # test_2 (every indexed artifact exists and matches its whole-file hash) and
    # test_3 (package hashes verify through the production canonicalizer) moved to
    # tests/integration_real_evidence/test_real_corpus_integration.py. Both open the
    # OANDA-derived artifacts under `evidence/` and hash them, which is their entire
    # point: neither can be answered by a fixture, and both are unrunnable where the
    # licensed data is not readable. What stays here is everything the index can be
    # checked for on its own -- test_2b still holds the index against the
    # EvidenceSource records, which is the check that stops it becoming a second,
    # divergent source of truth.

    def test_2b_index_agrees_with_the_evidence_source_records(self):
        """The index must not become a second, divergent source of truth."""
        import glob as globmod
        declared = {}
        pattern = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence",
                               "sources", "*.json")
        for path in globmod.glob(pattern):
            with open(path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
            rel = record.get("repositoryPath") or ""
            if record.get("storageLocationType") == "repository" and rel.startswith("evidence/"):
                declared.setdefault(rel, set()).add(record.get("contentHash"))
        self.assertTrue(declared, "no repository EvidenceSources; vacuous")
        for artifact in _index()["artifacts"]:
            self.assertIn(artifact["path"], declared,
                          "%s is indexed but no EvidenceSource declares it" % artifact["path"])
            self.assertIn(artifact["sha256"], declared[artifact["path"]],
                          "index hash disagrees with the EvidenceSource for %s" % artifact["path"])


class TestPassphraseNeverEscapes(unittest.TestCase):
    """4: the passphrase reaches hdiutil on stdin and goes nowhere else."""

    def test_4a_password_is_never_accepted_as_an_argument(self):
        for flag in ("--password", "--pass", "--passphrase", "-p"):
            result = _run("--backup", "--dest", "/tmp/x", "--confirm", flag, "hunter2")
            self.assertNotEqual(result.returncode, 0,
                                "%s was accepted; it would be visible in ps" % flag)
            self.assertIn("never be passed as a command-line argument",
                          result.stdout + result.stderr)
            self.assertNotIn("hunter2", result.stdout,
                             "the rejected password was echoed back")

    def test_4b_password_only_ever_reaches_hdiutil_via_stdin(self):
        uses = [ln for ln in _code_lines() if "$PASSWORD" in ln]
        self.assertTrue(uses, "no PASSWORD uses found; the scan is broken, not the script")
        for line in uses:
            self.assertTrue(
                line.strip().startswith("PASSWORD=") or
                ("printf '%s' \"$PASSWORD\" | hdiutil" in line),
                "PASSWORD used somewhere other than a stdin pipe to hdiutil: %s" % line.strip())

    def test_4c_password_is_never_written_logged_or_stored(self):
        code = "\n".join(_code_lines())
        self.assertTrue(code, "empty script; vacuous")
        for forbidden in ("security add-generic-password", "keychain", "> $PASSWORD",
                          "echo $PASSWORD", "echo \"$PASSWORD\"", "export PASSWORD",
                          "history -s"):
            self.assertNotIn(forbidden, code,
                             "the script contains %r" % forbidden)

    def test_4d_receipt_schema_contains_no_password_field(self):
        code = _script_source()
        self.assertIn("write_receipt()", code, "receipt writer not found; vacuous")
        # Slice the FUNCTION, not everything after it: do_verify and do_restore
        # legitimately pipe $PASSWORD to hdiutil, and including them made this test
        # fail on correct code.
        receipt_block = code.split("write_receipt()")[1].split("# ══ VERIFY")[0]
        self.assertTrue(receipt_block, "receipt writer is empty; vacuous")
        keys = re.findall(r'^\s*"([A-Za-z0-9_]+)":', receipt_block, re.MULTILINE)
        self.assertTrue(keys, "no receipt fields found; the scan is broken, not the script")
        for key in keys:
            self.assertNotIn("pass", key.lower(),
                             "the receipt declares a password-shaped field: %r" % key)
        self.assertNotIn("$PASSWORD", receipt_block,
                         "the receipt writer can see the passphrase variable")

    def test_4e_read_is_silent(self):
        code = "\n".join(_code_lines())
        self.assertIn("read -rs", code.replace("IFS= read -rs", "read -rs"),
                      "the passphrase prompt must use `read -s` so it is not echoed")


class TestRefusals(unittest.TestCase):
    """5-8: behavioural. Every one of these actually runs the script."""

    def test_5a_missing_mode_or_dest_or_confirm_fails(self):
        self.assertNotEqual(_run().returncode, 0)
        self.assertNotEqual(_run("--backup").returncode, 0)
        self.assertNotEqual(_run("--backup", "--dest", "/tmp/x").returncode, 0)
        result = _run("--backup", "--dest", "/tmp/x")
        self.assertIn("--confirm", result.stdout + result.stderr)

    def test_5b_confirm_alone_is_not_enough_without_a_destination(self):
        result = _run("--backup", "--confirm")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact --dest", result.stdout + result.stderr)

    def test_6a_globs_and_traversal_are_refused(self):
        for bad in ("/Volumes/*/backup", "/Volumes/MOGOTH/../etc", "/tmp/a?b"):
            result = _run("--backup", "--dest", bad, "--confirm")
            self.assertNotEqual(result.returncode, 0, "accepted %r" % bad)

    def test_6b_relative_destination_is_refused(self):
        result = _run("--backup", "--dest", "relative/path", "--confirm")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute", result.stdout + result.stderr)

    def test_6c_symlink_destination_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "real")
            os.makedirs(target)
            link = os.path.join(tmp, "link")
            os.symlink(target, link)
            result = _run("--backup", "--dest", link, "--confirm")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlink", result.stdout + result.stderr)

    def test_7_unmounted_or_nonexistent_volume_is_refused(self):
        result = _run("--backup", "--dest", "/Volumes/NO_SUCH_VOLUME_XYZ/folder", "--confirm")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not mounted", result.stdout + result.stderr)

    def test_7b_volume_root_is_refused(self):
        result = _run("--backup", "--dest", "/Volumes/MOGOTH", "--confirm")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("volume root", result.stdout + result.stderr)

    def test_8_time_machine_managed_directories_are_refused(self):
        for bad in ("/Volumes/MOGOTH/Backups.backupdb/x",
                    "/Volumes/MOGOTH/.timemachine/x",
                    "/Volumes/MOGOTH/.Spotlight-V100/x",
                    "/Volumes/MOGOTH/.fseventsd/x"):
            result = _run("--backup", "--dest", bad, "--confirm")
            self.assertNotEqual(result.returncode, 0, "accepted %r" % bad)
            # The exact REFUSAL, not the word "Time Machine" -- which also appears in
            # the informational note printed for any destination on a TM volume.
            # Matching the note made this test pass with the guard deleted; caught by
            # mutation M2.
            self.assertIn("is inside a Time Machine or system-managed directory",
                          result.stdout + result.stderr,
                          "refused for some other reason than the Time Machine guard")

    def test_8b_non_interactive_invocation_is_refused(self):
        """The guard that stops this running from a hook or a timer."""
        with tempfile.TemporaryDirectory() as tmp:
            result = _run("--backup", "--dest", tmp, "--confirm")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no terminal on stdin", result.stdout + result.stderr)


class TestOperationalScriptIsClean(unittest.TestCase):
    """13: no git, no network, no wildcards, restrictive umask."""

    def test_13a_no_git_invocation(self):
        code = _code_lines()
        self.assertTrue(code, "empty script; vacuous")
        offenders = [ln for ln in code if re.search(r"(^|[;&|\s(])git\s", ln)]
        self.assertEqual(offenders, [], "the backup tool must never invoke git")

    def test_13b_no_network_command(self):
        code = _code_lines()
        self.assertTrue(code, "empty script; vacuous")
        pattern = re.compile(r"(^|[;&|\s(])(curl|wget|nc|ssh|scp|ftp|sftp|sendmail|mail)\s")
        offenders = [ln for ln in code if pattern.search(ln)]
        self.assertEqual(offenders, [], "the backup tool must make no network call")

    def test_13c_no_wildcard_file_operations(self):
        code = _code_lines()
        self.assertTrue(code, "empty script; vacuous")
        offenders = [ln for ln in code
                     if re.search(r"(cp|rm|mv|tar|ditto)\s[^|]*\*", ln)]
        self.assertEqual(offenders, [], "file operations must use literal paths")

    def test_13d_restrictive_umask_is_set(self):
        # A trailing comment on the line is fine and defeats a `$` anchor.
        self.assertTrue(re.search(r"^umask 077(\s|#|$)", _script_source(), re.MULTILINE),
                        "the script must set a restrictive umask")

    def test_13e_artifact_list_comes_from_the_index_not_a_directory_glob(self):
        code = "\n".join(_code_lines())
        self.assertIn("read_index_paths", code,
                      "the artifact list must be read from the index")
        # A `case` pattern that VALIDATES a path is fine and is not enumeration. What
        # must not exist is a glob or listing that PRODUCES the set of artifacts.
        enumerating = [ln for ln in _code_lines()
                       if re.search(r"(for\s+\w+\s+in\s+[^;]*evidence/\*|ls\s[^|]*evidence/)", ln)]
        self.assertEqual(enumerating, [],
                         "artifacts are enumerated by a glob rather than by the index: %s"
                         % enumerating)

    def test_13f_script_is_not_referenced_by_any_automatic_entry_point(self):
        """It must not be reachable from capture, a hook, or a launch agent."""
        checked = 0
        for rel in ("scripts/forward_capture.sh", "tests/run_all.sh"):
            path = os.path.join(REPO_ROOT, rel)
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as handle:
                body = handle.read()
            self.assertNotIn("backup_source_artifacts", body,
                             "%s references the backup tool; it must never be automatic" % rel)
            checked += 1
        self.assertGreater(checked, 0, "checked no entry points; vacuous")


class TestGuardsExistStructurally(unittest.TestCase):
    """9-12: STRUCTURAL ONLY -- see the module docstring.

    These guards cannot be exercised behaviourally in this phase, because doing so
    would require creating a real encrypted image and copying OANDA-derived data,
    which this phase is explicitly not authorised to do. Each test asserts the guard
    is present and reached, which is weaker evidence than firing it, and is labelled
    so that weakness is visible rather than implied.
    """

    def test_9_structural_insufficient_space_is_checked_before_creation(self):
        code = "\n".join(_code_lines())
        self.assertIn("df -k", code, "no free-space check")
        self.assertIn("not enough free space", code)
        space_at = code.index("not enough free space")
        create_at = code.index("hdiutil create")
        self.assertLess(space_at, create_at,
                        "the space check must precede image creation")

    def test_10_structural_partial_image_is_removed_but_a_completed_one_is_not(self):
        code = "\n".join(_code_lines())
        self.assertIn("PARTIAL_IMAGE", code)
        # Was `trap cleanup EXIT INT TERM`. Behavioural testing showed that made $?
        # unreliable inside the trap, so a SIGTERM during creation looked like success
        # and the partial image survived. Now a signal handler records the fact and
        # cleanup runs on EXIT; see TestDefectsFoundByBehaviouralTesting.test_R2.
        self.assertIn('trap on_signal INT TERM', code,
                      "interruption must be handled, not only a clean exit")
        self.assertIn('trap cleanup EXIT', code)
        self.assertIn('PARTIAL_IMAGE=""', code,
                      "a completed backup must clear the partial marker so cleanup spares it")
        self.assertIn('rm -f -- "${PARTIAL_IMAGE}"', code)

    def test_11_structural_verify_compares_the_archive_hash_without_decrypting(self):
        code = _script_source()
        verify = code.split("do_verify()")[1].split("do_restore()")[0]
        self.assertIn("ARCHIVE CORRUPTED OR ALTERED", verify)
        corrupt_at = verify.index("ARCHIVE CORRUPTED OR ALTERED")
        attach_at = verify.index("hdiutil attach")
        self.assertLess(corrupt_at, attach_at,
                        "the hash comparison must happen before any decryption")
        self.assertIn("--deep", code, "deep verify must need its own explicit flag")

    def test_12_structural_restore_refuses_to_overwrite_and_rolls_back(self):
        code = _script_source()
        restore = code.split("do_restore()")[1]
        self.assertIn("refusing to overwrite", restore)
        self.assertIn("-readonly", restore, "restore must attach read-only")
        self.assertIn("rolling back", restore)

    def test_12b_structural_every_mode_detaches_on_the_way_out(self):
        code = "\n".join(_code_lines())
        self.assertIn("hdiutil detach", code)
        self.assertIn("cleanup()", code)
        self.assertIn("-force", code, "cleanup needs a forced detach fallback")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDefectsFoundByBehaviouralTesting(unittest.TestCase):
    """Regression guards for two defects the structural tests could not see.

    Both were found by running the real script against synthetic fixtures with real
    hdiutil. Both had passing structural tests at the time. That is the argument for
    behavioural testing, recorded here so the lesson survives the session.
    """

    def test_R1_hdiutil_is_not_given_a_double_dash(self):
        """`hdiutil create` rejects `--`, so the tool could never create an image.

        Every structural test passed against a tool that failed on its first real
        invocation with `hdiutil: create: unknown option "--"`. Safe to omit because
        --dest is required to be absolute, so a leading-dash path cannot occur.
        """
        offenders = [ln for ln in _code_lines()
                     if "hdiutil" in ln and re.search(r"\s--\s", ln)]
        self.assertEqual(offenders, [],
                         "hdiutil does not accept `--`; it fails at runtime: %s" % offenders)
        self.assertTrue([ln for ln in _code_lines() if "hdiutil create" in ln],
                        "no hdiutil create call found; the scan is broken, not the script")

    def test_R2_a_signal_is_treated_as_failure_by_cleanup(self):
        """On SIGTERM the trap's `$?` was 0, so the partial image was kept.

        A trap cannot read the exit status of a run that has not exited. The signal
        handler must record the fact separately, or cleanup concludes success and
        leaves a half-written encrypted image behind.
        """
        code = "\n".join(_code_lines())
        self.assertIn("SIGNALLED=0", code)
        self.assertIn("on_signal()", code)
        self.assertIn("trap on_signal INT TERM", code)
        self.assertIn('[ "$SIGNALLED" = "1" ] && rc=130', code,
                      "cleanup must treat a signal as failure regardless of $?")
        self.assertNotIn("trap cleanup EXIT INT TERM", code,
                         "cleanup must not be the direct signal handler; $? is unreliable there")


class TestTracingCannotLeakThePassphrase(unittest.TestCase):
    """xtrace would echo the pipeline that feeds the passphrase to hdiutil."""

    def test_X1_tracing_is_disabled_before_anything_else(self):
        code = _script_source()
        set_x_at = code.index("\nset +x")
        pass_at = code.index("read_password_twice")
        self.assertLess(set_x_at, pass_at,
                        "tracing must be disabled before the password function is defined")
        self.assertIn("unset BASH_XTRACEFD", code)
        self.assertIn("export -n SHELLOPTS", code)

    def test_X2_the_password_reader_disables_tracing_again(self):
        code = _script_source()
        reader = code.split("read_password_twice() {")[1].split("\n}")[0]
        self.assertTrue(reader.strip(), "password reader not found; vacuous")
        self.assertIn("set +x", reader,
                      "the password reader must disable tracing itself, in case something "
                      "re-enabled it after entry")
        self.assertNotIn("set -x", reader)
