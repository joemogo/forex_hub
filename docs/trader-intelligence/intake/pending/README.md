# pending/

**Drop transcripts here.** Any plain-text, timestamped-text, or structured-JSON transcript.

Naming: `{trader-slug}-{topic-slug}.txt` — e.g. `ict-2022-mentorship-ep01.txt`. The slug becomes
the manifest name, so keep it stable and descriptive.

Then run:

```bash
python3 scripts/trader_intelligence/ingest.py docs/trader-intelligence/intake/pending/<file> --trader <TRADER_ID>
```

`--trader` must match `^[A-Z][A-Z0-9_]*$` and have a record under `../../traders/{id}/profile.json`.
Registered today: `TJR`, `ICT`, `ALEX_G`, `JVM`.

Files here are **not** yet evidence — nothing in `pending/` is registered, hashed into the graph, or
citable.
