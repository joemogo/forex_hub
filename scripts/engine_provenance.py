#!/usr/bin/env python3
"""Which engine build produced a forward evidence package? (engine-provenance binding)

    python3 scripts/engine_provenance.py --packages <preserved packages JSON> [--repo DIR]
    python3 scripts/engine_provenance.py --artifact-of <index.html>      # hash one engine file

APP_VERSION does not identify a build: several different engines shipped under one version
string. Since the provenance binding, index.html stamps every NEW evidence package with
`engineProvenance.scriptSha256`: the SHA-256 of the page's own inline engine script text, taken
while that script ran. This tool hashes the same text out of every index.html blob in the
repository's history and maps a recorded artefact to the commits that introduced it.

Each package is classified, never guessed:

  BOUND                                the recorded artefact equals the engine text introduced by
                                       EXACTLY ONE commit (`introducingCommit`)
  AMBIGUOUS                            the same engine text was introduced by several commits (a
                                       revert, or an index.html change outside the script): every
                                       candidate is listed and NO single commit is named
  ARTIFACT_OBSERVED_SOURCE_UNMATCHED   an artefact was recorded, but no commit reachable here
                                       carries that exact engine text (a local edit, an unfetched
                                       branch, or a build outside this repository)
  UNKNOWN                              no artefact was recorded: every package captured before the
                                       binding, or one captured where the running script could not
                                       be named. A version string, a timestamp or a count is never
                                       used to fill this in.

What a match does NOT establish, stated on every verdict (`claims`): an artefact hash identifies
engine TEXT. It does not say which commit was deployed, nor which commit's build produced the
package -- any descendant that left index.html untouched carries the same text, and the introducing
commit is only where that text first appeared.

The configuration identity (`configSha256`) is reported as recorded: it is the RUNTIME
configuration, which this tool does not compare with any commit's defaults.

Assumptions, stated rather than hidden: (1) a browser hands an inline script's text to
document.currentScript.textContent exactly as the HTML parser tokenised it -- this tool extracts
the first <script> element without attributes up to its first </script> and normalises CR LF and
lone CR to LF, as HTML input preprocessing does; no real browser is driven here to confirm it.
(2) The packages given are already integrity-verified (forward_capture.sh refuses any whose
contentHash does not re-derive); this tool does not re-verify them. READ-ONLY. NO NETWORK.
"""
import argparse
import collections
import hashlib
import json
import re
import subprocess
import sys

SCRIPT_RE = re.compile(r"<script>([\s\S]*?)</script>")
METHOD = "SHA256_UTF8_INLINE_ENGINE_SCRIPT_TEXT"
#: stated on every verdict that found an artefact: what a hash match can never establish
NOT_CLAIMED = {"deployedCommit": "NOT_ESTABLISHED_BY_ARTIFACT_HASH",
               "producingCommit": "NOT_ESTABLISHED_BY_ARTIFACT_HASH"}


def script_text(index_html):
    """The inline engine script text as the browser presents it, or None."""
    if isinstance(index_html, bytes):
        index_html = index_html.decode("utf-8")
    text = index_html.replace("\r\n", "\n").replace("\r", "\n")
    m = SCRIPT_RE.search(text)
    return m.group(1) if m else None


def artifact_sha256(index_html):
    body = script_text(index_html)
    return None if body is None else hashlib.sha256(body.encode("utf-8")).hexdigest()


def _git(repo, *args, binary=False):
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, check=True)
    return r.stdout if binary else r.stdout.decode()


def history_index(repo):
    """{artifact sha256: [(commit, ISO date), ...]} over every commit reachable from any ref that
    introduced an index.html blob. Each distinct blob is hashed once."""
    # --topo-order: ancestry, not timestamps, orders the commits (timestamps can tie or lie)
    log = _git(repo, "log", "--all", "--topo-order", "--no-abbrev", "--format=C %H %cI", "--raw", "--", "index.html")
    by_blob, commit, seq = collections.defaultdict(list), None, 0
    for line in log.splitlines():
        if line.startswith("C "):
            _, sha, date = line.split(" ", 2)
            seq += 1
            commit = (-seq, sha, date)          # newest first in the log, so -seq sorts oldest first
        elif line.startswith(":") and line.rstrip().endswith("index.html"):
            blob = line.split()[3]
            if set(blob) != {"0"}:
                by_blob[blob].append(commit)
    out = collections.defaultdict(list)
    for blob, commits in by_blob.items():
        art = artifact_sha256(_git(repo, "cat-file", "blob", blob, binary=True))
        if art:
            out[art].extend(commits)
    return {k: [(c, d) for _, c, d in sorted(set(v))] for k, v in out.items()}


def classify(package, index):
    """One package's provenance verdict. Pure given the history index."""
    ep = package.get("engineProvenance") if isinstance(package, dict) else None
    base = {"packageId": (package or {}).get("packageId") if isinstance(package, dict) else None}
    if not isinstance(ep, dict):
        return dict(base, linkage="UNKNOWN", reason="NO_ENGINE_PROVENANCE_RECORDED")
    art = ep.get("scriptSha256")
    if ep.get("method") != METHOD or not isinstance(art, str) or not re.fullmatch(r"[0-9a-f]{64}", art):
        return dict(base, linkage="UNKNOWN", reason="ARTIFACT_NOT_RECORDED", configSha256=ep.get("configSha256"))
    commits = index.get(art, [])
    found = dict(base, scriptSha256=art, configSha256=ep.get("configSha256"), claims=dict(NOT_CLAIMED))
    if not commits:
        return dict(found, linkage="ARTIFACT_OBSERVED_SOURCE_UNMATCHED")
    candidates = [{"commit": c, "date": d} for c, d in commits]
    if len(commits) > 1:
        # several commits introduced this exact engine text: naming any one of them would be a guess
        return dict(found, linkage="AMBIGUOUS", candidateCommits=candidates)
    return dict(found, linkage="BOUND", introducingCommit=commits[0][0], candidateCommits=candidates)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--packages")
    g.add_argument("--artifact-of")
    a = ap.parse_args(argv[1:])
    if a.artifact_of:
        print(artifact_sha256(open(a.artifact_of, "rb").read()) or "NO_INLINE_SCRIPT")
        return 0
    doc = json.load(open(a.packages))
    packages = doc if isinstance(doc, list) else doc.get("packages", list(doc.values()) if isinstance(doc, dict) else [])
    index = history_index(a.repo)
    verdicts = [classify(p, index) for p in packages]
    print(json.dumps({"packages": len(verdicts),
                      "byLinkage": dict(collections.Counter(v["linkage"] for v in verdicts)),
                      "verdicts": verdicts}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
