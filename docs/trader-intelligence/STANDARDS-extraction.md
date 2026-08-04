# Extraction and Annotation Standards

**Applies to:** every `ManualAnnotation` created from any transcript, for any trader.
**Status:** Normative. Derived from the first production intake (`INTAKE|TJR|20260727|001`, 62
annotations) and intended to make a second operator — or the same operator six months later —
produce compatible data.

> **Why this document exists.** Confidence, gap detection, blueprint classification, and hypothesis
> generation are all deterministic functions of the fields chosen here. Two operators who classify
> the same sentence differently produce two different Knowledge Libraries from identical evidence.
> These are not stylistic preferences; they are the inputs to the engine.

---

## 1. The two inviolable rules

### Rule 1 — `exactExcerpt` is verbatim, always

An excerpt must be a literal substring of its segment's text. `register_annotation()` rejects
anything else, so this rule is machine-enforced rather than trusted. Never "clean up" a quote:
keep the filler, the repetition, the ASR mangling (`fiveminut`, `for value gap`, `breakup
structure`). Those artifacts are evidence of transcription quality and feed the
`ambiguous_evidence` review queue.

If a statement spans a section boundary, quote from **one** section only, or re-cut the section
boundary before extraction. Never stitch two sections into one excerpt.

### Rule 2 — `proposedClaim` restates; it never adds

A claim may compress, de-duplicate, and resolve pronouns. It may **not** introduce a threshold,
instrument, timeframe, condition, or causal link the excerpt does not contain.

| Excerpt | Acceptable claim | **Unacceptable** claim | Why |
|---|---|---|---|
| *"the first thing that I'm looking for is a liquidity sweep"* | "Step 1 of the setup is to identify a liquidity sweep." | "A liquidity sweep within the first 30 minutes of the session is required." | Adds a time window |
| *"You can put your stop loss underneath this low."* | "Stops are placed beyond the swing extreme the entry is taken against." | "Stops are placed 2 points beyond the swing low." | Invents a buffer |
| *"we don't need every single one of these"* | "Only one confirmation confluence is required; all four are not needed." | "Two or more confluences improve reliability." | Invents a claim about reliability |

**The generalization test.** A claim may generalize across the examples the source itself gives
(*"underneath this low"* + *"above these highs"* → "beyond the swing extreme"). It may **not**
generalize beyond them. If you find yourself reasoning "he'd obviously also do X", stop — that is
an `EvidenceQuestion`, not a claim.

**When the source is genuinely ambiguous**, record the ambiguity rather than resolving it. The
TJR intake transcribed a profit figure as `$1,47,984`; the claim says *"transcribed as $1,47,984
(figure as transcribed; the digit grouping is malformed and the true value is unverified)"* and
`extractionCertainty` is `ambiguous`. Guessing `$147,984` would have been invention.

---

## 2. Choosing `claimType`

`claimType` determines which blueprint section a claim lands in, which knowledge gaps fire, and
whether the claim is ever rule-candidate-eligible. Choose by **function in the strategy**, not by
grammatical form.

| claimType | Use when the statement… | Rule-eligible |
|---|---|---|
| `setup_requirement` | must be true before a setup exists at all | ✅ |
| `entry_rule` | triggers the actual entry | ✅ |
| `confirmation_rule` | is a gate between setup and entry | ✅ |
| `invalidation_rule` | says when the setup is dead | ✅ |
| `stop_rule` / `target_rule` | places a stop / a target | ✅ |
| `trade_management_rule` | governs the position after entry | ✅ |
| `risk_rule` | sizes the position or caps loss | ✅ |
| `session_rule` / `timeframe_rule` | restricts when/on what chart | ✅ |
| `failure_condition` | describes what goes wrong if a rule is skipped | ✅ |
| `exception` | carves out a case from another rule | ✅ |
| `definition` | defines a term (what *is* a break of structure) | ❌ |
| `marketCondition` | describes a market state | ❌ |
| `causal_hypothesis` | explains *why* something works | ❌ |
| `performance_hypothesis` | asserts a result, P&L, or win rate | ❌ |
| `behavioral_observation` | records what the trader does/did, not a rule | ❌ |
| `success_condition` | describes what a good outcome looks like | ❌ |
| `other` | genuinely none of the above | ❌ |

