# rejected/

Transcripts that were not ingested, each with a sibling `{file}.rejected.txt` recording **why** and
**when**.

Typical reasons: duplicate of an already-registered source (content hash match); unparseable or
corrupt; wrong material (not trading content); superseded by a better copy.

**Rejections are kept, not deleted.** A rejected file is evidence that a source was considered — it
prevents the same dead end being re-investigated, and a rejection can be reversed later by moving
the file back to `pending/`.
