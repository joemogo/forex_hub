#!/usr/bin/env python3
"""MOGO Trader Intelligence -- transcript ingestion CLI.

Pure Python standard library. NO NETWORK ACCESS. NO LLM. Never reads or writes
index.html, any protected function, or any trading state.

Two phases, deliberately separated so that nothing enters the evidence store
until a human (or Claude) has reviewed the extraction judgments:

  PHASE 1  ingest.py <transcript> --trader TJR
      verify -> duplicate-check -> preserve raw -> normalize -> propose sections
      -> emit a DRAFT manifest. Registers nothing in the evidence store.

  [ a researcher fills in the manifest's `annotations` array ]

  PHASE 2  ingest.py --apply <manifest>
      validate (every excerpt verbatim, fail-closed) -> register intake, source
      and segments -> apply annotations -> contradictions and questions ->
      post-annotation pipeline -> Knowledge Library -> graph -> integrity ->
      dashboard.

Extraction judgment is irreducibly human and is NOT automated here. What is
automated is everything around it: hashing, copying, normalizing, sectioning,
registering, validating, reporting, and rollback.

Other modes:
  ingest.py --status              queue and library state
  ingest.py --rollback <intakeId> remove every record created by one run
  ingest.py --apply <m> --dry-run validate a manifest without writing
"""
import argparse
import glob as globmod
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import graph_common as gc                # noqa: E402
import evidence_common as evc            # noqa: E402
import evidence_registry as reg          # noqa: E402
import intake_registry as ir             # noqa: E402
import annotation_pipeline as ap         # noqa: E402
import extraction_pipeline as ep         # noqa: E402
import evidence_questions as eq          # noqa: E402
import query_evidence as qe              # noqa: E402
import transcript_normalize as tn        # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TI_ROOT = os.path.join(REPO_ROOT, "docs", "trader-intelligence")
EVIDENCE_ROOT = os.path.join(TI_ROOT, "evidence")
INTAKE_ROOT = os.path.join(TI_ROOT, "intake")
MANIFEST_DIR = os.path.join(INTAKE_ROOT, "manifests")
IMPORTS_ROOT = os.path.join(TI_ROOT, "imports")

MANIFEST_VERSION = 1
ACTOR = "ingest-cli"
TARGET_SECTION_CHARS = 2000


def _rel(p):
    return os.path.relpath(p, REPO_ROOT).replace(os.sep, "/")


_YT_ID = re.compile(r"(?:[?&]v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{6,})")


def _video_key(url):
    """Publisher-stable identity for a source URL, for duplicate detection.

    Returns the YouTube video id when one is present, so `?v=X&list=Y`,
    `?v=X&t=90` and a bare `?v=X` all collapse to the same key. Falls back to
    the URL with query/fragment stripped, which is conservative -- a false
    NEGATIVE (missed duplicate) is recoverable by rollback, a false POSITIVE
    would block a legitimate source, so this errs toward under-matching."""
    if not url:
        return None
    m = _YT_ID.search(url)
    if m:
        return "yt:%s" % m.group(1)
    return url.split("?")[0].split("#")[0].rstrip("/")


def _dirs():
    d = {}
    for name in ("sources", "items", "claims", "links", "contradictions", "lifecycle", "questions",
                 "profiles", "blueprints", "gaps", "hypotheses", "intake", "segments",
                 "annotations", "proposals", "review-queue", "reports"):
        d[name] = os.path.join(EVIDENCE_ROOT, name)
        os.makedirs(d[name], exist_ok=True)
    return d


def _fail(msg, code=2):
    print("ERROR: %s" % msg, file=sys.stderr)
    raise SystemExit(code)


# ---------------------------------------------------------------------------
# Phase 1 -- automatic preparation
# ---------------------------------------------------------------------------

def _propose_sections(line_map):
    """Draft sections at ~TARGET_SECTION_CHARS, preferring to break after a
    line that ends a sentence so a quotable statement is not split across two
    sections. Titles are placeholders -- the operator is expected to retitle
    them, and the manifest says so."""
    sections, start, size = [], 1, 0
    n = len(line_map)
    for i, entry in enumerate(line_map, start=1):
        size += len(entry["normalizedText"]) + 1
        ends_sentence = entry["normalizedText"].rstrip().endswith((".", "?", "!"))
        if (size >= TARGET_SECTION_CHARS and ends_sentence) or i == n:
            sections.append({"n": len(sections) + 1, "lines": [start, i],
                             "type": "other", "title": "SECTION %d (retitle me)" % (len(sections) + 1)})
            start, size = i + 1, 0
    if start <= n:  # trailing remainder when the last line did not end a sentence
        sections.append({"n": len(sections) + 1, "lines": [start, n],
                         "type": "other", "title": "SECTION %d (retitle me)" % (len(sections) + 1)})
    return sections


def section_text(line_map, a, b):
    """Section text is the normalized lines joined with a single space.
    Transcripts wrap at fixed widths, not sentence ends, so a space join
    restores the spoken sentence without inserting or deleting a word."""
    return " ".join(e["normalizedText"] for e in line_map[a - 1:b] if e["normalizedText"])


