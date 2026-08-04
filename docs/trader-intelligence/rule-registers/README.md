# Rule Registers

One register per ingested source, recording every extracted rule against the full evaluation
schedule: exact rule · source timestamp · explicit/implied/inferred · objective/discretionary ·
required variables · missing definitions · potential algorithmic representation · replay-test
feasibility · supporting sources · contradicting sources · confidence.

**These are analysis artifacts, not the evidence store.** The canonical records are the JSON under
`../evidence/`. A register is the human-readable bridge between a claim and a replay specification —
it is where "is this rule actually formalizable?" gets answered explicitly rather than assumed.

A register may conclude that a rule is **not** formalizable. That is a result, not a failure: see
`ALEX_G-advanced-market-structure.md` §C3 on the snake trick.

| Register | Source | Rules |
|---|---|---|
| [ALEX_G — Advanced Market Structure](ALEX_G-advanced-market-structure.md) | `EVSRC\|ALEX_G\|20260728\|001` | 18 across A–F |
