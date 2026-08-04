# PROPOSAL-002 — Ingestion Toolkit

**Status:** Proposal only. **Not implemented.**
**Serves:** Priority 1 (repeatable ingestion), Priority 2 (minimize manual work).
**Requires:** owner approval to write code under `scripts/trader_intelligence/`.

---

## 1. Problem

The first production ingestion worked, but **the procedure that produced it does not exist in the
repository.** It ran from two ad-hoc scripts in a session scratchpad
(`normalize_intake.py`, `run_intake.py`, ~700 lines) which are outside the repo and will not
survive. What was committed is the *output*, not the *method*.

The practical consequences, measured against the stated priorities:

| Priority | Current state |
|---|---|
| **1. Repeatable** | ❌ The next transcript starts by re-writing ~700 lines of bespoke scripting |
| **2. Minimal manual work** | ❌ Every ingestion is a fresh programming task, not a data task |
| **3. Provenance preserved** | ⚠️ Achieved, but by hand-written assertions that a future operator may simply omit |
| **4. Never invent rules** | ✅ Machine-enforced by `register_annotation()` — the one property that is genuinely safe |
| **5. No unearned confidence** | ✅ Machine-enforced by the confidence engine |

`OPERATOR-PLAYBOOK.md` documents the procedure, which raises the floor. But a playbook describing
700 lines of scripting is a mitigation, not a solution: the quality of ingestion #7 will depend on
how carefully someone re-implements pre-flight validation and the reversibility assertion.

**The core insight:** an ingestion is *data plus judgment*, but it is currently expressed as *code*.
The judgment (which excerpt, which claimType) is irreducibly human. Everything else — hashing,
copying, normalizing, sectioning, registering, validating — is mechanical and identical every time.

---

## 2. Proposal

Split ingestion into a **declarative manifest** (the judgment, authored per transcript) and a
**generic runner** (the mechanics, written once).

### 2.1 The Ingestion Manifest

One JSON file per transcript, at `imports/{trader}/{slug}.ingest.json`. It is a first-class,
reviewable, diffable artifact — the thing an operator actually authors.

```json
{
  "manifestVersion": 1,
  "traderId": "TJR",
  "title": "TJR — session-based liquidity-sweep strategy walkthrough",
  "sourceFile": "tjr-forex-session-strategy-transcript.txt",

  "provenance": {
    "canonicalReference": "https://www.youtube.com/watch?v=...",
    "channelOrPublisher": "...",
    "publicationDate": "2025-10-02",
    "transcriptProvider": "youtube_auto_caption_copy",
    "licensingStatus": "unknown",
    "transcriptCompleteness": "unknown"
  },

  "normalization": {
    "profile": "youtube_duration_label",
    "unlabelledLinePolicy": "assign_zero_timestamp",
    "requireReversible": true
  },

  "sections": [
    {"n": 1, "lines": [1, 15],  "type": "introduction", "title": "Performance claims and credibility framing"},
    {"n": 3, "lines": [23, 27], "type": "instruction",  "title": "Core premise: liquidity sweeps defined"}
  ],

  "annotations": [
    {
      "key": "premise",
      "section": 3,
      "excerpt": "My strategy is based off of liquidity sweeps.",
      "evidenceType": "explicit_statement",
      "directness": "direct_explicit",
      "extractionCertainty": "certain",
      "evidenceQuality": "high",
      "claimType": "setup_requirement",
      "claim": "The strategy is based on liquidity sweeps."
    },
    {
      "key": "step1_always",
      "section": 9,
      "excerpt": "And I'm looking for a liquidity sweep every single time.",
      "evidenceType": "explicit_statement",
      "directness": "direct_explicit",
      "extractionCertainty": "high",
      "evidenceQuality": "high",
      "supports": "step1"
    }
  ],

  "contradictions": [
    {"a": "step3", "b": "exc_no_equilibrium", "type": "CONDITIONAL_SCOPE",
     "severity": "material", "rationale": "..."}
  ],

  "openQuestions": [
    {"claim": null, "type": "unclear_scope", "priority": "critical",
     "blocking": "blocks_promotion", "text": "...", "reason": "..."}
  ]
}
```

`key` is a stable local handle so annotations can attach to claims created earlier in the same
manifest — replacing the runtime dictionary the first ingestion used.

### 2.2 The runner

```bash
python3 scripts/trader_intelligence/ingest_transcript.py \
    --manifest docs/trader-intelligence/imports/tjr/tjr-session-strategy.ingest.json \
    [--dry-run] [--stage STAGE] [--rollback]
```

Stages map 1:1 onto the playbook: `verify → preserve → normalize → section → register → annotate
→ contradictions → post → library → graph → validate → report`.

**Behaviours that matter:**

- **`--dry-run` validates the entire manifest and writes nothing.** Every excerpt is checked
  verbatim, every `supports` reference resolved, every enum value validated, section coverage
  asserted, normalization reversibility proven. This turns the first intake's hand-written
  pre-flight check into a guarantee rather than a habit.
- **Fail-closed.** Any assertion failure aborts before the first write.
- **`--rollback`** removes every record created by a named `intakeId`, then rebuilds and
  re-validates the graph. The first intake had to be wiped and re-run twice; that was manual.
- **Deterministic.** Same manifest + same source file ⇒ same records (modulo timestamps), so an
  ingestion can be replayed and diffed.
- **Correct ordering built in** — profile last (defect D3), so the ordering bug cannot recur.

### 2.3 Normalization profiles

A named, tested, reusable transform per artifact class. `youtube_duration_label` is the one the
first intake needed. Others will follow (`speaker_prefixed`, `srt_vtt`, `plain_paragraphs`). Each
profile ships with its own fixtures. **Every profile must satisfy the reversibility contract** —
that is a property of the profile interface, not of each caller.

### 2.4 Manifest authoring aids (not automation of judgment)

- `--suggest` emits a **draft manifest** with sections proposed at topic-shift heuristics and the
  existing keyword suggestions pre-filled as commented candidates. The operator edits it.
- `--coverage` reports which source lines are not cited by any annotation, so under-extraction is
  visible rather than invisible.

**Explicitly not proposed:** automatic claim generation, automatic claimType assignment, or any LLM
call inside the pipeline. The judgment stays human, and the no-LLM/no-network guarantee of every
existing module is preserved. This proposal automates the *mechanics* around the judgment.

---

## 3. Expected ROI

| Dimension | Today | With toolkit |
|---|---|---|
| Per-transcript effort | ~700 lines of bespoke scripting + extraction | Extraction judgment + a JSON manifest |
| Mechanical-error risk | Depends on operator discipline | Fail-closed, machine-checked |
| Rollback | Manual deletion | One command |
| Review surface | A one-off script | A diffable manifest |
| Cross-ingestion consistency | Convention | Enforced by a shared runner |

Break-even is roughly **the second or third transcript**. `BACKLOG-002` already identifies seven
TJR sources, so break-even arrives within the currently-planned work.

The reviewability gain may matter more than the effort gain: a reviewer can read a manifest and
check every extraction judgment against the source. Nobody can meaningfully review a 700-line
bespoke script for the same property.

---

## 4. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| New code in `scripts/trader_intelligence/` | Low | Additive only; no existing module modified; the runner *calls* the existing pipeline rather than reimplementing it |
| Touches trading logic | **None** | No import path to `index.html`; the existing no-network/no-LLM structural tests extend to the new module |
| Manifest becomes a second source of truth | Medium | The manifest is an *input*; canonical records remain the JSON in `evidence/`. Never read at query time. |
| Over-automation erodes extraction quality | Medium | `--suggest` produces a draft the operator must edit; suggestions are never auto-applied |
| Schema churn on `manifestVersion` | Low | Versioned from v1; the runner rejects unknown versions rather than guessing |
| Scope creep | Medium | Phase it (§5); phase A alone captures most of the value |

---

## 5. Suggested phasing

| Phase | Content | Value |
|---|---|---|
| **A** | Manifest schema + `--dry-run` validator only. **Writes nothing.** | Highest value per unit risk — makes every future ingestion machine-checked before it touches disk |
| **B** | Full runner: all stages, correct ordering, `--stage` | Removes the bespoke scripting |
| **C** | `--rollback`, `--coverage` | Operational safety and quality visibility |
| **D** | `--suggest`, additional normalization profiles | Reduces authoring effort |

**Phase A is worth doing even if B–D are never approved**, because it converts the first intake's
hand-written pre-flight assertions into a permanent guarantee.

---

## 6. OWNER DECISION REQUIRED

### The problem

The method that produced the first production ingestion is not in the repository, and Priorities 1
and 2 cannot be met by documentation alone. Writing this toolkit means writing new code, which the
current standing instruction does not authorize.

### Options

**Option 1 — Approve phases A–D now.** Full toolkit.
*Risk:* largest new-code surface; all of it additive and outside trading logic.
*ROI:* highest; break-even at transcript #2–3.

**Option 2 — Approve phase A only (`--dry-run` validator).** ✅ **Recommended**
*Risk:* minimal — a module that writes nothing cannot corrupt anything.
*ROI:* captures the largest single risk reduction (fail-closed validation of every manifest) for
roughly a fifth of the work, and produces the manifest schema that phases B–D need. Ingestion
remains scripted, but the script is validated against a reviewed manifest.

**Option 3 — Approve nothing; rely on the playbook.**
*Risk:* every future ingestion re-implements provenance assertions from prose. The failure mode is
silent — a missing reversibility assertion produces a plausible-looking result.
*ROI:* zero cost now, compounding cost per transcript.

**Option 4 — Preserve the first intake's scripts as-is under `scripts/trader_intelligence/`.**
*Risk:* they are TJR-specific with the annotation table inlined; committing them invites
copy-paste-and-edit, which spreads bespoke code rather than replacing it.
*ROI:* low. **Not recommended** — but note that today the alternative is losing them entirely.

### Recommendation

**Option 2 now, Option 1 after the second transcript.** Phase A is nearly risk-free, produces the
manifest format that everything else depends on, and makes the highest-value property — fail-closed
validation before any write — permanent. Deferring B–D until a second transcript has been ingested
means the runner gets designed against two real examples rather than one, which is a materially
better basis for a general tool.

If Option 2 is approved I would additionally recommend **retrospectively authoring the TJR manifest**
for the completed intake. It would not re-run anything, but it would prove the schema against real
data and make the first intake's extraction judgments reviewable as data.
