"""PROGRAM-006 Phase 1A -- deterministic claim normalization/deduplication
support (ADR-008, Deliverable 6).

Pure Python standard library. NO NETWORK ACCESS. Never performs a destructive
automatic merge -- only ever produces advisory candidate lists and merge
recommendations that a caller may act on (or ignore) explicitly.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_common as evc  # noqa: E402


def find_exact_duplicate_groups(claims):
    """Groups claims sharing an identical normalizedFingerprint (same
    normalized text AND same scope tuple). Returns a list of claimId lists,
    each of length >= 2."""
    groups = {}
    for c in claims:
        groups.setdefault(c["normalizedFingerprint"], []).append(c["claimId"])
    return [ids for ids in groups.values() if len(ids) > 1]


def _scope_tuple(claim):
    return (
        claim.get("traderId"), claim.get("strategyFamilyId"), claim.get("timeframe"),
        claim.get("session"), claim.get("marketCondition"),
    )


def find_near_duplicate_candidates(claims, threshold=None):
    """Pairwise near-duplicate detection restricted to claims sharing the
    exact same scope tuple -- scope must matter (ADR-008/Deliverable 6): two
    claims with different timeframe/session/marketCondition are never
    proposed as near-duplicates no matter how similar their text is, since
    scope difference may be the entire point of the distinct claim."""
    threshold = threshold if threshold is not None else evc._NEAR_DUP_THRESHOLD
    candidates = []
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            a, b = claims[i], claims[j]
            if a["normalizedFingerprint"] == b["normalizedFingerprint"]:
                continue  # already an exact duplicate, not merely a "candidate"
            if _scope_tuple(a) != _scope_tuple(b):
                continue  # scoped variants must not be treated as identical without analysis
            ratio = evc.near_duplicate_ratio(a["normalizedClaim"], b["normalizedClaim"])
            if ratio >= threshold:
                candidates.append({
                    "claimAId": a["claimId"], "claimBId": b["claimId"],
                    "similarity_ratio": round(ratio, 4),
                })
    return candidates


def recommend_merge(claim_a, claim_b, similarity_ratio, now):
    """Advisory only -- never applied automatically. The caller decides
    whether to act on this recommendation; no claim is ever merged, deleted,
    or overwritten by this function."""
    older, newer = (claim_a, claim_b) if claim_a["createdAt"] <= claim_b["createdAt"] else (claim_b, claim_a)
    return {
        "recommendedMergeIntoClaimId": older["claimId"],
        "rationale": "Near-duplicate candidate (similarity=%.2f) with identical scope; recommending the "
                     "earlier-created claim (%s, createdAt=%s) as the merge target over %s (createdAt=%s). "
                     "This is a recommendation only -- no automatic merge is performed." % (
                         similarity_ratio, older["claimId"], older["createdAt"], newer["claimId"], newer["createdAt"]),
        "computedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
