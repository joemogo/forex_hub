# processing/

A transcript lives here while an ingestion run is in flight. `ingest.py` moves it in at the start
of the automatic phase and out when the run is applied or rejected.

**A file sitting here with no run in progress means an interrupted ingestion.** The intake manifest
will be at a non-terminal `intakeStatus`. Either re-run `ingest.py --resume`, or roll back with
`ingest.py --rollback <intakeId>` and move the file back to `pending/`.

Nothing should ever be moved *into* this directory by hand.
