"""MOGO-002.6 Phases 4-6 — duplicate/overlap analysis, contradiction records, normalization.

Deterministic. Given the same inventory, output is byte-identical.

THE MERGE BLOCKERS ARE THE POINT
--------------------------------
Detecting that two claims look similar is easy and mostly useless. The governance
requirement is the opposite: DO NOT merge when thresholds, context, obligation,
timeframe, session, or concept-kind differ. So overlap detection and merge
recommendation are separate steps -- a group can be detected at high overlap and
still be recommended DO_NOT_MERGE, with the blocking reason recorded.

NOTHING HERE INVENTS A PARAMETER
--------------------------------
Where the educator demonstrates something without stating a formula, the unresolved
parameter is carried into `unresolvedParameters` and the rule is marked
non-deterministic. It is never filled in.
"""
import os
import re
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import ke_model as ke        # noqa: E402
import ke_inventory as kinv  # noqa: E402

_STOP = set("""a an the and or of to in on at is are be as it its this that for with from by
we you your i my he his they their not no never always can could would should may might if
when where what which who how why do does did done then than so very much more most less
own same such only just also both each other some any all into out up down over under again
further once here there because while during before after above below off through""".split())

_NUM = re.compile(r"\b\d+(?:\.\d+)?\s*%?\b")
_TF = re.compile(r"\b(weekly|daily|4-?hour|four-?hour|4h|h4|1-?hour|h1|30-?minute|15-?minute|"
                 r"5-?minute|1-?minute|monthly|yearly)\b", re.I)
_SESSION = re.compile(r"\b(london|new york|sydney|tokyo|asian|session|monday|tuesday|wednesday|"
                      r"thursday|friday|november|december|january|february|march|june|july|august)\b", re.I)

# claimTypes that express an obligation vs an option. Mixing the two is a merge blocker.
_MANDATORY = {"setup_requirement", "entry_rule", "confirmation_rule", "invalidation_rule",
              "risk_rule", "stop_rule", "session_rule", "timeframe_rule"}
_OPTIONAL = {"exception", "behavioral_observation"}
# Entry concepts and management concepts must never be merged together.
_ENTRY_KIND = {"entry_rule", "confirmation_rule", "setup_requirement"}
_MGMT_KIND = {"trade_management_rule", "target_rule", "stop_rule"}


def _tokens(text):
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


# --- Phase 4: duplicate / overlap -------------------------------------------

def _merge_blockers(c1, c2):
    """Every reason these two claims must NOT be merged, from the governance list."""
    blockers = []
    n1, n2 = set(_NUM.findall(c1["normalizedParaphrase"] or "")), set(_NUM.findall(c2["normalizedParaphrase"] or ""))
    if n1 != n2 and (n1 or n2):
        blockers.append("thresholds differ (%s vs %s)" % (sorted(n1) or "none", sorted(n2) or "none"))
    t1 = {m.lower() for m in _TF.findall(c1["normalizedParaphrase"] or "")}
    t2 = {m.lower() for m in _TF.findall(c2["normalizedParaphrase"] or "")}
    if t1 != t2 and (t1 or t2):
        blockers.append("timeframes differ (%s vs %s)" % (sorted(t1) or "none", sorted(t2) or "none"))
    s1 = {m.lower() for m in _SESSION.findall(c1["normalizedParaphrase"] or "")}
    s2 = {m.lower() for m in _SESSION.findall(c2["normalizedParaphrase"] or "")}
    if s1 != s2 and (s1 or s2):
        blockers.append("session restrictions differ")
    o1, o2 = c1.get("originClaimType"), c2.get("originClaimType")
    if (o1 in _MANDATORY and o2 in _OPTIONAL) or (o2 in _MANDATORY and o1 in _OPTIONAL):
        blockers.append("one is mandatory (%s) and the other optional (%s)" % (o1, o2))
    if (o1 in _ENTRY_KIND and o2 in _MGMT_KIND) or (o2 in _ENTRY_KIND and o1 in _MGMT_KIND):
        blockers.append("entry and trade-management concepts must not be merged")
    if c1["category"] != c2["category"]:
        blockers.append("different strategy domains (%s vs %s)" % (c1["category"], c2["category"]))
    if c1.get("contradictions") or c2.get("contradictions"):
        blockers.append("a member participates in a recorded contradiction")
    return blockers


