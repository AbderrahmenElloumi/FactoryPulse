---
garden: 03
started: 2026-11-13
status: closed
---

# Garden 03 (started 2026-11-13)

## Scope

- Gotchas: `docs/agents/gotchas/README.md`, `airflow.md`, `dbt.md`,
  `delta.md`, `docker.md`, `spark.md`, `windows-host.md`.
- Specs: `.scratch/factorypulse/spec.md` and `.scratch/repo-release/spec.md`.
  Neither feature has an open ticket, so every spec/code gap has no owner.
- `CONTEXT.md`.
- ADRs: `docs/adr/0001-event-contract-as-single-seam.md`.
- Checked against the code, the tests, and the tickets closed since garden 02:
  repo-release 03, 04, 05. Since garden 02, the code outside `.scratch/`
  changed only in `scripts/release.sh`, `scripts/import-contribution.sh`,
  `README.md`, `.github/CONTRIBUTING.md`, `.env.example` and their tests.
- Open minor findings of garden 02's review read: S1 is in a gotcha and is
  fixed here (G3); P2 is a spec gap, asked as D2; P3 and P4 are about garden
  02's own record, which is closed.
- Skipped: `.scratch/design.md`, frozen working material.

## Decisions

Questions D1-D3 as the gardener asked them, with the maintainer's answers.
Each option is given as its label, then its description.

- **D1.** "Q1. .scratch/repo-release/spec.md, Implementation Decisions, The
  release script, lists the preflight checks as: clean working tree, on main,
  suite green, version equal to package metadata, a changelog heading. The
  script also refuses a release tree that lacks a required path or holds an
  excluded one, a compose.yaml that embeds a credential (closed ticket 03) or
  interpolates a variable .env.example does not declare, a missing public
  remote, and a tag already on public. The credential check reads compose's
  own parse, so a release needs the docker CLI with its compose plugin (no
  running daemon). No open ticket owns this gap. Story 7 asks that a future
  session can follow the release step from the spec; today the spec does not
  say that a release needs the docker CLI. Edit: the list becomes \"clean
  working tree, on main, test suite green, package metadata version equal to
  the argument, a changelog heading for that version, a release tree with
  every required path and no excluded one, a compose.yaml that embeds no
  credential and interpolates only variables .env.example declares, a public
  remote that does not hold the tag yet\", followed by the sentence \"The
  compose checks read compose's own parse, so a release needs the docker CLI
  with its compose plugin, not a running daemon.\" Effect for readers: the
  spec names every refusal a release can hit and the one tool it needs.
  Which?" Options: **Name every check (Recommended)**: The full list above,
  plus the docker CLI sentence. The spec matches the script; a new preflight
  check then needs a spec edit. **Compose checks only**: Add only "a
  compose.yaml that embeds no credential and interpolates only variables
  .env.example declares" and the docker CLI sentence. The path, remote and
  tag checks stay unnamed; the list still reads as complete. **Keep as is**:
  No change. The spec does not mention the credential guard or the docker CLI
  need; closed ticket 03 holds both. Answer: **Name every check
  (Recommended).**
- **D2.** "Q2. .scratch/factorypulse/spec.md, Implementation Decisions, Data
  quality, says: \"Coverage is table-level (row count, required columns) and
  column-level (range, null %, allowed status values, unit-to-sensor
  agreement).\" Garden 02's review (P2) left this gap to triage, and no open
  ticket owns it. The code also checks that event_id is unique, that every
  fact event_id is in the raw table, that each machine reports from one site,
  and that dim_machine and both marts agree with the fact table (same machine
  set, reading_count sums to its row count). Its missingness check is \"never
  null\", not a percentage bound. Edit: \"Coverage is table-level (row count,
  agreement with the table a model is built from) and column-level (required
  columns never null, value ranges, allowed values, unique event_id,
  unit-to-sensor and machine-to-site agreement).\" Effect for readers: the
  spec, which owns the coverage list (the CONTEXT.md Quality Check entry
  gives only examples), names every kind of check the code runs; a new kind
  needs a spec edit. Which?" Options: **Complete the list (Recommended)**: The
  edit above. Spec and code agree; "null %" becomes "never null", as the code
  checks. **Make it examples**: "Coverage includes table-level checks such as
  row count and column-level checks such as value ranges and allowed values."
  Never stale, but no longer says what is covered. **Keep as is**: No change.
  The list stays incomplete and P2 of garden 02's review stays with triage.
  Answer: **Complete the list (Recommended).**
- **D3.** "Q3. .scratch/factorypulse/spec.md, Implementation Decisions, Data
  quality, now says (G2, per D2): \"Coverage is table-level (row count,
  agreement with the table a model is built from) and column-level (required
  columns never null, value ranges, allowed values, unique event_id,
  unit-to-sensor and machine-to-site agreement).\" Garden 03's review finds
  two errors. P1: mrt_machine_weekly is built from the hourly mart, but its
  checks compare it with the fact, so \"the table a model is built from\"
  states a check the code does not run. P2: the old \"required columns\"
  stood for the schema check; the new list drops it, yet the code fails a
  table that is not built or lacks a declared column, and story 18 asks for
  schema validation. Edit: \"Coverage is table-level (the table is built and
  stores every declared column, row count, the fact agrees with the raw lake,
  and dim_machine and both marts agree with the fact) and column-level
  (required columns never null, value ranges, allowed values, unique
  event_id, unit-to-sensor and machine-to-site agreement).\" Effect for
  readers: the spec states only checks the code runs, names the schema check
  again, and says the weekly mart is checked against the fact, not the hourly
  mart it is built from. Which?" Options: **Correct the list (Recommended)**:
  The edit above. Fixes P1 and P2; the list stays complete, so a new kind of
  check still needs a spec edit. **Make it examples**: "Coverage includes
  table-level checks such as schema and row count, and column-level checks
  such as value ranges and allowed values." Never stale, but no longer says
  what is covered; reverses D2. **Revert to the old text**: Restore
  "table-level (row count, required columns) and column-level (range, null %,
  allowed status values, unit-to-sensor agreement)". Schema check named
  again, but the list is incomplete and says "null %", which the code does
  not check. Answer: **Correct the list (Recommended).**

## Changes

- **G1** `.scratch/repo-release/spec.md`: The release script names every
  preflight check the script runs, and says that a release needs the docker
  CLI with its compose plugin, per D1.
- **G2** `.scratch/factorypulse/spec.md`: Data quality names every kind of
  check the code runs, and "null %" becomes "required columns never null",
  per D2 and D3. The table-level list names the schema check (the table is
  built and stores every declared column), the fact's agreement with the raw
  lake, and the agreement of dim_machine and both marts with the fact. This
  settles P2 of garden 02's review.
- **G3** `docs/agents/gotchas/windows-host.md`: the `.venv` rebuild entry
  points at the `pip install` line under the README's `## Tests`, the section
  that holds it. The README has no section called "virtualenv steps". This
  fixes S1 of garden 02's review.
- Checked and unchanged: every other gotcha entry and the gotcha index (the
  code they describe has not changed since garden 02). The docker entry
  "Never use `${VAR:?message}`" stands beside the release credential guard,
  which accepts that form: the guard decides what may hold a credential, the
  entry decides what compose can load. `CONTEXT.md` (Release matches the
  release script; no term changed meaning in tickets 03-05). The rest of both
  specs: the import, inbound-triage and public-tree decisions match closed
  tickets 04 and 05. `docs/adr/0001-event-contract-as-single-seam.md` is not
  edited.

## Log

2026-11-13 · garden · - · G1-G3; D1-D2 asked · -
2026-11-13 · review · - · block (P1, P2) · .scratch/garden/03-2026-11-13/review.md
2026-11-13 · regarden · - · fixed P1, P2 (G2, D3) · P3, S1, S2 left to triage · .scratch/garden/03-2026-11-13/review.md
2026-11-13 · rereview · - · pass · fixed P1, P2 · P3, P4, S1, S2, S3 (minor) left to triage · .scratch/garden/03-2026-11-13/review.md
