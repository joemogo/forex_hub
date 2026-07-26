#!/usr/bin/env python3
"""One-off generator for the PROGRAM-006 Phase 1B comprehensive synthetic TJR
fixture (ADR-009, Deliverable 20). Run once to (re)produce the static files
checked in under tests/trader_intelligence/evidence/fixtures/synthetic_tjr_demo/.

Not part of the runtime or the test suite's import graph -- the test suite
loads the already-generated static files, exactly like the Phase 1A
synthetic_demo fixture.

SYNTHETIC TEST DATA
NOT A REAL TJR TRANSCRIPT
NOT VALIDATED TRADING KNOWLEDGE
NOT A PRODUCTION STRATEGY
DO NOT USE FOR TRADING

Every string below is invented for demonstration purposes only.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import intake_registry as ir            # noqa: E402
import transcript_adapters as ta        # noqa: E402
import annotation_pipeline as ap        # noqa: E402
import evidence_registry as reg         # noqa: E402
import extraction_pipeline as ep        # noqa: E402
import evidence_explain as ee           # noqa: E402
import tjr_report as tr                 # noqa: E402
import query_evidence as qe             # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FIXTURE_ROOT = os.path.join(REPO_ROOT, "tests", "trader_intelligence", "evidence", "fixtures", "synthetic_tjr_demo")

MARKER = ("SYNTHETIC TEST DATA / NOT A REAL TJR TRANSCRIPT / NOT VALIDATED TRADING KNOWLEDGE / "
          "NOT A PRODUCTION STRATEGY / DO NOT USE FOR TRADING")
NOW = datetime(2026, 7, 26, 15, 0, 0, tzinfo=timezone.utc)

TRANSCRIPT_1 = "\n".join([
    "[00:00:00] TJR: %s." % MARKER,
    "[00:01:00] TJR: Displacement must always follow a liquidity sweep before I consider an entry valid.",
    "[00:02:15] TJR: You always want confirmation before entering, that's basically required.",
    "[00:03:30] TJR: Here is a chart example where price swept the high and then displaced down hard, that is the setup.",
    "[00:04:45] TJR: Sometimes I skip the confirmation candle if the displacement is really strong.",
    "[00:05:50] TJR: I think a confirmation candle is usually a good idea but it is not a hard rule for me.",
    "[00:07:00] TJR: Except when the news just came out, then I ignore the sweep requirement entirely.",
    "[00:08:10] TJR: My stop management is honestly discretionary, it depends on the day.",
    "[00:09:20] TJR: This trade worked out well, displacement carried price straight to target.",
    "[00:10:30] TJR: This other trade failed because the displacement reversed right after entry.",
    "[00:11:40] TJR: Risk-wise, I never risk more than one percent per trade.",
    "[00:12:50] TJR: Displacement must always follow a liquidity sweep before I consider an entry valid.",
    "[00:13:55] TJR: On the 15 minute chart, displacement must always follow a liquidity sweep before I consider an entry valid.",
    "[00:15:00] TJR: Maybe the stop should go above the sweep high, or maybe below the previous structure, I have not fully decided.",
    "[00:16:10] TJR: Not sure yet whether this only works in New York session or all sessions.",
])

TRANSCRIPT_2 = ("%s.\n\nOwner confirms the same displacement-after-sweep pattern from a separate, "
                "independent review session." % MARKER)


def main():
    dirs = {name: os.path.join(FIXTURE_ROOT, name) for name in
            ("sources", "items", "claims", "links", "lifecycle", "intake", "segments",
             "annotations", "contradictions", "questions", "proposals", "review-queue", "reports")}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    # --- Intake 1: main synthetic transcript -------------------------------
    manifest1 = ir.register_intake_manifest(
        dirs["intake"], dirs["lifecycle"], "transcript", "fixture_generator", NOW,
        traderId="TJR", title="%s -- synthetic multi-topic session" % MARKER,
        transcriptFormat="timestamped_text", transcriptCompleteness="complete",
        licensingStatus="owner_authored")
    ir.transition_intake_status(dirs["intake"], dirs["lifecycle"], manifest1["intakeId"], "validated", "fixture_generator", NOW)
    ir.transition_intake_status(dirs["intake"], dirs["lifecycle"], manifest1["intakeId"], "ready_for_extraction", "fixture_generator", NOW)

    src1 = reg.register_source(dirs["sources"], dirs["lifecycle"], "transcript", "fixture_generator", NOW,
                                traderId="TJR", title="%s -- source for main session" % MARKER)
    ir.link_intake_to_source(dirs["intake"], dirs["lifecycle"], manifest1["intakeId"], src1["sourceId"], "fixture_generator", NOW)

    audit1 = ep.run_intake_extraction_pipeline(FIXTURE_ROOT, manifest1["intakeId"], TRANSCRIPT_1, now=NOW)
    seg = qe.EvidenceIndex.load(FIXTURE_ROOT).segments_for_intake(manifest1["intakeId"])
    seg_by_seq = {s["sequenceNumber"]: s for s in seg}

    # --- Intake 2: independent corroborating source -------------------------
    manifest2 = ir.register_intake_manifest(
        dirs["intake"], dirs["lifecycle"], "owner_observation", "fixture_generator", NOW,
        traderId="TJR", title="%s -- independent corroborating note" % MARKER,
        transcriptFormat="plain_text", transcriptCompleteness="complete", licensingStatus="owner_authored")
    ir.transition_intake_status(dirs["intake"], dirs["lifecycle"], manifest2["intakeId"], "validated", "fixture_generator", NOW)
    ir.transition_intake_status(dirs["intake"], dirs["lifecycle"], manifest2["intakeId"], "ready_for_extraction", "fixture_generator", NOW)
    src2 = reg.register_source(dirs["sources"], dirs["lifecycle"], "owner_observation", "fixture_generator", NOW,
                                traderId="TJR", title="%s -- independent corroborating source" % MARKER)
    ir.link_intake_to_source(dirs["intake"], dirs["lifecycle"], manifest2["intakeId"], src2["sourceId"], "fixture_generator", NOW)
    audit2 = ep.run_intake_extraction_pipeline(FIXTURE_ROOT, manifest2["intakeId"], TRANSCRIPT_2, now=NOW)
    seg2 = qe.EvidenceIndex.load(FIXTURE_ROOT).segments_for_intake(manifest2["intakeId"])

    def annotate_and_apply(intake_id, segment, excerpt, evidence_type, directness, certainty, quality,
                            existing_claim_id=None, relationship=None, proposed_claim=None, claim_type=None,
                            **scope):
        annotation = ap.register_annotation(
            dirs["annotations"], dirs["segments"], dirs["intake"], NOW, intake_id, segment["segmentId"],
            excerpt, evidence_type, directness, certainty, "synthetic_researcher",
            evidenceQuality=quality, existingClaimId=existing_claim_id, relationshipType=relationship,
            proposedClaim=proposed_claim, claimType=claim_type, **scope)
        ap.set_annotation_review_status(dirs["annotations"], annotation["annotationId"], "approved", NOW)
        return ap.apply_annotation(dirs["annotations"], dirs["segments"], dirs["intake"], dirs["items"],
                                    dirs["sources"], dirs["claims"], dirs["links"], dirs["lifecycle"], NOW,
                                    annotation["annotationId"], "fixture_generator")

    # ---- Claim A: entry_rule -> reaches "supported" (explicit rule statement, duplicate, demonstrated behavior, independent corroboration) ----
    r_a1 = annotate_and_apply(manifest1["intakeId"], seg_by_seq[2],
        "Displacement must always follow a liquidity sweep before I consider an entry valid.",
        "explicit_statement", "direct_explicit", "certain", "high",
        proposed_claim="Displacement occurs after a liquidity sweep.", claim_type="entry_rule", traderId="TJR")
    claim_a_id = r_a1["claimId"]
    annotate_and_apply(manifest1["intakeId"], seg_by_seq[12],  # duplicate statement -> exact_duplicate, reuses claim A
        "Displacement must always follow a liquidity sweep before I consider an entry valid.",
        "explicit_statement", "direct_explicit", "certain", "high",
        proposed_claim="Displacement occurs after a liquidity sweep.", claim_type="entry_rule", traderId="TJR")
    annotate_and_apply(manifest1["intakeId"], seg_by_seq[4],  # demonstrated trade behavior -> exemplifies claim A
        "Here is a chart example where price swept the high and then displaced down hard, that is the setup.",
        "demonstrated_behavior", "direct_demonstrated", "high", "high",
        existing_claim_id=claim_a_id, relationship="exemplifies")
    annotate_and_apply(manifest2["intakeId"], seg2[-1],  # independent corroborating source -> 2nd independence group
        "Owner confirms the same displacement-after-sweep pattern from a separate, independent review session.",
        "explicit_statement", "direct_explicit", "high", "high",
        existing_claim_id=claim_a_id, relationship="supports")
    annotate_and_apply(manifest1["intakeId"], seg_by_seq[15],  # unresolved question -> 'unresolved' relationship, no score impact
        "Not sure yet whether this only works in New York session or all sessions.",
        "unresolved_question", "unresolved", "unresolved", "unknown",
        existing_claim_id=claim_a_id, relationship="unresolved")

    # ---- Claim A2: scoped variant (same text, explicit timeframe) -> a genuinely SEPARATE claim ----
    r_a2 = annotate_and_apply(manifest1["intakeId"], seg_by_seq[13],
        "On the 15 minute chart, displacement must always follow a liquidity sweep before I consider an entry valid.",
        "explicit_statement", "direct_explicit", "certain", "high",
        proposed_claim="Displacement occurs after a liquidity sweep.", claim_type="entry_rule",
        traderId="TJR", timeframe="15m")
    assert r_a2["claimId"] != claim_a_id, "scoped variant must not merge into claim A"

    # ---- Claim B: confirmation_rule -> reaches "contested" (implied requirement vs. explicit hedge) ----
    r_b1 = annotate_and_apply(manifest1["intakeId"], seg_by_seq[3],
        "You always want confirmation before entering, that's basically required.",
        "explicit_statement", "indirect_implied", "moderate", "medium",
        proposed_claim="A confirmation candle is required before entry.", claim_type="confirmation_rule", traderId="TJR")
    claim_b_id = r_b1["claimId"]
    annotate_and_apply(manifest1["intakeId"], seg_by_seq[5],
        "Sometimes I skip the confirmation candle if the displacement is really strong.",
        "exception_statement", "direct_explicit", "high", "medium",
        existing_claim_id=claim_b_id, relationship="contradicts")
    annotate_and_apply(manifest1["intakeId"], seg_by_seq[6],  # unsupported opinion -> weakens claim B
        "I think a confirmation candle is usually a good idea but it is not a hard rule for me.",
        "opinion", "inferred_from_context", "low", "low",
        existing_claim_id=claim_b_id, relationship="weakens")

    # ---- Claim C: exception -> from an explicit exception statement ----
    r_c = annotate_and_apply(manifest1["intakeId"], seg_by_seq[7],
        "Except when the news just came out, then I ignore the sweep requirement entirely.",
        "exception_statement", "direct_explicit", "high", "medium",
        proposed_claim="The liquidity-sweep requirement is waived immediately after high-impact news.",
        claim_type="exception", traderId="TJR")
    claim_c_id = r_c["claimId"]

    # ---- Claim D: registered directly with zero evidence -> genuinely "insufficient_evidence".
    # claimStatus stays the default "active" (not "pending_review") -- pending_review means
    # "came from unreviewed annotation/extraction and should carry that evidence"; this is
    # instead a manually-posed research placeholder that legitimately has no evidence yet,
    # which validate_evidence's CLAIM_CANDIDATE_WITHOUT_EVIDENCE check correctly distinguishes.
    claim_d = reg.register_claim(dirs["claims"], dirs["lifecycle"], "confirmation_rule",
        "Whether a confirmation candle is truly required is not yet resolved.", "fixture_generator", NOW,
        traderId="TJR")

    # ---- Claim E: stop_rule -> ambiguous stop placement (only weak/inferred support) ----
    r_e = annotate_and_apply(manifest1["intakeId"], seg_by_seq[14],
        "Maybe the stop should go above the sweep high, or maybe below the previous structure, I have not fully decided.",
        "opinion", "inferred_from_context", "ambiguous", "low",
        proposed_claim="Stop placement follows a single well-defined rule.", claim_type="stop_rule", traderId="TJR")
    claim_e_id = r_e["claimId"]

    # ---- Claim F: trade_management_rule -> discretionary statement ----
    r_f = annotate_and_apply(manifest1["intakeId"], seg_by_seq[8],
        "My stop management is honestly discretionary, it depends on the day.",
        "exception_statement", "direct_explicit", "high", "medium",
        proposed_claim="Trade management follows a fixed, non-discretionary rule.",
        claim_type="trade_management_rule", traderId="TJR")
    claim_f_id = r_f["claimId"]

    # ---- Claim G: behavioral_observation -> success vs. failure observation (contested via evidence, not just claim B) ----
    r_g = annotate_and_apply(manifest1["intakeId"], seg_by_seq[9],
        "This trade worked out well, displacement carried price straight to target.",
        "success_observation", "direct_demonstrated", "high", "medium",
        proposed_claim="Displacement-based entries reliably reach target once the setup criteria are met.",
        claim_type="behavioral_observation", traderId="TJR")
    claim_g_id = r_g["claimId"]
    annotate_and_apply(manifest1["intakeId"], seg_by_seq[10],
        "This other trade failed because the displacement reversed right after entry.",
        "failure_observation", "direct_demonstrated", "high", "medium",
        existing_claim_id=claim_g_id, relationship="contradicts")

    # ---- Claim H: risk_rule -> explicit risk statement ----
    r_h = annotate_and_apply(manifest1["intakeId"], seg_by_seq[11],
        "Risk-wise, I never risk more than one percent per trade.",
        "explicit_statement", "direct_explicit", "certain", "high",
        proposed_claim="Risk per trade should not exceed one percent.", claim_type="risk_rule", traderId="TJR")
    claim_h_id = r_h["claimId"]

    # ---- ContradictionRecord: Claim B (confirmation basically required) vs Claim C (sweep requirement waived after news) ----
    contradiction = reg.create_contradiction(
        dirs["contradictions"], dirs["claims"], dirs["lifecycle"], claim_b_id, claim_c_id,
        "SCOPE_MISMATCH", "material", "fixture_generator", NOW,
        rationale="%s: one claim treats confirmation as basically required; the other says the underlying "
                   "sweep requirement itself is waived immediately after high-impact news -- these need "
                   "owner reconciliation, not automatic resolution." % MARKER)

    # ---- Run the post-annotation pipeline for every claim: generates EvidenceQuestions, ----
    # ---- auto-proposes a RuleCandidateProposal for claim A (rule-eligible + supported), ----
    # ---- and rebuilds all 14 review queues. ----
    all_claim_ids = [claim_a_id, r_a2["claimId"], claim_b_id, claim_c_id, claim_d["claimId"],
                      claim_e_id, claim_f_id, claim_g_id, claim_h_id]
    post_audit = ep.run_post_annotation_pipeline(FIXTURE_ROOT, all_claim_ids, now=NOW)

    idx = qe.EvidenceIndex.load(FIXTURE_ROOT)
    claim_a_final = idx.claims[claim_a_id]
    claim_b_final = idx.claims[claim_b_id]
    print("Claim A confidenceState:", claim_a_final["confidenceState"], claim_a_final["confidenceScore"])
    print("Claim B confidenceState:", claim_b_final["confidenceState"], claim_b_final["confidenceScore"])
    print("Claim D confidenceState:", idx.claims[claim_d["claimId"]]["confidenceState"])
    print("Post-annotation audit:", json.dumps(post_audit, indent=2))

    # ---- Write a full explainability report + a complete TJR research report as static files. ----
    explanation = ee.explain_claim(idx, claim_a_id, now=NOW)
    with open(os.path.join(dirs["reports"], "claim_a_explanation.json"), "w", encoding="utf-8") as f:
        json.dump(explanation, f, indent=2, sort_keys=True, default=str)
    with open(os.path.join(dirs["reports"], "claim_a_explanation.txt"), "w", encoding="utf-8") as f:
        f.write("%s\n\n" % MARKER + ee.render_explanation_text(explanation))

    tjr_report_json = tr.generate_tjr_research_report(idx, manifest1["intakeId"], now=NOW)
    with open(os.path.join(dirs["reports"], "tjr_research_report.json"), "w", encoding="utf-8") as f:
        json.dump(tjr_report_json, f, indent=2, sort_keys=True, default=str)
    with open(os.path.join(dirs["reports"], "tjr_research_report.md"), "w", encoding="utf-8") as f:
        f.write("<!-- %s -->\n\n" % MARKER + tr.render_tjr_report_markdown(tjr_report_json))

    print("\nGenerated fixture under %s" % FIXTURE_ROOT)
    print("intake1=%s intake2=%s" % (manifest1["intakeId"], manifest2["intakeId"]))
    print("claims=%r" % all_claim_ids)
    print("contradiction=%s" % contradiction["contradictionId"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