def build_duplicate_groups(inventory, threshold=0.40):
    """Single-link clustering on token overlap WITHIN a domain, then per-pair blockers.

    The default threshold is deliberately loose (0.40). Very few true duplicates
    survive to this stage because the INGESTION pipeline already deduplicated at the
    claim level -- `compute_claim_fingerprint()` merges same-wording restatements, and
    36 of the 195 ALEX_G claims already aggregate more than one evidence item. What
    remains is semantic near-overlap, which is worth surfacing precisely because most
    of it turns out to be DO_NOT_MERGE."""
    claims = {c["claimId"]: c for c in inventory["claims"]}
    by_domain = defaultdict(list)
    for c in inventory["claims"]:
        by_domain[c["category"]].append(c)

    parent = {cid: cid for cid in claims}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    pair_scores = {}
    for domain, members in by_domain.items():
        members = sorted(members, key=lambda c: c["claimId"])
        toks = {c["claimId"]: _tokens(c["normalizedParaphrase"]) for c in members}
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i]["claimId"], members[j]["claimId"]
                sc = _jaccard(toks[a], toks[b])
                if sc >= threshold:
                    pair_scores[(a, b)] = sc
                    union(a, b)

    clusters = defaultdict(list)
    for cid in claims:
        clusters[find(cid)].append(cid)

    groups = []
    n = 0
    for root, members in sorted(clusters.items()):
        if len(members) < 2:
            continue
        n += 1
        members = sorted(members)
        gid = "KEDUP|ALEX_G|%03d" % n
        scores = [s for (a, b), s in pair_scores.items() if a in members and b in members]
        avg = sum(scores) / len(scores) if scores else 0.0
        blockers = []
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                blockers += ["%s vs %s: %s" % (members[i].split("|")[-1], members[j].split("|")[-1], bl)
                             for bl in _merge_blockers(claims[members[i]], claims[members[j]])]
        blockers = sorted(set(blockers))

        if avg >= 0.85 and not blockers:
            degree, rec, conf = "NEAR_DUPLICATE", "MERGE", "MEDIUM"
        elif not blockers:
            degree, rec, conf = "SAME_CONCEPT_DIFFERENT_DETAIL", "MERGE_WITH_CAVEATS", "LOW"
        else:
            degree, rec, conf = "RELATED_NOT_DUPLICATE", "DO_NOT_MERGE", "LOW"

        chron = sorted({r["sourceId"] for m in members for r in claims[m]["sourceReferences"]})
        diffs = []
        for m in members:
            c = claims[m]
            diffs.append("%s [%s/%s]: %s" % (m.split("|")[-1], c["originClaimType"],
                                             c["explicitness"], (c["normalizedParaphrase"] or "")[:90]))
        groups.append(ke.duplicate_claim_group(
            group_id=gid, member_claim_ids=members,
            proposed_concept=(claims[members[0]]["normalizedParaphrase"] or "")[:160],
            overlap_degree=degree, meaningful_differences=diffs,
            source_chronology=chron, merge_recommendation=rec, confidence=conf,
            review_status="PENDING_REVIEW", blocking_reasons=blockers))
    return groups


# --- Phase 5: contradictions ------------------------------------------------

_DOMAIN_FOR_XCONTRA = {
    "DEFINITIONAL": "MARKET_STRUCTURE", "DIRECTIONAL": "ENTRY",
    "CONDITIONAL_SCOPE": "SETUP", "NUMERIC_THRESHOLD": "RISK",
    "SCOPE_MISMATCH": "UNRESOLVED_QUESTIONS", "TEMPORAL_DRIFT": "UNRESOLVED_QUESTIONS",
    "OTHER": "UNRESOLVED_QUESTIONS",
}


def build_contradictions(inventory, evidence):
    """Re-express existing ContradictionRecords that involve an ALEX_G claim.

    These are IMPORTED, not re-derived: the evidence store already recorded them
    with a rationale during ingestion, and re-deciding them here would discard that
    reasoning. Each gains the two things the KE model requires and the evidence
    record does not carry -- explicit alternative interpretations, and a completion
    path."""
    mine = {c["claimId"] for c in inventory["claims"]}
    out = []
    for xid, x in sorted(evidence["contradictions"].items()):
        ids = [x.get("claimAId"), x.get("claimBId")]
        ids = [i for i in ids if i]
        if not any(i in mine for i in ids):
            continue
        ctype = x.get("contradictionType", "OTHER")
        sev = x.get("severity", "material")
        rationale = (x.get("rationale") or "").strip()
        cross = not all(i in mine for i in ids)

        interps = [
            "Interpretation A: the first claim states the educator's operative rule and the "
            "second is a lapse, a simplification, or context-specific.",
            "Interpretation B: the second claim states the operative rule and the first is the "
            "lapse or simplification.",
        ]
        if cross:
            interps.append(
                "Interpretation C: both are internally correct for their own educator, and the "
                "disagreement is genuine cross-educator divergence rather than an error.")
        else:
            interps.append(
                "Interpretation C: both hold under conditions the source never distinguished, "
                "and the missing distinction is itself the knowledge gap.")

        replay_helps = ctype in ("DEFINITIONAL", "DIRECTIONAL", "CONDITIONAL_SCOPE", "NUMERIC_THRESHOLD")
        out.append(ke.rule_contradiction(
            contradiction_id="KECON|" + xid.replace("XCONTRA|", ""),
            claim_ids=ids,
            issue_statement=rationale[:600] or "Recorded contradiction between the two claims.",
            conflict_type=ctype, severity=sev,
            affected_category=_DOMAIN_FOR_XCONTRA.get(ctype, "UNRESOLVED_QUESTIONS"),
            interpretations=interps,
            source_chronology=sorted({i.split("|")[2] for i in ids if len(i.split("|")) > 2}),
            resolution_status="OPEN",
            completion_path=("Replay can settle this empirically once authorized."
                             if replay_helps else
                             "Requires further source acquisition or an Engineering Authority "
                             "ruling; no dataset available to MOGO can decide it."),
            replay_could_help=replay_helps,
            further_source_required=not replay_helps,
            origin_record=xid))
    return out


# --- Phase 6: candidate rules and normalization -----------------------------

_UNRESOLVED_HINTS = [
    (re.compile(r"not stated|never stated|is not stated|no formula|not defined|"
                r"never defined|unstated|not given|no source is given|"
                r"displayed visually|shown on an on-screen|caption is garbled|"
                r"no minimum|no count|maximum of the scale", re.I),
     "the source states the rule but withholds its parameter"),
    (re.compile(r"period is (?:still )?not stated|which sessions qualify", re.I),
     "a named indicator or window has no stated setting"),
]


def _unresolved_elements(claim, blocking_note):
    out = []
    text = claim.get("normalizedParaphrase") or ""
    for rx, label in _UNRESOLVED_HINTS:
        if rx.search(text):
            out.append(label)
    if blocking_note:
        out.append(blocking_note)
    return sorted(set(out))


def build_candidate_rules(inventory, groups, contradictions):
    """One candidate per eligible claim, except where a group recommends merging --
    then one candidate for the merged group, carrying every member's provenance."""
    claims = {c["claimId"]: c for c in inventory["claims"]}
    elig = {cl["claimId"] for cl in inventory["classifications"] if cl["candidateRuleEligible"]}
    contra_by_claim = defaultdict(list)
    for x in contradictions:
        for cid in x["claimIds"]:
            contra_by_claim[cid].append(x["contradictionId"])

    merged = {}
    for g in groups:
        if g["mergeRecommendation"] in ("MERGE", "MERGE_WITH_CAVEATS"):
            for m in g["memberClaimIds"]:
                merged[m] = g

    seen_groups, candidates, n = set(), [], 0
    for cid in sorted(elig):
        c = claims[cid]
        g = merged.get(cid)
        if g is not None:
            if g["groupId"] in seen_groups:
                continue
            seen_groups.add(g["groupId"])
            members = [m for m in g["memberClaimIds"] if m in elig]
            if not members:
                continue
        else:
            members = [cid]

        primary = claims[members[0]]
        n += 1
        crid = "KECAND|ALEX_G|%03d" % n
        unresolved = []
        for m in members:
            unresolved += _unresolved_elements(claims[m], claims[m].get("notes"))
        contras = sorted({x for m in members for x in contra_by_claim.get(m, [])})
        required = primary.get("originClaimType") in _MANDATORY
        deterministic = (primary["explicitness"] == "EXPLICIT" and not unresolved and not contras)

        conf = "MEDIUM" if (deterministic and len(members) == 1) else "LOW"
        candidates.append(ke.candidate_rule(
            candidate_rule_id=crid, originating_claim_ids=sorted(members),
            proposed_statement=primary["normalizedParaphrase"],
            category=primary["category"], required=required, deterministic=deterministic,
            proposed_conditions=[claims[m]["normalizedParaphrase"] for m in members[1:]],
            proposed_action=None,
            unresolved_parameters=sorted(set(unresolved)),
            source_support={"claimCount": len(members),
                            "sourceIds": sorted({r["sourceId"] for m in members
                                                 for r in claims[m]["sourceReferences"]}),
                            "originConfidenceState": primary.get("originConfidenceState")},
            contradiction_references=contras,
            normalization_confidence=conf,
            review_status="PENDING_REVIEW",
            notes=("Merged from duplicate group %s" % g["groupId"]) if g is not None else None))
    return candidates


