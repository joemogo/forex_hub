# Operator Playbook — Transcript Ingestion

**Audience:** whoever runs the next transcript ingestion (human or Claude).
**Status:** Normative. Validated end-to-end against a real transcript and against a synthetic
round-trip (ingest → apply → rollback → byte-identical baseline).
**Companions:** [`STANDARDS-extraction.md`](STANDARDS-extraction.md) (how to classify) ·
[`SPEC-provenance.md`](SPEC-provenance.md) (what must stay true) ·
[`KNOWLEDGE-DASHBOARD.md`](KNOWLEDGE-DASHBOARD.md) (current state).

---

## TL;DR — the whole workflow

```bash
# 1. Drop the transcript in the queue
cp my-transcript.txt docs/trader-intelligence/intake/pending/ict-ep01.txt

# 2. Automatic phase: verify, dedupe, archive, normalize, section, draft manifest
python3 scripts/trader_intelligence/ingest.py \
    docs/trader-intelligence/intake/pending/ict-ep01.txt --trader ICT

# 3. Extraction (the only judgment step) — fill in `annotations` in
#    docs/trader-intelligence/intake/manifests/ict-ep01.ingest.json

# 4. Validate without writing, then apply
python3 scripts/trader_intelligence/ingest.py --apply <manifest> --dry-run
python3 scripts/trader_intelligence/ingest.py --apply <manifest>

# 5. Regression (Stage 9)
python3 -m unittest tests.trader_intelligence.test_graph \
  tests.trader_intelligence.acquisition.test_acquisition \
  tests.trader_intelligence.evidence.test_evidence \
  tests.trader_intelligence.evidence.test_phase1b \
  tests.trader_intelligence.evidence.test_phase7a
bash tests/run_all.sh && python3 regression-baseline-tools.py
```

Steps 2 and 4 automate everything mechanical — hashing, duplicate detection, raw archiving,
reversible normalization, sectioning, intake/source/segment registration, annotation application,
contradictions, questions, the post-annotation pipeline, the Knowledge Library, the graph rebuild,
integrity validation, the dashboard, and the queue move. **Step 3 is the only part that requires
judgment, and it is deliberately not automated.**

---

## Stage 0 — Gates

| Gate | Check | If it fails |
|---|---|---|
| **Trader record** | `traders/{id}/profile.json` exists | Create it — Appendix A. `ingest.py` refuses without one. |
| **Identity** | Canonical URL/ID, channel, publication date | Pass via `--url`, `--channel`, `--published`. A source you cannot name is one you cannot assess. |
| **Publisher verification** | Resolve the real title and channel from the publisher before extraction — see below | Record the title as provisional and say so in the record. Never invent one. |
| **Duplicate** | Same content **or same video** already ingested? | `ingest.py` checks the content hash **and the canonical URL** and auto-rejects. The URL check exists because the same video in a different transcript rendering has different bytes — see `BACKLOG-003/H27`. **Always pass `--url`**; without it only the hash check runs. |
| **Clean baseline** | Suites green, `--verify-provenance` clean | Establish a known-good state before adding data. |

Licensing is **not** a gate: `DECISION|MOGO|20260727|005` permits internal research and extraction.
It defaults to `restricted_third_party` and **prohibits redistribution or public reproduction**.

---

### Verifying the publisher (do this first — it is one call)

For a YouTube source, the oEmbed endpoint returns the published title and the channel:

```bash
curl -s "https://www.youtube.com/oembed?url=<VIDEO_URL>&format=json"
# -> {"title": "...", "author_name": "fxalexg", "author_url": "https://www.youtube.com/@fxalexg__"}
```

**This is not a nicety — `author_name` decides the educator, and the educator decides the
independence group.** Under `DECISION|MOGO|20260727|006` all material from one educator shares a
group and cannot corroborate itself, so attributing a transcript to the wrong educator silently
changes the confidence arithmetic for every claim in it. Verify; do not infer from style or tone.
Transcript #6 read nothing like the same educator's previous video and was the same channel.

Record what was verified **and what was not** in `metadata.titleVerification`. Publisher identity
being confirmed does **not** make the source `verified`: an owner-pasted transcript's fidelity to the
actual audio is still unchecked, and that is the property every excerpt depends on. Leave
`provenanceStatus` at `partially_verified`.

If the owner supplied a title that disagrees with the published one, **keep both** — record the
verified string as the title and the supplied one as `ownerSuppliedTitle` with a note. Do not
silently overwrite the owner.

---

## Stage 1 — Queue the transcript

Drop it in `intake/pending/`. Name it `{trader-slug}-{topic-slug}.txt`; the slug becomes the
manifest name, so keep it stable.

## Stage 2 — Automatic phase

```bash
python3 scripts/trader_intelligence/ingest.py <path> --trader ICT \
    [--title "..."] [--url ...] [--channel ...] [--published YYYY-MM-DD] \
    [--provider youtube_auto_caption_copy] [--normalize-profile ...] [--dry-run]
```

Performs: verify non-empty · SHA-256 · duplicate check against every registered source ·
byte-verified raw archive + `.sha256` sidecar · reversible normalization (profile auto-detected,
reversibility asserted per line, run aborts on failure) · draft sectioning with a coverage assertion ·
draft manifest · `pending → processing`.

**Registers nothing in the evidence store.** Nothing becomes evidence until Stage 4.

**Acceptance:** duplicate `none` · reversibility asserted · unmatched lines are few and explicable
(a large count means the wrong normalization profile) · manifest written.

## Stage 3 — Extraction *(the judgment step)*

Read the whole transcript. Then edit the manifest:

1. **Re-cut and retitle `sections`** so no quotable statement spans a boundary. Draft sections are
   chunked at ~2,000 characters on sentence ends — a reasonable start, not a topic analysis.
2. **Fill `annotations`** per [`STANDARDS-extraction.md`](STANDARDS-extraction.md). Each needs a
   `key`, `section`, verbatim `excerpt`, `evidenceType`, `directness`, `extractionCertainty`,
   `evidenceQuality`, and either `claimType` + `claim` (new claim) or `supports: <earlier key>`
   (corroborating evidence for a claim already created in this manifest).
3. **Add `contradictions`** — `{a, b, type, severity, rationale}` between two annotation keys.
4. **Add `openQuestions`** — `{claim|null, type, priority, blocking, text, reason}`. Use
   `claim: null` for questions about an *absence*, which by construction attach to no claim.

## Stage 4 — Validate and apply

```bash
python3 scripts/trader_intelligence/ingest.py --apply <manifest> --dry-run   # writes nothing
python3 scripts/trader_intelligence/ingest.py --apply <manifest>
```

`--dry-run` is **fail-closed**: every excerpt is checked verbatim, every vocabulary value against
the real enums, every `supports` reference resolved, section coverage asserted, and the manifest
cross-checked against the normalization map's source hash. A single changed character fails the run
with nothing written. *Always run `--dry-run` first.*

The real run then registers, applies, builds the library **in the correct order (profile last —
defect D3)**, rebuilds the graph, validates integrity, regenerates the dashboard, collapses
duplicate review-queue entries, and moves `processing → completed`.

**Acceptance:** graph `status=success` with zero ERROR/FATAL · evidence integrity zero findings ·
**zero rule candidates on a first-source intake** (a non-zero count means a claim was corroborated
by 2+ independent sources — verify that is real).

## Stage 5 — Regression

Run the suites in the TL;DR. **Any protected-function drift means something touched trading logic —
stop immediately.** Nothing in ingestion can cause it.

Triage Python failures into: **contamination** (a fixture picked up production data — a real bug,
fix the fixture) versus **obsolete precondition** (a test asserting a state this ingestion
legitimately ended — an owner decision, do not silently rewrite).

## Stage 6 — Downstream artifacts

The CLI regenerates the dashboard automatically. These remain manual because each needs judgment:

| Artifact | Update |
|---|---|
| [`RESEARCH-LOG.md`](RESEARCH-LOG.md) | Append a cycle entry with the six-point ROI review. **Every ingestion, without exception.** |
| [`GLOSSARY.md`](GLOSSARY.md) | Add evidenced terms with claim IDs; promote "term used, definition absent" entries a new source defines. |
| [`CROSS-STRATEGY-ANALYSIS.md`](CROSS-STRATEGY-ANALYSIS.md) | Add the source's concepts; record agreements, conflicts, terminology collisions. |
| [`proposals/REPLAY-CANDIDATES.md`](proposals/REPLAY-CANDIDATES.md) | Add a structured candidate per objectively testable rule. Mark unknown fields `UNKNOWN — not in source`. |
| [`proposals/BACKLOG-002-tjr-source-acquisition.md`](proposals/BACKLOG-002-tjr-source-acquisition.md) | Add acquisition targets for revealed gaps. |

**Every 10th completed ingestion:** write a Trader Intelligence Review
([`TRADER-INTELLIGENCE-REVIEW.md`](TRADER-INTELLIGENCE-REVIEW.md)). The dashboard prints the count
and the next threshold.

---

## Maintenance commands

```bash
ingest.py --status               # queue + library state
ingest.py --verify-provenance    # re-verify archives, working copies, maps, excerpts
ingest.py --rollback <intakeId>  # remove every record from one run
```

**Run `--verify-provenance` periodically.** Its first run found a real drift: a working transcript
copy had been altered after ingestion (`"I'm sure that"` → `"I'm x that"`) while the raw archive
stayed intact. Evidence was unaffected — everything derives from the archive — but nothing would
have noticed without this check. The altered copy is quarantined in `intake/rejected/`.

**Rollback removes** links, evidence, claims, segments, annotations, the intake, the source,
contradictions and questions scoped to that run, their lifecycle events, and orphaned queue
entries. It does **not** remove `TraderProfile` / `StrategyBlueprint` / `KnowledgeGap` /
`Hypothesis` snapshots — those are immutable point-in-time artifacts that may summarise other
sources. Delete any that are now wrong, then rebuild the graph.

**Prefer a clean re-run over a partial repair.** IDs are sequential per day, so a half-cleaned tree
produces confusing gaps.

---

## Quality gates

| # | Gate | Enforced by |
|---|---|---|
| 1 | File non-empty, hashed | `ingest.py` phase 1 |
| 2 | Not a duplicate | content-hash check, auto-reject |
| 3 | Raw archive byte-identical | asserted at copy time |
| 4 | Normalization reversible | asserted per line; run aborts |
| 5 | Every source line in exactly one section | coverage assertion |
| 6 | Every excerpt verbatim | `--apply` validator **and** `register_annotation()` |
| 7 | Vocabulary values valid | validator, against the real enums |
| 8 | Zero rule candidates on a single-source intake | confidence engine |
| 9 | Graph zero ERROR/FATAL | `build_graph.py` |
| 10 | Evidence integrity zero findings | `validate_evidence.py` |
| 11 | Zero protected-function drift | `regression-baseline-tools.py` |

---

## Appendix A — Onboarding a new trader

1. Create `traders/{id}/profile.json`; `traderId` must match `^[A-Z][A-Z0-9_]*$`.
2. Set `externalResearchStatus` and `repositoryModelStatus` **separately** — a trader can be live in
   the codebase with zero external research (true of ALEX_G and JVM).
3. **Only assert `markets`/`instruments` you can evidence.** An unevidenced value is carried into
   the Knowledge Library as `confirmed` (defect **D1**) and silently outranks real evidence.
4. Do not pre-create empty subdirectories.

Registered today: `TJR`, `ICT`, `ALEX_G`, `JVM`.

## Appendix B — Known defects affecting operators

| ID | Effect | Workaround |
|---|---|---|
| **D1** | Unevidenced `markets` shows as `confirmed`, outranking evidence | Only assert evidenced values |
| **D2** | Permissive `exception` claims appear under `forbiddenConditions` | Type correctly anyway; note in the report |
| **D3** | Profile built first reports `hypothesisCount: 0` | Handled — the CLI builds it last |
| **D4** | Absence-questions not counted in the profile | Note explicitly in the report |
| **D5** | Evidence quality barely affects score at one source | Set honestly regardless |
| **D6** | Review queues re-append on every ingestion | Handled — the CLI collapses duplicates |

Detail and proposed fixes: [`proposals/BACKLOG-003-pipeline-hardening.md`](proposals/BACKLOG-003-pipeline-hardening.md).
