# Intake Queue

The front door for transcript ingestion. A transcript moves through four states, each a real
directory, so queue position is visible from the filesystem alone — no separate status database to
drift out of sync.

```
pending/     -> you drop a file here
processing/  -> ingest.py moves it here while a run is in flight
completed/   -> moved here after the run is applied and validated
rejected/    -> moved here with a .rejected.txt reason file
manifests/   -> one <slug>.ingest.json per transcript (the reviewable extraction record)
```

**Drop new transcripts in `pending/`.** Everything else is moved by `ingest.py`; move files by hand
only to recover from an interrupted run.

A file in `processing/` with no active run means an ingestion was interrupted. Re-run
`ingest.py --resume <file>` or move it back to `pending/`.

See [`../OPERATOR-PLAYBOOK.md`](../OPERATOR-PLAYBOOK.md).