### The four classification traps

**Trap 1 — Rationale is not a rule.** *"we know that when we go into these new sessions… there's
going to be some form of manipulation"* explains why the strategy expects a sweep. It is
`causal_hypothesis`, not `setup_requirement`. Typing rationale as a rule inflates the rule count
and, worse, makes an untested belief rule-candidate-eligible.

**Trap 2 — Performance claims are never rules.** Every P&L figure, win rate, average win/loss, and
risk-reward outcome is `performance_hypothesis`. This is the single most important separation in
the whole system: it is what stops a marketing number becoming a trading rule. Six of TJR's 47
claims are performance claims, and none is rule-eligible.

**Trap 3 — Observed behavior is not a stated rule.** *"I've been kind of avoiding trading this
week"* is `behavioral_observation`. It becomes a `no_trade` rule only if the trader states it as a
rule. Recording it as a rule would invent a policy from a mood.

**Trap 4 — A `definition` that contains a threshold is still a definition.** *"a candlestick
closure underneath the 79% extension"* defines the confluence; it does not instruct you to trade.
The rule that *uses* it is separate.

### The `exception` caveat (known defect)

`build_strategy_blueprint()` currently routes **every** `exception` claim into
`entryLogic.forbiddenConditions`, including exceptions that *permit* something. Use `exception`
anyway — it is the correct type — and expect the blueprint to mislabel permissive ones until
defect **D2** is fixed (see `proposals/BACKLOG-003-pipeline-hardening.md`). Do not work around this
by mistyping the claim.

---

## 3. Choosing `directness`

`directness` answers: **how directly did the source establish this?** It is not a quality judgment.

| Value | Use when |
|---|---|
| `direct_explicit` | The trader states it in words |
| `direct_demonstrated` | The trader shows it happening on a chart/trade without stating it as a rule |
| `indirect_implied` | The behavior is visible but framed as reasoning, not instruction |
| `inferred_from_context` | You concluded it; the source did not say or show it |
| `derived_from_analysis` | Produced by analysis of other evidence, not from the source |
| `owner_observation` | The repository owner's own observation |
| `unresolved` | Cannot be determined |

