"""MOGO-002.6 Phase 3 — inventory and classify the ALEX_G educator claim library.

READ-ONLY on `docs/trader-intelligence/evidence/`. Nothing in this module writes to,
mutates, or re-authors a source claim. Classification is DERIVED from fields the
evidence store already holds -- `claimType`, the linked evidence items' `directness`
and `evidenceType`, and blocking open questions -- so every classification is
attributable to existing repository data rather than to a fresh judgement call.

Where a derivation genuinely needs the claim's own wording (marketing and psychology
are not distinguishable from `claimType` alone), the lexical trigger is recorded in
the ClaimClassification's `derivedFrom`, so a reviewer can see exactly what drove it.
"""
import glob
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import ke_model as ke  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
EVIDENCE = os.path.join(REPO_ROOT, "docs", "trader-intelligence", "evidence")
EDUCATOR_ID = "ALEX_G"


class InventoryError(RuntimeError):
    """Raised when the claim library cannot be located or reconciled."""


# --- Load (read-only) -------------------------------------------------------

def _load_dir(name, key):
    out = {}
    for f in glob.glob(os.path.join(EVIDENCE, name, "*.json")):
        with open(f, encoding="utf-8") as fh:   # context-managed: no handle leak
            d = json.load(fh)
        out[d[key]] = d
    return out


def load_evidence():
    if not os.path.isdir(EVIDENCE):
        raise InventoryError(
            "evidence store not found at %s -- the ALEX_G educator claim library "
            "cannot be located. MOGO-002.6 stop condition." % EVIDENCE)
    claims = _load_dir("claims", "claimId")
    if not claims:
        raise InventoryError("evidence/claims is empty -- nothing to inventory.")
    return {
        "claims": claims,
        "items": _load_dir("items", "evidenceId"),
        "links": _load_dir("links", "linkId") if glob.glob(os.path.join(EVIDENCE, "links", "*.json")) else {},
        "sources": _load_dir("sources", "sourceId"),
        "contradictions": _load_dir("contradictions", "contradictionId"),
        "questions": _load_dir("questions", "questionId") if glob.glob(os.path.join(EVIDENCE, "questions", "*.json")) else {},
        "segments": _load_dir("segments", "segmentId") if glob.glob(os.path.join(EVIDENCE, "segments", "*.json")) else {},
    }


def _links_by_claim(ev):
    out = {}
    for l in ev["links"].values():
        out.setdefault(l["claimId"], []).append(l)
    return out


# --- Classification derivation ----------------------------------------------
#
# Ordered rules. The FIRST match wins, and the matching rule's name is recorded, so
# a reviewer can see which derivation fired rather than inferring it.

# claimType -> (classification, strategy domain). Straightforward structural mapping.
_TYPE_MAP = {
    "entry_rule":            ("ENTRY",               "ENTRY"),
    "confirmation_rule":     ("ENTRY",               "ENTRY"),
    "setup_requirement":     ("TRADING_RULE",        "SETUP"),
    "invalidation_rule":     ("INVALIDATION",        "INVALIDATION"),
    "stop_rule":             ("RISK",                "RISK"),
    "risk_rule":             ("RISK",                "RISK"),
    "target_rule":           ("TRADE_MANAGEMENT",    "TRADE_MANAGEMENT"),
    "trade_management_rule": ("TRADE_MANAGEMENT",    "TRADE_MANAGEMENT"),
    "session_rule":          ("SESSION",             "SESSION_RESTRICTIONS"),
    "timeframe_rule":        ("TIMEFRAME",           "TIMEFRAMES"),
    "definition":            ("DEFINITION",          "MARKET_STRUCTURE"),
    "marketCondition":       ("MARKET_CONTEXT",      "MARKET_CONDITIONS"),
    "failure_condition":     ("NO_TRADE_CONDITION",  "NO_TRADE_CONDITIONS"),
    "exception":             ("DISCRETIONARY_GUIDANCE", "DISCRETIONARY_ELEMENTS"),
    "behavioral_observation": ("EDUCATIONAL_COMMENTARY", "DISCRETIONARY_ELEMENTS"),
    "causal_hypothesis":     ("EDUCATIONAL_COMMENTARY", "MARKET_CONDITIONS"),
    "performance_hypothesis": ("MARKETING",          "UNRESOLVED_QUESTIONS"),
    "other":                 ("UNKNOWN",             "UNRESOLVED_QUESTIONS"),
}

# Lexical overrides. Applied ONLY to claim types that are not already rule-shaped,
# so a real trading rule can never be reclassified as psychology by a stray word.
_PSYCH = re.compile(
    r"mindset|psycholog|emotion|impulse|salary|money mindset|30/30/30|splurge|"
    r"surround yourself|attachment to the money|greed|fear|blame|displacement|"
    r"numbers on a screen|stop losing money|luxur", re.I)
_MARKETING = re.compile(
    r"\$\d|per day|a week as a beginner|payout|funded|students are claimed|"
    r"evaluation fee|% a month|accuracy|of traders lose", re.I)
_LIQUIDITY = re.compile(r"liquidit|sweep|liquidat", re.I)
_EXAMPLE = re.compile(r"in the demonstrated example|worked example|the source is a live", re.I)

_NON_RULE_TYPES = {"behavioral_observation", "causal_hypothesis", "performance_hypothesis",
                   "definition", "failure_condition", "other", "marketCondition"}


def classify_claim(claim, evidence_items, blocking_question_count):
    """Returns (classification, domain, explicitness, confidence, eligible, rationale, derived_from)."""
    ct = claim["claimType"]
    text = claim.get("normalizedClaim") or ""
    derived = ["claimType=%s" % ct]

    classification, domain = _TYPE_MAP.get(ct, ("UNKNOWN", "UNRESOLVED_QUESTIONS"))
    rule_name = "type_map"

    if ct in _NON_RULE_TYPES:
        if _MARKETING.search(text) and ct == "performance_hypothesis":
            classification, domain, rule_name = "MARKETING", "UNRESOLVED_QUESTIONS", "lexical_marketing"
            derived.append("lexical:marketing")
        elif _PSYCH.search(text):
            classification, domain, rule_name = "PSYCHOLOGY", "DISCRETIONARY_ELEMENTS", "lexical_psychology"
            derived.append("lexical:psychology")
        elif _EXAMPLE.search(text):
            classification, domain, rule_name = "EXAMPLE", "MARKET_CONDITIONS", "lexical_example"
            derived.append("lexical:example")
        elif _LIQUIDITY.search(text) and ct in ("definition", "failure_condition"):
            domain, rule_name = "LIQUIDITY", "lexical_liquidity"
            derived.append("lexical:liquidity")

    # Explicitness from the linked evidence's own `directness` -- the field the
    # extraction standard already uses (STANDARDS-extraction sec. 5b).
    directness = [i.get("directnessClassification") or i.get("directness")
                  for i in evidence_items]
    directness = [d for d in directness if d]
    derived.append("directness=%s" % ",".join(sorted(set(directness)) or ["none"]))
    if ct == "exception":
        explicitness = "DISCRETIONARY"
    elif any(d in ("direct_explicit", "direct_demonstrated") for d in directness):
        explicitness = "EXPLICIT"
    elif any(d == "indirect_implied" for d in directness):
        explicitness = "IMPLIED"
    elif any(d in ("inferred_from_context", "derived_from_analysis") for d in directness):
        explicitness = "INFERRED"
    else:
        explicitness = "UNRESOLVED"

    # A rule-shaped claim carrying a BLOCKING open question is UNRESOLVED in the
    # sense that matters, however plainly it was worded: the educator stated
    # something, but not enough of it to act on. Reporting these as EXPLICIT would
    # overstate the library -- 188 of 195 came back EXPLICIT before this guard,
    # which flattered material that is frequently missing its own parameters.
    # This mirrors MOGO-002.5's treatment of ALEX_SR_008, which is directly stated
    # and still classified UNRESOLVED because the source gives "no formula".
    rule_shaped = ct in set(ke.evc.RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES)
    if rule_shaped and blocking_question_count and explicitness == "EXPLICIT":
        explicitness = "UNRESOLVED"
        derived.append("blockingQuestions=%d -> UNRESOLVED" % blocking_question_count)

    # Confidence mirrors the evidence store's own state -- never re-scored here.
    state = claim.get("confidenceState")
    conf = {"insufficient_evidence": "NONE", "tentative": "LOW", "emerging": "LOW",
            "supported": "MEDIUM", "strongly_supported": "HIGH"}.get(state, "NONE")
    derived.append("confidenceState=%s" % state)

    eligible = (rule_shaped
                and classification not in ("MARKETING", "PSYCHOLOGY", "OPINION",
                                           "EDUCATIONAL_COMMENTARY", "EXAMPLE", "UNKNOWN")
                and explicitness in ("EXPLICIT", "IMPLIED", "DISCRETIONARY", "UNRESOLVED"))

    if eligible:
        rationale = ("Rule-shaped claimType %s, explicitness %s; eligible to become a candidate "
                     "rule. %s" % (ct, explicitness,
                     "Carries %d blocking open question(s): candidacy stands, but the unresolved "
                     "parameter must survive normalization and blocks determinism."
                     % blocking_question_count
                     if blocking_question_count else "No blocking questions."))
    else:
        why = []
        if not rule_shaped:
            why.append("claimType %s is not in RULE_CANDIDATE_ELIGIBLE_CLAIM_TYPES" % ct)
        if classification in ("MARKETING", "PSYCHOLOGY", "OPINION",
                              "EDUCATIONAL_COMMENTARY", "EXAMPLE", "UNKNOWN"):
            why.append("classified %s, which describes the educator or the reader rather than "
                       "a market decision" % classification)
        if explicitness == "INFERRED":
            why.append("explicitness INFERRED -- the source never stated it")
        rationale = "Not promoted to candidate-rule status: " + "; ".join(why) + "."

    return classification, domain, explicitness, conf, eligible, rationale, derived, rule_name