def _section_records(line_map, sections):
    out = []
    for s in sections:
        a, b = s["lines"]
        body = section_text(line_map, a, b)
        out.append({
            "sectionNumber": s["n"], "sectionTitle": s["title"], "segmentType": s.get("type", "other"),
            "startTimestamp": line_map[a - 1]["timestamp"], "endTimestamp": line_map[b - 1]["timestamp"],
            "lineStart": a, "lineEnd": b, "text": body,
            "textSha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        })
    return out


def _assert_coverage(sections, n_lines):
    seen = set()
    for s in sections:
        a, b = s["lines"]
        for x in range(a, b + 1):
            if x in seen:
                _fail("section coverage: line %d is in two sections" % x)
            seen.add(x)
    missing = sorted(set(range(1, n_lines + 1)) - seen)
    if missing:
        _fail("section coverage gap: lines %r are in no section" % missing[:20])


def phase1(args):
    src = os.path.abspath(args.transcript)
    if not os.path.isfile(src):
        _fail("no such file: %s" % args.transcript)
    raw = open(src, "rb").read()
    if not raw.strip():
        _fail("file is empty: %s" % args.transcript)
    sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    trader = args.trader.upper()

    if not re.match(r"^[A-Z][A-Z0-9_]*$", trader):
        _fail("--trader %r must match ^[A-Z][A-Z0-9_]*$" % trader)
    profile_path = os.path.join(TI_ROOT, "traders", trader.lower().replace("_", "-"), "profile.json")
    if not os.path.isfile(profile_path):
        profile_path = os.path.join(TI_ROOT, "traders", trader.lower(), "profile.json")
    if not os.path.isfile(profile_path):
        _fail("no TraderRecord for %r -- create %s first (see OPERATOR-PLAYBOOK Appendix A)"
              % (trader, _rel(profile_path)))

    print("== 1. verify ==")
    print("   file    : %s" % _rel(src))
    print("   bytes   : %d" % len(raw))
    print("   sha256  : %s" % sha)

    # Duplicate check against every registered source. TWO keys, because they
    # catch different things:
    #
    #   contentHash    -- the same FILE offered twice.
    #   canonicalRef   -- the same VIDEO offered twice in a different transcript
    #                     rendering. YouTube's "Show transcript" panel and the
    #                     duration-label copy produce different bytes for
    #                     identical speech, so the hash check alone misses it.
    #                     Found 2026-07-29 when sZAE_lqdeno was re-supplied in
    #                     the timestamp-lines format after being ingested from
    #                     the duration-label format (BACKLOG-003/H27).
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)

    def _reject(reason):
        if not args.dry_run:
            rej = os.path.join(INTAKE_ROOT, "rejected", os.path.basename(src))
            os.makedirs(os.path.dirname(rej), exist_ok=True)
            shutil.move(src, rej)
            with open(rej + ".rejected.txt", "w", encoding="utf-8") as f:
                f.write("%s\n%s\n" % (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), reason))
            print("   -> moved to intake/rejected/")
        _fail(reason, code=3)

    for s in idx.sources.values():
        if s.get("contentHash") == sha:
            _reject("Duplicate of %s (identical contentHash %s). Not ingested."
                    % (s["sourceId"], sha))

    if args.url:
        vid = _video_key(args.url)
        for s in idx.sources.values():
            ref = s.get("canonicalReference")
            if ref and vid and _video_key(ref) == vid:
                _reject(
                    "Duplicate SOURCE of %s -- same canonical reference (%s), different bytes.\n"
                    "  already ingested : %s\n"
                    "  as               : %r\n"
                    "This is the same video in a different transcript rendering. The content hash\n"
                    "differs, so the hash check does not catch it. Nothing ingested."
                    % (s["sourceId"], vid, ref, s.get("title")))
    print("   duplicate: none")

    print("== 2. normalize ==")
    try:
        used_profile, line_map = tn.normalize(text, args.normalize_profile)
    except tn.NormalizationError as exc:
        _fail("normalization failed (nothing written): %s" % exc)
    policy = tn.policy_summary(used_profile, line_map)
    print("   profile : %s%s" % (used_profile, "" if args.normalize_profile else " (auto-detected)"))
    print("   lines   : %d (%d transformed, %d chars removed)"
          % (policy["lineCount"], policy["linesTransformed"], policy["charsRemoved"]))
    print("   reversible: asserted for every transformed line")
    if policy["unmatchedLines"]:
        print("   note    : %d line(s) matched no rule and are recorded as exceptions: %r"
              % (len(policy["unmatchedLines"]), policy["unmatchedLines"][:10]))

    sections = _propose_sections(line_map)
    _assert_coverage(sections, len(line_map))
    print("== 3. propose sections ==")
    print("   sections: %d (draft -- retitle and re-cut before --apply)" % len(sections))

    slug = args.slug or os.path.splitext(os.path.basename(src))[0]
    manifest = {
        "manifestVersion": MANIFEST_VERSION,
        "traderId": trader,
        "title": args.title or slug.replace("-", " "),
        "slug": slug,
        "sourceFile": _rel(src),
        "sourceFileBytes": len(raw),
        "sourceFileSha256": sha,
        "sourceLineCount": len(line_map),
        "provenance": {
            "canonicalReference": args.url,
            "channelOrPublisher": args.channel,
            "publicationDate": args.published,
            "transcriptProvider": args.provider,
            "licensingStatus": args.licensing,
            "transcriptCompleteness": args.completeness,
            "language": args.language,
        },
        "normalization": policy,
        "sections": sections,
        "annotations": [],
        "contradictions": [],
        "openQuestions": [],
        "_instructions": (
            "1) Retitle and re-cut `sections` so no quotable statement spans a boundary. "
            "2) Fill `annotations`: each needs key, section, excerpt (VERBATIM substring of that "
            "section's text), evidenceType, directness, extractionCertainty, evidenceQuality, and "
            "either claimType+claim (new claim) or supports=<earlier key> (corroborating evidence). "
            "3) Add `contradictions` [{a,b,type,severity,rationale}] and `openQuestions` "
            "[{claim|null,type,priority,blocking,text,reason}]. "
            "4) Run: ingest.py --apply <this file> --dry-run, then without --dry-run. "
            "See docs/trader-intelligence/STANDARDS-extraction.md."),
    }

    if args.dry_run:
        print("\n[dry-run] nothing written. Manifest would be %d sections, 0 annotations."
              % len(sections))
        return 0

    # --- persist: raw archive, normalized archive, manifest -----------------
    trader_dir = os.path.join(IMPORTS_ROOT, trader.lower().replace("_", "-"))
    raw_dir, norm_dir = os.path.join(trader_dir, "raw"), os.path.join(trader_dir, "normalized")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(norm_dir, exist_ok=True)

    raw_copy = os.path.join(raw_dir, "%s.raw.txt" % slug)
    shutil.copyfile(src, raw_copy)
    if hashlib.sha256(open(raw_copy, "rb").read()).hexdigest() != sha:
        _fail("raw archive copy is not byte-identical -- aborting")
    with open(raw_copy + ".sha256", "w", encoding="utf-8") as f:
        f.write("%s  %s\n" % (sha, os.path.basename(raw_copy)))

    with open(os.path.join(norm_dir, "%s.normalized.txt" % slug), "w", encoding="utf-8") as f:
        for e in line_map:
            f.write("%s\t%s\n" % (e["timestamp"] or "-", e["normalizedText"]))
    gc.atomic_write_text(os.path.join(norm_dir, "%s.normalization-map.json" % slug),
                         gc.pretty_json({"sourceFileSha256": sha, "policy": policy, "lines": line_map}))

    os.makedirs(MANIFEST_DIR, exist_ok=True)
    manifest_path = os.path.join(MANIFEST_DIR, "%s.ingest.json" % slug)
    gc.atomic_write_text(manifest_path, gc.pretty_json(manifest))

    # Move the working copy into processing/ only after everything above
    # succeeded, so a failed run never leaves the queue in a false state.
    if os.path.dirname(src) == os.path.join(INTAKE_ROOT, "pending"):
        dest = os.path.join(INTAKE_ROOT, "processing", os.path.basename(src))
        shutil.move(src, dest)
        print("   queue   : pending -> processing")

    print("== 4. archives + draft manifest ==")
    print("   raw     : %s" % _rel(raw_copy))
    print("   normal. : %s" % _rel(os.path.join(norm_dir, "%s.normalized.txt" % slug)))
    print("   MANIFEST: %s" % _rel(manifest_path))
    print("\nNEXT: fill in `annotations` in the manifest, then run")
    print("   python3 scripts/trader_intelligence/ingest.py --apply %s --dry-run" % _rel(manifest_path))
    return 0


