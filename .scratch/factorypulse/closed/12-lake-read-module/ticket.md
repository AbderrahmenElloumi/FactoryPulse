# 12: Lake read module

**What to build:** reading any lake table from Python through one module that owns the endpoint and the credentials. A caller asking for a table that has not been built gets a named error it can act on, never an empty result it cannot tell apart from a table with no rows.

**Blocked by:** None (can start immediately).

Status: `closed`

- [x] Reading a named table returns its declared columns in their declared order.
- [x] A table that has not been built raises a named, catchable error rather than returning an empty result.
- [x] Credentials and the endpoint are read from the environment in one place, and the difference between a container reaching storage by service name and a host process reaching it on localhost is handled there rather than at every call site.
- [x] A local Delta directory works as the source, so the behaviour is testable without object storage running.
- [x] Importing the module does not require the Delta reader to be installed, because the Spark image runs an older interpreter that does not have it.

## Current state

Decisions later tickets depend on:

- Non-Spark code reads a lake table through `factorypulse.lake.read_table(name, root=None)` and nowhere else. The quality checks and the dashboard are its consumers.
- Declared columns live in `analytics.TABLE_COLUMNS`, the existing registry, so no second module names tables. A name with no entry raises `ValueError` before any read, so a typo is never reported as "not built".
- `LakeTableMissing` (a `LookupError` carrying the table name and its location) is raised only for the reader's `TableNotFoundError`: an absent path, or a directory without `_delta_log`. Every other failure propagates, including credential, bucket and network errors (`OSError`) and a built table the reader cannot read (a plain `DeltaError`).
- `root` defaults to the object-store lake from the environment. A local directory passed as `root` gets no storage options, so tests need no MinIO.
- Inside a container (`/.dockerenv` exists) the endpoint is used as given. A host process rewrites only the compose service name `minio` to `localhost`, keeps the port and any other host, and defaults to `localhost:9000`.
- `table_exists` from the design sketch is not built: `LakeTableMissing` answers the same question.

Known gaps owned elsewhere:

- The dashboard does not use this module yet: `dashboard.delta_table_exists` always returns `True`, `dashboard.read_delta_table` turns every failure into an empty frame, and `tests/test_streamlit_dashboard.py::test_delta_table_exists` asserts the first. Ticket 09 replaces both with `lake.read_table` and handles `LakeTableMissing`.
- An unreachable MinIO takes about 28 s (10 retries) before `OSError`. Whether the dashboard needs a shorter timeout is open, no ticket.

## Log

2026-10-13 · triage · 11bccc7 · created · -
2026-11-07 · impl · 15acab1 · `lake.read_table`, `LakeTableMissing`, `analytics.TABLE_COLUMNS`; host 162 passed, 2 skipped · -
2026-11-07 · review · 40204ee · block (2 major: other read failures untested, `TABLE_COLUMNS` not locked to the dbt models) · .scratch/factorypulse/closed/12-lake-read-module/review.md
2026-11-07 · fix · 4e0c271 · fixed both majors, the port carry-over and the gotchas layout; host 163 passed, 2 skipped · .scratch/factorypulse/closed/12-lake-read-module/review.md
2026-11-07 · rereview · 776099f · block (major: a plain `DeltaError` from a built table untested) · .scratch/factorypulse/closed/12-lake-read-module/review.md
2026-11-07 · fix · 3343083 · fixed the `DeltaError` major, the leftover-key and `monkeypatch` minors; host 165 passed, 2 skipped · .scratch/factorypulse/closed/12-lake-read-module/review.md
2026-11-07 · rereview · 6a52dd1 · pass; minors left open · .scratch/factorypulse/closed/12-lake-read-module/review.md
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · -
