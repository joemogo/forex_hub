# replay/

One JSON record per replay candidate: claims under test, instruments, timeframes, setup
precondition, required confirmations, entry, exit, stop, risk, invalidation, expected behaviour,
success and failure criteria, priority, blockers.

**`UNKNOWN — not in source` is a required, first-class value.** A candidate whose `risk` is unknown
cannot produce a P&L result — only occurrence, frequency, sequence, and excursion results. Filling
that field with a plausible default converts a knowledge gap into a fabricated backtest.

Every completed run must produce a `replay_result` EvidenceItem, with the run registered as its own
EvidenceSource (inputs hashed) so replay evidence forms a **distinct independence group** from
transcript evidence. That is what makes replay a genuine route past the `emerging` ceiling.

**Gate:** extraction-pipeline review + an OwnerDecision with `replayAuthorization: true` + market
data. None of the three currently holds.