# ---------------------------------------------------------------------------
# Phase 2 -- validate and apply
# ---------------------------------------------------------------------------

def _validate_manifest(m, line_map, existing_claim_ids=None):
    errs = []
    existing_claim_ids = existing_claim_ids or set()
    if m.get("manifestVersion") != MANIFEST_VERSION:
        errs.append("manifestVersion %r is not supported (expected %d)"
                    % (m.get("manifestVersion"), MANIFEST_VERSION))
    if not m.get("annotations"):
        errs.append("`annotations` is empty -- nothing to apply")
    sec_text = {}
    for s in m["sections"]:
        a, b = s["lines"]
        sec_text[s["n"]] = section_text(line_map, a, b)
    _assert_coverage(m["sections"], len(line_map))

    seen = set()
    for i, a in enumerate(m.get("annotations", []), start=1):
        where = "annotation #%d (%s)" % (i, a.get("key"))
        if not a.get("key"):
            errs.append("%s: missing `key`" % where)
        elif a["key"] in seen:
            errs.append("%s: duplicate key" % where)
        else:
            seen.add(a["key"])
        if a.get("section") not in sec_text:
            errs.append("%s: section %r does not exist" % (where, a.get("section")))
        elif not a.get("excerpt"):
            errs.append("%s: missing `excerpt`" % where)
        elif a["excerpt"] not in sec_text[a["section"]]:
            errs.append("%s: excerpt is NOT a verbatim substring of section %d"
                        % (where, a["section"]))
        for field, vocab in (("evidenceType", evc.EVIDENCE_TYPES),
                             ("directness", evc.DIRECTNESS_CLASSIFICATIONS),
                             ("extractionCertainty", evc.EXTRACTION_CERTAINTY_LEVELS),
                             ("evidenceQuality", evc.EVIDENCE_QUALITIES)):
            if a.get(field) not in vocab:
                errs.append("%s: %s=%r is not one of %r" % (where, field, a.get(field), vocab))
        if a.get("claimType"):
            if a["claimType"] not in evc.CLAIM_TYPES:
                errs.append("%s: claimType=%r invalid" % (where, a["claimType"]))
            if not a.get("claim"):
                errs.append("%s: claimType set but `claim` text missing" % where)
        elif a.get("supports"):
            if a["supports"] not in seen:
                errs.append("%s: supports=%r is not an earlier annotation key" % (where, a["supports"]))
        elif a.get("supportsClaimId"):
            # Cross-source corroboration: attaching this source's evidence to a
            # claim created by an EARLIER intake. This is the only mechanism by
            # which a claim gains a second independence group and can therefore
            # exceed `emerging` (POLICY-001 / DECISION|MOGO|20260727|003).
            if a["supportsClaimId"] not in existing_claim_ids:
                errs.append("%s: supportsClaimId=%r does not exist in the evidence store"
                            % (where, a["supportsClaimId"]))
        else:
            errs.append("%s: needs claimType+claim, supports, or supportsClaimId" % where)
        if a.get("relationshipType") and a["relationshipType"] not in evc.RELATIONSHIP_TYPES:
            errs.append("%s: relationshipType=%r invalid" % (where, a["relationshipType"]))

    for i, c in enumerate(m.get("contradictions", []), start=1):
        # Each side is either an annotation key from THIS manifest, or the id of
        # a claim from an EARLIER source (`aClaimId` / `bClaimId`). The latter is
        # how a cross-educator disagreement gets recorded -- two traders asserting
        # incompatible things about the same operation.
        for side, idkey in (("a", "aClaimId"), ("b", "bClaimId")):
            if c.get(idkey):
                if c[idkey] not in existing_claim_ids:
                    errs.append("contradiction #%d: %s=%r does not exist in the evidence store"
                                % (i, idkey, c[idkey]))
            elif c.get(side) not in seen:
                errs.append("contradiction #%d: %r is not an annotation key" % (i, c.get(side)))
        if c.get("type") not in evc.CONTRADICTION_TYPES:
            errs.append("contradiction #%d: type=%r invalid" % (i, c.get("type")))
        if c.get("severity") not in evc.CONTRADICTION_SEVERITIES:
            errs.append("contradiction #%d: severity=%r invalid" % (i, c.get("severity")))

    for i, q in enumerate(m.get("openQuestions", []), start=1):
        if q.get("type") not in evc.QUESTION_TYPES:
            errs.append("openQuestion #%d: type=%r invalid" % (i, q.get("type")))
        if q.get("priority") not in evc.QUESTION_PRIORITIES:
            errs.append("openQuestion #%d: priority=%r invalid" % (i, q.get("priority")))
        if q.get("blocking") not in evc.QUESTION_BLOCKING_STATUSES:
            errs.append("openQuestion #%d: blocking=%r invalid" % (i, q.get("blocking")))
        if q.get("claim") and q["claim"] not in seen:
            errs.append("openQuestion #%d: claim=%r is not an annotation key" % (i, q["claim"]))
    return errs


