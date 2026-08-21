#!/usr/bin/env python3
"""PROGRAM-006 Phase 1A -- Evidence Intelligence Engine integrity validator
(ADR-008, Deliverable 11).

Pure Python standard library. NO NETWORK ACCESS. Strictly read-only against
every evidence record and (optionally) the built Knowledge Graph -- this
module never edits, corrects, or deletes anything. It only ever reports.

Mirrors validate_graph.py's report shape (one wrapper document embedding a
findings array) per evidence-integrity-report.schema.json, rather than
introducing a redundant standalone IntegrityFinding entity type.
"""
import argparse
import glob as globmod
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc            # noqa: E402
import evidence_common as evc        # noqa: E402
import evidence_confidence as conf   # noqa: E402
import trade_observation as to       # noqa: E402
import research_assimilation as _assimilation  # noqa: E402
from import_mogo_observations import (CAPTURE_BASIS_SOURCE_TYPE,  # noqa: E402
                                      is_developer_test_package)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
EVIDENCE_ROOT = os.path.join(TI_ROOT, "evidence")


def _load_dir(dir_path, id_field):
    records = []
    if not os.path.isdir(dir_path):
        return records
    for path in sorted(globmod.glob(os.path.join(dir_path, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            record = json.load(f)
        records.append(record)
    return records


def _check_missing_artifact(findings, source, rel, sources_by_id, now):
    """A repository source whose artifact is gone -- resolvable, or not.

    A missing artifact is not always lost evidence. The real case (B-28): a DRY RUN
    wrote a capture file, a source was registered for it, the dry-run cleanup deleted
    the file, and the --write run 27 seconds later produced a BYTE-IDENTICAL artifact
    registered under a different sourceId. The observation citing the first source is
    undamaged and its evidence demonstrably survives -- at another path.

    Recording that with `artifactSupersededBy` keeps provenance walkable without
    rewriting anything: the original repositoryPath still says what this source
    described, and the supersession is a new fact ABOUT the record.

    But a supersession field is also a new way to LAUNDER broken provenance -- point a
    dangling source at any healthy one and the warning disappears. So the claim is
    never taken at its word. It resolves only when the named source exists, ITS artifact
    exists, and the two contentHashes are equal, which is what makes "the same artifact
    survives elsewhere" a checkable fact rather than an assertion.

    A supersession that fails any of those is an ERROR, not a warning, and deliberately
    louder than the plain missing artifact it replaced: a dangling path is a visible
    gap, while a false supersession is a gap wearing a resolution.
    """
    superseded_by = source.get("artifactSupersededBy")
    if not superseded_by:
        _finding(findings, "UNRESOLVABLE_ARTIFACT", "WARNING", "EVIDENCE_SOURCE",
                  source["sourceId"],
                  "repositoryPath %r does not exist, so this source cannot be "
                  "walked back to the artifact it describes." % (rel,), now)
        return

    target = sources_by_id.get(superseded_by)
    if target is None:
        _finding(findings, "UNVERIFIED_SUPERSESSION", "ERROR", "EVIDENCE_SOURCE",
                  source["sourceId"],
                  "artifactSupersededBy names %r, which is not a registered "
                  "EvidenceSource." % (superseded_by,), now)
        return

    target_rel = target.get("repositoryPath")
    if not target_rel or not os.path.exists(os.path.join(REPO_ROOT, target_rel)):
        _finding(findings, "UNVERIFIED_SUPERSESSION", "ERROR", "EVIDENCE_SOURCE",
                  source["sourceId"],
                  "artifactSupersededBy names %s, whose own artifact %r is missing -- "
                  "the supersession resolves to nothing."
                  % (superseded_by, target_rel), now)
        return

    own_hash = source.get("contentHash")
    target_hash = target.get("contentHash")
    if not own_hash or not target_hash or own_hash != target_hash:
        _finding(findings, "UNVERIFIED_SUPERSESSION", "ERROR", "EVIDENCE_SOURCE",
                  source["sourceId"],
                  "artifactSupersededBy names %s, but the contentHashes differ (%s vs "
                  "%s), so the surviving artifact is NOT the one this source described."
                  % (superseded_by, (own_hash or "unset")[:12],
                     (target_hash or "unset")[:12]), now)
        return
    # Resolved: identical content exists at a recorded path. No finding.


def _finding(findings, finding_type, severity, entity_type, entity_id, message, now, metadata=None):
    findings.append({
        "findingId": "EVF%04d" % (len(findings) + 1),
        "severity": severity,
        "findingType": finding_type,
        "entityType": entity_type,
        "entityId": entity_id,
        "message": message,
        "detectedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resolutionStatus": "open",
        "resolutionNotes": None,
        "metadata": metadata or {},
    })


# ---------------------------------------------------------------------------
# 1. Orphans (ORPHANED_EVIDENCE / ORPHANED_LINK / ORPHANED_CLAIM)
# ---------------------------------------------------------------------------

#: The importer stamps "captureBasis=<basis> sourceType=<type>" into notes at mint
#: time. That string is the only record of what the source was WHEN the observation
#: was created, which is what makes the rebinding check possible. Deliberately
#: tolerant of spacing and case: a stamp written "sourceType = X" must be READ, not
#: missed -- a stamp the reader skips is a stamp an attacker can hide behind.
#: Assimilation ledger -- the committed record of every corpus transition.
#: Every sourceType that derives a population. Deliberately built from
#: trade_observation's own tuples so a new population type cannot be added
#: there and forgotten here.
_POPULATION_BEARING_SOURCE_TYPES = (set(to.HISTORICAL_SOURCE_TYPES)
                                   | set(to.FORWARD_SOURCE_TYPES)
                                   | set(to.RECONSTRUCTED_SOURCE_TYPES))

_LEDGER_DIR = os.path.join(REPO_ROOT, "docs", "trader-intelligence",
                           "research-state", "ledger")

_MINTED_SOURCE_TYPE_RE = re.compile(r"sourceType\s*=\s*([A-Za-z_-]*)", re.IGNORECASE)

#: The SECOND stamp in the same notes string, and it was being discarded.
#: `captureBasis` records HOW the observation was captured -- REPLAY_RUN,
#: LIVE_CLOSE, HISTORICAL_BACKFILL -- and maps 1:1 onto the expected sourceType
#: via the importer's own table. Measured across all 259 preserved records:
#: 221 REPLAY_RUN -> HISTORICAL, 29 LIVE_CLOSE -> FORWARD, 9 HISTORICAL_BACKFILL
#: -> RECONSTRUCTED, zero missing, zero contradictions.
#: Deliberately SYMMETRIC with _MINTED_SOURCE_TYPE_RE, including the character
#: class. `[A-Za-z_]+` truncated "REPLAY-RUN" to "REPLAY", which maps to nothing
#: and silently no-opped -- so a mangled stamp was indistinguishable from an
#: unknown one, and one hyphen defeated the check.
_CAPTURE_BASIS_RE = re.compile(r"captureBasis\s*=\s*([A-Za-z_-]*)", re.IGNORECASE)


def check_source_capture_basis_agrees_with_type(sources, findings, now):
    """A THIRD stamp, on the source record itself, that nothing was reading.

    Both stamps the rebinding check uses live in one field of one record -- the
    observation's `notes` -- so a rewrite thorough enough to change both defeats
    them together. Adversarial verification did exactly that, and also retyped a
    source IN PLACE, which needs no observation edit at all.

    `EvidenceSource.metadata.captureBasis` is written by the importer and, until
    now, never read back. It sits on the OTHER record, so no edit to an observation
    can reach it, and it maps onto `sourceType` through the importer's own table.
    Measured on the live corpus: 47 of 59 sources carry it -- 33 REPLAY_RUN ->
    replay_observation, 13 LIVE_CLOSE -> paper_trade, 1 HISTORICAL_BACKFILL ->
    journal_entry -- with zero disagreements, so this costs no false positives.

    Sources that BEAR A POPULATION must carry the stamp; the rest are not reported.
    An earlier version of this paragraph said "sources without the stamp are NOT
    reported: 12 predate it" -- false twice over. The 12 are all `transcript`
    sources, which the importer never stamps and no observation cites; they do not
    "predate" anything. And leaving the stamp optional let any source shed this
    anchor by deleting one field. What remains true, and is why an exemption exists
    at all, is that inventing a capture basis for a record that never recorded one
    would be the fabrication this layer exists to prevent -- so unstamped
    non-population-bearing sources stay silent.
    """
    for source in sources:
        metadata = source.get("metadata")
        # A non-dict `metadata` raised AttributeError and aborted the whole run.
        basis = metadata.get("captureBasis") if isinstance(metadata, dict) else None
        if not isinstance(basis, str) or not basis.strip():
            # Skipping ANY unstamped source was justified in this docstring as "12
            # predate it". That was wrong: the 12 are all `transcript` sources, which
            # the importer never stamps and which no observation cites. The types the
            # importer DOES produce always carry it, so requiring it there costs zero
            # false positives -- and leaving it optional let a source shed this anchor
            # by deleting one field, exactly as the engineStrategyId branch did.
            # POPULATION-BEARING types, not "types the importer produces". Those are
            # different sets: `generated_analysis` (HISTORICAL) and
            # `live_trade_review` (FORWARD) bear a population and are not importer
            # outputs, so retyping a source to one of them and deleting the stamp shed
            # this anchor entirely -- the very evasion this branch was added to close.
            if source.get("sourceType") in _POPULATION_BEARING_SOURCE_TYPES:
                _finding(findings, "MISSING_SOURCE_CAPTURE_BASIS", "ERROR",
                          "EVIDENCE_SOURCE", source.get("sourceId"),
                          "A %r source records no metadata.captureBasis, so its type "
                          "cannot be cross-checked against how it was captured."
                          % (source.get("sourceType"),), now)
            continue
        expected = CAPTURE_BASIS_SOURCE_TYPE.get(basis.strip().upper())
        actual = source.get("sourceType")
        if actual and expected is None:
            # FAILS CLOSED, mirroring the observation side. Without this the same
            # one-hyphen defect repaired there survived here: "REPLAY-RUN", a
            # trailing space, or an unknown basis all made the anchor silently
            # no-op, so retyping a source in place went unreported.
            _finding(findings, "UNRECOGNISED_CAPTURE_BASIS", "ERROR", "EVIDENCE_SOURCE",
                      source.get("sourceId"),
                      "metadata.captureBasis=%r is not one the importer produces (%s), "
                      "so this source's type cannot be cross-checked against it."
                      % (basis, ", ".join(sorted(CAPTURE_BASIS_SOURCE_TYPE))), now)
        elif expected and actual and expected != actual:
            _finding(findings, "SOURCE_TYPE_CONTRADICTS_CAPTURE_BASIS", "ERROR",
                      "EVIDENCE_SOURCE", source.get("sourceId"),
                      "Source records metadata.captureBasis=%s, which the importer "
                      "captures as %r, but its sourceType is %r. Population is derived "
                      "from sourceType, so retyping a source in place moves every "
                      "observation citing it between populations."
                      % (basis, expected, actual), now)


#: Every artifact and field the corpus-integrity gates read. Declared as a TABLE so
#: availability is one invariant instead of a `return` inside each check -- see
#: check_corpus_anchors_are_available for why that distinction is the whole point.
CORPUS_ANCHORS = (
    ("research-state/current-state.json", "file"),
    ("current-state.json:observationTotal", "int"),
    ("current-state.json:corpusFingerprint", "str"),
    ("research-state/ledger/", "non-empty directory"),
    ("evidence/ledger-preservation/", "non-empty directory"),
    ("ledger-preservation:identities", "non-empty list of objects"),
)


def check_preserved_identities_still_present(observations, findings, now,
                                             preservation_dir=None):
    """Every trade identity ever preserved must still BE in the corpus.

    THE FIFTH CATEGORY, and the one every previous anchor is blind to by
    construction. Append-only has been enforced in AGGREGATE -- a cardinality, plus
    a whole-corpus hash pinned in a file the same actor can rewrite -- and never per
    IDENTITY. No gate asked which observations have existed. So any
    cardinality-preserving substitution was invisible:

      * delete the 21 losing forward trades, pad with 21 copies of a winner, and
        recompute `corpusFingerprint` -- count stays 259, ledger untouched, exit 0;
      * or skip the forgery entirely and run `research_assimilation.py --write`,
        which re-stamps the fingerprint from whatever is on disk. One documented
        maintenance command, no file hand-edited, and the ledger diff shows a normal
        append with an intact chain because the official tool wrote it.

    Forward mean R moved from -0.18 to +2.00 in both, with every gate green.

    The anchor was already on disk, committed, and read by nothing but its own
    writer: `evidence/ledger-preservation/` records the PAPER account's closed
    trades by `tradeId`, and a preserved trade's id is the observation's
    `sequenceId`. Measured on the live corpus: 39 identities, 35 present, and the 4
    absent are all `AGT|TEST|` developer trades the importer refuses by policy --
    which the manifest itself counts as `closedDeveloperTest: 4`. So requiring every
    NON-developer identity costs zero false positives today.

    Crucially it survives the laundering path, because `research_assimilation` never
    touches this file. An aggregate anchor can be recomputed from the tampered
    corpus; a per-identity manifest cannot, because it records what was there
    BEFORE.

    Developer trades are excluded using the importer's own predicate, so the two
    cannot drift about what a developer trade is (B-31).
    """
    if not preservation_dir or not os.path.isdir(preservation_dir):
        return
    present = {obs.get("sequenceId") for obs in observations
               if isinstance(obs.get("sequenceId"), str)}
    recorded = set()
    saw_manifest = False
    for path in sorted(globmod.glob(os.path.join(preservation_dir, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (ValueError, OSError):
            _finding(findings, "UNREADABLE_PRESERVED_IDENTITIES", "ERROR",
                      "TRADE_OBSERVATION", os.path.basename(path),
                      "A preserved-identity manifest cannot be read, so the trades it "
                      "records cannot be confirmed still present.", now)
            continue
        if not isinstance(manifest, dict):
            continue
        saw_manifest = True
        for row in manifest.get("identities") or []:
            if not isinstance(row, dict):
                continue
            trade_id = row.get("tradeId")
            if not isinstance(trade_id, str) or not trade_id:
                continue
            # Prefers the flag RECORDED AT CAPTURE TIME. The importer reads three
            # markers and a manifest row carries no position object, so re-deriving
            # this from the id alone sees one of three -- a developer trade without
            # the `AGT|TEST|` prefix would be required forever and never satisfiable,
            # because the importer refuses it and the manifest is append-only. The
            # docstring claimed the two "cannot drift"; two of three markers were
            # structurally unreachable. Rows written before the flag existed fall back
            # to the prefix, which is all they carry.
            refused = row.get("refusedByImportPolicy")
            if refused is True:
                continue
            if refused is None and is_developer_test_package({"sourceTradeId": trade_id}):
                continue
            recorded.add(trade_id)
            if trade_id not in present:
                _finding(findings, "PRESERVED_IDENTITY_MISSING", "ERROR",
                          "TRADE_OBSERVATION", trade_id,
                          "Trade %s was preserved in %s (pnl %s) but no observation "
                          "carries it as a sequenceId. A preserved trade cannot stop "
                          "existing -- and a substitution that keeps the corpus the "
                          "same size is invisible to every count-based check."
                          % (trade_id, os.path.basename(path), row.get("pnl")), now)

    # THE OTHER DIRECTION, and it only became askable once coverage was continuous.
    #
    # Everything above asks "did something disappear". Nothing asked "did something
    # APPEAR that was never observed" -- so appending a source and 200 invented
    # winning observations with fresh ids moved forward mean R from -0.18 to +1.72
    # with every gate green and every preserved identity still present. Growth is
    # what append-only expects, and a require-list cannot tell invented growth from
    # real growth. Only an allow-list can, and an allow-list needs a manifest that
    # covers the whole corpus -- which is why this is enabled now and could not have
    # been before (B-32.15).
    #
    # The pipeline updates the manifest BEFORE it imports, so any observation minted
    # from a captured package is already anchored by the time it exists. An
    # observation whose identity appears in no manifest was therefore not minted from
    # a captured package.
    if saw_manifest and recorded:
        for obs in observations:
            sequence_id = obs.get("sequenceId")
            if not isinstance(sequence_id, str) or not sequence_id:
                # FAILS CLOSED. This skipped, on the stated grounds that "absence is
                # reported by the sequence-id checks" -- and no such check exists:
                # `sequenceId` is read in exactly two places and BOTH skip a
                # non-string. So deleting one key per fabricated record walked 200
                # invented winners straight past the allow-list, forward mean R
                # -0.18 to +2.60 -- and a test of mine asserted that was correct.
                #
                # The shape is documented verbatim earlier in this same file, for
                # this same field, in the docstring explaining why `sequenceId` was
                # abandoned as an anchor. The gate written after that comment
                # reproduced it.
                _finding(findings, "UNANCHORED_OBSERVATION", "ERROR",
                          "TRADE_OBSERVATION", obs.get("observationId"),
                          "Observation carries sequenceId %r, so it can be tied to no "
                          "captured trade. An observation anchored by nothing was not "
                          "minted from a captured package." % (sequence_id,), now)
                continue
            if sequence_id in recorded:
                continue
            _finding(findings, "UNANCHORED_OBSERVATION", "ERROR", "TRADE_OBSERVATION",
                      obs.get("observationId"),
                      "Observation carries sequenceId %s, which appears in no "
                      "preserved-identity manifest. Every trade MOGO captured is "
                      "recorded before it is imported, so an observation anchored by "
                      "nothing was not minted from a captured package."
                      % (sequence_id,), now)


def _check_preservation_anchor(preservation_dir, report):
    # THE PRESERVATION MANIFEST IS AN ANCHOR AND WAS NOT IN THIS TABLE.
    #
    # The identity gate opened with `if not preservation_dir ... : return` -- the
    # exact shape rounds 9-12 spent four rounds eliminating, reintroduced in the
    # commit that cited the lesson. Eleven one-touch bypasses followed: remove the
    # directory, empty it, rename the extension, move it into a subdirectory, make
    # the document `null` or a list, rename `identities`, or re-prefix every tradeId
    # `AGT|TEST|`. Each restored full exit-0 substitution. A test of mine asserted
    # the first of them was correct behaviour.
    #
    # Availability belongs here, once, like every other anchor -- which is what the
    # comment at the top of this table already said.
    if not preservation_dir or not os.path.isdir(preservation_dir):
        report("evidence/ledger-preservation/", "absent")
    else:
        manifests = globmod.glob(os.path.join(preservation_dir, "*.json"))
        if not manifests:
            report("evidence/ledger-preservation/", "empty")
        else:
            identities = 0
            for path in sorted(manifests):
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        manifest = json.load(handle)
                except (ValueError, OSError):
                    report("evidence/ledger-preservation/",
                           "unreadable (%s)" % os.path.basename(path))
                    continue
                if not isinstance(manifest, dict):
                    report("evidence/ledger-preservation/",
                           "not a JSON object in %s (%s)"
                           % (os.path.basename(path), type(manifest).__name__))
                    continue
                rows = manifest.get("identities")
                if not isinstance(rows, list):
                    report("ledger-preservation:identities",
                           "absent or not a list in %s" % os.path.basename(path))
                    continue
                # Counts only identities the gate will actually REQUIRE, i.e. the
                # non-developer ones. Counting all of them left a bypass: re-prefix
                # every tradeId `AGT|TEST|` and the manifest is still "non-empty"
                # while the gate excludes every row, so it requires nothing. An
                # anchor that requires nothing is an anchor that is not there.
                identities += sum(
                    1 for r in rows
                    if isinstance(r, dict) and isinstance(r.get("tradeId"), str)
                    and r["tradeId"]
                    and not is_developer_test_package({"sourceTradeId": r["tradeId"]}))
            if identities == 0 and manifests:
                report("ledger-preservation:identities",
                       "no requirable trade identities in any manifest (every row is "
                       "absent, malformed, or a developer test trade)")


def check_corpus_anchors_are_available(observations, findings, now,
                                       state_path=None, ledger_dir=None,
                                       preservation_dir=None, sources=None):
    """Every anchor the corpus-integrity gates depend on must BE THERE.

    Rounds 9, 10, 11 and 12 each repaired one instance of a single shape: a gate
    that returns silently when the thing it reads is missing. Each repair closed the
    instance in front of it -- the ledger was unread, then the ledger was deletable,
    then the state FILE was deletable -- and each time the next round found the next
    door. Round 12's were: keep the state file but delete the `observationTotal`
    KEY, and delete the ledger DIRECTORY. Two edits, pure `rm` of the 21 losing
    forward observations, mean R -0.18 to +2.01, exit 0.

    Patching the fifth door would have been the fifth instance. This is the
    invariant: availability is checked ONCE, from a declared table, so a gate cannot
    be disabled by removing what it reads -- whether removed by an attacker, or by a
    maintainer pointing it at a path that does not exist. Those are the same bug seen
    from two sides, and both are now reported.

    Scoped to a corpus that HOLDS evidence. An empty corpus has no history to have
    lost, and demanding anchors for it would be inventing a past it never had.
    """
    if not observations:
        return
    sources_by_id = {src["sourceId"]: src for src in (sources or [])
                     if isinstance(src.get("sourceId"), str)}

    def report(anchor, detail):
        _finding(findings, "CORPUS_ANCHOR_UNAVAILABLE", "ERROR", "TRADE_OBSERVATION",
                  "corpus",
                  "%d observations are preserved but the integrity anchor %r is %s. "
                  "A gate that cannot read its anchor reports nothing, which is "
                  "indistinguishable from a clean corpus."
                  % (len(observations), anchor, detail), now)

    # A sentinel, because `json.load` of the document `null` returns None -- which is
    # indistinguishable from "never loaded" and so slipped past the type report below.
    # One type away from the case the table test covers, again.
    _NOT_LOADED = object()
    state = _NOT_LOADED
    if not state_path or not os.path.exists(state_path):
        report("research-state/current-state.json", "absent")
    else:
        try:
            with open(state_path, "r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (ValueError, OSError):
            report("research-state/current-state.json", "unreadable")
    if state is not _NOT_LOADED and not isinstance(state, dict):
        # A state document that is not an object -- `null`, a string, a list, a number.
        # The field checks below are guarded by `isinstance(state, dict)`, so every one
        # of these reported NOTHING: one type away from the `{}` case the table test
        # covers. The only thing that stopped it being an exit-0 deletion bypass was a
        # crash in the next function, and a crash is not a report -- it loses every
        # other finding and leaves the last integrity-report.json on disk still green.
        #
        # This ordering is deliberate: failing closed here must land BEFORE the crash
        # is fixed, or fixing the crash converts a loud failure into a silent pass.
        report("research-state/current-state.json",
               "not a JSON object (%s)" % type(state).__name__)
    if isinstance(state, dict):
        total = state.get("observationTotal")
        # `bool` is an `int` in Python, and True would sail through a bare isinstance.
        if not isinstance(total, int) or isinstance(total, bool):
            report("current-state.json:observationTotal",
                   "absent or not an integer (%r)" % (total,))
        fingerprint = state.get("corpusFingerprint")
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            report("current-state.json:corpusFingerprint",
                   "absent or not a string (%r)" % (fingerprint,))

    # SCOPE-CONDITION LAUNDERING, and the condition was the attacker's to set.
    #
    # This ran only when the corpus held FORWARD observations -- a scoping convenience
    # to keep replay-only fixtures quiet. It meant the require-list, the allow-list
    # and this availability check all switched off together the moment the corpus
    # contained no forward record, which is a state anyone can create by DELETING the
    # very evidence the anchor protects. Destroying all 29 forward observations and
    # appending 200 invented historical winners moved historical mean R from 0.167 to
    # 1.038 in total silence, exit 0.
    #
    # A category of its own: rounds 9-12 closed "delete what the gate READS", and
    # every one of those repairs still required the anchor to exist. This was "delete
    # what makes the gate APPLY". A condition an attacker controls is not a scope, it
    # is a switch.
    #
    # The manifest is not forward-only anyway -- it records every captureBasis the
    # importer produces, 221 REPLAY_RUN identities included -- so requiring it of any
    # corpus holding evidence is both safe and correct.
    _check_preservation_anchor(preservation_dir, report)

    if not ledger_dir or not os.path.isdir(ledger_dir):
        report("research-state/ledger/", "absent")
        return
    if not globmod.glob(os.path.join(ledger_dir, "*.json")):
        report("research-state/ledger/", "empty")
        return

    # THE TWO ANCHORS MUST AGREE WITH EACH OTHER.
    #
    # An anchor can be present, correctly typed, and still lie. Decrementing
    # `observationTotal` by one makes the content comparison read the corpus as
    # "grown" and skip entirely -- an availability check cannot see that, because
    # nothing is unavailable. But assimilation writes state and ledger together, so
    # a recorded total BELOW the ledger's high-water mark means state was rewritten
    # backwards. Two anchors are only worth more than one if they are compared.
    if not isinstance(state, dict):
        return
    recorded_total = state.get("observationTotal")
    if not isinstance(recorded_total, int) or isinstance(recorded_total, bool):
        return          # already reported above
    high_water = None
    for path in sorted(globmod.glob(os.path.join(ledger_dir, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                entry = json.load(handle)
        except (ValueError, OSError):
            continue
        total = entry.get("observationTotalAfter")
        if isinstance(total, int) and not isinstance(total, bool):
            high_water = total if high_water is None else max(high_water, total)
    # Required only of a corpus that actually holds FORWARD evidence. The manifest
    # records the PAPER account's closed trades, so a corpus with no forward
    # observations has none to preserve, and demanding one would fire on every
    # replay-only or synthetic corpus -- the same over-reach that would train people
    # to ignore this. Same scoping principle as the "corpus that HOLDS evidence"
    # guard above, applied to the population the anchor is actually about.
    if high_water is not None and recorded_total < high_water:
        _finding(findings, "STATE_CONTRADICTS_LEDGER", "ERROR", "TRADE_OBSERVATION",
                  "corpus",
                  "Research state records %d observations but the ledger has recorded "
                  "as many as %d. Assimilation writes both together, so a state total "
                  "below the ledger's high-water mark means state was rewritten "
                  "backwards -- which silently disables the content comparison."
                  % (recorded_total, high_water), now)


def check_observation_source_content_unique(observations, findings, now):
    """No two observations may derive from the same preserved package.

    `sequenceId` closed DELETE-AND-PAD only while the attacker left it alone: the
    gate skips any record whose sequenceId is not a non-empty string, so padding
    needed no fresh ids at all -- just DELETE the field. Five variants (absent, "",
    12345, null, trailing whitespace) all walked straight through. That is the
    fail-open shape again, on a field the attacker fully controls.

    `sourceContentHash` is used instead: present and distinct on all 259 records.

    A CORRECTION, because the first version of this docstring overstated it. It said
    freshening the value "means computing a hash of bytes that must also exist --
    which is precisely the authoring cost delete-and-pad exists to avoid". That is
    FALSE. Nothing in this validator compares `sourceContentHash` to anything: it
    names a package inside a capture artifact, and those artifacts are gitignored by
    design, so the corpus cannot re-derive it (SPEC-provenance 7.4 says exactly
    this). Measured: 0 of 259 observations have a `sourceContentHash` equal to their
    source's `contentHash` -- they are different granularities. Forging it costs one
    character.

    So this is a DUPLICATE DETECTOR, not an authoring-cost barrier. It catches the
    naive copy, which is the realistic accident and the cheap attack; it does not
    stop a deliberate forgery, and the claim that it "blocks laundering upstream" was
    wrong. What actually catches a forged pad is CORPUS_CONTENT_DIVERGED, and that
    reads an anchor -- which is why anchor availability is now its own invariant.

    Absence is reported, not skipped, for the same reason the stamps are: silence has
    to mean "checked and fine", never "could not tell".
    """
    seen = {}
    for obs in observations:
        content_hash = obs.get("sourceContentHash")
        if not isinstance(content_hash, str) or not content_hash.strip():
            _finding(findings, "MISSING_SOURCE_CONTENT_HASH", "ERROR",
                      "TRADE_OBSERVATION", obs.get("observationId"),
                      "sourceContentHash is %r, so this observation cannot be tied to "
                      "the preserved package it was minted from."
                      % (content_hash,), now)
            continue
        seen.setdefault(content_hash.strip(), []).append(obs.get("observationId"))
    for content_hash, owners in sorted(seen.items()):
        if len(owners) > 1:
            _finding(findings, "DUPLICATE_SOURCE_CONTENT_HASH", "ERROR",
                      "TRADE_OBSERVATION",
                      sorted(str(o) for o in owners)[0],
                      "%d observations derive from the same package %s (%s). One "
                      "preserved package produced one trade; duplicating a record "
                      "re-weights every statistic it appears in."
                      % (len(owners), content_hash[:12],
                         ", ".join(sorted(str(o) for o in owners)[:4])), now)


def check_observation_sequence_ids_unique(observations, findings, now):
    """No two observations may share a `sequenceId`.

    Closes DELETE-AND-PAD, which the count anchor cannot see by construction:
    delete the 21 losing FORWARD observations, then copy a winning one 21 times
    changing only `observationId`. The count returns to exactly 259, forward `n`
    stays at 29 -- the one number a reader would sanity-check -- and the headline
    forward mean R moves from -0.18 to +2.00. Nothing is authored: no timestamps
    invented, no hashes computed, no stamps written. It is `cp` plus one id, which
    makes it materially cheaper than the "fabricated whole record" case in
    SPEC-provenance 7.4.

    `sequenceId` is the engine's own identifier for the decision that produced the
    trade, and it is unique across all 259 preserved records with none missing, so
    this costs nothing today. A duplicate means one decision was recorded twice.
    """
    seen = {}
    for obs in observations:
        sequence_id = obs.get("sequenceId")
        if not isinstance(sequence_id, str) or not sequence_id:
            continue      # absence is a different defect; not invented here
        seen.setdefault(sequence_id, []).append(obs.get("observationId"))
    for sequence_id, owners in sorted(seen.items()):
        if len(owners) > 1:
            _finding(findings, "DUPLICATE_SEQUENCE_ID", "ERROR", "TRADE_OBSERVATION",
                      sorted(o for o in owners if o)[0] if any(owners) else "corpus",
                      "%d observations share sequenceId %r (%s). One engine decision "
                      "cannot have produced several preserved trades; duplicating a "
                      "record re-weights every statistic it appears in."
                      % (len(owners), sequence_id,
                         ", ".join(sorted(str(o) for o in owners)[:4])), now)


def check_corpus_matches_recorded_state(observations, sources, findings, now,
                                        state_path=None):
    """Does the corpus still match the state assimilation last recorded?

    The round-9 repair anchored on the ledger's observation COUNT, and round 10
    showed what that bought: the attack surface moved to the ledger. Deleting the
    ledger directory, corrupting every entry, renaming the files, or removing the
    one field each defeated `EVIDENCE_REMOVED` outright -- six one-touch bypasses of
    a six-file directory no validator inspected. A repair that anchors on an artifact
    inherits the security of that artifact.

    This anchors on a DIFFERENT committed file, `research-state/current-state.json`,
    and on content rather than on a count. `corpusFingerprint` hashes every record in
    full together with the source its population derives from, so it moves for any
    edit, deletion or duplication -- and SPEC-provenance 7.4 already names it as the
    backstop for the limits it documents, while nothing anywhere read it.

    The comparison is deliberately conditional on the count, which is what makes it
    free of false positives. A corpus that GREW since assimilation has a different
    fingerprint legitimately, and reporting that would train everyone to ignore this.
    But a corpus with the SAME number of records and a DIFFERENT fingerprint has not
    grown -- its contents changed underneath a stable count, which is precisely the
    delete-and-pad signature and every same-count tamper.
    """
    path = state_path
    if path is None:
        return
    if not os.path.exists(path):
        # REPORTED, not skipped. Both anchors added by the last two rounds live under
        # research-state/ and both returned silently when absent, so a single
        # `rm -rf research-state/` restored the original deletion defect in full --
        # 21 records gone, headline mean R -0.18 to +2.01, exit 0. "Silent when
        # absent" also means "silent when misconfigured": pointing either anchor at a
        # path that does not exist disabled it with the suite green.
        #
        # A corpus holding observations has been imported, and importing assimilates,
        # so recorded state exists for any corpus that has any evidence in it. No
        # observations means no history to have lost, and that stays silent.
        if observations:
            _finding(findings, "RESEARCH_STATE_MISSING", "ERROR", "TRADE_OBSERVATION",
                      "corpus",
                      "%d observations are preserved but %s does not exist, so the "
                      "corpus cannot be compared with any recorded state."
                      % (len(observations), os.path.basename(path)), now)
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (ValueError, OSError):
        _finding(findings, "UNREADABLE_RESEARCH_STATE", "ERROR", "TRADE_OBSERVATION",
                  "corpus",
                  "research-state/current-state.json cannot be read, so the corpus "
                  "cannot be compared with the state assimilation last recorded.", now)
        return
    if not isinstance(state, dict):
        # Same hazard as the non-dict `metadata` fixed 300 lines above, unfixed here:
        # `state.get(...)` on a null document raised AttributeError and aborted the
        # whole run. Reported by the anchor invariant; skipped rather than fatal here.
        return
    recorded_total = state.get("observationTotal")
    recorded_fingerprint = state.get("corpusFingerprint")
    if not isinstance(recorded_total, int) or not isinstance(recorded_fingerprint, str):
        return
    current = len(observations)
    if current < recorded_total:
        _finding(findings, "EVIDENCE_REMOVED", "ERROR", "TRADE_OBSERVATION", "corpus",
                  "The corpus holds %d observations but research state records %d. "
                  "Evidence is append-only; %d record(s) are gone."
                  % (current, recorded_total, recorded_total - current), now)
        return
    if current != recorded_total:
        return          # grew since assimilation; a different fingerprint is expected
    # Both arguments are dicts keyed by id -- corpus_fingerprint iterates
    # `sorted(observations)` and looks sources up by `sourceId`.
    by_source_id = {src["sourceId"]: src for src in sources
                    if isinstance(src.get("sourceId"), str)}
    by_observation_id = {obs["observationId"]: obs for obs in observations
                         if isinstance(obs.get("observationId"), str)}
    actual = _assimilation.corpus_fingerprint(by_observation_id, by_source_id)
    if actual != recorded_fingerprint:
        _finding(findings, "CORPUS_CONTENT_DIVERGED", "ERROR", "TRADE_OBSERVATION",
                  "corpus",
                  "The corpus holds the recorded number of observations (%d) but its "
                  "content fingerprint is %s, not the recorded %s. Same count, "
                  "different content -- records were changed or swapped rather than "
                  "added." % (current, actual[:12], recorded_fingerprint[:12]), now)


def _state_verifies_corpus(observations, sources, state_path):
    """Does research state independently confirm this exact corpus, content included?"""
    if not state_path or not os.path.exists(state_path):
        return False
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (ValueError, OSError):
        return False
    if not isinstance(state, dict):
        # Third site of the same hazard. A non-dict state document cannot verify
        # anything, so this answers "no" rather than raising -- the crash it used to
        # raise aborted the whole run and left the previous integrity-report.json on
        # disk still reading clean while records were missing.
        return False
    if state.get("observationTotal") != len(observations):
        return False
    by_source_id = {src["sourceId"]: src for src in sources
                    if isinstance(src.get("sourceId"), str)}
    by_observation_id = {obs["observationId"]: obs for obs in observations
                         if isinstance(obs.get("observationId"), str)}
    return (state.get("corpusFingerprint")
            == _assimilation.corpus_fingerprint(by_observation_id, by_source_id))


def check_corpus_is_append_only(observations, findings, now, ledger_dir=None,
                                sources=None, state_path=None):
    """Has evidence been REMOVED?

    Nine rounds of adversarial verification attacked rewriting. None attacked
    removal, and every gate was blind to it: deleting the 21 losing FORWARD
    observations moved the headline forward mean R from -0.18 to +2.01 with all
    three validators exiting 0 and the WARNING count unchanged at 31. Deleting the
    ENTIRE corpus raised only orphan WARNINGs, which deliberately do not fail. So
    the strongest available attack on this corpus was never a clever edit -- it was
    `rm`.

    The anchor already existed and nothing read it. Every assimilation writes a
    ledger entry recording `observationTotalAfter`, and those entries are committed.
    Evidence in MOGO is append-only by design -- CLAUDE.md forbids destroying it --
    so a corpus smaller than the highest total ever recorded means records are gone.

    Counts, not identities, because counts are what the ledger carries. That catches
    deletion; it nets out under an equal delete-and-add, which is a coordinated
    change to two places and shows plainly in the ledger diff. Raising the floor
    from "rm is invisible" to "rm is an ERROR" is the point.

    Silent when no ledger exists: a corpus with no assimilation history has no
    high-water mark, and inventing one would be the fabrication this layer prevents.
    """
    # The ledger is resolved RELATIVE to the corpus being validated, never from a
    # module-level constant. Pointing it at the live repo made every scratch and
    # synthetic corpus inherit the real corpus's high-water mark, so a 0-observation
    # fixture "lost" 259 records. A gate that reports on a corpus other than the one
    # it was handed is worse than no gate.
    sources = sources or []
    pattern = os.path.join(ledger_dir, "*.json") if ledger_dir else None
    if pattern is None:
        return
    high_water, source_entry = None, None
    for path in sorted(globmod.glob(pattern)):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                entry = json.load(handle)
        except (ValueError, OSError):
            continue
        total = entry.get("observationTotalAfter")
        if isinstance(total, int) and (high_water is None or total > high_water):
            high_water, source_entry = total, os.path.basename(path)
    if high_water is None:
        return
    current = len(observations)
    if current < high_water:
        # If research state independently VERIFIES this corpus -- same count and a
        # matching content fingerprint -- then a ledger claiming more records is
        # evidence the LEDGER is wrong, not that evidence is missing. Saying
        # "21 records are gone" when nothing is gone sends the reader hunting for
        # files that were never deleted; a misleading diagnostic costs more than a
        # silent one. Still an ERROR either way, so it fails closed.
        if _state_verifies_corpus(observations, sources, state_path):
            _finding(findings, "LEDGER_DISAGREES_WITH_STATE", "ERROR",
                      "TRADE_OBSERVATION", "corpus",
                      "The assimilation ledger records as many as %d observations (%s) "
                      "but research state verifies the present %d exactly, fingerprint "
                      "included. The ledger is inconsistent with the corpus it "
                      "describes." % (high_water, source_entry, current), now)
            return
        _finding(findings, "EVIDENCE_REMOVED", "ERROR", "TRADE_OBSERVATION",
                  "corpus",
                  "The corpus holds %d observations but the assimilation ledger has "
                  "recorded as many as %d (%s). Evidence is append-only; %d record(s) "
                  "are gone, and deleting records moves every population statistic "
                  "they belonged to."
                  % (current, high_water, source_entry, high_water - current), now)


def check_observation_population_rebinding(observations, sources, findings, now):
    """Does an observation still point at the source it was MINTED from -- and can
    its population still be resolved at all?

    Population -- HISTORICAL / FORWARD / RECONSTRUCTED -- is derived from the
    source's `sourceType` and deliberately never stored on the observation. That
    keeps one source of truth, and it has a consequence nothing was checking:
    repointing an observation's `sourceId` at a source of a different type silently
    MOVES it between populations. A replay trade becomes a forward trade, forward
    performance absorbs bar-quantised simulated fills, and every diagnostic stays
    green because each one individually is still self-consistent.

    The cross-check is the observation's OWN record: the importer stamps
    `notes: "captureBasis=... sourceType=..."` at mint time, so the record carries
    what its source was WHEN THE OBSERVATION WAS CREATED.

    THIS CHECK FAILS CLOSED, and that is the whole design. The first version simply
    skipped any record whose stamp it could not read, which made the stamp itself
    the attack surface -- adversarial verification moved 24 replay observations into
    FORWARD by blanking the stamps and retyping one source, with every diagnostic
    still green. Silence has to mean "checked and fine", never "could not tell".
    So four distinct conditions are reported:

      POPULATION_REBINDING     (ERROR)   minted type != the source's type today.
      UNRESOLVED_POPULATION    (ERROR)   the population does not resolve to a real
                                         one. Catches the source-side attack: blank
                                         or delete `sourceType` on a cited source
                                         and its observations fall into UNKNOWN,
                                         which nothing else objected to.
      MISSING_MINT_PROVENANCE  (ERROR)   no readable stamp, so no rebinding check is
                                         possible for this record.

    MISSING_MINT_PROVENANCE was a WARNING at first, on the reasoning that a record
    which never recorded a stamp is a gap rather than a contradiction. That was the
    remaining hole, and it was the whole attack: blinding every stamp and retyping
    one source moved replay trades into FORWARD while producing WARNINGS ONLY -- and
    WARNINGs exit 0, so no CI gate could ever fire on the contamination.

    It is an ERROR because an observation whose population cannot be VERIFIED still
    participates in population totals that claim to be separated. That is a breach of
    the separation guarantee, not an open question about one record. Every preserved
    record carries a stamp, so this is anomalous rather than legacy; if some future
    import path mints records without one, the right response is to fix that path,
    not to tolerate an unverifiable population.
      AMBIGUOUS_MINT_PROVENANCE (ERROR)  more than one `sourceType=` in `notes`.
                                         Prepending a decoy made the first match win.

    Nothing here repairs anything. A mismatch is a contradiction for a human to
    resolve; rewriting `sourceId` or `notes` to agree would destroy the evidence of
    the rebinding, and inventing a mint-time type for a record that never recorded
    one is precisely the fabrication this exists to catch.
    """
    # Only STRING ids are indexed or looked up. A list- or dict-valued sourceId
    # raised `TypeError: unhashable type` out of the dict access below and aborted
    # the ENTIRE validator run -- losing every other finding in the corpus with it,
    # including the population findings this function exists to produce. That is the
    # same defect already fixed for `notes`; the hardening had not been carried
    # across to the id. An unhashable id is not skipped silently: it falls through
    # to the missing-sourceId branch and is reported.
    by_id = {s["sourceId"]: s for s in sources
             if isinstance(s.get("sourceId"), str) and s["sourceId"]}
    for obs in observations:
        obs_id = obs.get("observationId")
        obs_source_id = obs.get("sourceId")
        source = by_id.get(obs_source_id) if isinstance(obs_source_id, str) else None

        # 1. Can the population be resolved at all? Independent of the stamp, so a
        #    source-side edit cannot hide behind a missing or blinded one.
        if source is not None:
            population = to.observation_population(obs, by_id)
            # Compared against UNKNOWN_POPULATION explicitly, NOT `not in POPULATIONS`.
            # UNKNOWN is itself a member of POPULATIONS -- it is a legitimate value of
            # the enum, not an absence from it -- so the membership test could never
            # fire, and this check silently passed the source-side attack it exists to
            # catch. Found by re-running that attack rather than by any fixture.
            if population == to.UNKNOWN_POPULATION:
                _finding(findings, "UNRESOLVED_POPULATION", "ERROR", "TRADE_OBSERVATION",
                          obs_id,
                          "Population does not resolve (%r) because source %s has "
                          "sourceType %r. An observation whose population is unknown "
                          "silently leaves every population total it belonged to."
                          % (population, obs.get("sourceId"), source.get("sourceType")),
                          now)

        # 2. The mint-time stamp. `notes` is not guaranteed to be a string, and a
        #    non-string one used to raise TypeError and abort the ENTIRE validator
        #    run, losing every other finding with it.
        notes = obs.get("notes")
        matches = _MINTED_SOURCE_TYPE_RE.findall(notes) if isinstance(notes, str) else []
        matches = [m for m in matches if m]
        bases = [b for b in (_CAPTURE_BASIS_RE.findall(notes)
                             if isinstance(notes, str) else []) if b]

        # Both stamp ABSENCES are reported here, before the sourceType branch below
        # can `continue` past them. A record missing both used to report only the
        # first -- the same incomplete-reporting shape as an early check aborting the
        # rest of the run, and it understates how damaged such a record is.
        if not bases:
            # SYMMETRY. The `sourceType=` stamp's absence is MISSING_MINT_PROVENANCE
            # (ERROR); the `captureBasis=` stamp's absence was not reported at all,
            # so the second anchor was defeated by DELETING it rather than rewriting
            # it -- 24 replay observations into FORWARD, every gate exit 0, forward
            # mean R sign-flipped. The "absence is anomalous, so report it" argument
            # that made the other stamp an ERROR had never been applied here.
            #
            # All 259 preserved records carry both stamps, so this costs nothing.
            # Blanking the value happened to be caught already, but by a regex bleed
            # (the pattern ate the space and captured the next key name), which is an
            # accident rather than a designed path.
            _finding(findings, "MISSING_CAPTURE_BASIS", "ERROR", "TRADE_OBSERVATION",
                      obs_id,
                      "notes carries no readable captureBasis stamp, so this "
                      "observation's population cannot be cross-checked against how it "
                      "was captured.", now)

        if len(matches) > 1:
            _finding(findings, "AMBIGUOUS_MINT_PROVENANCE", "ERROR", "TRADE_OBSERVATION",
                      obs_id,
                      "notes records %d different sourceType stamps (%s); which one the "
                      "observation was minted from is not decidable."
                      % (len(matches), ", ".join(sorted(set(matches)))), now)
            continue
        if not matches:
            _finding(findings, "MISSING_MINT_PROVENANCE", "ERROR", "TRADE_OBSERVATION",
                      obs_id,
                      "notes carries no readable sourceType stamp, so this observation "
                      "cannot be checked against the source it was minted from.", now)
            continue

        minted = matches[0]
        if source is None:
            # NOT "reported elsewhere". That comment was true for a sourceId that
            # names a source which does not exist -- the graph build reports that as
            # MISSING_REFERENCE -- and FALSE for a sourceId that is absent, blank or
            # unhashable, where there is no dangling reference for anything to catch.
            # Deleting `sourceId` from 24 observations moved them all into UNKNOWN
            # while this validator reported nothing, and a test of mine positively
            # asserted that silence, which is how the hole got enshrined.
            raw = obs.get("sourceId")
            if not isinstance(raw, str) or not raw.strip():
                _finding(findings, "UNRESOLVED_POPULATION", "ERROR", "TRADE_OBSERVATION",
                          obs_id,
                          "sourceId is %r, so this observation names no source and its "
                          "population cannot be derived at all -- it silently leaves "
                          "every population total it belonged to." % (raw,), now)
            else:
                # A well-formed id naming a source that does not exist. This fell
                # through on the reasoning that the graph build reports it as
                # MISSING_REFERENCE -- but that finding never reaches
                # integrity-report.json, which is the artifact an operator reads, and
                # deleting one cited source file moved 24 observations into UNKNOWN
                # while this validator reported a clean corpus.
                _finding(findings, "UNRESOLVED_POPULATION", "ERROR", "TRADE_OBSERVATION",
                          obs_id,
                          "sourceId %r names no registered EvidenceSource, so this "
                          "observation's population cannot be derived." % (raw,), now)
            continue
        actual = source.get("sourceType")
        if actual and actual != minted:
            _finding(findings, "POPULATION_REBINDING", "ERROR", "TRADE_OBSERVATION",
                      obs_id,
                      "Observation was minted from a %r source but its sourceId now names "
                      "%s, whose sourceType is %r. Population is derived from sourceType, so "
                      "this moves the observation between evidence populations."
                      % (minted, obs.get("sourceId"), actual), now)
            continue

        # THE SECOND STAMP. `sourceType=` alone is defeated by a CONSISTENT rewrite:
        # repoint sourceId AND rewrite the stamp to agree, and the two sides match
        # while 24 replay observations sit in FORWARD. Adversarial verification did
        # exactly that with every tool green.
        #
        # `captureBasis` is the same notes string's other half and was being thrown
        # away. It says HOW the trade was captured, which the importer maps 1:1 onto
        # a sourceType, so it independently implies the population. An attacker must
        # now rewrite BOTH stamps consistently rather than one.
        #
        # This is defence in depth, not proof: both stamps live in one field, so a
        # thorough enough rewrite still defeats it. What it removes is the cheap
        # version of the attack.
        # A FOURTH anchor, and the only one that lives on the OTHER record.
        #
        # Every stamp above sits in the observation's own `notes`, so a rewrite
        # thorough enough to change them all defeats them together -- and repointing
        # `sourceId` needs no source edit at all. The source's
        # `metadata.engineStrategyId` records which engine produced the trades in that
        # capture, and it matches the observation's `strategyId` on 259 of 259
        # preserved records with zero disagreements. Repointing an observation at a
        # source produced by a DIFFERENT engine therefore contradicts a field the
        # attacker never touched.
        #
        # Not a complete defence, and the limit is worth stating carefully, because
        # the first attempt at stating it was falsified. It said this "removes the
        # freedom to repoint at ANY forward source" -- it did not, until the source
        # side also failed closed: deleting `metadata.engineStrategyId` from one
        # source made the whole anchor evaporate and restored that freedom against
        # every forward source. With MISSING_SOURCE_ATTRIBUTION above, deleting the
        # field is itself reported.
        #
        # The residual limit is narrower and real: 7 paper_trade sources carry
        # engineStrategyId=alex_g_sr_v1, so a replay observation repointed at one of
        # THOSE agrees here legitimately. That is documented in SPEC-provenance 7.4
        # as the third out-of-scope case, not claimed as covered.
        metadata = source.get("metadata")
        engine = metadata.get("engineStrategyId") if isinstance(metadata, dict) else None
        strategy = obs.get("strategyId")

        # THE SOURCE SIDE FAILS CLOSED TOO -- symmetrically, and once.
        #
        # The observation side was hardened so deleting `strategyId` could not make
        # this anchor evaporate. The same anchor was left fail-open on the other
        # record: with `engine` falsy the comparison evaluated away in silence, so
        # deleting `metadata.engineStrategyId` from ONE source restored the freedom to
        # repoint at any forward source -- 24 replay observations into FORWARD, zero
        # findings, exit 0. Hardening one side of a two-sided comparison is hardening
        # neither.
        #
        # Framed as a CLAIM and its CORROBORATION, which is what makes it one finding
        # rather than a field checklist: the observation states which engine produced
        # it, the source states which engine produced the capture. Either side missing
        # means the claim cannot be verified.
        #
        # Deliberately scoped to `engineStrategyId` alone. Requiring the source's
        # `captureBasis` here too duplicated an anchor that
        # check_source_capture_basis_agrees_with_type already owns, and doubled the
        # findings per observation for no additional coverage.
        source_meta = metadata if isinstance(metadata, dict) else {}
        if strategy and not source_meta.get("engineStrategyId"):
            _finding(findings, "MISSING_SOURCE_ATTRIBUTION", "ERROR",
                      "TRADE_OBSERVATION", obs_id,
                      "Observation claims strategy %r but its cited source %s records no "
                      "metadata.engineStrategyId, so the claim cannot be corroborated "
                      "against the capture it comes from."
                      % (strategy, obs.get("sourceId")), now)

        if not strategy:
            # FAILS CLOSED. The condition used to read `if engine and strategy and
            # engine != strategy`, so deleting or blanking `strategyId` made the
            # anchor evaluate to False and vanish -- the cheapest evasion found in
            # five rounds: drop one field and 24 replay observations enter FORWARD
            # with every tool green. All 259 preserved records carry a strategyId, so
            # its absence is anomalous, and an observation that cannot be attributed
            # to an engine cannot be cross-checked against the capture it cites.
            _finding(findings, "MISSING_STRATEGY_ATTRIBUTION", "ERROR", "TRADE_OBSERVATION",
                      obs_id,
                      "strategyId is %r, so this observation cannot be checked against "
                      "the engineStrategyId (%r) of the source it cites."
                      % (strategy, engine), now)
        elif engine and strategy and engine != strategy:
            _finding(findings, "ENGINE_STRATEGY_MISMATCH", "ERROR", "TRADE_OBSERVATION",
                      obs_id,
                      "Observation was produced by strategy %r but its source %s records "
                      "engineStrategyId %r -- the observation does not belong to the "
                      "capture it cites."
                      % (obs.get("strategyId"), obs.get("sourceId"), engine), now)

        if len(bases) > 1:
            # The decoy attack, which the sourceType stamp already caught and this one
            # did not: `.search` took the first match, so prepending 24 characters
            # defeated the check while the true stamp sat untouched in the record.
            # Both stamps now use findall and both report ambiguity.
            _finding(findings, "AMBIGUOUS_MINT_PROVENANCE", "ERROR", "TRADE_OBSERVATION",
                      obs_id,
                      "notes records %d different captureBasis stamps (%s); which one "
                      "the observation was captured under is not decidable."
                      % (len(bases), ", ".join(sorted(set(bases)))), now)
        elif bases and actual:
            expected = CAPTURE_BASIS_SOURCE_TYPE.get(bases[0].upper())
            if expected is None:
                # FAILS CLOSED, where it used to fall through. A basis the importer
                # does not know is still not GUESSED at -- no population is inferred
                # from it -- but it is reported, because "genuinely new basis" and
                # "stamp mangled to evade the check" are indistinguishable from here
                # and only one of them is harmless.
                _finding(findings, "UNRECOGNISED_CAPTURE_BASIS", "ERROR",
                          "TRADE_OBSERVATION", obs_id,
                          "captureBasis=%r is not one the importer produces (%s), so this "
                          "observation's population cannot be cross-checked against it."
                          % (bases[0], ", ".join(sorted(CAPTURE_BASIS_SOURCE_TYPE))), now)
            elif expected != actual:
                _finding(findings, "CAPTURE_BASIS_CONTRADICTS_SOURCE", "ERROR",
                          "TRADE_OBSERVATION", obs_id,
                          "Observation records captureBasis=%s, which is captured as %r, "
                          "but its source %s has sourceType %r. The two stamps in this "
                          "record disagree about which population it belongs to."
                          % (bases[0], expected, obs.get("sourceId"), actual), now)


def check_orphans(sources, items, claims, links, findings, now):
    source_ids = {s["sourceId"] for s in sources}
    item_ids = {i["evidenceId"] for i in items}
    claim_ids = {c["claimId"] for c in claims}

    for item in items:
        # `.get`, not `[...]`. `check_orphans` runs FIRST, so a single EvidenceItem
        # missing this key raised KeyError and aborted the entire run before any
        # population check executed -- no report written, every other finding lost.
        # Fourth instance of the defect already fixed for `notes`, `sourceId` and
        # `metadata`; a malformed record must be REPORTED, never fatal to the run.
        if item.get("sourceId") not in source_ids:
            _finding(findings, "ORPHANED_EVIDENCE", "ERROR", "EVIDENCE_ITEM", item["evidenceId"],
                      "EvidenceItem references nonexistent sourceId %r." % (item.get("sourceId"),), now)

    for link in links:
        if link["evidenceId"] not in item_ids:
            _finding(findings, "ORPHANED_LINK", "ERROR", "EVIDENCE_CLAIM_LINK", link["linkId"],
                      "Link references nonexistent evidenceId %r." % (link["evidenceId"],), now)
        if link["claimId"] not in claim_ids:
            _finding(findings, "ORPHANED_LINK", "ERROR", "EVIDENCE_CLAIM_LINK", link["linkId"],
                      "Link references nonexistent claimId %r." % (link["claimId"],), now)

    links_by_claim = {}
    for link in links:
        links_by_claim.setdefault(link["claimId"], []).append(link)
    for claim in claims:
        if claim["evidenceCount"] > 0 and not links_by_claim.get(claim["claimId"]):
            _finding(findings, "ORPHANED_CLAIM", "ERROR", "CLAIM", claim["claimId"],
                      "Claim reports evidenceCount=%d but no matching EvidenceClaimLink records exist." % (
                          claim["evidenceCount"],), now)


# ---------------------------------------------------------------------------
# 2. Duplicate IDs (DUPLICATE_ID)
# ---------------------------------------------------------------------------

def check_duplicate_ids(sources, items, claims, links, contradictions, findings, now, extra=None):
    for label, records, id_field in (
        ("EVIDENCE_SOURCE", sources, "sourceId"), ("EVIDENCE_ITEM", items, "evidenceId"),
        ("CLAIM", claims, "claimId"), ("EVIDENCE_CLAIM_LINK", links, "linkId"),
        ("CONTRADICTION_RECORD", contradictions, "contradictionId"),
    ) + tuple(extra or ()):
        seen = {}
        for r in records:
            rid = r[id_field]
            seen[rid] = seen.get(rid, 0) + 1
        for rid, count in seen.items():
            if count > 1:
                _finding(findings, "DUPLICATE_ID", "FATAL", label, rid,
                          "%s appears %d times across stored records (expected exactly once)." % (rid, count), now)


# ---------------------------------------------------------------------------
# 3. Duplicate immutable content (DUPLICATE_IMMUTABLE_CONTENT)
# ---------------------------------------------------------------------------

def check_duplicate_immutable_content(items, findings, now):
    by_source_hash = {}
    for item in items:
        if item.get("evidenceStatus") == "superseded" or not item.get("contentHash"):
            continue
        key = (item["sourceId"], item["contentHash"])
        by_source_hash.setdefault(key, []).append(item["evidenceId"])
    for (source_id, content_hash), ids in by_source_hash.items():
        if len(ids) > 1:
            _finding(findings, "DUPLICATE_IMMUTABLE_CONTENT", "WARNING", "EVIDENCE_ITEM", ids[0],
                      "Evidence items %r from source %s share identical content hash %s but neither "
                      "supersedes the other -- likely an unintentional duplicate registration." % (
                          ids, source_id, content_hash), now, metadata={"allEvidenceIds": ids})


# ---------------------------------------------------------------------------
# 4. Inconsistent hash (INCONSISTENT_HASH)
# ---------------------------------------------------------------------------

def check_inconsistent_hash(items, findings, now):
    for item in items:
        expected = None
        if item.get("exactExcerpt") or item.get("normalizedObservation"):
            expected = gc.content_hash_of({
                "exactExcerpt": item.get("exactExcerpt"),
                "normalizedObservation": item.get("normalizedObservation"),
            })
        stored = item.get("contentHash")
        if stored != expected:
            _finding(findings, "INCONSISTENT_HASH", "ERROR", "EVIDENCE_ITEM", item["evidenceId"],
                      "Stored contentHash %r does not match hash recomputed from exactExcerpt/"
                      "normalizedObservation (%r) -- content may have been edited in place, which is "
                      "prohibited (corrections must supersede, never edit)." % (stored, expected), now)


# ---------------------------------------------------------------------------
# 5. Malformed provenance (MALFORMED_PROVENANCE)
# ---------------------------------------------------------------------------

def check_malformed_provenance(sources, items, findings, now):
    # Needed to verify an artifactSupersededBy claim against the source it names.
    sources_by_id = {src["sourceId"]: src for src in sources if src.get("sourceId")}
    for source in sources:
        if source.get("storageLocationType") == "external" and not (
            source.get("externalAssetReference") and source.get("canonicalReference")
        ):
            _finding(findings, "MALFORMED_PROVENANCE", "ERROR", "EVIDENCE_SOURCE", source["sourceId"],
                      "storageLocationType='external' requires both externalAssetReference and "
                      "canonicalReference to be set.", now)
        # A repository-stored source whose artifact is GONE. The validator never
        # looked at repositoryPath, so a source pointing at a deleted or renamed
        # capture file passed cleanly -- and one did: EVSRC|MOGO|20260818|015 cites
        # a file removed during a duplicate cleanup, while the observation that
        # cites it is intact. Provenance that cannot be walked back to an artifact
        # is not provenance, and WARNING rather than ERROR because the observation
        # itself is undamaged and its content survives under another path.
        # Only a path that is SET but missing is reported. An absent repositoryPath
        # is a pre-existing, schema-permitted state that several fixtures rely on;
        # turning it into an error here would be changing a rule while fixing a
        # different one.
        if source.get("storageLocationType") == "repository":
            rel = source.get("repositoryPath")
            if rel and not os.path.exists(os.path.join(REPO_ROOT, rel)):
                _check_missing_artifact(findings, source, rel, sources_by_id, now)
        if source.get("provenanceStatus") not in evc.PROVENANCE_STATUSES:
            _finding(findings, "MALFORMED_PROVENANCE", "ERROR", "EVIDENCE_SOURCE", source["sourceId"],
                      "Unknown provenanceStatus %r." % (source.get("provenanceStatus"),), now)

    for item in items:
        if not (item.get("exactExcerpt") or item.get("normalizedObservation")):
            _finding(findings, "MALFORMED_PROVENANCE", "WARNING", "EVIDENCE_ITEM", item["evidenceId"],
                      "EvidenceItem carries neither exactExcerpt nor normalizedObservation -- no "
                      "traceable content is recorded for this item.", now)


# ---------------------------------------------------------------------------
# 6. Lifecycle sequence validity (INVALID_LIFECYCLE_SEQUENCE)
# ---------------------------------------------------------------------------

_GENESIS_EVENT_TYPE_BY_ENTITY_TYPE = {
    "EVIDENCE_CLAIM_LINK": "linked",  # a link's genesis event is "linked", not "created"
    # MOGO-020: EvidenceQuestions are created WITHOUT a lifecycle event --
    # evidence_questions.create_question() has never emitted one, and MOGO-020
    # deliberately did not start backdating a synthetic "created" event onto the
    # 281 existing records. A question's first lifecycle event is therefore its
    # first human adjudication, whose eventType is "reviewed".
    "EVIDENCE_QUESTION": "reviewed",
}


def _lifecycle_seq(event):
    # eventId always ends "...|%03d" with a monotonic per-entity sequence
    # (evidence_common.next_lifecycle_event_id) -- more reliable than
    # timestamp string comparison when two events share the same second.
    return int(event["eventId"].rsplit("|", 1)[1])


def check_lifecycle_sequences(lifecycle_events, known_ids_by_type, findings, now):
    by_entity = {}
    for event in lifecycle_events:
        by_entity.setdefault((event["entityType"], event["entityId"]), []).append(event)

    for (entity_type, entity_id), events in by_entity.items():
        events.sort(key=lambda e: (e["timestamp"], _lifecycle_seq(e)))
        expected_genesis = _GENESIS_EVENT_TYPE_BY_ENTITY_TYPE.get(entity_type, "created")
        if events[0]["eventType"] != expected_genesis:
            _finding(findings, "INVALID_LIFECYCLE_SEQUENCE", "ERROR", entity_type, entity_id,
                      "First lifecycle event for %s is %r, expected %r." % (
                          entity_id, events[0]["eventType"], expected_genesis), now)
        known = known_ids_by_type.get(entity_type)
        if known is not None and entity_id not in known:
            _finding(findings, "INVALID_LIFECYCLE_SEQUENCE", "WARNING", entity_type, entity_id,
                      "Lifecycle events reference %s %r which no longer has a stored record." % (
                          entity_type, entity_id), now)


# ---------------------------------------------------------------------------
# 7. Confidence/count mismatch (CONFIDENCE_COUNT_MISMATCH)
# ---------------------------------------------------------------------------

def check_confidence_count_mismatch(claims, links, items, findings, now):
    items_by_id = {i["evidenceId"]: i for i in items}
    links_by_claim = {}
    for link in links:
        links_by_claim.setdefault(link["claimId"], []).append(dict(link))

    for claim in claims:
        claim_links = links_by_claim.get(claim["claimId"], [])
        state, score, counts, _explanation = conf.compute_confidence(claim_links, items_by_id)
        for field, expected in counts.items():
            if claim.get(field) != expected:
                _finding(findings, "CONFIDENCE_COUNT_MISMATCH", "ERROR", "CLAIM", claim["claimId"],
                          "Stored %s=%r does not match recomputed value %r from current links." % (
                              field, claim.get(field), expected), now)
        if claim.get("confidenceState") != state:
            _finding(findings, "CONFIDENCE_COUNT_MISMATCH", "ERROR", "CLAIM", claim["claimId"],
                      "Stored confidenceState=%r does not match recomputed state %r -- confidence "
                      "appears stale (was recompute_claim_confidence run after the last link change?)." % (
                          claim.get("confidenceState"), state), now)
        elif claim.get("confidenceScore") != score:
            _finding(findings, "CONFIDENCE_COUNT_MISMATCH", "WARNING", "CLAIM", claim["claimId"],
                      "Stored confidenceScore=%r does not match recomputed score %r." % (
                          claim.get("confidenceScore"), score), now)


# ---------------------------------------------------------------------------
# 8. Unresolved supersession chains (UNRESOLVED_SUPERSESSION_CHAIN)
# ---------------------------------------------------------------------------

def check_unresolved_supersession_chains(items, findings, now):
    superseded_by = {}
    for item in items:
        if item.get("supersedesEvidenceId"):
            superseded_by[item["supersedesEvidenceId"]] = item["evidenceId"]

    for item in items:
        if item.get("evidenceStatus") == "superseded" and item["evidenceId"] not in superseded_by:
            _finding(findings, "UNRESOLVED_SUPERSESSION_CHAIN", "ERROR", "EVIDENCE_ITEM", item["evidenceId"],
                      "EvidenceItem is marked evidenceStatus='superseded' but no other item's "
                      "supersedesEvidenceId points back to it -- the supersession chain is broken.", now)


# ---------------------------------------------------------------------------
# 9/10. Circular derivation / supersession (CIRCULAR_DERIVATION / CIRCULAR_SUPERSESSION)
# ---------------------------------------------------------------------------

def _find_cycle(adjacency):
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in adjacency}
    cycles = []

    def visit(node, stack):
        color[node] = GRAY
        stack.append(node)
        for nxt in adjacency.get(node, []):
            if color.get(nxt, WHITE) == GRAY:
                cycles.append(stack[stack.index(nxt):] + [nxt])
            elif color.get(nxt, WHITE) == WHITE:
                visit(nxt, stack)
        stack.pop()
        color[node] = BLACK

    for node in list(adjacency.keys()):
        if color.get(node, WHITE) == WHITE:
            visit(node, [])
    return cycles


def check_circular_derivation(items, findings, now):
    adjacency = {i["evidenceId"]: ([i["parentEvidenceId"]] if i.get("parentEvidenceId") else []) for i in items}
    for cycle in _find_cycle(adjacency):
        _finding(findings, "CIRCULAR_DERIVATION", "FATAL", "EVIDENCE_ITEM", cycle[0],
                  "Circular parentEvidenceId chain: %s" % (" -> ".join(cycle),), now, metadata={"cycle": cycle})


def check_circular_supersession(items, findings, now):
    adjacency = {i["evidenceId"]: ([i["supersedesEvidenceId"]] if i.get("supersedesEvidenceId") else []) for i in items}
    for cycle in _find_cycle(adjacency):
        _finding(findings, "CIRCULAR_SUPERSESSION", "FATAL", "EVIDENCE_ITEM", cycle[0],
                  "Circular supersedesEvidenceId chain: %s" % (" -> ".join(cycle),), now, metadata={"cycle": cycle})


# ---------------------------------------------------------------------------
# 11. Invalid contradiction records (INVALID_CONTRADICTION_RECORD)
# ---------------------------------------------------------------------------

def check_contradiction_records(contradictions, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for cr in contradictions:
        cid = cr["contradictionId"]
        if cr["claimAId"] == cr["claimBId"]:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "FATAL", "CONTRADICTION_RECORD", cid,
                      "ContradictionRecord references the same claim (%r) as both sides." % (cr["claimAId"],), now)
        if cr["claimAId"] not in claim_ids:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "claimAId %r does not exist." % (cr["claimAId"],), now)
        if cr["claimBId"] not in claim_ids:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "claimBId %r does not exist." % (cr["claimBId"],), now)
        if cr.get("contradictionType") not in evc.CONTRADICTION_TYPES:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "Unknown contradictionType %r." % (cr.get("contradictionType"),), now)
        if cr.get("severity") not in evc.CONTRADICTION_SEVERITIES:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "Unknown severity %r." % (cr.get("severity"),), now)
        if cr.get("status") not in evc.CONTRADICTION_STATUSES:
            _finding(findings, "INVALID_CONTRADICTION_RECORD", "ERROR", "CONTRADICTION_RECORD", cid,
                      "Unknown status %r." % (cr.get("status"),), now)


# ---------------------------------------------------------------------------
# 12. Invalid claim scope (INVALID_CLAIM_SCOPE)
# ---------------------------------------------------------------------------

def check_claim_scope(claims, findings, now):
    for claim in claims:
        if claim.get("claimType") not in evc.CLAIM_TYPES:
            _finding(findings, "INVALID_CLAIM_SCOPE", "ERROR", "CLAIM", claim["claimId"],
                      "Unknown claimType %r." % (claim.get("claimType"),), now)
        if claim.get("confidenceState") not in evc.CONFIDENCE_STATES:
            _finding(findings, "INVALID_CLAIM_SCOPE", "ERROR", "CLAIM", claim["claimId"],
                      "Unknown confidenceState %r." % (claim.get("confidenceState"),), now)
        expected_fingerprint = evc.compute_claim_fingerprint(
            claim.get("normalizedClaim"), claim.get("traderId"), claim.get("strategyFamilyId"),
            claim.get("timeframe"), claim.get("session"), claim.get("marketCondition"))
        if claim.get("normalizedFingerprint") != expected_fingerprint:
            _finding(findings, "INVALID_CLAIM_SCOPE", "ERROR", "CLAIM", claim["claimId"],
                      "Stored normalizedFingerprint does not match the hash recomputed from this claim's "
                      "own normalizedClaim + scope fields -- either the claim text/scope changed after "
                      "creation (prohibited) or the fingerprint was computed inconsistently.", now)


# ---------------------------------------------------------------------------
# 13. Unsupported schema versions (UNSUPPORTED_SCHEMA_VERSION)
# ---------------------------------------------------------------------------

def check_schema_versions(sources, items, claims, links, contradictions, findings, now):
    for label, records, id_field in (
        ("EVIDENCE_SOURCE", sources, "sourceId"), ("EVIDENCE_ITEM", items, "evidenceId"),
        ("CLAIM", claims, "claimId"), ("EVIDENCE_CLAIM_LINK", links, "linkId"),
        ("CONTRADICTION_RECORD", contradictions, "contradictionId"),
    ):
        for r in records:
            v = r.get("schemaVersion")
            if not isinstance(v, int) or v > evc.SCHEMA_VERSION:
                _finding(findings, "UNSUPPORTED_SCHEMA_VERSION", "ERROR", label, r[id_field],
                          "Record has schemaVersion=%r; this validator supports up to %d." % (
                              v, evc.SCHEMA_VERSION), now)


# ---------------------------------------------------------------------------
# 14. Graph relationship checks (MISSING_GRAPH_RELATIONSHIP / GRAPH_REFERENCES_NONEXISTENT_EVIDENCE)
# ---------------------------------------------------------------------------

def _iter_strategy_rule_paths(ti_root):
    return sorted(globmod.glob(os.path.join(ti_root, "traders", "*", "rules", "*.json")))


def check_graph_relationships(repo_root, ti_root, links, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for path in _iter_strategy_rule_paths(ti_root):
        with open(path, "r", encoding="utf-8") as f:
            rule = json.load(f)
        for cid in rule.get("originatingClaimIds", []) or []:
            if cid not in claim_ids:
                _finding(findings, "GRAPH_REFERENCES_NONEXISTENT_EVIDENCE", "ERROR", "STRATEGY_RULE",
                          rule.get("ruleId", path), "originatingClaimIds references nonexistent claimId %r." % (cid,), now)

    try:
        graph_root = os.path.join(ti_root, "graph")
        nodes, edges, _construction_findings, _raw = gc.build_nodes_and_edges(repo_root, ti_root, graph_root)
    except Exception as exc:  # pragma: no cover - defensive only, graph build has its own tests
        _finding(findings, "MISSING_GRAPH_RELATIONSHIP", "WARNING", "KNOWLEDGE_GRAPH", "n/a",
                  "Could not build the Knowledge Graph to cross-check evidence links: %s" % (exc,), now)
        return

    node_by_entity_id = {n["entityId"]: n["nodeId"] for n in nodes}
    edge_pairs = {(e["fromNodeId"], e["toNodeId"], e["edgeType"]) for e in edges}
    relationship_to_edge_type = {
        "supports": "SUPPORTS", "exemplifies": "EXEMPLIFIES", "contradicts": "CONTRADICTS",
        "weakens": "WEAKENS", "contextualizes": "CONTEXTUALIZES", "qualifies": "QUALIFIES",
        "supersedes": "SUPERSEDES", "unresolved": "UNRESOLVED",
    }
    for link in links:
        from_node = node_by_entity_id.get(link["evidenceId"])
        to_node = node_by_entity_id.get(link["claimId"])
        edge_type = relationship_to_edge_type.get(link["relationshipType"])
        if from_node is None or to_node is None or edge_type is None:
            continue
        if (from_node, to_node, edge_type) not in edge_pairs:
            _finding(findings, "MISSING_GRAPH_RELATIONSHIP", "ERROR", "EVIDENCE_CLAIM_LINK", link["linkId"],
                      "Link exists in evidence storage but no corresponding %s edge was found in the "
                      "built Knowledge Graph -- run build_graph.py to regenerate." % (edge_type,), now)


# ---------------------------------------------------------------------------
# 15. Production rule linkage without approval (PRODUCTION_RULE_LINKAGE_WITHOUT_APPROVAL)
# ---------------------------------------------------------------------------

def check_production_rule_linkage(ti_root, findings, now):
    decisions_dir = os.path.join(ti_root, "graph", "decisions")
    decisions_by_affected = {}
    for path in sorted(globmod.glob(os.path.join(decisions_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            decision = json.load(f)
        for affected in decision.get("affectedEntityIds", []) or []:
            decisions_by_affected.setdefault(affected, []).append(decision)

    for path in _iter_strategy_rule_paths(ti_root):
        with open(path, "r", encoding="utf-8") as f:
            rule = json.load(f)
        if not rule.get("originatingClaimIds"):
            continue
        state = rule.get("promotionState")
        if state is None or state not in getattr(gc, "PROMOTION_STATES", []):
            continue
        idx = gc.PROMOTION_STATES.index(state)
        if idx >= gc.PROMOTION_STATES.index("IMPLEMENTATION_APPROVED"):
            decisions = decisions_by_affected.get(rule.get("ruleId"), [])
            if not any(d.get("status") == "active" and d.get("implementationAuthorization") for d in decisions):
                _finding(findings, "PRODUCTION_RULE_LINKAGE_WITHOUT_APPROVAL", "FATAL", "STRATEGY_RULE",
                          rule.get("ruleId", path),
                          "Rule has originatingClaimIds linked and promotionState=%s with no active "
                          "OwnerDecision granting implementationAuthorization -- claim linkage must never "
                          "itself authorize promotion." % (state,), now)


# ---------------------------------------------------------------------------
# 16. Mislabeled synthetic fixtures (MISLABELED_SYNTHETIC_FIXTURE)
# ---------------------------------------------------------------------------

def check_synthetic_leakage(sources, items, claims, findings, now, is_production):
    if not is_production:
        return
    for label, records, id_field, text_fields in (
        ("EVIDENCE_SOURCE", sources, "sourceId", ("title", "transcriptReference")),
        ("EVIDENCE_ITEM", items, "evidenceId", ("exactExcerpt", "normalizedObservation")),
        ("CLAIM", claims, "claimId", ("normalizedClaim",)),
    ):
        for r in records:
            blob = " ".join(str(r.get(f) or "") for f in text_fields) + " " + json.dumps(r.get("metadata") or {})
            if evc.contains_synthetic_markers(blob):
                _finding(findings, "MISLABELED_SYNTHETIC_FIXTURE", "FATAL", label, r[id_field],
                          "Record stored under the production evidence tree contains synthetic-fixture "
                          "markers (%r) -- synthetic test data must never be mistaken for real evidence." % (
                              evc.SYNTHETIC_MARKERS,), now)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# PROGRAM-006 Phase 1B (ADR-009, Deliverable 19) additive integrity checks
# ---------------------------------------------------------------------------

def check_orphaned_segments(intakes, segments, findings, now):
    intake_ids = {m["intakeId"] for m in intakes}
    for seg in segments:
        if seg["intakeId"] not in intake_ids:
            _finding(findings, "ORPHANED_SEGMENT", "ERROR", "TRANSCRIPT_SEGMENT", seg["segmentId"],
                      "TranscriptSegment references nonexistent intakeId %r." % (seg["intakeId"],), now)


def check_missing_transcript_locator(items, findings, now):
    for item in items:
        if item.get("extractionMethod") == "manual_transcription" and not item.get("sourceLocator"):
            _finding(findings, "MISSING_TRANSCRIPT_LOCATOR", "WARNING", "EVIDENCE_ITEM", item["evidenceId"],
                      "extractionMethod='manual_transcription' but sourceLocator is null -- transcript-derived "
                      "evidence should preserve its originating segment locator.", now)


def check_annotation_references(annotations, intakes, segments, findings, now):
    intake_ids = {m["intakeId"] for m in intakes}
    segment_ids = {s["segmentId"] for s in segments}
    for a in annotations:
        if a["intakeId"] not in intake_ids:
            _finding(findings, "INVALID_ANNOTATION_REFERENCE", "ERROR", "MANUAL_ANNOTATION", a["annotationId"],
                      "Annotation references nonexistent intakeId %r." % (a["intakeId"],), now)
        if a["segmentId"] not in segment_ids:
            _finding(findings, "INVALID_ANNOTATION_REFERENCE", "ERROR", "MANUAL_ANNOTATION", a["annotationId"],
                      "Annotation references nonexistent segmentId %r." % (a["segmentId"],), now)


def check_directness_and_certainty_present(items, findings, now):
    for item in items:
        has_directness = item.get("directness") is not None
        has_certainty = item.get("extractionCertainty") is not None
        if has_directness != has_certainty:
            _finding(findings, "MISSING_DIRECTNESS_OR_CERTAINTY", "WARNING", "EVIDENCE_ITEM", item["evidenceId"],
                      "directness=%r but extractionCertainty=%r -- Phase 1B evidence should set both together, "
                      "or leave both null (Phase 1A legacy record)." % (
                          item.get("directness"), item.get("extractionCertainty")), now)


def check_claim_candidate_without_evidence(claims, links, findings, now):
    links_by_claim = {}
    for l in links:
        links_by_claim.setdefault(l["claimId"], []).append(l)
    for c in claims:
        if c["claimStatus"] == "pending_review" and not links_by_claim.get(c["claimId"]):
            _finding(findings, "CLAIM_CANDIDATE_WITHOUT_EVIDENCE", "ERROR", "CLAIM", c["claimId"],
                      "claimStatus='pending_review' but no EvidenceClaimLink references this claim.", now)


def check_rule_candidate_proposals(proposals, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for p in proposals:
        if not p.get("originatingClaimIds"):
            _finding(findings, "RULE_CANDIDATE_WITHOUT_CLAIM", "FATAL", "RULE_CANDIDATE_PROPOSAL", p["proposalId"],
                      "originatingClaimIds is empty.", now)
        else:
            missing = [cid for cid in p["originatingClaimIds"] if cid not in claim_ids]
            if missing:
                _finding(findings, "RULE_CANDIDATE_WITHOUT_CLAIM", "ERROR", "RULE_CANDIDATE_PROPOSAL", p["proposalId"],
                          "originatingClaimIds references nonexistent claims %r." % (missing,), now)
        if p.get("status") not in evc.RULE_CANDIDATE_STATUSES:
            _finding(findings, "RULE_CANDIDATE_INCORRECTLY_ACTIVE", "FATAL", "RULE_CANDIDATE_PROPOSAL", p["proposalId"],
                      "status=%r is not one of the non-executable values %r -- a RuleCandidateProposal must "
                      "never claim an execution-implying status." % (p.get("status"), evc.RULE_CANDIDATE_STATUSES), now)


def check_questions_reference_existing_claims(questions, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for q in questions:
        if q.get("claimId") and q["claimId"] not in claim_ids:
            _finding(findings, "QUESTION_REFERENCES_NONEXISTENT_CLAIM", "ERROR", "EVIDENCE_QUESTION", q["questionId"],
                      "claimId %r does not exist." % (q["claimId"],), now)


def check_review_queue_references(queue_entries, known_ids_by_entity_type, findings, now):
    for e in queue_entries:
        known = known_ids_by_entity_type.get(e["entityType"])
        if known is not None and e["entityId"] not in known:
            _finding(findings, "REVIEW_QUEUE_REFERENCES_NONEXISTENT_ENTITY", "ERROR", "REVIEW_QUEUE_ENTRY", e["queueEntryId"],
                      "References nonexistent %s %r." % (e["entityType"], e["entityId"]), now)


def check_approved_intake_findings(intakes, findings, now):
    for m in intakes:
        if m["intakeStatus"] == "approved" and m.get("warnings"):
            _finding(findings, "APPROVED_INTAKE_WITH_UNRESOLVED_FINDINGS", "WARNING", "INTAKE_MANIFEST", m["intakeId"],
                      "intakeStatus='approved' but warnings list is still non-empty: %r." % (m["warnings"],), now)


def check_approved_source_licensing(intakes, findings, now):
    for m in intakes:
        if m["intakeStatus"] == "approved" and m.get("licensingStatus") in ("unknown", "restricted_third_party"):
            _finding(findings, "APPROVED_SOURCE_WITH_UNRESOLVED_LICENSING", "FATAL", "INTAKE_MANIFEST", m["intakeId"],
                      "intakeStatus='approved' but licensingStatus=%r is still unresolved." % (m["licensingStatus"],), now)


def check_segment_hashes(segments, findings, now):
    for seg in segments:
        expected = evc.text_sha256(seg["rawText"])
        if seg.get("textHash") != expected:
            _finding(findings, "SEGMENT_HASH_MISMATCH", "ERROR", "TRANSCRIPT_SEGMENT", seg["segmentId"],
                      "Stored textHash does not match the hash recomputed from rawText -- content may have "
                      "been edited in place, which is prohibited.", now)


def check_intake_content_hash(intakes, findings, now):
    for m in intakes:
        if m.get("contentHash") is not None and not isinstance(m["contentHash"], str):
            _finding(findings, "TRANSCRIPT_HASH_MISMATCH", "ERROR", "INTAKE_MANIFEST", m["intakeId"],
                      "contentHash is set but is not a string hash value.", now)


def check_segment_sequence_and_line_ranges(segments, findings, now):
    by_intake = {}
    for seg in segments:
        by_intake.setdefault(seg["intakeId"], []).append(seg)
    for intake_id, segs in sorted(by_intake.items()):
        seqs = sorted(s["sequenceNumber"] for s in segs)
        if seqs != list(range(1, len(seqs) + 1)):
            _finding(findings, "SEGMENT_SEQUENCE_GAP", "ERROR", "INTAKE_MANIFEST", intake_id,
                      "Segment sequence numbers are not a contiguous 1..N run: found %r." % (seqs,), now)
        seen_timestamps = {}
        for s in segs:
            if s.get("startTimestamp"):
                seen_timestamps.setdefault(s["startTimestamp"], []).append(s["segmentId"])
        for ts, ids in sorted(seen_timestamps.items()):
            if len(ids) > 1:
                _finding(findings, "OVERLAPPING_SEGMENT_TIMESTAMPS", "WARNING", "TRANSCRIPT_SEGMENT", sorted(ids)[0],
                          "Segments %r in intake %r share identical startTimestamp %r." % (sorted(ids), intake_id, ts), now)
    for seg in segments:
        if seg.get("lineStart") is not None and seg.get("lineEnd") is not None and seg["lineStart"] > seg["lineEnd"]:
            _finding(findings, "IMPOSSIBLE_LINE_RANGE", "ERROR", "TRANSCRIPT_SEGMENT", seg["segmentId"],
                      "lineStart=%r is greater than lineEnd=%r." % (seg["lineStart"], seg["lineEnd"]), now)


def check_explanation_provenance(claims, links, findings, now):
    links_by_claim = {}
    for l in links:
        links_by_claim.setdefault(l["claimId"], []).append(l)
    for c in claims:
        if c["evidenceCount"] > 0 and not links_by_claim.get(c["claimId"]):
            _finding(findings, "EXPLANATION_WITHOUT_PROVENANCE", "ERROR", "CLAIM", c["claimId"],
                      "evidenceCount>0 but no linked evidence exists -- any explanation generated for this "
                      "claim would have counts with nothing to cite.", now)


# ---------------------------------------------------------------------------
# PROGRAM-007 Phase 7A (Deliverable 8/19) -- Knowledge Library integrity
# ---------------------------------------------------------------------------

def check_blueprint_claim_references(blueprints, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for bp in blueprints:
        for cid in (bp.get("sourceLineage") or {}).get("claimIds", []) or []:
            if cid not in claim_ids:
                _finding(findings, "BLUEPRINT_REFERENCES_NONEXISTENT_CLAIM", "ERROR", "STRATEGY_BLUEPRINT",
                          bp["blueprintId"], "sourceLineage.claimIds references nonexistent claimId %r." % (cid,), now)


def check_gap_blueprint_references(gaps, blueprints, findings, now):
    blueprint_ids = {bp["blueprintId"] for bp in blueprints}
    for gap in gaps:
        bid = gap.get("blueprintId")
        if bid and bid not in blueprint_ids:
            _finding(findings, "GAP_REFERENCES_NONEXISTENT_BLUEPRINT", "ERROR", "KNOWLEDGE_GAP", gap["gapId"],
                      "blueprintId references nonexistent blueprintId %r." % (bid,), now)


def check_hypothesis_claim_references(hypotheses, claims, findings, now):
    claim_ids = {c["claimId"] for c in claims}
    for h in hypotheses:
        for cid in h.get("sourceClaimIds", []) or []:
            if cid not in claim_ids:
                _finding(findings, "HYPOTHESIS_REFERENCES_NONEXISTENT_CLAIM", "ERROR", "HYPOTHESIS",
                          h["hypothesisId"], "sourceClaimIds references nonexistent claimId %r." % (cid,), now)


def check_no_executable_blueprint_linkage(ti_root, findings, now):
    """Structural proof that a StrategyRule -- the one thing that IS
    executable -- never names a Blueprint as its origin. A Blueprint is
    research output only; nothing may cite one as authorization for a rule."""
    for path in _iter_strategy_rule_paths(ti_root):
        with open(path, "r", encoding="utf-8") as f:
            rule = json.load(f)
        for value in rule.values():
            values = value if isinstance(value, list) else [value]
            for v in values:
                if isinstance(v, str) and v.startswith("BLUEPRINT|"):
                    _finding(findings, "EXECUTABLE_LINKAGE_FROM_RESEARCH_BLUEPRINT", "FATAL", "STRATEGY_RULE",
                              rule.get("ruleId", path),
                              "StrategyRule references %r -- a research-only StrategyBlueprint must never "
                              "be cited as authorization for an executable rule." % (v,), now)


def check_duplicate_canonical_trader_identity(profiles, findings, now):
    """Multiple TraderProfile snapshots for the same traderId are expected
    (each build is a new immutable snapshot) -- but they must always agree
    on canonicalName. Disagreement means two conflicting canonical identities
    exist for one traderId, which Deliverable 8 requires this validator to
    catch."""
    names_by_trader = {}
    for p in profiles:
        names_by_trader.setdefault(p["traderId"], set()).add(p["canonicalName"])
    for trader_id, names in names_by_trader.items():
        if len(names) > 1:
            _finding(findings, "DUPLICATE_CANONICAL_TRADER_IDENTITY", "ERROR", "TRADER_PROFILE", trader_id,
                      "TraderProfile snapshots for traderId %r disagree on canonicalName: %s." % (
                          trader_id, sorted(names)), now)


def run_integrity_checks(evidence_root, repo_root=None, ti_root=None, is_production=True):
    now = datetime.now(timezone.utc)
    sources = _load_dir(os.path.join(evidence_root, "sources"), "sourceId")
    items = _load_dir(os.path.join(evidence_root, "items"), "evidenceId")
    claims = _load_dir(os.path.join(evidence_root, "claims"), "claimId")
    links = _load_dir(os.path.join(evidence_root, "links"), "linkId")
    contradictions = _load_dir(os.path.join(evidence_root, "contradictions"), "contradictionId")
    lifecycle_events = _load_dir(os.path.join(evidence_root, "lifecycle"), "eventId")
    # PROGRAM-006 Phase 1B (ADR-009):
    intakes = _load_dir(os.path.join(evidence_root, "intake"), "intakeId")
    segments = _load_dir(os.path.join(evidence_root, "segments"), "segmentId")
    annotations = _load_dir(os.path.join(evidence_root, "annotations"), "annotationId")
    questions = _load_dir(os.path.join(evidence_root, "questions"), "questionId")
    proposals = _load_dir(os.path.join(evidence_root, "proposals"), "proposalId")
    queue_entries = _load_dir(os.path.join(evidence_root, "review-queue"), "queueEntryId")
    # PROGRAM-007 Phase 7A (Knowledge Library vertical slice):
    profiles = _load_dir(os.path.join(evidence_root, "profiles"), "profileId")
    blueprints = _load_dir(os.path.join(evidence_root, "blueprints"), "blueprintId")
    gaps = _load_dir(os.path.join(evidence_root, "gaps"), "gapId")
    hypotheses = _load_dir(os.path.join(evidence_root, "hypotheses"), "hypothesisId")
    observations = _load_dir(os.path.join(evidence_root, "observations"), "observationId")

    findings = []
    check_orphans(sources, items, claims, links, findings, now)
    # Ledger lives beside the evidence root: <ti_root>/research-state/ledger.
    _state_root = os.path.dirname(os.path.abspath(evidence_root))
    check_preserved_identities_still_present(
        observations, findings, now,
        preservation_dir=os.path.join(os.path.abspath(evidence_root),
                                      "ledger-preservation"))
    check_corpus_anchors_are_available(
        observations, findings, now,
        state_path=os.path.join(_state_root, "research-state", "current-state.json"),
        ledger_dir=os.path.join(_state_root, "research-state", "ledger"),
        preservation_dir=os.path.join(os.path.abspath(evidence_root),
                                      "ledger-preservation"),
        sources=sources)
    check_observation_source_content_unique(observations, findings, now)
    check_observation_sequence_ids_unique(observations, findings, now)
    check_corpus_matches_recorded_state(
        observations, sources, findings, now,
        state_path=os.path.join(os.path.dirname(os.path.abspath(evidence_root)),
                                "research-state", "current-state.json"))
    check_corpus_is_append_only(
        observations, findings, now,
        ledger_dir=os.path.join(_state_root, "research-state", "ledger"),
        sources=sources,
        state_path=os.path.join(_state_root, "research-state", "current-state.json"))
    check_observation_population_rebinding(observations, sources, findings, now)
    check_source_capture_basis_agrees_with_type(sources, findings, now)
    check_duplicate_ids(sources, items, claims, links, contradictions, findings, now, extra=[
        ("TRANSCRIPT_SEGMENT", segments, "segmentId"), ("INTAKE_MANIFEST", intakes, "intakeId"),
        ("MANUAL_ANNOTATION", annotations, "annotationId"), ("EVIDENCE_QUESTION", questions, "questionId"),
        ("RULE_CANDIDATE_PROPOSAL", proposals, "proposalId"), ("REVIEW_QUEUE_ENTRY", queue_entries, "queueEntryId"),
        ("TRADER_PROFILE", profiles, "profileId"), ("STRATEGY_BLUEPRINT", blueprints, "blueprintId"),
        ("KNOWLEDGE_GAP", gaps, "gapId"), ("HYPOTHESIS", hypotheses, "hypothesisId"),
    ])
    check_duplicate_immutable_content(items, findings, now)
    check_inconsistent_hash(items, findings, now)
    check_malformed_provenance(sources, items, findings, now)
    known_ids_by_type = {
        "EVIDENCE_SOURCE": {s["sourceId"] for s in sources}, "EVIDENCE_ITEM": {i["evidenceId"] for i in items},
        "CLAIM": {c["claimId"] for c in claims}, "EVIDENCE_CLAIM_LINK": {l["linkId"] for l in links},
        "CONTRADICTION_RECORD": {c["contradictionId"] for c in contradictions},
    }
    check_lifecycle_sequences(lifecycle_events, known_ids_by_type, findings, now)
    check_confidence_count_mismatch(claims, links, items, findings, now)
    check_unresolved_supersession_chains(items, findings, now)
    check_circular_derivation(items, findings, now)
    check_circular_supersession(items, findings, now)
    check_contradiction_records(contradictions, claims, findings, now)
    check_claim_scope(claims, findings, now)
    check_schema_versions(sources, items, claims, links, contradictions, findings, now)
    check_synthetic_leakage(sources, items, claims, findings, now, is_production)

    # PROGRAM-006 Phase 1B (ADR-009, Deliverable 19):
    check_orphaned_segments(intakes, segments, findings, now)
    check_missing_transcript_locator(items, findings, now)
    check_annotation_references(annotations, intakes, segments, findings, now)
    check_directness_and_certainty_present(items, findings, now)
    check_claim_candidate_without_evidence(claims, links, findings, now)
    check_rule_candidate_proposals(proposals, claims, findings, now)
    check_questions_reference_existing_claims(questions, claims, findings, now)
    check_review_queue_references(queue_entries, {
        "EVIDENCE_SOURCE": {s["sourceId"] for s in sources}, "EVIDENCE_ITEM": {i["evidenceId"] for i in items},
        "CLAIM": {c["claimId"] for c in claims}, "CONTRADICTION_RECORD": {c["contradictionId"] for c in contradictions},
        "EVIDENCE_QUESTION": {q["questionId"] for q in questions}, "RULE_CANDIDATE_PROPOSAL": {p["proposalId"] for p in proposals},
        "INTAKE_MANIFEST": {m["intakeId"] for m in intakes}, "TRANSCRIPT_SEGMENT": {s["segmentId"] for s in segments},
    }, findings, now)
    check_approved_intake_findings(intakes, findings, now)
    check_approved_source_licensing(intakes, findings, now)
    check_segment_hashes(segments, findings, now)
    check_intake_content_hash(intakes, findings, now)
    check_segment_sequence_and_line_ranges(segments, findings, now)
    check_explanation_provenance(claims, links, findings, now)

    # PROGRAM-007 Phase 7A (Deliverable 8/19):
    check_blueprint_claim_references(blueprints, claims, findings, now)
    check_gap_blueprint_references(gaps, blueprints, findings, now)
    check_hypothesis_claim_references(hypotheses, claims, findings, now)
    check_duplicate_canonical_trader_identity(profiles, findings, now)
    for label, records, id_field in (
        ("TRADER_PROFILE", profiles, "profileId"), ("STRATEGY_BLUEPRINT", blueprints, "blueprintId"),
        ("KNOWLEDGE_GAP", gaps, "gapId"), ("HYPOTHESIS", hypotheses, "hypothesisId"),
    ):
        for r in records:
            v = r.get("schemaVersion")
            if not isinstance(v, int) or v > evc.SCHEMA_VERSION:
                _finding(findings, "UNSUPPORTED_SCHEMA_VERSION", "ERROR", label, r[id_field],
                          "Record has schemaVersion=%r; this validator supports up to %d." % (
                              v, evc.SCHEMA_VERSION), now)

    if repo_root and ti_root:
        check_graph_relationships(repo_root, ti_root, links, claims, findings, now)
        check_production_rule_linkage(ti_root, findings, now)
        check_no_executable_blueprint_linkage(ti_root, findings, now)

    summary = {"INFO": 0, "WARNING": 0, "ERROR": 0, "FATAL": 0}
    for f in findings:
        summary[f["severity"]] += 1

    seq = 1
    report = {
        "generated": True,
        "integrityReportId": evc.make_integrity_report_id(now, seq),
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "validatorVersion": "1.0.0",
        "findings": findings,
        "summary": summary,
    }
    return report


#: Re-exported from graph_common so all four validators share ONE definition.
#: Two of them hand-rolled it and got it wrong identically; see the canonical
#: docstring. `ve.exit_code_for` stays importable for the tests that pin it.
exit_code_for = gc.exit_code_for


def main():
    parser = argparse.ArgumentParser(description="Validate PROGRAM-006 Evidence Intelligence Engine data integrity.")
    parser.add_argument("--repo-root", default=REPO_ROOT)
    parser.add_argument("--ti-root", default=None)
    parser.add_argument("--evidence-root", default=None)
    parser.add_argument("--no-graph-check", action="store_true", help="Skip cross-checking against the built Knowledge Graph.")
    parser.add_argument("--allow-synthetic", action="store_true", help="Do not flag synthetic-fixture markers (use only against a test fixture tree).")
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    ti_root = args.ti_root or os.path.join(repo_root, "docs", "trader-intelligence")
    evidence_root = args.evidence_root or os.path.join(ti_root, "evidence")

    report = run_integrity_checks(
        evidence_root,
        repo_root=None if args.no_graph_check else repo_root,
        ti_root=None if args.no_graph_check else ti_root,
        is_production=not args.allow_synthetic,
    )

    out_path = os.path.join(evidence_root, "reports", "integrity-report.json")
    gc.atomic_write_text(out_path, gc.pretty_json(report))
    print("Wrote %s" % out_path)
    print("Summary: %r" % (report["summary"],))
    return exit_code_for(report["summary"])


if __name__ == "__main__":
    raise SystemExit(main())