# --- Build the inventory ----------------------------------------------------

def build_inventory(educator_id=EDUCATOR_ID):
    ev = load_evidence()
    links = _links_by_claim(ev)

    blocking = {}
    for q in ev["questions"].values():
        cid = q.get("claimId")
        if cid and str(q.get("blockingStatus", "")).startswith("blocks"):
            blocking[cid] = blocking.get(cid, 0) + 1

    contra_by_claim = {}
    for c in ev["contradictions"].values():
        for k in ("claimAId", "claimBId"):
            if c.get(k):
                contra_by_claim.setdefault(c[k], []).append(c["contradictionId"])

    # Source artifacts
    artifacts = []
    for s in sorted(ev["sources"].values(), key=lambda x: x["sourceId"]):
        if s["traderId"] != educator_id:
            continue
        md = s.get("metadata", {})
        tv = md.get("titleVerification", {})
        notes = []
        if tv.get("status"):
            notes.append("title %s via %s" % (tv["status"], tv.get("method", "?")))
        if tv.get("ownerSuppliedTitle"):
            notes.append("owner-supplied title differs: %r" % tv["ownerSuppliedTitle"])
        for lim in tv.get("stillUnverified", []) or []:
            notes.append("unverified: %s" % lim)
        artifacts.append(ke.source_artifact(
            source_id=s["sourceId"], educator_id=educator_id,
            source_type=s.get("sourceType"), title=s.get("title"),
            reference=s.get("canonicalReference") or s.get("repositoryPath"),
            content_hash=s.get("contentHash"),
            ingestion_date=s.get("registeredAt"),
            provenance_status=s.get("provenanceStatus"),
            publication_date=s.get("sourceDate"),
            transcript_version=s.get("transcriptReference"),
            quality_notes=notes))

    claims_out, classifications = [], []
    for cid, c in sorted(ev["claims"].items()):
        if c["traderId"] != educator_id:
            continue
        my_links = links.get(cid, [])
        my_items = [ev["items"][l["evidenceId"]] for l in my_links
                    if l["evidenceId"] in ev["items"]]
        refs = [ke.source_reference(
                    source_id=i.get("sourceId"),
                    evidence_id=i.get("evidenceId"),
                    segment_id=i.get("sourceLocator"),
                    exact_excerpt=i.get("exactExcerpt"))
                for i in my_items]
        if not refs:
            raise InventoryError(
                "claim %s has no reachable source reference -- provenance is materially "
                "missing. MOGO-002.6 stop condition." % cid)

        cls, domain, expl, conf, eligible, rationale, derived, rule_name = classify_claim(
            c, my_items, blocking.get(cid, 0))

        # The educator's own words: the longest verbatim excerpt behind the claim.
        excerpts = [r["exactExcerpt"] for r in refs if r.get("exactExcerpt")]
        source_text = max(excerpts, key=len) if excerpts else None

        claims_out.append(ke.educator_claim(
            claim_id=cid, educator_id=educator_id, source_references=refs,
            source_text=source_text,
            normalized_paraphrase=c.get("normalizedClaim"),
            category=domain, classification=cls, explicitness=expl, confidence=conf,
            context=c.get("scope") or None,
            timeframe_references=[c["timeframe"]] if c.get("timeframe") else [],
            session_references=[c["session"]] if c.get("session") else [],
            instrument_references=[c["marketSymbol"]] if c.get("marketSymbol") else [],
            contradictions=contra_by_claim.get(cid, []),
            review_status="NOT_REVIEWED",
            notes=("%d blocking open question(s)" % blocking[cid]) if cid in blocking else None,
            origin_claim_type=c.get("claimType"),
            origin_confidence_state=c.get("confidenceState")))

        classifications.append(ke.claim_classification(
            claim_id=cid, classification=cls, explicitness=expl,
            rationale=rationale, candidate_rule_eligible=eligible,
            derived_from=derived + ["derivationRule=%s" % rule_name]))

    return {
        "modelVersion": ke.KE_MODEL_VERSION,
        "generatorVersion": ke.KE_GENERATOR_VERSION,
        "educatorId": educator_id,
        "sourceArtifactCount": len(artifacts),
        "claimCount": len(claims_out),
        "sourceArtifacts": artifacts,
        "claims": claims_out,
        "classifications": classifications,
    }