**The line that matters most is `indirect_implied` vs `direct_explicit`.** A statement made while
narrating a chart ("*if this high has already been pushed past and we haven't gotten much of a
reaction, it's not necessarily going to be beneficial… to be considering it as a level*") reads
like a rule but is delivered as reasoning. That is `indirect_implied`. Only 3 of 62 TJR items were
`indirect_implied` or `inferred_from_context`; if your ratio is much higher, you are probably
inferring rather than extracting.

`directness` drives `TraderProfile` concept status: `direct_*` → `confirmed`, anything else →
`inferred`. It also determines whether a `stop_rule` triggers the `missing_stop_placement`
question.

---

## 4. Choosing `extractionCertainty`

**How confident are you that you read the source correctly?** Never a judgment about whether the
trader is right.

| Value | Use when |
|---|---|
| `certain` | Unambiguous, cleanly transcribed, no interpretation needed |
| `high` | Clear, minor ASR noise that does not change meaning |
| `moderate` | Meaning clear but phrasing loose, or context needed to disambiguate |
| `low` | You believe you understood it but would not defend the reading |
| `ambiguous` | The text genuinely supports more than one reading, or a figure is garbled |
| `unresolved` | Cannot be determined |

`ambiguous` and `low` route the item into review queues, which is the point — use them. TJR's
garbled `124.27` risk-reward is `ambiguous`; that is a correct, useful outcome, not a failure.

---

## 5. Choosing `evidenceQuality`

**How strong is this item as support for the claim, on its own?** This feeds confidence scoring
directly (`unknown` 0.25 / `low` 0.4 / `medium` 0.7 / `high` 1.0).

| Value | Use when |
|---|---|
| `high` | Explicit, unambiguous, central to the strategy, stated as a rule |
| `medium` | Clear but incidental, example-specific, or a supporting restatement |
| `low` | Passing mention, opinion, promotional framing, or an unverifiable assertion |
| `unknown` | Genuinely cannot assess |

**All performance claims are `low`** regardless of how clearly stated — they are unverifiable from
a transcript by construction. TJR states his own figures are inexact because fees are not
subtracted; that is a reason to record the claim, and a reason it can never be `high`.

> **Known engine limitation (defect D5).** At one independence group, quality barely affects the
> score: a single `low` opinion and a single `high` explicit statement both land at 22.0 points.
> Set the field honestly anyway — it will matter as soon as a second source exists, and correcting
> a mis-set field retroactively across hundreds of items is far more expensive than setting it now.

---

## 5b. The seven-category rule classification (derived, not stored)

The MOGO charter names seven classifications every extracted rule must carry: **Explicit,
Implicit, Inferred, Opinion, Speculative, Unsupported, Unknown.**

These are **already fully determined** by fields you set — they span `directness`, `evidenceType`,
and the claim's computed `confidenceState`. They are a *view*, and are derived as follows:

| Charter class | Derivation |
|---|---|
| **Explicit** | `directness ∈ {direct_explicit, direct_demonstrated}` **and** `evidenceType ∈ {explicit_statement, rule_statement, demonstrated_behavior, trade_example, chart_example}` |
| **Implicit** | `directness = indirect_implied` |
| **Inferred** | `directness ∈ {inferred_from_context, derived_from_analysis}` |
| **Opinion** | `evidenceType ∈ {opinion, intuition}` |
| **Speculative** | `evidenceType ∈ {prediction, performance_hypothesis-backed}` or `claimType ∈ {causal_hypothesis, performance_hypothesis}` |
| **Unsupported** | `confidenceState ∈ {insufficient_evidence, tentative}` — a property of the *claim*, not of any single item |
| **Unknown** | `directness = unresolved` or `extractionCertainty ∈ {ambiguous, unresolved}` |

**Do not add a separate classification field.** Two independently-writable representations of the
same fact drift, and a stored classification could silently contradict the evidence it summarizes —
exactly the failure mode the `exactExcerpt`/`normalizedClaim` separation exists to prevent. Set the
three underlying fields honestly and the classification follows.

Note that **Unsupported is not a property of an excerpt.** It describes a claim whose evidence is
too thin — which is why it is computed, never annotated. A perfectly explicit statement can back an
unsupported claim if it is the only evidence there is. On the current TJR library that would be all
47 claims were they at `insufficient_evidence`; they sit one step above, at `emerging`.

## 6. Scope fields

| Field | Set it when | Effect |
|---|---|---|
| `traderId` | Always | Scopes the claim; omitting it triggers an `unclear_scope` question |
| `timeframe` | The rule names a chart timeframe | Populates blueprint `executionTimeframes` / `confirmationTimeframes` |
| `session` | The rule names a session | Populates blueprint `sessions` |
| `symbol` | The item names an instrument | Populates blueprint `scope.instruments` |
| `marketCondition` | The rule is conditional on market state | Populates preferred/avoided conditions |

**Only set a scope field the source actually establishes.** A missing timeframe generates a
`missing_timeframe` question, which is the correct outcome — inventing `5m` to silence the question
defeats the purpose.

**Scope is part of the claim fingerprint.** The same sentence at `5m` and at `1m` are two distinct
claims, deliberately. Do not "simplify" by dropping scope to merge them.

**Caution on `timeframe`:** any claim carrying a timeframe that is *not* a `confirmation_rule` and
whose text lacks "higher"/"htf" lands in `executionTimeframes`. An `invalidation_rule` at `5m`
therefore appears as an execution timeframe. Accept it; do not distort the claim text to game the
bucketing.

---

## 7. One claim, many evidence items

To attach corroborating evidence to an existing claim, set `existingClaimId` and
`relationshipType` instead of a new `proposedClaim`.

| relationshipType | Use when |
|---|---|
| `supports` | The item backs the claim |
| `exemplifies` | The item is a worked example of the claim |
| `contradicts` | The item conflicts with the claim |
| `weakens` | The item undermines without contradicting |
| `contextualizes` / `qualifies` | The item bounds the claim's applicability |
| `unresolved` | Relationship genuinely unclear |

**Same-source corroboration is discounted to 25% by design.** Adding five excerpts from one
transcript to one claim does not make it well-supported, and should not be attempted for that
purpose. Add them because they are genuinely distinct evidence, not to move a number.

**Do not use `contradicts` to represent a trader's exception.** An exception is a separate
`exception` claim plus a `ContradictionRecord` between the two claims. Linking contradicting
evidence directly to a claim drives it to `contested` and destroys the distinction between "the
trader contradicted himself" and "the evidence is disputed".

---

## 8. When to create a `ContradictionRecord`

Create one when **two claims** genuinely conflict — not when a single claim is merely uncertain.

- ✅ Step 3 stated as required, versus a worked example that enters without it (`CONDITIONAL_SCOPE`,
  `material`).
- ✅ A closed set defined ("only equilibrium and FVG"), then extended under a branch
  (`DEFINITIONAL`, `minor`).
- ❌ A claim with weak evidence — that is a confidence outcome, not a contradiction.
- ❌ Two claims at different scopes saying different things — scope is part of the claim; they do
  not conflict.

Severity: `blocking` (cannot proceed) > `material` (changes what a rule would be) > `minor`
(definitional untidiness) > `cosmetic`. **An open contradiction blocks rule candidacy for every
claim it touches** — so severity is a real gate, not a label.

---

## 9. When to author an `EvidenceQuestion`

The pipeline auto-detects structural questions (missing timeframe, missing invalidation, low
support). Author one manually when you observe something the detector structurally cannot:

- An **absence** with no claim to attach to ("no risk rule appears anywhere") — pass `claimId: None`.
- A **conflict with repository state** (the filename says forex; the source says indices).
- A **transcription defect** making a figure unrecoverable.
- An **undefined term the trader relies on** ("our special little number").
- A **stated-but-unspecified variation** ("the ordering can be variable when 2B activates").

Attach `claimId` whenever the question is genuinely *about* a claim — this creates the
`RAISES_QUESTION` edge and makes the question visible in the trader's profile. Questions about
absences cannot be attached, and are consequently under-counted in `TraderProfile` (defect **D4**).

---

## 10. Sectioning standards

Sections are the addressing scheme for every excerpt, so cut them for **traceability**, not
narrative elegance.

1. Cut on topic change, not on time.
2. Never split a sentence you intend to quote; move the boundary instead.
3. Cover every source line exactly once — assert this, never assume it.
4. Record `startsMidSentence` where wrapping forces it; do not hide it.
5. Aim for 500–4,000 characters. Larger sections make excerpts hard to locate; smaller ones prevent
   quoting complete thoughts.
6. Assign `segmentType` honestly — `promotion` for sales content. TJR's 7,000-character promotional
   section produced zero claims, which is useful calibration for future prioritization.

---

## 11. What "done" looks like for one transcript

- Every rule-like statement in the source is either extracted or consciously skipped.
- Every extracted item quotes verbatim and restates without adding.
- Every unknown you noticed is an `EvidenceQuestion`, not a silently-resolved assumption.
- Every genuine self-contradiction is a `ContradictionRecord`.
- Promotional and results content produced `performance_hypothesis`/`behavioral_observation`
  claims at most — never rules.
- `validate_evidence.py` reports zero findings.

**Coverage expectation.** The TJR intake produced 62 annotations / 47 claims from 397 lines
(~51 minutes). A dense instructional transcript should yield roughly one claim per 8–10 source
lines. Far fewer suggests under-extraction; far more suggests you are splitting one rule across
many claims, which fragments evidence and depresses confidence for every fragment.
