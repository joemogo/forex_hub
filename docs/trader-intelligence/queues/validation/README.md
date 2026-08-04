# validation/

Claims awaiting the corroboration that would move them past `emerging`.

Per `DECISION|MOGO|20260727|003`, confidence rises only through independent corroboration, replay
validation, paper trading, or historical testing. This queue tracks which claims are waiting on
which of those, so "what would it take to validate this?" is answerable per claim rather than as a
general statement.

Each entry names the claim, its current confidence, the validation route required, and the specific
blocker. Entries are resolved by evidence arriving through the normal pipeline — **never by editing
a confidence value.**
