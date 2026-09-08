# MOGO Trading OS — working agreement

MOGO is a single-file browser application (`index.html`) running **PAPER (simulated)
trading only**, plus a Python research corpus under `scripts/trader_intelligence/` and
`docs/trader-intelligence/`. A live PAPER instance runs continuously in the operator's
Chrome and is the sole source of forward evidence.

## What MOGO is for

An autonomous scientific trading laboratory running three concurrent missions:

1. **Forward PAPER operations** — observe every configured instrument, evaluate setups under
   frozen semantics, paper trade, detect the real market exit, preserve every close.
2. **Post-trade learning** — every legitimate close becomes durable evidence and is assimilated,
   compared against the corpus, and classified. Storage is not learning.
3. **External trader research** — discover, acquire and reconstruct other traders' methods well
   enough to test them.

**LIVE-money trading is prohibited.** Quiet markets are a valid result; never manufacture trades
or loosen a rule to create activity.

## Where the governance gates actually live

The hard boundaries are **enforced**, not documented: `scripts/auto_mode/mogo_rules.json`
generates the `autoMode` block in `~/.claude/settings.json` via
`scripts/auto_mode/build_auto_mode_config.py`. Live money, protected strategy semantics,
inference promotion, evidence destruction and production disturbance all require operator
approval there. **Re-run the generator after a Claude Code upgrade** — each section
replaces the shipped defaults rather than merging, so the copy goes stale otherwise.

This file holds what a permission classifier cannot enforce: how to judge evidence, and
when to stop.

## Scientific integrity

- **Evidence beats assumption.** Never fabricate what is missing. If the source material
  does not state an entry trigger, a stop placement or a risk-per-trade, that is an
  acquisition problem — record it in the queue, do not invent the rule.
- **UNKNOWN stays UNKNOWN.** Do not infer a field merely to complete a record.
- **Inference never becomes source-stated fact**, however many times it is restated.
- **Replay/historical evidence stays distinguishable from forward/live.** Population is
  derived from `EvidenceSource.sourceType`, never denormalised onto the record, and
  forward-performance statistics never silently include replay observations.
- `alex_g_sr_v1` is MOGO's *implementation*; `ALEX_G` is a *person*. Replaying the former
  measures the implementation, not whether the trader's stated rule holds. Counting one as
  evidence for the other is the easiest way to manufacture a false result here.
- A human example disagreeing with MOGO is not grounds to change a rule.
- Any forward figure carries its coverage caveat: the preserved set is a subset of the
  account's closed positions (backlog B-22).

## Researching other traders

The target is **scientifically reconstructable trading behaviour**, not popular traders.

Prioritise by **expected information value × evidence quality × reconstructability ÷ cost**.
What earns effort: real trades carrying entry, stop, target and outcome; **published before the
outcome is known**; showing losers and skipped setups as well as winners; repeated across enough
examples to reconstruct mechanically. What does not: commentary, motivational content,
hindsight-only winning screenshots, unverifiable signals, affiliate material.

- **"Said" is not "did."** A stated rule is `SOURCE_STATED`; a trade you can see is `OBSERVED`.
  Never let one become the other. A video's title is not evidence of its contents.
- Self-reported profitability, follower counts, lifestyle marketing and claimed win rates are
  **not evidence of trading success** and never enter a performance figure.
- One authoritative candidate registry (`docs/trader-intelligence/acquisition/`). Never start a
  competing list.
- Never bypass authentication, paywalls, private communities, rate limits or platform
  protections. Record the source as unavailable and move on.
- **Record negative results.** A source adequately classified as unavailable or low-value is not
  searched again without new evidence — see `NEGATIVE_ACQUISITION_LOG.md`.

## Strategy discovery, and where it stops

The intended end state is several independently derived strategies paper trading at once. The
pipeline is: trader discovery → evidence acquisition → rule reconstruction → ambiguity analysis →
mechanical specification → replay testing where scientifically valid → adversarial verification →
promotion candidate.

**Discovery is not authorisation.** Promoting any strategy into PAPER is an operator governance
boundary. A candidate arrives with a dossier — evidence, reconstructed rules, what remains
UNKNOWN, sample size, test methodology and results, failure cases, contamination checks, and the
reasons both for and against — and the operator decides.

The right thing to bring the operator is *"candidate X has earned consideration, here is the
evidence"*, never *"what should I research next?"*.

## Testing

- **A passing fixture is not evidence until breaking the mechanism makes it fail.**
  Mutation-test new gates; an exclusion test needs a positive control.
- **Never pin a corpus snapshot as an oracle.** `answered == 0`, `links == 416`,
  `balance == 9756.23` are not invariants — they are snapshots, and they break within the
  hour when the system is live. Assert the before/after relationship instead. This defect
  class has been found and fixed here repeatedly; it is the most common failure mode.
- Assert filters are non-empty, or the loop passes vacuously.
- Clear `__pycache__` before a mutation run — a same-byte-length edit restored within the
  same second leaves stale bytecode loaded and produces false survivors.
- Balances do **not** chain trade-by-trade: up to 5 positions run concurrently,
  `balanceBefore` is stamped at entry and `balanceAfter` at exit.

## Delivering a release to the operator

The sandbox git proxy refuses to push to `joemogo/forex_hub` (403, repository not in the session's
authorized set). `fetch` works. So every release reaches the operator as a **bundle** he applies
himself, and the shape of that command matters more than it looks.

**NEVER give him a force-fetch into his working branch.** The obvious command is:

```
git fetch <bundle> '+refs/heads/<branch>:refs/heads/<branch>'     # WRONG
```

The `+` is a force update. If his local branch holds commits the bundle does not — and it will, the
moment any other session, machine or person commits there — that fetch **resets the branch and
those commits survive only in the reflog**. On 2026-09-07 every deploy command in a long session
used this form. It was safe purely by luck: his branch happened to sit exactly on each bundle's
base. A second Claude session then committed five times on the same branch, and the next command
would have destroyed three commits that existed nowhere else, *then* failed at the final step —
so the operator would have seen an error, no success line, and the work already gone.

**Use a temp ref, and publish only to `mogo-main`:**

```
cd ~/Desktop/"Forex Hub" \
  && git fetch <bundle> refs/heads/<branch>:refs/temp/<release> \
  && git push origin refs/temp/<release>:mogo-main \
  && echo "=== DEPLOYED OK ==="
```

No `+`, a ref that cannot already exist, and his working branch is never touched. `mogo-main` is the
branch the live PAPER instance serves, so it is the only one a deploy needs. Pushing the working
branch was always just a backup copy, and it is the half that can destroy things.

**Before quoting any deploy command, `git fetch origin` and look at where the branch actually is.**
It is a shared branch now. A bundle whose base is no longer origin's tip is a bundle whose command
needs re-deriving, not re-sending.

## The running instance

Prefer read-only inspection, isolated testing and replay analysis. Do not restart MOGO,
reset accounts, alter positions, clear journals or manufacture trades to create activity.
Per **INC-004**, browser verification never uses the operator's profile or live origin —
read-only file copies only, and the test origin is confirmed with the operator every time.

**An operator-initiated shutdown, or the operator simply being away, is known downtime —
record it as such.** It is not an unexplained engine continuity failure, and it is not
something to repair.

Forward evidence is perishable: packages can exist only in the uncompacted WAL and are
lost to compaction within hours. Preserving promptly is the priority; `evidence/` is
gitignored by design, so **import into `docs/trader-intelligence/evidence/` IS the
preservation mechanism**.

That whole chain is one command — detect → preserve → recover → import → reconcile:

```
scripts/forward_capture.sh            # dry run: reports, writes nothing
scripts/forward_capture.sh --write    # imports any new closes
```

It is read-only with respect to the running instance, scoped to MOGO's own origin, and
fails closed: a package whose stored contentHash does not re-derive from the preserved
bytes is never written and never imported. Run it when the store may have changed; it
costs almost nothing when nothing has (it exits at the detect step).

## Prefer a diagnostic to a reconstruction

When an operational property has to be established by hand more than once, build a small reusable
diagnostic instead of reinventing the check. Existing ones:

```
scripts/forward_capture.sh                     detect -> preserve -> import -> assimilate
scripts/mogo_observation_coverage.js --store   are all configured instruments actually observed?
scripts/mogo_evidence_checkpoint.sh --selftest preservation is read-only and verified
python3 scripts/trader_intelligence/research_assimilation.py   what changed, and what did not
python3 scripts/trader_intelligence/forward_coverage.py        is a missing cohort rarity or starvation?
python3 scripts/trader_intelligence/reconstructability.py      could a strategy be rebuilt from a candidate?
python3 scripts/trader_intelligence/observation_graph_reconcile.py  do the preserved observations and the graph agree?
python3 scripts/trader_intelligence/identity_manifest.py --packages <file>  which trades have ever existed (append-only)
python3 scripts/candidate_power.py --effect E --sigma S --n N --cost C   BEFORE building anything:
                                               can the effect clear its cost, and could this sample
                                               see it if it did? Two floors. --selftest runs the
                                               project's own six arms as fixtures.
python3 scripts/replay_compare.py <package>... [--band LO HI]  the standing replay analysis: per-arm
                                               distribution with median planned R and stop size, an error
                                               bar on every figure, pairwise differences, a subgroup sweep
                                               Sidak-corrected for the number of slices EXAMINED, and spread
                                               charged per trade (never against the mean). REFUSES to mix
                                               captureBasis populations. --band restricts to a stop-size
                                               range so arms with different geometry can be compared.
```

**Cost and power the candidate BEFORE building it — `candidate_power.py`.** Six arms were built
here before anyone asked either question in advance, and two of them were answerable in an hour.
`tod_session_v1` chased a 0.58-pip effect against a 0.8-pip spread: negative before the statistics
began, and its sample could only resolve 2.02 pips regardless. `carry_g10_v1` found a **real**
3.01%/yr effect of which the broker keeps 1.09%, leaving 1.92% against a 4.13% detection floor —
105 years of data would be needed to resolve it. **A null from an underpowered test is not evidence
of absence**, and four of this project's six arms were in exactly that position.

**The standing bar this implies.** For a trade-based arm (1R stop, 2R target, sigma about 1.0R) with
a 0.05R round trip, the gross edge needed is 0.089R at 2,542 trades and 0.061R at 30,000 — and it
**stops falling there, because past ~5,000 trades the cost dominates the detection floor**. More
data cannot lower the bar below about **0.06R per trade, roughly a 2-point win-rate lift over a
coin**. Nothing tested here has come close; the best, `psych_round`, measured +0.026R. Do not build
a candidate whose plausible edge is under that bar, and where one clears it, run the replay WIDE
before concluding — n is the cheapest thing to buy, right up until cost takes over.

**Every R-denominated replay result goes through `replay_compare.py`.** The same analysis was
hand-written four times before this existed, and two of those hand runs contained errors that
changed the conclusion: spread charged against the mean rather than per trade (which hid the whole
CRT result), and a subgroup reported as significant without correcting for the 17 slices examined.
A result quoted from anything other than this script is a result nobody has checked the method of.

**The one exception is `tod_session_v1`, and it is an exception on purpose.** That arm holds a
position between two clock times: no stop, no target, therefore no risk denominator and **no R**.
Every statistic `replay_compare.py` reports is R-denominated, so running it against that arm's
evidence is meaningless rather than merely imprecise. Its packages are `evidenceKind:
SESSION_RETURN_OBSERVATIONS`, carry no `realizedR` field at all so nothing can average them against
genuine R-multiples, and state both facts in their own `disclosures`. Its analysis lives with the
arm and is gated by `tests/v166_tod_session_tests.js` (37 fixtures) and
`tests/mutate_v166_tod_session.js` (25 mutations, run against `index.html` itself).
**Never average a session return against an R-multiple.**

A diagnostic must test reality, not restate a dashboard. If reality contradicts a report, a test,
or a previous conclusion, **trust the evidence and investigate.**

Distinguish, always: *no trade because no setup* from *no trade because evaluation failed*.

## Anti-loop

- Verification must answer a **bounded material question**. No repo-wide audits, no
  re-verifying already-proven properties without new contradictory evidence, no recursive
  subagent verification, no speculative defect hunting outside the current objective.
- **P0/P1** → repair and verify when authorised. **P2/P3** → record and defer unless the
  active objective needs them. A failing count-pinning test is P2/P3 until a causal path
  shows materially wrong runtime behaviour.

## Autonomous continuation

inspect → choose the highest-value bounded objective → execute → validate proportionately
→ preserve evidence → checkpoint → choose the next objective → continue.

Do not stop merely because one task finished. Do not manufacture work to stay busy. When a
lane hits a governance boundary or a genuine external dependency, **preserve the finding
and continue the other lanes**; stop only when authorised useful work is actually
exhausted.