def phase2(args):
    mpath = os.path.abspath(args.apply)
    if not os.path.isfile(mpath):
        _fail("no such manifest: %s" % args.apply)
    m = json.load(open(mpath, encoding="utf-8"))
    trader, slug = m["traderId"], m["slug"]
    trader_dir = os.path.join(IMPORTS_ROOT, trader.lower().replace("_", "-"))
    nmap_path = os.path.join(trader_dir, "normalized", "%s.normalization-map.json" % slug)
    if not os.path.isfile(nmap_path):
        _fail("normalization map missing (%s) -- run phase 1 first" % _rel(nmap_path))
    nmap = json.load(open(nmap_path, encoding="utf-8"))
    if nmap["sourceFileSha256"] != m["sourceFileSha256"]:
        _fail("manifest and normalization map disagree on sourceFileSha256 -- refusing to proceed")
    line_map = nmap["lines"]

    print("== validate manifest ==")
    errs = _validate_manifest(m, line_map, set(qe.EvidenceIndex.load(EVIDENCE_ROOT).claims))
    if errs:
        for e in errs:
            print("   FAIL %s" % e)
        _fail("%d validation error(s); nothing written" % len(errs))
    print("   %d annotations, %d sections, %d contradictions, %d open questions -- all valid"
          % (len(m["annotations"]), len(m["sections"]), len(m.get("contradictions", [])),
             len(m.get("openQuestions", []))))
    print("   every excerpt confirmed verbatim")
    if args.dry_run:
        print("\n[dry-run] validation passed. Nothing written.")
        return 0

    now = datetime.now(timezone.utc)
    D = _dirs()
    raw_copy = os.path.join(trader_dir, "raw", "%s.raw.txt" % slug)
    sections = _section_records(line_map, m["sections"])
    structured = gc.pretty_json({"language": m["provenance"].get("language") or "en",
                                 "segments": [{k: s[k] for k in ("text", "sectionTitle", "startTimestamp",
                                                                 "endTimestamp", "lineStart", "lineEnd")}
                                              for s in sections]})

    print("== register ==")
    # repositoryPath names the RAW ARCHIVE, not the queue copy. The queue copy
    # migrates pending -> processing -> completed, so recording it here would
    # leave a stale path the moment the run finishes; the archive never moves
    # and is the source of truth (SPEC-provenance.md §2). The original queue
    # location is preserved in sourceMetadata for the record.
    archive_rel = _rel(raw_copy)
    intake = ir.register_intake_manifest(
        D["intake"], D["lifecycle"], "transcript", ACTOR, now, traderId=trader, title=m["title"],
        repositoryPath=archive_rel, transcriptPath=archive_rel,
        canonicalReference=m["provenance"].get("canonicalReference"),
        language=m["provenance"].get("language") or "en", transcriptFormat="structured_json",
        transcriptProvider=m["provenance"].get("transcriptProvider"),
        transcriptCompleteness=m["provenance"].get("transcriptCompleteness") or "unknown",
        licensingStatus=m["provenance"].get("licensingStatus") or "unknown",
        contentHash=m["sourceFileSha256"],
        sourceMetadata={"fileBytes": m["sourceFileBytes"], "fileSha256": m["sourceFileSha256"],
                        "sourceLineCount": m["sourceLineCount"],
                        "importTimestampUtc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "originalQueuePath": m["sourceFile"],
                        "rawCopyPath": archive_rel, "manifestPath": _rel(mpath),
                        "normalizationMapPath": _rel(nmap_path),
                        "normalization": m["normalization"], "sectionCount": len(sections)})
    iid = intake["intakeId"]
    ir.transition_intake_status(D["intake"], D["lifecycle"], iid, "validated", ACTOR, now,
                                reason="Manifest validated; every excerpt confirmed verbatim.")
    ir.transition_intake_status(D["intake"], D["lifecycle"], iid, "ready_for_extraction", ACTOR, now,
                                reason="%d reviewed sections with full line-level provenance." % len(sections))
    source = reg.register_source(
        D["sources"], D["lifecycle"], "transcript", ACTOR, now, traderId=trader, title=m["title"],
        storageLocationType="repository", repositoryPath=archive_rel,
        transcriptReference=_rel(nmap_path), contentHash=m["sourceFileSha256"],
        canonicalReference=m["provenance"].get("canonicalReference"),
        language=m["provenance"].get("language") or "en",
        licensingStatus=m["provenance"].get("licensingStatus") or "unknown",
        provenanceStatus="partially_verified",
        metadata={"manifestPath": _rel(mpath), "fileBytes": m["sourceFileBytes"]})
    ir.link_intake_to_source(D["intake"], D["lifecycle"], iid, source["sourceId"], ACTOR, now)
    result = ep.run_intake_extraction_pipeline(EVIDENCE_ROOT, iid, structured, now=now, actor=ACTOR)
    seg_ids = result["segmentsCreated"]
    print("   intake  : %s" % iid)
    print("   source  : %s" % source["sourceId"])
    print("   segments: %d" % len(seg_ids))

    print("== apply annotations ==")
    by_key, claim_ids = {}, set()
    for a in m["annotations"]:
        kw = {"traderId": trader, "evidenceQuality": a["evidenceQuality"],
              "normalizedObservation": a.get("claim"), "timeframe": a.get("timeframe"),
              "session": a.get("session"), "marketCondition": a.get("marketCondition"),
              "symbol": a.get("symbol"), "notes": a.get("notes")}
        if a.get("claimType"):
            kw["claimType"], kw["proposedClaim"] = a["claimType"], a["claim"]
        else:
            kw["existingClaimId"] = (by_key[a["supports"]] if a.get("supports")
                                     else a["supportsClaimId"])
            kw["relationshipType"] = a.get("relationshipType") or "supports"
        ann = ap.register_annotation(D["annotations"], D["segments"], D["intake"], now, iid,
                                     seg_ids[a["section"] - 1], a["excerpt"], a["evidenceType"],
                                     a["directness"], a["extractionCertainty"], ACTOR, **kw)
        ap.set_annotation_review_status(D["annotations"], ann["annotationId"], "approved", now)
        out = ap.apply_annotation(D["annotations"], D["segments"], D["intake"], D["items"],
                                  D["sources"], D["claims"], D["links"], D["lifecycle"], now,
                                  ann["annotationId"], ACTOR)
        by_key[a["key"]] = out["claimId"]
        claim_ids.add(out["claimId"])
    print("   %d annotations -> %d distinct claims" % (len(m["annotations"]), len(claim_ids)))

    for c in m.get("contradictions", []):
        a_id = c.get("aClaimId") or by_key[c["a"]]
        b_id = c.get("bClaimId") or by_key[c["b"]]
        cr = reg.create_contradiction(D["contradictions"], D["claims"], D["lifecycle"],
                                      a_id, b_id, c["type"], c["severity"],
                                      ACTOR, now, rationale=c.get("rationale"))
        cross = (idx_traders_differ(a_id, b_id) and " [CROSS-EDUCATOR]") or ""
        print("   contradiction %s (%s/%s)%s" % (cr["contradictionId"], c["type"], c["severity"], cross))
    for q in m.get("openQuestions", []):
        eq.create_question(D["questions"], now, q["type"], q["text"], q["priority"],
                           q.get("reason") or "", q["blocking"],
                           claimId=by_key.get(q["claim"]) if q.get("claim") else None,
                           sourceIds=[source["sourceId"]])
    if m.get("openQuestions"):
        print("   %d authored open question(s)" % len(m["openQuestions"]))

    # Independence policy MUST run before the post-annotation pipeline: that
    # pipeline auto-proposes a RuleCandidateProposal for any claim already at
    # `supported`, and confidence is only correct once links are grouped by
    # educator. Running it afterwards proposed two rules off same-educator
    # repetition alone before the policy pulled the claims back to `emerging`.
    apply_author_independence_policy()  # same-educator repetition is not confirmation

    post = ep.run_post_annotation_pipeline(EVIDENCE_ROOT, sorted(claim_ids), now=now, actor=ACTOR)
    print("   auto questions: %d | rule candidates: %d"
          % (len(post["questionsCreated"]), len(post["proposalsCreated"])))
    gc_orphans()  # that pipeline re-appends all 14 review queues; collapse the duplicates
    if post["proposalsCreated"]:
        print("   NOTE: rule candidates were auto-proposed -- expected only when a claim is "
              "corroborated by 2+ independent sources.")

    ir.transition_intake_status(D["intake"], D["lifecycle"], iid, "review_required", ACTOR, now,
                                reason="Extraction complete; awaiting owner review.",
                                extraWarnings=m.get("warnings") or [])

    print("== knowledge library ==")
    _build_library(trader, now)

    # Move the queue file BEFORE regenerating the dashboard: the dashboard reads
    # the live queue, so regenerating first reports this very transcript as
    # still awaiting work.
    processing = os.path.join(INTAKE_ROOT, "processing", os.path.basename(m["sourceFile"]))
    if os.path.isfile(processing):
        shutil.move(processing, os.path.join(INTAKE_ROOT, "completed", os.path.basename(processing)))
        print("   queue   : processing -> completed")

    print("== graph + integrity + dashboard ==")
    _run_step("build_graph.py")
    _run_step("validate_evidence.py")
    _run_step("build_knowledge_dashboard.py")
    print("\nDONE. intakeId=%s -- review, then run the regression suites (Playbook Stage 9)." % iid)
    return 0


