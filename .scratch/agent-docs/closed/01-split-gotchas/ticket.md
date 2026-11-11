# 01: Split and verify the gotchas

**What to build:** the single file `docs/agents/gotchas.md` becomes area files under `docs/agents/gotchas/`, with an index. Each remaining entry is a lasting trap that still holds against the code, written by the Gotchas and Writing rules sections of the implementer prompt. An agent then reads the index and only the areas its change touches.

**Blocked by:** None (can start immediately).

Status: `closed`

- [x] `docs/agents/gotchas/` holds `README.md` (the entry rule from the prompt's Gotchas section, then the index: one line per area file, saying which traps it covers) and the area files `spark.md`, `delta.md`, `dbt.md`, `docker.md`, `airflow.md`, `quality.md` and `windows-host.md`. An area with no remaining entry gets no file.
- [x] Every entry of the old file was checked against the code and the tests. Each one had exactly one outcome:
  - **kept**: rewritten as a general rule in its area file, with no ticket number and no story
  - **moved**: a true fact that is not a trap goes to its owner (the table in the prompt's Writing rules section). A design reason becomes a code comment next to the code it explains, and a decision goes to the ticket's `## Current state` or to `design.md`. Any code edit here is a comment only.
  - **deleted**: stale, or already reported by a test or a linter with a clear failure
- [x] Ticket-specific is not a reason to delete. A true rule found during a ticket is kept, as a general rule. Only the story around it goes.
- [x] The "Verification habit" section is deleted. Its rule now lives in the implementer prompt (Implementer, step 4).
- [x] The commit message lists each old entry with its outcome (kept to which file, moved to where, or deleted and why), so the change can be audited.
- [x] Every reference to the old file was checked. If the gotcha it points to still holds, the reference names the area file. If not, the reference is removed. The references are `dbt/profiles.yml` (the managed-table comment) and `scripts/dbt-entrypoint.sh` (the `spark.jars.packages` comment). A closed ticket or review that names the old file is left as it is, because ticket 02 condenses those.
- [x] `docs/agents/gotchas.md` is deleted.
- [x] `AGENTS.md` points to `docs/agents/gotchas/README.md` only, with no mention of the old file.

## Current state

- The `.gitignore` line for `.scratch/factorypulse/gotchas.md` stays: it ignores a legacy local path and does not point a reader at the old file.

## Log

2026-11-09 · triage · - · created from the doc-hygiene grilling session · -
2026-11-09 · impl · f6a800c · gotchas split into 6 area files and an index; host 358 passed, 19 skipped · -
2026-11-09 · review · 93c322d · block (S1) · .scratch/agent-docs/closed/01-split-gotchas/review.md
2026-11-09 · fix · bb0a7b3 · fixed S1, S2, S3, S4; P1, P2 open · .scratch/agent-docs/closed/01-split-gotchas/review.md
2026-11-09 · review · 8e7ccdd · block (S1, S5, P3) · fixed S2, S3, S4 · .scratch/agent-docs/closed/01-split-gotchas/review.md
2026-11-09 · fix · 261830a · fixed S1, S5, P3; P1, P2 open for triage; host 358 passed, 19 skipped · .scratch/agent-docs/closed/01-split-gotchas/review.md
2026-11-09 · rereview · - · pass · fixed S1, S5, P3 · P1, P2 open, no ticket · .scratch/agent-docs/closed/01-split-gotchas/review.md
