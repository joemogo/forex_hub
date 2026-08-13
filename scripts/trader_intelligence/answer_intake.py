#!/usr/bin/env python3
"""MOGO-020 Step 2 -- governed research answer intake.

Pure Python standard library. NO NETWORK ACCESS. NO LLM. Deterministic.

WHAT THIS DOES, AND WHAT IT REFUSES TO DO

    DOES:     records a HUMAN's semantic decision about an EvidenceQuestion or
              a ContradictionRecord, after validating that the decision refers
              to real, in-corpus, provenance-complete governed objects.

    DOES NOT: make the semantic decision. Nothing in this module reads question
              text, ranks evidence, or infers which evidence answers what. Every
              evidence id is supplied explicitly by the human; there is no
              search, no scoring and NO SUBSTRING MATCHING anywhere in this file.

THE PUBLIC BOUNDARY -- THERE IS NO "JUST WRITE IT" ENTRY POINT

    preview(...)      validate an action and report what it WOULD do. Writes
                      nothing. Returns a previewToken bound to the exact state
                      reviewed. A preview is NOT an approval.
    commit(...)       perform exactly the previewed action, and only if the
                      recomputed token still matches current state.
    reevaluate(...)   re-run the existing read-only evaluators.

    The three governed actions, selected by the `action` argument:

        QUESTION_ADJUDICATION        accepted / rejected / uncertain
        DIRECT_TRADER_CLARIFICATION  preserved educator answer -> evidence
        CONTRADICTION_RULING         explicit operator ruling

    The `_record_*` / `_plan_*` / `_apply_*` functions below are PRIVATE
    implementation detail (MOGO-020 Step 5.3.1). They were public through Step
    4, which left a path that could write a governed research decision without
    ever producing a preview -- exactly the stale-approval hazard the Step 4
    boundary exists to prevent. They keep every fail-closed check they always
    had; they are simply no longer a supported way in.

SOURCE FACT != OPERATOR RULING

    A ruling is recorded ON the question/contradiction and in the append-only
    lifecycle history. This module NEVER edits a Claim, never edits an
    EvidenceItem's exactExcerpt, and never rewrites source material to encode
    somebody's interpretation of it. The two source claims behind a ruled
    contradiction stay byte-identical.

CANDIDATE EVIDENCE != ACCEPTED ANSWER

    DIRECT_TRADER_CLARIFICATION deliberately does NOT answer the question it
    was collected for. It creates governed evidence and stops. That evidence
    becomes a CANDIDATE; accepting it is a separate, explicit second act by a
    human -- its own preview, its own token, its own commit. Even an answer
    straight from the educator's mouth does not self-promote to an accepted
    answer.

ACCEPTED ANSWER != STRATEGY RULE

    This module creates NO EvidenceClaimLink and NO RuleCandidateProposal, and
    never calls extraction_pipeline.run_post_annotation_pipeline() -- directly
    or transitively. Linking evidence to a claim triggers confidence
    recomputation, which can raise a claim to `supported`, which is the input
    that pipeline turns into a proposal. That chain stays broken here, by
    construction. Reevaluation is a separate, later, explicitly authorized step.
"""
import argparse
import glob as globmod
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc                              # noqa: E402
import evidence_common as evc                          # noqa: E402
import evidence_registry as reg                        # noqa: E402
import research_understanding as ru                    # noqa: E402
from query_evidence import EvidenceIndex               # noqa: E402
from candidate_search import resolve_corpus, SearchRefused  # noqa: E402

INTAKE_SCHEMA_VERSION = "mogo.governed-answer-intake.v1"

# Every write this module makes is one of these. "reviewed" is the existing
# LIFECYCLE_EVENT_TYPES value for a human decision; no new event type was added.
_ADJUDICATION_EVENT_TYPE = "reviewed"

# Outcome labels returned to the caller. Not stored statuses -- these describe
# what this CALL did, so a replay is visibly distinguishable from a first write.
APPLIED = "APPLIED"
DUPLICATE_NOOP = "DUPLICATE_NOOP"

# The three governed actions. Closed set -- preview/commit refuse anything else.
QUESTION_ADJUDICATION = "question_adjudication"
DIRECT_TRADER_CLARIFICATION = "direct_trader_clarification"
CONTRADICTION_RULING = "contradiction_ruling"
ACTIONS = (QUESTION_ADJUDICATION, DIRECT_TRADER_CLARIFICATION, CONTRADICTION_RULING)

_DIR_NAMES = ("sources", "items", "claims", "links", "lifecycle", "contradictions",
              "questions", "proposals")


def _dirs(evidence_root):
    return {name: os.path.join(evidence_root, name) for name in _DIR_NAMES}


def _fail(message):
    raise evc.EvidenceValidationError(message)


def _changed_fields(before, after):
    """Exactly which stored fields a plan would change, old -> new. Empty when a
    plan writes no record at all (a rejection)."""
    return {key: {"from": before.get(key), "to": after.get(key)}
            for key in sorted(set(before) | set(after))
            if before.get(key) != after.get(key)}


def _require_text(value, field):
    """A required human-supplied string. Empty/whitespace-only is refused --
    never silently coerced to None or to a placeholder."""
    if not isinstance(value, str) or not value.strip():
        _fail("%s is required and must be a non-empty string (got %r)" % (field, value))
    return value


# ---------------------------------------------------------------------------
# Idempotency -- reuses the existing content-hash primitive, not a new framework
# ---------------------------------------------------------------------------

def _fingerprint(payload):
    """SHA-256 over the canonicalized decision tuple (graph_common.content_hash_of,
    the same primitive used for claim fingerprints and evidence content hashes).
    Two identical decisions fingerprint identically; any difference in target,
    decision, cited evidence, actor or rationale produces a different value."""
    return gc.content_hash_of(payload)