def _run_step(script_name):
    """Run a sibling script as a subprocess. Uses an argv list rather than a
    shell string: the repository path contains a space, which silently broke
    an earlier os.system() version of this."""
    import subprocess
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    proc = subprocess.run([sys.executable, path], cwd=REPO_ROOT,
                          capture_output=True, text=True)
    tail = (proc.stdout or proc.stderr).strip().splitlines()
    for line in tail[-2:]:
        print("   %s" % line)
    if proc.returncode != 0:
        print("   WARNING: %s exited %d" % (script_name, proc.returncode))
    return proc.returncode


def idx_traders_differ(claim_a_id, claim_b_id):
    """True when a contradiction spans two different traders -- worth calling out,
    because a cross-educator disagreement is a materially different finding from
    one trader contradicting himself."""
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    a, b = idx.claims.get(claim_a_id), idx.claims.get(claim_b_id)
    return bool(a and b and a.get("traderId") != b.get("traderId"))


def _build_library(trader, now):
    """Blueprint -> gaps -> hypotheses -> profile LAST. The profile counts
    hypotheses and questions at build time and the report reads its statistics
    off the profile, so building it first under-reports (defect D3)."""
    import strategy_blueprint as sb
    import knowledge_gaps as kg
    import hypothesis_proposals as hp
    import trader_profile as tp
    import knowledge_library_report as klr

    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    bp = sb.register_strategy_blueprint(os.path.join(EVIDENCE_ROOT, "blueprints"), idx, trader,
                                        actor=ACTOR, now=now)
    if bp is None:
        print("   no claims for %s -- nothing to draft" % trader)
        return
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    gaps = kg.generate_knowledge_gaps(os.path.join(EVIDENCE_ROOT, "gaps"), idx, bp, actor=ACTOR, now=now)
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    hyps = hp.generate_hypotheses(os.path.join(EVIDENCE_ROOT, "hypotheses"), idx, bp, gaps=gaps,
                                  actor=ACTOR, now=now)
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    prof = tp.register_trader_profile(os.path.join(EVIDENCE_ROOT, "profiles"), idx, trader,
                                      actor=ACTOR, now=now)
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    rep = klr.generate_knowledge_library_report(idx, trader, prof, bp, gaps, hyps, now=now)
    gc.atomic_write_text(os.path.join(EVIDENCE_ROOT, "reports",
                                      "knowledge-library-report-%s.json" % trader), gc.pretty_json(rep))
    out_md = os.path.join(IMPORTS_ROOT, trader.lower().replace("_", "-"),
                          "%s-KNOWLEDGE-LIBRARY-REPORT.md" % trader)
    gc.atomic_write_text(out_md, klr.render_knowledge_library_report_markdown(rep))
    print("   blueprint %s | %d gaps | %d hypotheses | profile %s"
          % (bp["blueprintId"], len(gaps), len(hyps), prof["profileId"]))
    print("   report  : %s" % _rel(out_md))