def classification_totals(inv):
    from collections import Counter
    by_cls = Counter(c["classification"] for c in inv["claims"])
    by_expl = Counter(c["explicitness"] for c in inv["claims"])
    by_conf = Counter(c["confidence"] for c in inv["claims"])
    by_review = Counter(c["reviewStatus"] for c in inv["claims"])
    by_domain = Counter(c["category"] for c in inv["claims"])
    elig = Counter(("ELIGIBLE" if c["candidateRuleEligible"] else "NOT_ELIGIBLE")
                   for c in inv["classifications"])
    by_source = Counter()
    for c in inv["claims"]:
        for r in c["sourceReferences"]:
            by_source[r["sourceId"]] += 1
            break          # count each claim once, against its primary source
    return {
        "byClassification": dict(sorted(by_cls.items())),
        "byExplicitness": dict(sorted(by_expl.items())),
        "byStrategyDomain": dict(sorted(by_domain.items())),
        "byConfidence": dict(sorted(by_conf.items())),
        "byReviewStatus": dict(sorted(by_review.items())),
        "byCandidateRuleEligibility": dict(sorted(elig.items())),
        "bySource": dict(sorted(by_source.items())),
        "total": inv["claimCount"],
    }


if __name__ == "__main__":
    inv = build_inventory()
    print(ke.dumps(classification_totals(inv)))
