# completed/

Transcripts whose ingestion applied cleanly: evidence registered, graph rebuilt, integrity clean.

The file here is the **working copy**. The immutable provenance copy lives at
`../../imports/{trader}/raw/{file}.raw.txt` with its `.sha256` sidecar, and that is the one the
`IntakeManifest.contentHash` chain refers to. Deleting a file here loses nothing; deleting the raw
archive breaks provenance.

Every file here should have a matching `IntakeManifest` at `intakeStatus: review_required` or
`approved`, and a manifest in `../manifests/`.