# ---------------------------------------------------------------------------
# Rollback and status
# ---------------------------------------------------------------------------

def rollback(intake_id):
    removed = 0
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    if intake_id not in idx.intakes:
        _fail("unknown intakeId %r" % intake_id)
    source_id = idx.intakes[intake_id].get("sourceId")
    seg_ids = {s["segmentId"] for s in idx.segments.values() if s["intakeId"] == intake_id}
    ev_ids = {i["evidenceId"] for i in idx.items.values() if i.get("sourceId") == source_id}
    touched = {l["claimId"] for l in idx.links.values() if l["evidenceId"] in ev_ids}

    # A claim that ALSO carries evidence from another source was not created by
    # this run -- this run merely corroborated or contextualised it. Deleting it
    # would destroy a prior source's work. Such claims are kept and their
    # confidence is recomputed after this run's links are removed.
    foreign = {l["claimId"] for l in idx.links.values() if l["evidenceId"] not in ev_ids}
    claim_ids = touched - foreign
    shared = sorted(touched & foreign)

    def _drop(dirname, id_field, ids):
        nonlocal removed
        for p in globmod.glob(os.path.join(EVIDENCE_ROOT, dirname, "*.json")):
            rec = json.load(open(p, encoding="utf-8"))
            if rec.get(id_field) in ids:
                os.remove(p)
                removed += 1

    # Contradictions and questions that reference ONLY this run's claims.
    contra_ids = {c["contradictionId"] for c in idx.contradictions.values()
                  if c["claimAId"] in claim_ids and c["claimBId"] in claim_ids}
    question_ids = {q["questionId"] for q in idx.questions.values()
                    if q.get("claimId") in claim_ids
                    or (source_id and q.get("sourceIds") == [source_id])}

    _drop("links", "evidenceId", ev_ids)
    _drop("items", "evidenceId", ev_ids)
    _drop("claims", "claimId", claim_ids)
    _drop("segments", "segmentId", seg_ids)
    _drop("annotations", "intakeId", {intake_id})
    _drop("intake", "intakeId", {intake_id})
    _drop("contradictions", "contradictionId", contra_ids)
    _drop("questions", "questionId", question_ids)
    if source_id:
        _drop("sources", "sourceId", {source_id})

    # Lifecycle events for entities that no longer exist. The audit trail is
    # append-only for LIVE entities; an event pointing at a rolled-back record
    # is a dangling reference that blocks the graph build, not an audit record.
    dead = ev_ids | claim_ids | seg_ids | contra_ids | {intake_id} | ({source_id} if source_id else set())
    _drop("lifecycle", "entityId", dead)
    print("rollback %s: removed %d record(s)." % (intake_id, removed))

    # Claims shared with other sources survive, but their confidence must be
    # re-derived now that this run's links are gone -- never left stale.
    for cid in shared:
        reg.recompute_claim_confidence(EVIDENCE_ROOT + "/claims", EVIDENCE_ROOT + "/links",
                                       EVIDENCE_ROOT + "/items", EVIDENCE_ROOT + "/lifecycle",
                                       cid, ACTOR, datetime.now(timezone.utc))
    if shared:
        print("   kept %d claim(s) shared with other sources; confidence recomputed: %s"
              % (len(shared), ", ".join(shared)))
    removed += gc_orphans()
    print("NOTE: TraderProfile / StrategyBlueprint / KnowledgeGap / Hypothesis snapshots are NOT")
    print("      removed -- they are immutable point-in-time artifacts that may summarise other")
    print("      sources too. Delete any that are now wrong, then rebuild the graph.")
    return 0


