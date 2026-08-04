# Work Queues

Machine-readable queues for work that follows extraction. Distinct from the 14 **review** queues
under `../evidence/review-queue/`, which are generated from evidence state — these hold work items
with their own lifecycle.

```
replay/      -> replay candidates awaiting execution
validation/  -> claims awaiting corroboration or empirical validation
```

Both are currently **specification-only**: no replay has been authorized
(`replayAuthorization: false` on every OwnerDecision) and MOGO holds no ES/NQ market data. The
queues exist so candidates accumulate in a structured form rather than in prose.

Narrative specifications: [`../proposals/REPLAY-CANDIDATES.md`](../proposals/REPLAY-CANDIDATES.md).
