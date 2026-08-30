#!/usr/bin/env python3
"""Prepare a reviewed upload bundle for the synthetic LEAN engine smoke test.

ONE command, run before an operator uploads anything to QuantConnect. It answers a single
bounded question: *are the bytes about to be uploaded the reviewed, manifest-matching,
locally-validated bytes, taken from a committed tree?*

WHAT IT DOES
  1. Recomputes sha256 for every file in MANIFEST.sha256 and compares. A mismatch, a listed
     file that is missing, or a package file that is present but unlisted, all FAIL.
  2. Records the git commit and whether the package is CLEAN or DIRTY.
  3. Runs the package's own focused local checks (test_synthetic_local.py) and requires exit 0.
  4. Copies exactly the three upload files into a bundle directory under $TMPDIR -- never
     inside the repository -- and stamps BUNDLE.json beside them.

WHAT IT DOES NOT DO, AND CANNOT
  It does not run LEAN. It is not an engine run. The bundle hash proves what was PREPARED
  LOCALLY on this machine and NOTHING about what executed in QuantConnect: no cloud run is
  attested, and a matching hash does not establish that the uploaded project contained these
  bytes or that any backtest ever ran. Only the platform run record can say that.

It writes no tracked file. Refreshing the manifest is a separate, explicit, deliberately
non-green operation (--refresh-manifest), so a stale manifest can never be silently rewritten
and reported as a passing check in the same invocation.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

#: Exactly the files the operator uploads. The CSVs are fetched by LEAN over HTTPS from the
#: pinned gist revision and are deliberately NOT uploaded (see RUN_PROCEDURE.md).
UPLOAD_FILES = ("main.py", "br_machine.py", "synthetic_bars.py")

#: Published fixtures. Hashed from the local copies so the stamp records what the gist
#: revision was published FROM; this reads no network and attests nothing about the gist.
FIXTURE_FILES = ("mogo_synthetic_qualify.csv", "mogo_synthetic_reject.csv")

#: The package's own focused local validation. Not an engine run.
LOCAL_CHECKS = "test_synthetic_local.py"

MANIFEST_NAME = "MANIFEST.sha256"

#: Package files that are intentionally outside the reproduction manifest. Anything else
#: found in the package directory is an unlisted file and FAILS -- silence is not a pass.
#: Files in this directory that are TOOLING, not reproduction inputs.
#:
#: MANIFEST.sha256 covers the files an operator uploads or that LEAN fetches -- the things you
#: need to reproduce the engine run. preflight.py, import_run.py and smoke_log.py prepare and
#: validate that run; they are never uploaded and are not part of what it reproduces, so hashing
#: them into the manifest would make every change to the tooling read as a change to the evidence
#: inputs. RUN_PROCEDURE.md is operator documentation for the same reason.
#:
#: SINGLE SOURCE OF TRUTH. tests/trader_intelligence/test_lean_synthetic_smoke.py imports this
#: tuple rather than keeping its own copy -- two hand-maintained exclusion lists would drift, and
#: the drift would surface as a mystifying manifest failure rather than as an obvious one.
MANIFEST_EXEMPT = (MANIFEST_NAME, "preflight.py", "import_run.py", "smoke_log.py",
                   "RUN_PROCEDURE.md")

#: Subdirectories skipped by the unlisted-file scan (build noise and preserved run records).
SKIP_DIRS = ("__pycache__", "evidence")

DISCLAIMER = (
    "This bundle and its hashes prove ONLY what was PREPARED LOCALLY on this machine. They "
    "prove NOTHING about what executed in QuantConnect: no LEAN engine ran here, no cloud "
    "backtest is attested, and a matching hash does not establish that the uploaded project "
    "contained these bytes or that any backtest was performed. Only the platform run record "
    "(project id, backtest id, algorithm id, LEAN version) can establish that."
)

EXIT_OK = 0
EXIT_MANIFEST = 2
EXIT_REFRESHED = 3
EXIT_DIRTY = 4
EXIT_LOCAL_CHECKS = 5
EXIT_BUNDLE = 6

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- helpers

def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def say(line=""):
    sys.stdout.write(line + "\n")


def parse_manifest(path):
    """Return (entries, header_lines, errors). entries maps filename -> sha256."""
    entries, header, errors = {}, [], []
    if not os.path.isfile(path):
        return entries, header, ["manifest is missing: %s" % path]
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    seen_entry = False
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            if not seen_entry:
                header.append(raw)
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            errors.append("manifest line %d is not '<sha256>  <filename>': %r" % (number, raw))
            continue
        seen_entry = True
        digest, name = parts[0], parts[1].strip()
        if name in entries:
            errors.append("manifest lists %s more than once" % name)
        entries[name] = digest
    return entries, header, errors


def manifest_candidates(package_dir):
    """Every package file that must appear in the manifest."""
    found = []
    for name in sorted(os.listdir(package_dir)):
        full = os.path.join(package_dir, name)
        if os.path.isdir(full):
            continue
        if name.startswith(".") or name in MANIFEST_EXEMPT or name.endswith(".pyc"):
            continue
        found.append(name)
    return found


def check_manifest(package_dir):
    """Recompute every hash. Returns (ok, problems, computed)."""
    path = os.path.join(package_dir, MANIFEST_NAME)
    entries, _header, problems = parse_manifest(path)
    computed = {}
    present = set(manifest_candidates(package_dir))

    for name in sorted(entries):
        full = os.path.join(package_dir, name)
        if not os.path.isfile(full):
            problems.append("MISSING: %s is listed in the manifest but is not on disk" % name)
            continue
        actual = sha256_of(full)
        computed[name] = actual
        if actual != entries[name]:
            problems.append("HASH MISMATCH: %s expected %s got %s"
                            % (name, entries[name], actual))

    for name in sorted(present - set(entries)):
        problems.append("UNLISTED: %s is present in the package but absent from the manifest"
                        % name)

    if not entries and not problems:
        problems.append("the manifest lists no files at all")

    return (not problems), problems, computed


def refresh_manifest(package_dir):
    """Rewrite MANIFEST.sha256 from what is on disk. Deliberately never a passing run."""
    path = os.path.join(package_dir, MANIFEST_NAME)
    _entries, header, _errors = parse_manifest(path)
    if not header:
        header = ["# SHA-256 manifest -- MOGO synthetic LEAN engine smoke test", "#"]
    names = manifest_candidates(package_dir)
    lines = list(header)
    if lines and lines[-1].strip():
        lines.append("")
    for name in names:
        lines.append("%s  %s" % (sha256_of(os.path.join(package_dir, name)), name))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path, names


def git_state(repo_root, package_dir):
    """(commit, tree_state, dirty_paths, note). Fails closed: unknown git state is DIRTY."""

    def git(*args):
        return subprocess.run(("git", "-C", repo_root) + args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True)

    head = git("rev-parse", "HEAD")
    if head.returncode != 0:
        return (None, "DIRTY", [],
                "git could not resolve HEAD (%s); treated as DIRTY, fail closed"
                % (head.stderr.strip().splitlines() or ["no detail"])[0])
    commit = head.stdout.strip()

    # Scoped to the package: a change anywhere else in the repo does not invalidate these
    # bytes, and scoping also keeps the scan away from unrelated directories.
    status = git("status", "--porcelain", "--", package_dir)
    if status.returncode != 0:
        return (commit, "DIRTY", [],
                "git status failed (%s); treated as DIRTY, fail closed"
                % (status.stderr.strip().splitlines() or ["no detail"])[0])
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    return (commit, "DIRTY" if dirty else "CLEAN", dirty, "")


def pinned_gist_revision(package_dir):
    """(revision, gist_id, problems) read out of main.py's pinned URLs."""
    problems = []
    with open(os.path.join(package_dir, "main.py"), encoding="utf-8") as handle:
        source = handle.read()
    revisions = re.findall(r"/raw/([0-9a-f]{40})/", source)
    gists = re.findall(r"gist\.githubusercontent\.com/[^/]+/([0-9a-f]{32})/", source)
    if not revisions:
        problems.append("main.py has no REVISION-PINNED gist URL "
                        "(a mutable /raw/ link carries no revision sha)")
    elif len(set(revisions)) != 1:
        problems.append("main.py pins more than one gist revision: %s"
                        % ", ".join(sorted(set(revisions))))
    return ((revisions[0] if revisions else None),
            (gists[0] if gists else None),
            problems)