def apply_author_independence_policy(verbose=True):
    """Collapse every link from the same EDUCATOR into ONE independence group.

    Owner directive 2026-07-27 (`DECISION|MOGO|20260727|006`): repetition by the
    same educator is NOT independent confirmation. Without this, two videos by
    one trader create two independence groups and can carry a claim from
    `emerging` to `supported` -- which would treat a person restating himself as
    corroboration.

    `EvidenceClaimLink.independenceGroup` already overrides the sourceId default
    in `evidence_confidence._independence_groups()`, so this needs no engine
    change: it sets the field to `AUTHOR|{traderId}` and recomputes.

    Idempotent. Safe to re-run at any time.
    """
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    changed, touched = 0, set()
    for link in idx.links.values():
        item = idx.items.get(link["evidenceId"])
        if not item:
            continue
        src = idx.sources.get(item.get("sourceId")) or {}
        trader = src.get("traderId")
        group = "AUTHOR|%s" % trader if trader else item.get("sourceId")
        if link.get("independenceGroup") != group:
            link["independenceGroup"] = group
            gc.atomic_write_text(
                os.path.join(EVIDENCE_ROOT, "links", evc.link_id_to_filename(link["linkId"])),
                gc.pretty_json(link))
            changed += 1
        touched.add(link["claimId"])

    now = datetime.now(timezone.utc)
    for cid in sorted(touched):
        reg.recompute_claim_confidence(os.path.join(EVIDENCE_ROOT, "claims"),
                                       os.path.join(EVIDENCE_ROOT, "links"),
                                       os.path.join(EVIDENCE_ROOT, "items"),
                                       os.path.join(EVIDENCE_ROOT, "lifecycle"),
                                       cid, "independence-policy", now)
    if verbose:
        print("   independence policy: %d link(s) re-grouped by author, %d claim(s) recomputed"
              % (changed, len(touched)))
    return changed


def gc_orphans():
    """Remove review-queue entries pointing at records that no longer exist,
    and collapse duplicate queue entries.

    Both conditions arise in normal operation: `run_post_annotation_pipeline`
    rebuilds ALL 14 review queues on every ingestion and appends fresh entries
    without removing prior ones, so an unrelated ingestion duplicates every
    existing entry (observed: 23 -> 46 after one unrelated run). Left
    unchecked this grows linearly with ingestion count."""
    live = set()
    for sub, field in (("contradictions", "contradictionId"), ("questions", "questionId"),
                       ("claims", "claimId"), ("items", "evidenceId"), ("sources", "sourceId"),
                       ("intake", "intakeId"), ("proposals", "proposalId")):
        for p in globmod.glob(os.path.join(EVIDENCE_ROOT, sub, "*.json")):
            live.add(json.load(open(p, encoding="utf-8"))[field])

    seen, dangling, dupes = {}, 0, 0
    for p in sorted(globmod.glob(os.path.join(EVIDENCE_ROOT, "review-queue", "*.json"))):
        r = json.load(open(p, encoding="utf-8"))
        ent = r.get("entityId")
        if ent and ent not in live:
            os.remove(p); dangling += 1
            continue
        key = (r.get("queueType"), r.get("entityType"), ent)
        if key in seen:
            os.remove(p); dupes += 1
        else:
            seen[key] = p
    if dangling or dupes:
        print("   gc: removed %d dangling and %d duplicate review-queue entr(ies)" % (dangling, dupes))
    return dangling + dupes