def _events_for(lifecycle_dir, entityType, entityId):
    """Existing lifecycle events for one entity, read from their own recorded
    entityType/entityId (lifecycle filenames are hash-derived, so a filename
    scan cannot find them -- same reason evidence_common.next_lifecycle_event_id
    reads file contents)."""
    out = []
    if not os.path.isdir(lifecycle_dir):
        return out
    for path in sorted(globmod.glob(os.path.join(lifecycle_dir, "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            event = json.load(f)
        if event.get("entityType") == entityType and event.get("entityId") == entityId:
            out.append(event)
    return out


def _prior_decision(events, fingerprint):
    for event in events:
        if (event.get("metadata") or {}).get("decisionFingerprint") == fingerprint:
            return event
    return None


# ---------------------------------------------------------------------------
# Shared validation
# ---------------------------------------------------------------------------

def _load_question(idx, questionId):
    if not isinstance(questionId, str) or questionId not in idx.questions:
        _fail("no EvidenceQuestion %r exists; refusing to adjudicate an unknown question" % (questionId,))
    return idx.questions[questionId]


def _question_corpus(idx, question):
    """The trader whose corpus this question belongs to, via the existing
    fail-closed resolver (candidate_search.resolve_corpus) -- resolved from
    governed identifiers only, never from the words in the question."""
    try:
        return resolve_corpus(idx, question)
    except SearchRefused as exc:
        _fail("corpus attribution failed for %r: %s" % (question["questionId"], exc))


def _validate_evidence_ids(idx, evidenceIds, corpus_trader, field="evidenceIds"):
    """Every cited evidence id must be an EXACT, existing, in-corpus,
    provenance-complete, hash-verified EvidenceItem. Returns the deduplicated,
    sorted list actually validated.

    Identity is by exact governed id. There is no substring match, no prefix
    match and no fuzzy resolution anywhere in this function.
    """
    if not isinstance(evidenceIds, (list, tuple)) or not evidenceIds:
        _fail("%s must be a non-empty list of exact EvidenceItem ids" % (field,))
    validated = []
    for evidenceId in evidenceIds:
        if not isinstance(evidenceId, str):
            _fail("%s contains a non-string entry %r" % (field, evidenceId))
        item = idx.items.get(evidenceId)
        if item is None:
            _fail("evidence %r does not exist; refusing to cite missing evidence" % (evidenceId,))

        source = idx.sources.get(item.get("sourceId"))
        if source is None:
            _fail("evidence %r references nonexistent sourceId %r (incomplete provenance)"
                  % (evidenceId, item.get("sourceId")))

        # ── corpus isolation ──
        # Terminology overlap between educators must never pull one corpus into
        # another's accepted answers. The check is on the governed traderId, not
        # on any text.
        item_trader = source.get("traderId")
        if not item_trader:
            _fail("evidence %r belongs to source %r which has no traderId; corpus attribution "
                  "is ambiguous and is refused rather than guessed" % (evidenceId, source["sourceId"]))
        if item_trader != corpus_trader:
            _fail("evidence %r belongs to corpus %r but the question belongs to corpus %r; "
                  "foreign-corpus evidence is refused" % (evidenceId, item_trader, corpus_trader))

        # ── provenance completeness ──
        if source.get("provenanceStatus") == "unverified":
            _fail("evidence %r comes from source %r with provenanceStatus='unverified'; "
                  "incomplete provenance is refused" % (evidenceId, source["sourceId"]))
        if not item.get("directness"):
            _fail("evidence %r has no directness recorded; incomplete provenance is refused"
                  % (evidenceId,))

        # ── hash verification ──
        # Recomputed exactly as validate_evidence.check_inconsistent_hash does,
        # so the two can never disagree about what a correct hash is.
        expected = None
        if item.get("exactExcerpt") or item.get("normalizedObservation"):
            expected = gc.content_hash_of({
                "exactExcerpt": item.get("exactExcerpt"),
                "normalizedObservation": item.get("normalizedObservation"),
            })
        if item.get("contentHash") != expected:
            _fail("evidence %r fails hash verification (stored %r, recomputed %r); content may have "
                  "been edited in place" % (evidenceId, item.get("contentHash"), expected))

        validated.append(evidenceId)
    return sorted(set(validated))


# ---------------------------------------------------------------------------
# 1. EvidenceQuestion adjudication
# ---------------------------------------------------------------------------

# The ONLY state changes this module will make to an EvidenceQuestion. Both
# target values already exist in evc.QUESTION_ANSWER_STATUSES /
# QUESTION_RESEARCH_STATUSES -- MOGO-020 invented no question status.
#
#   accepted   -> answered          (requires cited evidence)
#   uncertain  -> partially_answered when evidence is cited; otherwise the
#                 answer state is left ALONE and only researchStatus moves to
#                 "researching". This is deliberate: "answered-ish with no
#                 evidence" is exactly the inconsistent shape the Step 1 audit
#                 found on EQ|20260727|015, and this module will not create more
#                 of it.
#   rejected   -> NO state change at all. A rejection is history, not an answer.
_ANSWER_STATUS_BY_DECISION = {
    "accepted": "answered",
    "uncertain": "partially_answered",
}
_RESEARCH_STATUS_BY_DECISION = {
    "accepted": "answered",
    "uncertain": "researching",
}


def _plan_question_adjudication(idx, dirs, questionId, decision, reviewer, now,
                                 evidenceIds=None, rationale=None):
    """FULL validation for one adjudication, plus the exact state it would
    produce. WRITES NOTHING.

    This is the single authority on whether an adjudication is legal. Both
    preview() and commit() call it -- commit never trusts a preview's verdict,
    it re-derives it from current state.
    """
    if decision not in evc.ADJUDICATION_DECISIONS:
        _fail("unknown adjudication decision %r (expected one of %r)"
              % (decision, evc.ADJUDICATION_DECISIONS))
    evc.require_human_actor(reviewer, "reviewer")

    question = _load_question(idx, questionId)
    corpus_trader = _question_corpus(idx, question)

    # `accepted` and `rejected` must both name what they are acting on. Only
    # `uncertain` may legitimately cite nothing ("I looked; still not settled").
    if decision in ("accepted", "rejected"):
        validated_ids = _validate_evidence_ids(idx, evidenceIds, corpus_trader)
    elif evidenceIds:
        validated_ids = _validate_evidence_ids(idx, evidenceIds, corpus_trader)
    else:
        validated_ids = []

    fingerprint = _fingerprint({
        "op": "question_adjudication", "questionId": questionId, "decision": decision,
        "evidenceIds": validated_ids, "reviewer": reviewer, "rationale": rationale,
    })
    events = _events_for(dirs["lifecycle"], "EVIDENCE_QUESTION", questionId)

    # Exact replay -> deterministic no-op. Checked BEFORE the conflict rule, so
    # re-running the identical accepted adjudication is idempotent rather than
    # tripping the "already answered" guard it created itself.
    duplicate_of = _prior_decision(events, fingerprint)

    prior_answer_status = question["answerStatus"]

    # ── legal prior state ──
    # Skipped for an exact replay: re-submitting the identical decision must be
    # idempotent, not trip the "already answered" guard it created itself.
    if (duplicate_of is None and decision in ("accepted", "uncertain")
            and prior_answer_status == "answered"):
        accepted_before = sorted(question.get("answerEvidenceIds") or [])
        _fail("question %r is already answerStatus='answered' with answerEvidenceIds=%r; a "
              "different %s adjudication citing %r is an inconsistent duplicate and is refused. "
              "Supersede the existing answer explicitly instead."
              % (questionId, accepted_before, decision, validated_ids))

    record = dict(question)
    new_answer_status = prior_answer_status
    if decision in _ANSWER_STATUS_BY_DECISION and validated_ids:
        new_answer_status = _ANSWER_STATUS_BY_DECISION[decision]
        record["answerStatus"] = new_answer_status
        record["answerEvidenceIds"] = sorted(set((record.get("answerEvidenceIds") or []) + validated_ids))
    if decision in _RESEARCH_STATUS_BY_DECISION:
        record["researchStatus"] = _RESEARCH_STATUS_BY_DECISION[decision]

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    if decision == "accepted":
        record["resolvedAt"] = now_iso

    # Post-condition. An answered/partially_answered question MUST cite the
    # evidence that answers it; anything else is unverifiable by construction.
    if record["answerStatus"] in ("answered", "partially_answered") and not record.get("answerEvidenceIds"):
        _fail("refusing to write answerStatus=%r with an empty answerEvidenceIds on %r"
              % (record["answerStatus"], questionId))

    # The event that WOULD be appended. build_lifecycle_event only READS the
    # lifecycle directory to derive the next sequence number.
    event = evc.build_lifecycle_event(
        dirs["lifecycle"], "EVIDENCE_QUESTION", questionId, _ADJUDICATION_EVENT_TYPE, reviewer, now,
        priorStatus=prior_answer_status, newStatus=record["answerStatus"],
        reason=rationale or ("Human adjudication: %s." % decision),
        metadata={"decision": decision, "decisionFingerprint": fingerprint,
                  "evidenceIds": validated_ids, "corpusTraderId": corpus_trader,
                  "intakeSchemaVersion": INTAKE_SCHEMA_VERSION})

    return {
        "action": QUESTION_ADJUDICATION,
        "targetType": "EVIDENCE_QUESTION", "targetId": questionId,
        "actor": reviewer, "decision": decision, "rationale": rationale,
        "corpusTraderId": corpus_trader, "evidenceIds": validated_ids,
        "priorRecord": question, "newRecord": record,
        "changedFields": _changed_fields(question, record),
        "writesRecord": decision != "rejected",
        "recordDir": "questions", "recordFilename": evc.question_id_to_filename(questionId),
        "event": event, "actionFingerprint": fingerprint, "duplicateOf": duplicate_of,
    }


def _apply_question_plan(dirs, plan):
    if plan["duplicateOf"] is not None:
        return {"outcome": DUPLICATE_NOOP, "questionId": plan["targetId"],
                "decision": plan["decision"], "question": plan["priorRecord"],
                "event": plan["duplicateOf"], "evidenceIds": plan["evidenceIds"]}
    if plan["writesRecord"]:
        path = os.path.join(dirs["questions"], plan["recordFilename"])
        gc.atomic_write_text(path, gc.pretty_json(plan["newRecord"]))
    evc.write_lifecycle_event(dirs["lifecycle"], plan["event"])
    return {"outcome": APPLIED, "questionId": plan["targetId"], "decision": plan["decision"],
            "question": plan["newRecord"], "event": plan["event"],
            "evidenceIds": plan["evidenceIds"]}


def _record_question_adjudication(evidence_root, questionId, decision, reviewer, now,
                                  evidenceIds=None, rationale=None):
    """Record one human adjudication of one EvidenceQuestion.

    The human supplies the decision AND the exact evidence it rests on. This
    function validates and records; it never selects evidence and never decides
    whether the evidence is semantically sufficient.
    """
    dirs = _dirs(evidence_root)
    idx = EvidenceIndex.load(evidence_root)
    plan = _plan_question_adjudication(idx, dirs, questionId, decision, reviewer, now,
                                        evidenceIds=evidenceIds, rationale=rationale)
    return _apply_question_plan(dirs, plan)


# ---------------------------------------------------------------------------
# 2. Direct-trader clarification
# ---------------------------------------------------------------------------

# Directness values that assert "the educator actually said/showed this". These
# are the ones that require preserved source material.
_PRESERVED_SOURCE_REQUIRED = ("direct_explicit", "direct_demonstrated")


_CLARIFICATION_DEFAULTS = {
    "directness": "direct_explicit", "evidenceType": "explicit_statement",
    "evidenceQuality": "high", "extractionCertainty": "high",
    "normalizedObservation": None, "observationDate": None, "sourceLocator": None,
    "title": None, "licensingStatus": "unknown", "provenanceStatus": "partially_verified",
    "timeframe": None, "session": None, "marketCondition": None, "marketSymbol": None,
}


def _plan_direct_trader_clarification(idx, dirs, questionId, reviewer, now, traderId,
                                       speaker, exactExcerpt, sourceChannel, sourceDate,
                                       **options):
    """FULL validation for one direct-trader clarification, plus the identifiers
    and records it would create. WRITES NOTHING."""
    unknown = sorted(set(options) - set(_CLARIFICATION_DEFAULTS))
    if unknown:
        _fail("unknown clarification option(s) %r" % (unknown,))
    opts = dict(_CLARIFICATION_DEFAULTS, **options)
    directness = opts["directness"]

    evc.require_human_actor(reviewer, "reviewer")
    if directness not in evc.DIRECTNESS_CLASSIFICATIONS:
        _fail("unknown directness %r" % (directness,))

    question = _load_question(idx, questionId)
    corpus_trader = _question_corpus(idx, question)

    if not isinstance(traderId, str) or traderId != corpus_trader:
        _fail("clarification is attributed to trader %r but question %r belongs to corpus %r; "
              "cross-corpus attribution is refused" % (traderId, questionId, corpus_trader))

    # ── THE FAIL-CLOSED GATE ──
    # A direct claim about what the educator said requires the preserved
    # material, an identified speaker, an identified channel and a date. Any
    # missing piece means this is somebody's recollection, not direct evidence.
    if directness in _PRESERVED_SOURCE_REQUIRED:
        _require_text(exactExcerpt, "exactExcerpt (preserved source material)")
        _require_text(speaker, "speaker")
        _require_text(sourceChannel, "sourceChannel")
        _require_text(sourceDate, "sourceDate")

    fingerprint = _fingerprint({
        "op": "direct_trader_clarification", "questionId": questionId, "traderId": traderId,
        "speaker": speaker, "exactExcerpt": exactExcerpt, "sourceChannel": sourceChannel,
        "sourceDate": sourceDate, "directness": directness,
    })

    # Deterministic duplicate handling: an identical clarification returns the
    # evidence already recorded instead of minting a second copy of it.
    duplicate_of = None
    for evidenceId in sorted(idx.items):
        existing = idx.items[evidenceId]
        if (existing.get("metadata") or {}).get("clarificationFingerprint") == fingerprint:
            duplicate_of = existing
            break

    # The identifiers this clarification WOULD receive. Both helpers only read
    # their directory to derive the next sequence number, so predicting the id
    # costs nothing and writes nothing -- and because the prediction depends on
    # current directory contents, a source registered between preview and commit
    # changes it, which the preview token then catches.
    planned_source_id = evc.next_source_id(dirs["sources"], traderId, now)
    planned_evidence_id = "EV|%s|%03d" % (planned_source_id, 1)

    return {
        "action": DIRECT_TRADER_CLARIFICATION,
        "targetType": "EVIDENCE_QUESTION", "targetId": questionId,
        "actor": reviewer, "decision": "record_candidate_evidence", "rationale": None,
        "corpusTraderId": corpus_trader, "evidenceIds": [],
        "traderId": traderId, "speaker": speaker, "sourceChannel": sourceChannel,
        "sourceDate": sourceDate, "directness": directness,
        "exactExcerpt": exactExcerpt, "questionAsked": question["questionText"],
        "plannedSourceId": planned_source_id, "plannedEvidenceId": planned_evidence_id,
        # A clarification creates CANDIDATE evidence and nothing else. It writes
        # no link, so no claim's evidence set changes and the question it was
        # collected for stays exactly as unresolved as it was.
        "answersQuestion": False,
        "priorRecord": question, "newRecord": question,
        "changedFields": {}, "writesRecord": False,
        "event": None, "actionFingerprint": fingerprint, "duplicateOf": duplicate_of,
        "_options": opts,
    }


def _apply_clarification_plan(dirs, plan, now):
    if plan["duplicateOf"] is not None:
        existing = plan["duplicateOf"]
        return {"outcome": DUPLICATE_NOOP, "questionId": plan["targetId"],
                "evidenceItem": existing, "source": None,
                "evidenceId": existing["evidenceId"]}
    opts = plan["_options"]
    source = reg.register_source(
        dirs["sources"], dirs["lifecycle"], "note", plan["actor"], now,
        traderId=plan["traderId"],
        title=opts["title"] or ("Direct clarification from %s" % plan["traderId"]),
        storageLocationType="repository", canonicalReference=plan["sourceChannel"],
        sourceDate=plan["sourceDate"], licensingStatus=opts["licensingStatus"],
        provenanceStatus=opts["provenanceStatus"],
        metadata={"clarificationForQuestionId": plan["targetId"],
                  "sourceChannel": plan["sourceChannel"],
                  "intakeSchemaVersion": INTAKE_SCHEMA_VERSION})

    item = reg.register_evidence_item(
        dirs["items"], dirs["sources"], dirs["lifecycle"], source["sourceId"],
        opts["evidenceType"], opts["evidenceQuality"], plan["actor"], now,
        exactExcerpt=plan["exactExcerpt"], normalizedObservation=opts["normalizedObservation"],
        extractionMethod="manual_owner_entry", directness=plan["directness"],
        extractionCertainty=opts["extractionCertainty"], speaker=plan["speaker"],
        observationDate=opts["observationDate"] or plan["sourceDate"],
        sourceLocator=opts["sourceLocator"], timeframe=opts["timeframe"],
        session=opts["session"], marketCondition=opts["marketCondition"],
        marketSymbol=opts["marketSymbol"],
        metadata={"clarificationFingerprint": plan["actionFingerprint"],
                  "answersQuestionId": plan["targetId"],
                  "questionAsked": plan["questionAsked"],
                  "sourceChannel": plan["sourceChannel"],
                  "candidateOnly": True,
                  "intakeSchemaVersion": INTAKE_SCHEMA_VERSION})

    return {"outcome": APPLIED, "questionId": plan["targetId"], "source": source,
            "evidenceItem": item, "evidenceId": item["evidenceId"]}


def _record_direct_trader_clarification(evidence_root, questionId, reviewer, now, traderId,
                                        speaker, exactExcerpt, sourceChannel, sourceDate,
                                        **options):
    """Record a preserved educator/trader clarification as governed evidence.

    THIS DOES NOT ANSWER THE QUESTION. It creates an EvidenceSource +
    EvidenceItem carrying the preserved material, tagged with the question it
    was collected for. Promoting it to an accepted answer is a separate,
    explicit call to _record_question_adjudication() by a human.

    FREE-FORM TEXT ALONE MUST NOT BECOME AUTHORITATIVE DIRECT-TRADER EVIDENCE:
    claiming `direct_explicit`/`direct_demonstrated` without preserved source
    material fails closed.
    """
    dirs = _dirs(evidence_root)
    idx = EvidenceIndex.load(evidence_root)
    plan = _plan_direct_trader_clarification(
        idx, dirs, questionId, reviewer, now, traderId, speaker, exactExcerpt,
        sourceChannel, sourceDate, **options)
    return _apply_clarification_plan(dirs, plan, now)


# ---------------------------------------------------------------------------
# 3. Operator contradiction ruling
# ---------------------------------------------------------------------------

def _plan_contradiction_ruling(idx, dirs, contradictionId, ruling, operator, now,
                                rationale=None, scopeOverlap=None):
    """FULL validation for one operator ruling, plus the exact state it would
    produce. WRITES NOTHING."""
    if ruling not in evc.CONTRADICTION_RULINGS:
        _fail("unknown contradiction ruling %r (expected one of %r)"
              % (ruling, sorted(evc.CONTRADICTION_RULINGS)))
    evc.require_human_actor(operator, "operator")
    _require_text(rationale, "rationale")
    if scopeOverlap is not None and scopeOverlap not in ("full", "partial", "none", "unknown"):
        _fail("unknown scopeOverlap %r" % (scopeOverlap,))

    record = idx.contradictions.get(contradictionId)
    if record is None:
        _fail("no ContradictionRecord %r exists; refusing to rule on an unknown contradiction"
              % (contradictionId,))

    target_status = evc.CONTRADICTION_RULINGS[ruling]
    fingerprint = _fingerprint({
        "op": "contradiction_ruling", "contradictionId": contradictionId, "ruling": ruling,
        "operator": operator, "rationale": rationale, "scopeOverlap": scopeOverlap,
    })
    events = _events_for(dirs["lifecycle"], "CONTRADICTION_RECORD", contradictionId)
    duplicate_of = _prior_decision(events, fingerprint)

    prior_status = record["status"]
    # Legal prior state: only an OPEN contradiction may be ruled on. A record
    # already settled by an earlier ruling must be reopened explicitly rather
    # than silently overwritten by a second, different one. Skipped for an exact
    # replay, which must stay idempotent.
    if duplicate_of is None and prior_status != "open":
        _fail("contradiction %r is already status=%r; a further %r ruling is an illegal "
              "transition and is refused" % (contradictionId, prior_status, ruling))

    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = dict(record)
    updated["status"] = target_status
    updated["reviewedAt"] = now_iso
    if scopeOverlap is not None:
        updated["scopeOverlap"] = scopeOverlap
    # `resolution` is the RULING-time field and is set only when the ruling
    # actually settles something. leave_open records the operator's reasoning in
    # history without making an open contradiction look resolved.
    if ruling != "leave_open":
        updated["resolution"] = rationale

    event = evc.build_lifecycle_event(
        dirs["lifecycle"], "CONTRADICTION_RECORD", contradictionId, "status_changed", operator, now,
        priorStatus=prior_status, newStatus=target_status, reason=rationale,
        metadata={"ruling": ruling, "decisionFingerprint": fingerprint,
                  "scopeOverlap": updated.get("scopeOverlap"),
                  "intakeSchemaVersion": INTAKE_SCHEMA_VERSION})

    return {
        "action": CONTRADICTION_RULING,
        "targetType": "CONTRADICTION_RECORD", "targetId": contradictionId,
        "actor": operator, "decision": ruling, "rationale": rationale,
        # Named for the operator's benefit, and deliberately NOT touched: an
        # operator ruling is governance interpretation, never a source fact.
        "sourceClaimIds": [record["claimAId"], record["claimBId"]],
        "evidenceIds": [],
        "corpusTraderId": (idx.claims.get(record["claimAId"]) or {}).get("traderId"),
        "priorRecord": record, "newRecord": updated,
        "changedFields": _changed_fields(record, updated),
        "writesRecord": True,
        "recordDir": "contradictions",
        "recordFilename": evc.contradiction_id_to_filename(contradictionId),
        "event": event, "actionFingerprint": fingerprint, "duplicateOf": duplicate_of,
    }


def _apply_contradiction_plan(dirs, plan):
    if plan["duplicateOf"] is not None:
        return {"outcome": DUPLICATE_NOOP, "contradictionId": plan["targetId"],
                "ruling": plan["decision"], "contradiction": plan["priorRecord"],
                "event": plan["duplicateOf"]}
    path = os.path.join(dirs["contradictions"], plan["recordFilename"])
    gc.atomic_write_text(path, gc.pretty_json(plan["newRecord"]))
    evc.write_lifecycle_event(dirs["lifecycle"], plan["event"])
    return {"outcome": APPLIED, "contradictionId": plan["targetId"], "ruling": plan["decision"],
            "contradiction": plan["newRecord"], "event": plan["event"]}


def _record_contradiction_ruling(evidence_root, contradictionId, ruling, operator, now,
                                 rationale, scopeOverlap=None):
    """Record one explicit human operator ruling on one ContradictionRecord.

    Both underlying Claims are left byte-identical -- ADR-008 sec. 8: a
    contradiction is never resolved by editing or deleting either claim. The
    ruling lives on the ContradictionRecord and in append-only history.
    """
    dirs = _dirs(evidence_root)
    idx = EvidenceIndex.load(evidence_root)
    plan = _plan_contradiction_ruling(idx, dirs, contradictionId, ruling, operator, now,
                                       rationale=rationale, scopeOverlap=scopeOverlap)
    return _apply_contradiction_plan(dirs, plan)


# ---------------------------------------------------------------------------
# 4. Deterministic post-intake reevaluation (MOGO-020 Step 3)
# ---------------------------------------------------------------------------
#
# THE SEMANTIC BOUNDARY THIS IMPLEMENTS
#
#     governed intake -> record the human decision -> READ-ONLY reevaluation
#
#     NOT: governed intake -> strategy generation.
#
# reevaluate() re-runs the EXISTING Step 2/3/4 evaluators over current state and
# reports what they now say. It re-derives nothing itself: there is no second
# eligibility engine, no second routing table and no second corpus view in this
# file. Every judgement below is made by research_understanding.py, unchanged.
#
# It makes no second semantic judgement of its own, and it cannot turn an
# accepted answer into a mechanical rule -- it has no code path to
# RuleCandidateProposal, specification freeze, backtesting or paper execution.


def blocker_key(blocker):
    """Stable identity for one Step 3 blocker, for before/after comparison.
    Derived from the blocker's own governed identifiers -- never from prose."""
    return "%s|%s" % (blocker["blockerType"],
                      blocker.get("questionId") or blocker.get("contradictionId")
                      or blocker.get("ruleCategory") or "")


def _reevaluate_index(idx, evidence_root, traderId, approved_destinations):
    """The evaluator chain over an ALREADY-LOADED index. Splitting this out is
    what lets preview() compute the prospective result against an in-memory
    index rather than by writing anything anywhere."""
    view = ru.corpus_view(idx, traderId)
    eligibility = ru.eligibility(view)
    gaps = ru.load_gaps(evidence_root)
    plan = ru.research_plan(view, eligibility, gaps,
                            approved_destinations=approved_destinations)
    return {
        "schemaVersion": INTAKE_SCHEMA_VERSION,
        "traderId": traderId,
        "readOnly": True,
        "view": view,
        "eligibility": eligibility,
        "plan": plan,
        "eligibilityStatus": eligibility["eligibility"],
        "blockerCount": eligibility["blockerCount"],
        "blockerKeys": sorted(blocker_key(b) for b in eligibility["blockers"]),
        "countsByAction": dict(plan["countsByAction"]),
        "meaning": "Informational only. Reevaluation reports what the existing "
                   "evaluators say about current evidence; it creates no rule "
                   "candidate, freezes no specification and authorizes nothing.",
    }


def reevaluate(evidence_root, traderId, approved_destinations=None):
    """Re-run the existing read-only research evaluation layers for one corpus.

    STRICTLY READ-ONLY. Loads the current records and calls, in order:

        research_understanding.corpus_view()    -- Step 2 understanding
        research_understanding.eligibility()    -- Step 3 reconstruction eligibility
        research_understanding.research_plan()  -- Step 4 research routing

    Writes nothing: no record, no lifecycle event, no link, no proposal. Running
    it twice on unchanged state returns the same answer and leaves the corpus
    byte-identical.

    INFORMATIONAL. Eligibility describing a corpus as
    ELIGIBLE_FOR_RECONSTRUCTION_DRAFT means the evidence contains no known
    blocker. It does NOT freeze a specification, approve a strategy, or
    authorize backtesting, paper trading or live trading -- each remains a
    separate explicit operator decision that this function cannot make.
    """
    return _reevaluate_index(EvidenceIndex.load(evidence_root), evidence_root,
                             traderId, approved_destinations)


# ---------------------------------------------------------------------------
# 5. Preview and explicit commit boundary (MOGO-020 Step 4)
# ---------------------------------------------------------------------------
#
# THE SAFETY PROBLEM THIS SOLVES
#
#     operator reviews STATE A -> state changes -> stale approval writes
#     against STATE B.
#
# The fix is a deterministic PREVIEW TOKEN: a SHA-256 over the canonical
# serialization of (the exact action) + (the exact stored state it was reviewed
# against). commit() recomputes both from CURRENT disk state and refuses if the
# recomputed token differs. No locking, no transaction manager, no server.
#
# This mirrors two patterns the repository already uses:
#
#   * ingest.py refuses to proceed when a manifest and its normalization map
#     disagree on `sourceFileSha256` -- a recorded hash compared against current
#     state, failing closed;
#   * the platform composes an idempotency key as "the SHA-256 of the canonical
#     serialization of the operation together with its parts", with the declared
#     parts fixed so "a caller cannot quietly widen or narrow a key"
#     (contracts/ids.py). _MATERIAL_PARTS below is that same discipline.
#
# It uses graph_common.content_hash_of -- the Knowledge Library's own hashing
# primitive -- rather than importing the trading platform, which this research
# layer must never depend on.

PREVIEW_SCHEMA_VERSION = "mogo.governed-intake-preview.v1"

# The declared parts of a material-state fingerprint. Fixed, so a caller can
# neither widen nor narrow what a token attests to.
_MATERIAL_PARTS = ("action", "targetType", "targetId", "targetRecord",
                   "corpusTraderId", "evidence", "sources", "plannedIds")


def _material_state(idx, plan):
    """The exact stored state this decision was reviewed against.

    Deliberately includes the WHOLE target record, so any change to it -- status,
    answer fields, anything -- invalidates a token. Evidence contributes its
    content hash, owning source, directness and status; each owning source
    contributes the two fields that govern admissibility (corpus and provenance).
    """
    evidence = {}
    sources = {}
    for evidenceId in plan.get("evidenceIds") or []:
        item = idx.items.get(evidenceId) or {}
        evidence[evidenceId] = {
            "contentHash": item.get("contentHash"), "sourceId": item.get("sourceId"),
            "directness": item.get("directness"), "evidenceStatus": item.get("evidenceStatus"),
        }
        source = idx.sources.get(item.get("sourceId")) or {}
        sources[item.get("sourceId")] = {
            "traderId": source.get("traderId"),
            "provenanceStatus": source.get("provenanceStatus"),
        }
    parts = {
        "action": plan["action"],
        "targetType": plan["targetType"],
        "targetId": plan["targetId"],
        "targetRecord": plan["priorRecord"],
        "corpusTraderId": plan.get("corpusTraderId"),
        "evidence": evidence,
        "sources": sources,
        "plannedIds": [plan.get("plannedSourceId"), plan.get("plannedEvidenceId")],
    }
    assert set(parts) == set(_MATERIAL_PARTS)          # declared parts, no drift
    return gc.content_hash_of(parts)


def preview_token(idx, plan):
    """Bind ONE exact action to ONE exact reviewed state.

    Changing the target, the decision, the actor, the cited evidence, the
    rationale, or any material stored state all change this value -- so a token
    can never authorize an action other than the one it was issued for.
    """
    return gc.content_hash_of({
        "previewSchemaVersion": PREVIEW_SCHEMA_VERSION,
        "actionFingerprint": plan["actionFingerprint"],
        "materialState": _material_state(idx, plan),
    })


_PLANNERS = {
    QUESTION_ADJUDICATION: _plan_question_adjudication,
    DIRECT_TRADER_CLARIFICATION: _plan_direct_trader_clarification,
    CONTRADICTION_RULING: _plan_contradiction_ruling,
}


def _plan_action(idx, dirs, action, now, **kwargs):
    if action not in _PLANNERS:
        _fail("unknown governed action %r (expected one of %r)" % (action, list(ACTIONS)))
    return _PLANNERS[action](idx, dirs, now=now, **kwargs)


def _apply_action(dirs, plan, now):
    if plan["action"] == QUESTION_ADJUDICATION:
        return _apply_question_plan(dirs, plan)
    if plan["action"] == CONTRADICTION_RULING:
        return _apply_contradiction_plan(dirs, plan)
    return _apply_clarification_plan(dirs, plan, now)


def _prospective_index(evidence_root, plan):
    """A FRESH index with the planned change applied IN MEMORY ONLY.

    Nothing is copied to disk and nothing is written. The returned index is a
    throwaway object, so the prospective reevaluation below cannot leak into
    stored state even in principle.
    """
    idx = EvidenceIndex.load(evidence_root)
    if plan["action"] == QUESTION_ADJUDICATION and plan["writesRecord"]:
        idx.questions[plan["targetId"]] = plan["newRecord"]
    elif plan["action"] == CONTRADICTION_RULING:
        idx.contradictions[plan["targetId"]] = plan["newRecord"]
    elif plan["action"] == DIRECT_TRADER_CLARIFICATION and plan["duplicateOf"] is None:
        # Candidate evidence, carrying no link. The evaluators reach evidence
        # only through EvidenceClaimLinks, so this correctly changes nothing --
        # which is exactly the boundary the operator needs to see.
        idx.sources[plan["plannedSourceId"]] = {
            "sourceId": plan["plannedSourceId"], "traderId": plan["traderId"],
            "provenanceStatus": plan["_options"]["provenanceStatus"],
        }
        idx.items[plan["plannedEvidenceId"]] = {
            "evidenceId": plan["plannedEvidenceId"], "sourceId": plan["plannedSourceId"],
            "directness": plan["directness"], "evidenceStatus": "active",
        }
    return idx


def _safe_reevaluation(idx, evidence_root, traderId, approved_destinations):
    """Reevaluation that reports its own unavailability instead of raising.

    A preview must still be renderable for a corpus the evaluators refuse to
    view (e.g. an unattributed claim makes corpus isolation unprovable) -- the
    operator needs to be told that, not handed a traceback.
    """
    if not traderId:
        return {"available": False,
                "reason": "no corpus trader could be resolved for this action"}
    try:
        result = _reevaluate_index(idx, evidence_root, traderId, approved_destinations)
    except ru.CorpusAmbiguous as exc:
        return {"available": False, "reason": str(exc)}
    result["available"] = True
    return result


_NO_AUTHORITY = ("This preview authorizes nothing. It creates no RuleCandidateProposal, "
                 "freezes no strategy specification, starts no backtest, authorizes no "
                 "paper trading and changes no live-money authority. Each of those "
                 "remains a separate explicit operator decision.")


def preview(evidence_root, action, now, approved_destinations=None, **kwargs):
    """Deterministically validate a governed action and report what it WOULD do.

    WRITES NOTHING. Runs the same authoritative validation commit() relies on,
    then computes the prospective research state against an in-memory index.

    PREVIEW IS NOT APPROVAL. Producing a preview grants no permission; a human
    must separately decide, and then call commit() with the returned token.
    """
    dirs = _dirs(evidence_root)
    idx = EvidenceIndex.load(evidence_root)
    plan = _plan_action(idx, dirs, action, now, **kwargs)

    trader = plan.get("corpusTraderId")
    before = _safe_reevaluation(EvidenceIndex.load(evidence_root), evidence_root,
                                trader, approved_destinations)
    after = _safe_reevaluation(_prospective_index(evidence_root, plan), evidence_root,
                               trader, approved_destinations)

    before_keys = set(before.get("blockerKeys") or [])
    after_keys = set(after.get("blockerKeys") or [])
    comparable = before.get("available") and after.get("available")

    return {
        "schemaVersion": PREVIEW_SCHEMA_VERSION,
        "previewToken": preview_token(idx, plan),
        "isAuthorization": False,
        "wouldWrite": plan["duplicateOf"] is None,
        "duplicateOfEventId": (plan["duplicateOf"] or {}).get("eventId"),
        # ── the action ──
        "action": plan["action"],
        "targetType": plan["targetType"],
        "targetId": plan["targetId"],
        "actor": plan["actor"],
        "decision": plan["decision"],
        "rationale": plan["rationale"],
        "corpusTraderId": trader,
        "evidenceIds": plan["evidenceIds"],
        # ── state ──
        "currentRecord": plan["priorRecord"],
        "proposedRecord": plan["newRecord"],
        "changedFields": plan["changedFields"],
        "wouldAppendLifecycleEvent": plan["event"],
        # ── provenance / source separation ──
        "provenanceSummary": _provenance_summary(idx, plan),
        "sourceClaimIds": plan.get("sourceClaimIds", []),
        "sourceClaimsUnchanged": True,
        "plannedSourceId": plan.get("plannedSourceId"),
        "plannedEvidenceId": plan.get("plannedEvidenceId"),
        "answersQuestion": plan.get("answersQuestion", plan["action"] == QUESTION_ADJUDICATION),
        # ── consequences, from the existing read-only evaluators only ──
        "reevaluationBefore": before,
        "reevaluationAfter": after,
        "blockersRemoved": sorted(before_keys - after_keys) if comparable else [],
        "blockersRetained": sorted(before_keys & after_keys) if comparable else [],
        "blockersAdded": sorted(after_keys - before_keys) if comparable else [],
        "eligibilityChanges": (comparable and
                               before.get("eligibilityStatus") != after.get("eligibilityStatus")),
        "eligibilityBefore": before.get("eligibilityStatus"),
        "eligibilityAfter": after.get("eligibilityStatus"),
        "routingChanged": (comparable and
                           before.get("countsByAction") != after.get("countsByAction")),
        "routingBefore": before.get("countsByAction"),
        "routingAfter": after.get("countsByAction"),
        "authorizes": _NO_AUTHORITY,
    }


def _provenance_summary(idx, plan):
    """Per cited evidence item: who said it, where it is preserved, and how
    directly -- so an operator reviews provenance, not just identifiers."""
    rows = []
    for evidenceId in plan.get("evidenceIds") or []:
        item = idx.items.get(evidenceId) or {}
        source = idx.sources.get(item.get("sourceId")) or {}
        rows.append({
            "evidenceId": evidenceId, "sourceId": item.get("sourceId"),
            "traderId": source.get("traderId"),
            "provenanceStatus": source.get("provenanceStatus"),
            "directness": item.get("directness"),
            "extractionCertainty": item.get("extractionCertainty"),
            "speaker": item.get("speaker"),
            "exactExcerpt": item.get("exactExcerpt"),
            "contentHash": item.get("contentHash"),
        })
    if plan["action"] == DIRECT_TRADER_CLARIFICATION:
        rows.append({
            "evidenceId": plan["plannedEvidenceId"], "sourceId": plan["plannedSourceId"],
            "traderId": plan["traderId"], "provenanceStatus": plan["_options"]["provenanceStatus"],
            "directness": plan["directness"], "speaker": plan["speaker"],
            "sourceChannel": plan["sourceChannel"], "sourceDate": plan["sourceDate"],
            "exactExcerpt": plan["exactExcerpt"], "candidateOnly": True,
        })
    return rows


def commit(evidence_root, action, now, previewToken, approved_destinations=None,
           reevaluate_after=True, **kwargs):
    """Perform exactly the previewed governed action -- and nothing else.

    Re-runs the authoritative validation from scratch; the preview's verdict is
    never trusted. If the recomputed token differs from `previewToken`, material
    state changed after review and the write is REFUSED.
    """
    if not isinstance(previewToken, str) or not previewToken.strip():
        _fail("commit requires the previewToken issued by preview(); refusing to write a "
              "governed research decision that was never previewed")

    dirs = _dirs(evidence_root)
    idx = EvidenceIndex.load(evidence_root)
    plan = _plan_action(idx, dirs, action, now, **kwargs)      # authoritative revalidation

    # An exact replay of an already-recorded decision is a no-op regardless of
    # token staleness: the intended effect already exists, and applying it again
    # is precisely what must NOT happen.
    if plan["duplicateOf"] is None:
        current = preview_token(idx, plan)
        if current != previewToken:
            _fail("material state changed after preview (previewToken %r, current %r); "
                  "the reviewed state no longer matches stored state, so the commit is "
                  "refused. Re-preview and review again." % (previewToken, current))

    result = _apply_action(dirs, plan, now)
    result["action"] = plan["action"]
    result["previewToken"] = previewToken
    result["authorizes"] = _NO_AUTHORITY
    if reevaluate_after and plan.get("corpusTraderId"):
        result["reevaluation"] = _safe_reevaluation(
            EvidenceIndex.load(evidence_root), evidence_root,
            plan["corpusTraderId"], approved_destinations)
    return result


# ---------------------------------------------------------------------------
# CLI -- deliberately requires an explicit --evidence-root. There is no default
# pointing at the live corpus: running this against production must be a
# conscious act, never the path of least resistance.
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="MOGO-020 governed answer intake. Records human decisions; makes none.")
    parser.add_argument("--evidence-root", required=True,
                        help="Evidence root to write to. REQUIRED -- no default.")
    sub = parser.add_subparsers(dest="command", required=True)

    adj = sub.add_parser("adjudicate", help="Record a human adjudication of an EvidenceQuestion.")
    adj.add_argument("--question-id", required=True)
    adj.add_argument("--decision", required=True, choices=evc.ADJUDICATION_DECISIONS)
    adj.add_argument("--reviewer", required=True, help="operator:<name> or reviewer:<name>")
    adj.add_argument("--evidence-id", action="append", dest="evidence_ids", default=[])
    adj.add_argument("--rationale", default=None)

    rule = sub.add_parser("rule-contradiction", help="Record an operator ruling on a contradiction.")
    rule.add_argument("--contradiction-id", required=True)
    rule.add_argument("--ruling", required=True, choices=sorted(evc.CONTRADICTION_RULINGS))
    rule.add_argument("--operator", required=True, help="operator:<name>")
    rule.add_argument("--rationale", required=True)
    rule.add_argument("--scope-overlap", default=None, choices=["full", "partial", "none", "unknown"])

    reev = sub.add_parser("reevaluate",
                          help="Re-run the existing read-only Step 2/3/4 evaluators. Writes nothing.")
    reev.add_argument("--trader", required=True)

    # Every mutating subcommand must say which side of the boundary it is on.
    # There is deliberately no bare "just write it" form: an operator either
    # previews, or commits an exact previewed action.
    for sub_parser in (adj, rule):
        mode = sub_parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--preview", action="store_true",
                          help="validate and report what WOULD happen. Writes nothing.")
        mode.add_argument("--commit-token", dest="commit_token", default=None,
                          help="the previewToken from a --preview run. Commits that exact action.")

    args = parser.parse_args(argv)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    if args.command == "reevaluate":
        result = reevaluate(args.evidence_root, args.trader)
        print("READ-ONLY reevaluation  trader=%s  eligibility=%s  blockers=%d"
              % (result["traderId"], result["eligibilityStatus"], result["blockerCount"]))
        for key in result["blockerKeys"]:
            print("  blocker  %s" % (key,))
        print("  " + result["meaning"])
        return 0

    if args.command == "adjudicate":
        action, action_kwargs = QUESTION_ADJUDICATION, {
            "questionId": args.question_id, "decision": args.decision,
            "reviewer": args.reviewer, "evidenceIds": args.evidence_ids or None,
            "rationale": args.rationale}
    else:
        action, action_kwargs = CONTRADICTION_RULING, {
            "contradictionId": args.contradiction_id, "ruling": args.ruling,
            "operator": args.operator, "rationale": args.rationale,
            "scopeOverlap": args.scope_overlap}

    if args.preview:
        try:
            result = preview(args.evidence_root, action, now, **action_kwargs)
        except evc.EvidenceValidationError as exc:
            print("REFUSED -- this action is not permissible; nothing was written")
            print("  %s" % (exc,))
            return 2
        print("PREVIEW -- NOTHING WRITTEN")
        print("  action     %s  target=%s" % (result["action"], result["targetId"]))
        print("  actor      %s  decision=%s" % (result["actor"], result["decision"]))
        print("  wouldWrite %s" % (result["wouldWrite"],))
        for field, change in sorted(result["changedFields"].items()):
            print("      %-20s %r -> %r" % (field, change["from"], change["to"]))
        print("  eligibility %s -> %s" % (result["eligibilityBefore"], result["eligibilityAfter"]))
        for key in result["blockersRemoved"]:
            print("      blocker removed   %s" % (key,))
        for key in result["blockersRetained"]:
            print("      blocker retained  %s" % (key,))
        print("  previewToken %s" % (result["previewToken"],))
        print("  " + result["authorizes"])
        print("  PREVIEW IS NOT APPROVAL. To apply, re-run with "
              "--commit-token %s" % (result["previewToken"],))
        return 0

    try:
        result = commit(args.evidence_root, action, now, args.commit_token, **action_kwargs)
    except evc.EvidenceValidationError as exc:
        # A refusal is an expected outcome of this boundary, not a crash. Report
        # it as one so an operator sees the reason rather than a traceback.
        print("REFUSED -- nothing was written")
        print("  %s" % (exc,))
        return 2
    print("%s  %s" % (result["outcome"], result.get("questionId") or result.get("contradictionId")))
    if result.get("reevaluation", {}).get("available"):
        print("  reevaluation  eligibility=%s  blockers=%d"
              % (result["reevaluation"]["eligibilityStatus"],
                 result["reevaluation"]["blockerCount"]))
    print("  " + result["authorizes"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
