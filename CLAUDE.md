# MOGO Trading OS — working agreement

MOGO is a single-file browser application (`index.html`) running **PAPER (simulated)
trading only**, plus a Python research corpus under `scripts/trader_intelligence/` and
`docs/trader-intelligence/`. A live PAPER instance runs continuously in the operator's
Chrome and is the sole source of forward evidence.

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