def verify_provenance():
    """Re-verify the whole chain against the bytes on disk.

    Closes gap G-a in SPEC-provenance.md: until this existed, the raw-copy hash
    was asserted once at ingestion time and never re-checked. Its first run
    found a real drift -- a working copy of the TJR transcript had been altered
    after ingestion while the raw archive stayed intact.
    """
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    findings, checked = [], 0

    for m in sorted(idx.intakes.values(), key=lambda x: x["intakeId"]):
        expected = m.get("contentHash")
        meta = m.get("sourceMetadata") or {}
        for label, rel in (("raw archive", meta.get("rawCopyPath")),
                           ("working copy", m.get("repositoryPath"))):
            if not rel:
                continue
            path = os.path.join(REPO_ROOT, rel)
            checked += 1
            if not os.path.isfile(path):
                findings.append(("MISSING", m["intakeId"], label, rel, "file not found"))
                continue
            actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
            if expected and actual != expected:
                findings.append(("HASH_MISMATCH", m["intakeId"], label, rel,
                                 "expected %s, found %s" % (expected[:16], actual[:16])))

        nmap_rel = meta.get("normalizationMapPath")
        if nmap_rel and os.path.isfile(os.path.join(REPO_ROOT, nmap_rel)):
            checked += 1
            nmap = json.load(open(os.path.join(REPO_ROOT, nmap_rel), encoding="utf-8"))
            if nmap.get("sourceFileSha256") not in (None, expected):
                findings.append(("MAP_DISAGREES", m["intakeId"], "normalization map", nmap_rel,
                                 "map records %s" % (nmap.get("sourceFileSha256") or "")[:16]))

    # Every evidence excerpt must still be a verbatim substring of its segment.
    for item in idx.items.values():
        loc = item.get("sourceLocator")
        if not (loc and loc.startswith("TSEG|") and item.get("exactExcerpt")):
            continue
        seg = idx.segments.get(loc)
        checked += 1
        if seg is None:
            findings.append(("ORPHAN_EVIDENCE", item["evidenceId"], "segment", loc, "segment missing"))
        elif item["exactExcerpt"] not in seg["rawText"]:
            findings.append(("EXCERPT_NOT_VERBATIM", item["evidenceId"], "segment", loc,
                             "excerpt no longer found in segment text"))

    print("provenance verification: %d check(s), %d finding(s)" % (checked, len(findings)))
    for kind, ident, label, rel, detail in findings:
        print("  %-22s %s  [%s] %s -- %s" % (kind, ident, label, rel, detail))
    if not findings:
        print("  all raw archives, working copies, normalization maps and excerpts verify.")
    return 1 if findings else 0


def status():
    idx = qe.EvidenceIndex.load(EVIDENCE_ROOT)
    for q in ("pending", "processing", "completed", "rejected"):
        d = os.path.join(INTAKE_ROOT, q)
        files = [f for f in sorted(os.listdir(d)) if not f.startswith(".") and f != "README.md"
                 and not f.endswith(".rejected.txt")] if os.path.isdir(d) else []
        print("%-11s %d %s" % (q + ":", len(files), files if files else ""))
    print("\nsources=%d intakes=%d claims=%d evidence=%d"
          % (len(idx.sources), len(idx.intakes), len(idx.claims), len(idx.items)))
    print("See docs/trader-intelligence/KNOWLEDGE-DASHBOARD.md for full state.")
    return 0


def main():
    p = argparse.ArgumentParser(description="MOGO Trader Intelligence transcript ingestion.")
    p.add_argument("transcript", nargs="?", help="path to a transcript (phase 1)")
    p.add_argument("--trader", help="traderId, e.g. TJR / ICT / ALEX_G")
    p.add_argument("--title", help="human-readable source title")
    p.add_argument("--slug", help="manifest slug (default: filename stem)")
    p.add_argument("--url", help="canonical reference (URL / video id)")
    p.add_argument("--channel", help="channel or publisher")
    p.add_argument("--published", help="publication date, YYYY-MM-DD")
    p.add_argument("--provider", help="transcript provider, e.g. youtube_auto_caption_copy")
    p.add_argument("--language", default="en")
    p.add_argument("--licensing", default="restricted_third_party",
                   choices=["unknown", "owner_authored", "permitted_third_party",
                            "restricted_third_party", "public_domain"])
    p.add_argument("--completeness", default="unknown", choices=["unknown", "complete", "partial"])
    p.add_argument("--normalize-profile", choices=list(tn.PROFILES))
    p.add_argument("--apply", metavar="MANIFEST", help="phase 2: validate and apply a manifest")
    p.add_argument("--rollback", metavar="INTAKE_ID", help="remove every record from one run")
    p.add_argument("--status", action="store_true", help="show queue and library state")
    p.add_argument("--apply-independence-policy", action="store_true",
                   help="re-group every link by educator and recompute confidence")
    p.add_argument("--verify-provenance", action="store_true",
                   help="re-verify every raw archive, working copy, normalization map and excerpt")
    p.add_argument("--dry-run", action="store_true", help="validate only; write nothing")
    args = p.parse_args()

    if args.apply_independence_policy:
        apply_author_independence_policy()
        return 0
    if args.verify_provenance:
        return verify_provenance()
    if args.status:
        return status()
    if args.rollback:
        return rollback(args.rollback)
    if args.apply:
        return phase2(args)
    if not args.transcript or not args.trader:
        p.print_help()
        return 1
    return phase1(args)


if __name__ == "__main__":
    raise SystemExit(main())