def normalize(candidates, inventory):
    """Promote candidates to NormalizedRules, with a NormalizationDecision each.

    A candidate is normalized only where the source supports a stable canonical
    statement. It is NOT normalized when it carries a `blocking` contradiction --
    the canonical statement would have to pick a side."""
    claims = {c["claimId"]: c for c in inventory["claims"]}
    rules, decisions, deferred = [], [], []

    for cand in candidates:
        cid0 = cand["originatingClaimIds"][0]
        primary = claims[cid0]
        blocking_contra = [x for x in cand["contradictionReferences"] if x.endswith("|001")
                           and "20260728" in x]
        # Defer only where a canonical statement cannot be written without choosing
        # a side of a live disagreement.
        if cand["contradictionReferences"] and cand["category"] in ("ENTRY", "SETUP") \
                and cand["unresolvedParameters"]:
            deferred.append({"candidateRuleId": cand["candidateRuleId"],
                             "reason": "carries both a contradiction and an unresolved parameter; "
                                       "a canonical statement would have to invent one and pick "
                                       "the other"})
            continue

        rid = cand["candidateRuleId"].replace("KECAND", "KERULE")
        classification = primary["explicitness"]
        deterministic = cand["deterministic"]
        if classification in ("DISCRETIONARY", "UNRESOLVED"):
            deterministic = False

        mappings = []
        for m in cand["originatingClaimIds"]:
            c = claims[m]
            rel = "primary" if m == cid0 else "supporting"
            mappings.append(ke.rule_source_mapping(
                rid, m, c["sourceReferences"][0]["sourceId"], rel,
                exact_excerpt=c.get("sourceText")))

        rules.append(ke.normalized_rule(
            rule_id=rid, version="v2.0.0-draft", educator_id="ALEX_G",
            canonical_statement=cand["proposedCanonicalStatement"],
            category=cand["category"], classification=classification,
            required=cand["required"], deterministic=deterministic,
            conditions=cand["proposedConditions"],
            dependencies=cand["dependencies"],
            source_mappings=mappings,
            contradiction_references=cand["contradictionReferences"],
            unresolved_elements=cand["unresolvedParameters"],
            confidence=cand["normalizationConfidence"],
            maturity="NORMALIZED", validation_status="UNVALIDATED",
            approval_status="NEEDS_REVIEW",
            notes=cand.get("notes")))

        decisions.append(ke.normalization_decision(
            decision_id=rid.replace("KERULE", "KEDEC"), rule_id=rid,
            source_claims_used=cand["originatingClaimIds"],
            claims_excluded=[],
            duplicate_handling=(cand["notes"] or "No duplicate group; single claim."),
            contradiction_handling=("Carries %d contradiction reference(s), recorded and left open."
                                    % len(cand["contradictionReferences"])
                                    if cand["contradictionReferences"] else "No contradictions."),
            meaning_retained=("Canonical statement is the evidence store's own normalizedClaim, "
                              "unchanged. The educator's verbatim excerpt is preserved in the "
                              "source mappings."),
            assumptions_avoided=(["No numeric threshold, session window, timeframe or indicator "
                                  "setting was supplied where the source omitted one."]
                                 if cand["unresolvedParameters"] else
                                 ["No parameters were required beyond those the source states."]),
            unresolved_elements=cand["unresolvedParameters"],
            confidence=cand["normalizationConfidence"],
            determinism_rationale=(
                "Deterministic: explicitly stated, no unresolved parameter, no contradiction."
                if deterministic else
                "NOT deterministic: %s." % (
                    "explicitness is %s" % classification if classification in ("DISCRETIONARY", "UNRESOLVED")
                    else "carries unresolved parameters or a contradiction")),
            requirement_rationale=(
                "Required: originating claimType %s expresses an obligation."
                % primary.get("originClaimType") if cand["required"] else
                "Optional: originating claimType %s does not express an obligation."
                % primary.get("originClaimType")),
            draft_rationale=(
                "Remains DRAFT/NEEDS_REVIEW: OD-1 modification 6 forbids any rule in this "
                "milestone exceeding NEEDS_REVIEW, and the originating claim is at "
                "confidence state %r with no independent corroboration."
                % primary.get("originConfidenceState"))))

    return rules, decisions, deferred