def run_local_checks(package_dir):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"     # leave no __pycache__ behind in the package
    proc = subprocess.run([sys.executable, os.path.join(package_dir, LOCAL_CHECKS)],
                          cwd=package_dir, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout


def default_out_dir():
    base = os.environ.get("TMPDIR") or "/tmp"
    return os.path.join(base, "mogo-lean-synthetic-bundle")


# --------------------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Prepare (and only prepare) the synthetic LEAN upload bundle.")
    parser.add_argument("--package-dir", default=HERE,
                        help="the tests/lean_synthetic package (default: this file's dir)")
    parser.add_argument("--repo-root", default=None,
                        help="git repository root (default: two levels above the package)")
    parser.add_argument("--out", default=None,
                        help="bundle output directory (default: $TMPDIR/mogo-lean-synthetic-bundle)")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="produce a DIRTY-stamped bundle for LOCAL INSPECTION ONLY; "
                             "never for an approved cloud run")
    parser.add_argument("--refresh-manifest", action="store_true",
                        help="rewrite MANIFEST.sha256 from disk, then exit nonzero for review")
    args = parser.parse_args(argv)

    package_dir = os.path.abspath(args.package_dir)
    repo_root = os.path.abspath(args.repo_root) if args.repo_root else \
        os.path.abspath(os.path.join(package_dir, "..", ".."))
    out_dir = os.path.abspath(args.out) if args.out else default_out_dir()

    say("PREFLIGHT synthetic LEAN upload bundle")
    say("PREFLIGHT package   %s" % package_dir)
    say("PREFLIGHT repo      %s" % repo_root)

    if not os.path.isdir(package_dir):
        say("PREFLIGHT VERDICT FAIL -- package directory does not exist")
        return EXIT_BUNDLE

    # ---- refresh is a separate operation, and is never green -------------------------
    if args.refresh_manifest:
        path, names = refresh_manifest(package_dir)
        say("PREFLIGHT REFRESHED %s (%d file(s))" % (path, len(names)))
        for name in names:
            say("PREFLIGHT   listed  %s" % name)
        say("PREFLIGHT VERDICT NOT-CHECKED -- the manifest was REWRITTEN from whatever is on")
        say("PREFLIGHT   disk. That is a change, not a check: nothing was validated in this")
        say("PREFLIGHT   run and no bundle was produced. Review the diff, commit it if it is")
        say("PREFLIGHT   what you intended, then re-run preflight without --refresh-manifest.")
        say("PREFLIGHT NOTE %s" % DISCLAIMER)
        return EXIT_REFRESHED

    # ---- 1. manifest ------------------------------------------------------------------
    ok, problems, computed = check_manifest(package_dir)
    if not ok:
        for problem in problems:
            say("PREFLIGHT MANIFEST %s" % problem)
        say("PREFLIGHT VERDICT FAIL -- manifest validation failed (%d problem(s)). No bundle "
            "was produced." % len(problems))
        say("PREFLIGHT   A file needed to reproduce the run must be LISTED: run "
            "--refresh-manifest, review the diff and commit it. A local tool or scratch file "
            "belongs outside the package directory instead.")
        return EXIT_MANIFEST
    say("PREFLIGHT MANIFEST OK -- %d file(s) re-hashed and matching" % len(computed))

    missing = [name for name in UPLOAD_FILES + FIXTURE_FILES
               if not os.path.isfile(os.path.join(package_dir, name))]
    if missing:
        say("PREFLIGHT VERDICT FAIL -- required file(s) absent: %s" % ", ".join(missing))
        return EXIT_MANIFEST

    # ---- 2. git state -----------------------------------------------------------------
    commit, tree_state, dirty_paths, note = git_state(repo_root, package_dir)
    say("PREFLIGHT GIT commit=%s tree=%s" % (commit or "UNKNOWN", tree_state))
    if note:
        say("PREFLIGHT GIT %s" % note)
    for line in dirty_paths:
        say("PREFLIGHT GIT dirty  %s" % line)

    if tree_state == "DIRTY" and not args.allow_dirty:
        say("PREFLIGHT VERDICT FAIL -- the package tree is DIRTY. An approved cloud run must "
            "upload bytes that exist in a commit, so that what ran can be identified later.")
        say("PREFLIGHT   Commit (or revert) the changes above and re-run, or pass "
            "--allow-dirty to build a DIRTY-stamped bundle for LOCAL INSPECTION ONLY.")
        return EXIT_DIRTY

    # ---- 3. the package's own local checks --------------------------------------------
    code, output = run_local_checks(package_dir)
    if code != 0:
        sys.stdout.write(output)
        say("PREFLIGHT VERDICT FAIL -- %s exited %d. No bundle was produced."
            % (LOCAL_CHECKS, code))
        return EXIT_LOCAL_CHECKS
    say("PREFLIGHT LOCAL-CHECKS PASS -- %s exited 0 (NOT an engine run)" % LOCAL_CHECKS)

    # ---- 4. pinned gist revision -------------------------------------------------------
    revision, gist_id, gist_problems = pinned_gist_revision(package_dir)
    if gist_problems:
        for problem in gist_problems:
            say("PREFLIGHT GIST %s" % problem)
        say("PREFLIGHT VERDICT FAIL -- fixture URLs are not revision-pinned. No bundle.")
        return EXIT_BUNDLE
    say("PREFLIGHT GIST revision=%s id=%s" % (revision, gist_id))

    # ---- 5. the bundle, outside the repository ----------------------------------------
    if os.path.commonpath([out_dir, repo_root]) == repo_root:
        say("PREFLIGHT VERDICT FAIL -- refusing to write the bundle inside the repository "
            "(%s). Bundles belong under $TMPDIR." % out_dir)
        return EXIT_BUNDLE

    upload = {name: {"sha256": computed.get(name) or sha256_of(os.path.join(package_dir, name)),
                     "bytes": os.path.getsize(os.path.join(package_dir, name))}
              for name in UPLOAD_FILES}
    fixtures = {name: {"sha256": computed.get(name) or sha256_of(os.path.join(package_dir, name)),
                       "bytes": os.path.getsize(os.path.join(package_dir, name))}
                for name in FIXTURE_FILES}

    fingerprint = hashlib.sha256(
        "\n".join("%s %s" % (name, upload[name]["sha256"])
                  for name in sorted(upload)).encode("utf-8")).hexdigest()

    stamp = {
        "bundleKind": "mogo-lean-synthetic-upload",
        "preparedAtUtc": datetime.datetime.now(datetime.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "preparedBy": "tests/lean_synthetic/preflight.py",
        "treeState": tree_state,
        "gitCommit": commit,
        "gitDirtyEntries": dirty_paths,
        "uploadFiles": upload,
        "publishedFixtures": fixtures,
        "pinnedGistRevision": revision,
        "pinnedGistId": gist_id,
        "manifest": {"file": MANIFEST_NAME, "filesChecked": len(computed), "result": "MATCH"},
        "localChecks": {"file": LOCAL_CHECKS, "exitCode": code, "result": "PASS",
                        "isEngineRun": False},
        "uploadFingerprintSha256": fingerprint,
        "provesLocalPreparationOnly": True,
        "provesQuantConnectExecution": False,
        "disclaimer": DISCLAIMER,
    }

    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    for name in UPLOAD_FILES:
        shutil.copyfile(os.path.join(package_dir, name), os.path.join(out_dir, name))
    with open(os.path.join(out_dir, "BUNDLE.json"), "w", encoding="utf-8") as handle:
        json.dump(stamp, handle, indent=2, sort_keys=True)
        handle.write("\n")

    say("PREFLIGHT BUNDLE %s" % out_dir)
    for name in UPLOAD_FILES:
        say("PREFLIGHT   upload  %s  %s" % (upload[name]["sha256"][:16], name))
    say("PREFLIGHT   stamp   BUNDLE.json")
    say("PREFLIGHT   fingerprint %s" % fingerprint)
    if tree_state == "DIRTY":
        say("PREFLIGHT VERDICT DIRTY-BUNDLE -- built under --allow-dirty for LOCAL INSPECTION "
            "ONLY. Do NOT upload it for an approved cloud run.")
    else:
        say("PREFLIGHT VERDICT READY -- upload exactly these three files; the CSVs are fetched "
            "by LEAN from the pinned gist revision and must NOT be uploaded.")
    say("PREFLIGHT NOTE %s" % DISCLAIMER)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
