#!/usr/bin/env python3
"""MOGO Automation Platform -- where research content is allowed to be written.

MOGO-017 Step 2B.

THE PROBLEM THIS EXISTS TO SOLVE

    `research.ingest.local-artifact.v1` resolved its intake and corpus roots from
    two module-level constants derived from __file__. They were not overridable,
    so a test that exercised the REAL ingestion path would write a synthetic
    artifact into the GENUINE research corpus. The MOGO-017 Step 1 audit named
    that as the largest contamination risk in the milestone, and Step 2B closes
    it before any change-detection fixture is written.

WHAT THIS IS

    One value object naming the two roots, and two ways to obtain one:

        production_corpus()          the real roots. The default. Unchanged.
        sandbox_corpus(a, b)         test-owned roots, VALIDATED (see below).

    That is the whole module. It is dependency injection, not global mutation:
    nothing here holds mutable state, there is no "current corpus" to set, no
    environment variable is read, and no production caller passes anything -- so
    production behaviour is byte-identical to before by construction rather than
    by convention.

WHY AN ENVIRONMENT VARIABLE WAS DELIBERATELY NOT USED

    `MOGO_RUNTIME_STATE_ROOT` exists and is right for runtime state, which is
    ephemeral, git-ignored and rebuildable. The research corpus is none of those:
    it is committed scientific evidence. An environment variable that silently
    redirects where evidence is written is a variable that can silently redirect
    where evidence is written -- including in production, including by accident.
    A caller that wants a different corpus must say so in code, at the call site.

FAIL CLOSED, AND IN THE DIRECTION THAT MATTERS

    The dangerous mistake is not "a test wrote somewhere odd". It is "a test
    wrote into the real corpus while believing it was sandboxed". So
    sandbox_corpus() REFUSES any root that is, contains, or is contained by
    either production root -- compared through os.path.realpath, so `..` and a
    planted symlink are defeated too. A sandbox that overlaps the genuine corpus
    cannot be constructed, which is what makes contamination impossible by
    construction rather than by remembering.
"""

import os

from . import errors as runtime_errors  # noqa: E402

# Repository-relative, resolved from this file. runtime/ -> mogo_platform -> src
# -> platform -> repository root is four levels up. No absolute literal appears
# in this module, which the platform boundary suite enforces for every runtime
# module.
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))

PRODUCTION_INTAKE_ROOT = os.path.join(
    REPO_ROOT, "docs", "trader-intelligence", "intake")
PRODUCTION_ARTIFACT_ROOT = os.path.join(
    REPO_ROOT, "docs", "trader-intelligence", "research-artifacts")


class ResearchCorpus(object):
    """The two locations research content may occupy. Immutable by intent.

    `production` is carried on the object rather than inferred by comparing
    paths at each use, so a reader can always tell which corpus an object names
    without re-deriving the answer.
    """

    __slots__ = ("intakeRoot", "artifactRoot", "production")

    def __init__(self, intake_root, artifact_root, production):
        # Explicit assignment, never setattr() in a loop: the platform boundary
        # suite forbids dynamic attribute writes in the runtime, and is right to.
        self.intakeRoot = intake_root
        self.artifactRoot = artifact_root
        self.production = production

    def __repr__(self):
        return ("ResearchCorpus(intakeRoot=%r, artifactRoot=%r, production=%r)"
                % (self.intakeRoot, self.artifactRoot, self.production))


def production_corpus():
    """The genuine research corpus. What every production call path uses."""
    return ResearchCorpus(PRODUCTION_INTAKE_ROOT, PRODUCTION_ARTIFACT_ROOT, True)


def _overlaps(candidate, protected):
    """True when the two paths are the same, or either contains the other.

    realpath on both sides, so `..` traversal and a symlink planted inside a
    temporary directory cannot be used to reach the protected tree.
    """
    a = os.path.realpath(os.path.abspath(candidate))
    b = os.path.realpath(os.path.abspath(protected))
    if a == b:
        return True
    return a.startswith(b + os.sep) or b.startswith(a + os.sep)


def _validate_sandbox_root(candidate, label):
    if not isinstance(candidate, str) or not candidate.strip():
        runtime_errors.fail(
            "sandbox %s must be a non-empty path" % (label,),
            runtime_errors.ContractValidationError)
    if not os.path.isabs(candidate):
        runtime_errors.fail(
            "sandbox %s must be an absolute path, got %r. A relative sandbox "
            "root resolves against whatever the caller's working directory "
            "happens to be, which is exactly how a test reaches the real corpus "
            "by accident" % (label, candidate),
            runtime_errors.ContractValidationError)
    for protected, name in ((PRODUCTION_INTAKE_ROOT, "intake"),
                            (PRODUCTION_ARTIFACT_ROOT, "research-artifacts")):
        if _overlaps(candidate, protected):
            runtime_errors.fail(
                "sandbox %s %r overlaps the genuine research %s root %r. A "
                "sandbox that can reach the real corpus is not a sandbox, and "
                "constructing one is refused rather than trusted"
                % (label, candidate, name, protected),
                runtime_errors.PathEscapeError)
    return candidate


def sandbox_corpus(intake_root, artifact_root):
    """A test-owned corpus. Refused unless it CANNOT reach the genuine one.

    Both roots are validated independently, so a caller cannot sandbox one and
    quietly leave the other pointing at real evidence.
    """
    _validate_sandbox_root(intake_root, "intakeRoot")
    _validate_sandbox_root(artifact_root, "artifactRoot")
    if _overlaps(intake_root, artifact_root):
        runtime_errors.fail(
            "sandbox intakeRoot %r and artifactRoot %r overlap; ingestion reads "
            "one and writes the other, and collapsing them would let a written "
            "artifact be re-read as its own input"
            % (intake_root, artifact_root),
            runtime_errors.ContractValidationError)
    return ResearchCorpus(os.path.abspath(intake_root),
                          os.path.abspath(artifact_root), False)


def resolve_corpus(corpus):
    """The corpus a caller supplied, or the production one when it supplied none.

    The single place the default is applied, so `corpus=None` means exactly one
    thing everywhere and no call site can invent a different fallback.
    """
    if corpus is None:
        return production_corpus()
    if not isinstance(corpus, ResearchCorpus):
        runtime_errors.fail(
            "corpus must be a ResearchCorpus, got %s" % (type(corpus).__name__,),
            runtime_errors.ContractValidationError)
    return corpus
