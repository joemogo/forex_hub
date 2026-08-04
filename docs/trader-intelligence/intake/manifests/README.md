# manifests/

One `{slug}.ingest.json` per transcript — the **reviewable record of every extraction judgment**.

`ingest.py` writes a draft during the automatic phase (provenance, normalization policy, sections,
candidate suggestions, empty `annotations`). A researcher fills in the annotations. `ingest.py
--apply` then validates every excerpt verbatim before writing anything to disk.

**This is the artifact to review.** A reviewer can read a manifest alongside the source and check
every judgment — which excerpt, which claimType, which confidence inputs. That is not meaningfully
possible against ad-hoc extraction code.

Manifests are inputs, never queried at runtime: the canonical records are the JSON under
`../../evidence/`. Schema: `../../evidence/schema/ingest-manifest.schema.json`.
