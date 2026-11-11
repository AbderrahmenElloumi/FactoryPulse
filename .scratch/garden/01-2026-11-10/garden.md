---
garden: 01
started: 2026-11-10
status: closed
---

# Garden 01 (started 2026-11-10)

Backfilled at triage from the message of `e29fc95` and the maintainer's record
of the questions. The first garden run, made before this record format
existed.

## Scope

`.scratch/design.md`, `.scratch/factorypulse/spec.md`,
`.scratch/repo-release/spec.md`, `CONTEXT.md`, every file under
`docs/agents/gotchas/`, checked against the code and closed tickets 06-13.

## Decisions

Questions D1-D4 as the gardener asked them, with the maintainer's answers.

- **D1.** "design.md lags the closed tickets. Stale items: (1) lake interface
  still lists `table_exists(name: bool)` and `read_table(name)`; ticket 12
  decided no `table_exists`, added `root=None` and `LakeColumnsMissing`. (2) §5
  ticket mapping wrong: merge_into_delta + weekly mart shipped in 11 (not 06),
  lake.py in 12 (not 07), conftest/macro/unit not-null in 13; nits sweep is
  14, not 13. (3) Dead refs: `spec.md:93/94`, `schema.yml:69-73`,
  `assert_close.sql` (real: `floats_match.sql`). (4) 'currently/previously'
  story sentences, done items in §4 Deletions, and §7 'Left to ticket time'
  (all now settled in code). (5) DAG tasks call scripts/lake.sh, dbt.sh,
  quality.sh (which wrap `docker compose run`). How far should the gardener
  go?" Answer: **Apply all (Recommended).**
  Triage note (2026-11-10): item (4) did not say that the cut markers were
  what kept target design apart from present state. Review P1 follows from
  it; see D6.
- **D2.** "repo-release spec.md: 'internal notes file that is already
  ignored' points at `.scratch/factorypulse/gotchas.md`, which no longer
  exists (gotchas now tracked in docs/agents/gotchas/). It also lists glossary
  and ADR as under `.scratch/`, but they live at CONTEXT.md and docs/adr/.
  'Replaces former spec1.md' is story. Change spec?" Answer: **Fix all three
  (Recommended).**
  Triage note (2026-11-10): dropping the exclusion also made the gotchas
  public; see D5.
- **D3.** "delta.md entry 'CREATE TABLE IF NOT EXISTS ... without a column
  list creates a table with no columns': merge_into_delta now always passes
  the column list, a code comment explains why, and
  `test_merge_into_delta_creates_a_new_table_with_the_source_columns` pins it.
  Triage 3edea3d kept it before ticket 08 split the silent-column-drop into
  its own entry. Delete it now?" Answer: **Delete (Recommended).**
- **D4.** "factorypulse spec.md: Deployment service list lacks
  `airflow-init`, `airflow-dag-processor`, `anomaly-detection` (all in
  compose.yaml). The 'Rebuild note (2026-10-13)' is story; 06-08 are now
  closed. Change spec?" Answer: **Add services, cut note (Recommended).**

Decisions taken at triage, 2026-11-10:

- **D5.** The public release includes `docs/agents/`, the gotcha files
  included. `.scratch/repo-release/spec.md` now says so.
- **D6.** `.scratch/design.md` is working material from the
  `codebase-design` step: input to `to-spec` and `to-tickets`, not a living
  document. It is retired in two passes:
  1. Each design decision in it that still holds and is found nowhere else
     moves into the matching spec's Implementation Decisions or Testing
     Decisions (`.scratch/factorypulse/spec.md`, or
     `.scratch/repo-release/spec.md` for the release seam). Each move is a
     spec change: ask first, and record the question as a new `D` entry. The
     spec's header pointer to `design.md` changes with it.
  2. `design.md` gets a frozen header: "Working material from
     `codebase-design`, 2026-10-13. Its decisions now live in the specs and
     tickets. Not maintained." Gardens skip it from then on.

  This replaces the triage plan of earlier on 2026-11-10 (strip the
  build-status sections and keep `design.md` up to date).
- **D7.** Review P6 is settled at triage: ticket 09's note now names ticket 12,
  and its `## Current state` lists the design gaps it closes.

The fix round (`REGARDEN:`) applies D6. Findings it settles:

- P1: the frozen header marks `design.md` as not maintained, so nothing in
  it reads as present fact.
- P2, P4 with S2, P5, S3, S4, S5: findings about text in `design.md`, which
  is no longer maintained. A decision that moves into a spec is written
  correctly there (P2: the Spark job classifies through `classify` and
  spells no threshold; P4: the quality coverage rule, not a list).
- P3: fix the `dbt.md` gotcha condition, as the review says.
- S1: the subject of `e29fc95` cannot change; `## Changes` is the accurate
  account.

Questions D8-D10 as the gardener asked them in the fix round (D6 pass 1),
with the maintainer's answers. Every other decision in `design.md` that still
holds already has an owner: the two specs, ADR 0001, a closed ticket's
`## Current state`, ticket 09's `## Current state`, or a code comment.

- **D8.** "Garden 01 / D6 pass 1. The header of
  .scratch/factorypulse/spec.md says that module shapes, seams and error modes
  \"are decided in ../design.md\". design.md becomes frozen working material
  that nobody maintains. Edit: cut that sentence and keep the pointer to
  repo-release/spec.md. Effect for readers: the spec and the tickets become the
  only place where module decisions are found. design.md is still in the tree,
  but no spec points to it. Change the header?" Options: **Cut the sentence
  (Recommended)**: no spec points at design.md; its decisions are already in
  the spec, ADR 0001 and the tickets' Current state. **Keep it, marked
  frozen**: rewrite it as "Module design was worked out in ../design.md, frozen
  working material; its decisions live in this spec and the tickets." Answer:
  **Keep it, marked frozen.**
- **D9.** "Garden 01 / D6 pass 1. design.md §6 has one test decision that has
  no owner except the tests: \"DAGs parse cleanly and expose the expected task
  graph\". The factorypulse spec's Testing Decisions cover every other stage
  but say nothing about orchestration. Edit: add to the spec's Testing
  Decisions \"**Orchestration:** both DAG files load without errors and expose
  the expected task chain; these tests run where Airflow is installed.\" Effect
  for readers: the spec names an orchestration test surface. This text is
  already built (test_dagbag_exposes_the_task_chain), so it adds no new work.
  Add it?" Options: **Add it (Recommended)**: Testing Decisions get an
  Orchestration bullet; it is the only design.md decision with no owner except
  the tests. **Leave it to the tests**: tests/test_airflow_dag.py is the only
  record; the spec stays as it is. Answer: **Add it (Recommended).**
- **D10.** "Garden 01 / D6 pass 1. The garden record mentions two decisions
  that review findings P2 and P4 point to. P2: anomaly_core owns the
  thresholds, and the Spark job classifies through `classify` without spelling
  any threshold. P4: mart quality checks assert what dbt cannot guarantee by
  construction. Closed tickets 08 and 07 already keep both decisions in their
  \"Decisions later tickets depend on\" lists. Edit option: also write both into
  the factorypulse spec's Anomaly detection and Data quality decisions. Effect
  for readers: the spec states the decisions directly, and each one then exists
  in two places. Move them?" Options: **Leave in tickets 07/08
  (Recommended)**: each fact stays in one place; closed tickets keep the
  decisions later tickets depend on. **Move both into the spec**: spec Anomaly
  detection gets the threshold-owner rule, Data quality gets the mart rule;
  delete them from the tickets' Current state. Answer: **Leave in tickets 07/08
  (Recommended).**

Question D11 as the gardener asked it in the second fix round, with the
maintainer's answer.

- **D11.** "Garden 01 / review P7. The Orchestration bullet in
  .scratch/factorypulse/spec.md Testing Decisions says \"both DAG files load
  without errors\". dags/ holds one file, factorypulse_dag.py, which defines
  both DAGs (confirmed by a live DagBag parse). The D9 question introduced
  this error. Edit: replace the bullet's start. Effect for readers: an
  implementer stops looking for a second DAG file. Which wording?" Options:
  **Both DAGs load (Recommended)**: \"both DAGs load without errors and expose
  the expected task chain\"; the spec names no file count. **The DAG file
  loads**: \"the DAG file loads without errors and both DAGs expose the
  expected task chain\"; it states the one-file layout that closed ticket 06
  decided. Answer: **The DAG file loads.** Both DAGs stay in one file.

## Changes

- **G1** `docs/agents/gotchas/delta.md`: deleted the "CREATE TABLE IF NOT
  EXISTS … without a column list" entry, per D3. The README index drops
  "empty-schema tables".
- **G2** `docs/agents/gotchas/dbt.md`: `--indirect-selection cautious` scoped
  to a run whose selected test reads a model the run does not build. Review P3.
- **G3** `docs/agents/gotchas/windows-host.md`: rebuild command installs
  `pytest streamlit -r requirements-quality.txt`; `jsonschema` is imported
  nowhere.
- **G4** `.scratch/design.md`: `lake.py` interface matches ticket 12
  (`read_table(name, root=None)`, `LakeColumnsMissing`, no `table_exists`).
- **G5** `.scratch/design.md`: `quality/` interface gains `root`, `runner`,
  per-check evidence and the `--stage` CLI. Review P4 and S2 settled by D6
  (G17); the coverage rule stays in closed ticket 07, per D10.
- **G6** `.scratch/design.md`: scheduling runs `scripts/lake.sh`, `dbt.sh` and
  `quality.sh`.
- **G7** `.scratch/design.md`: dead references replaced (`floats_match.sql`
  for `assert_close.sql`; spec and `schema.yml` line references).
- **G8** `.scratch/design.md`: "currently"/"previously" sentences and the
  "(new)" markers cut; done items removed from §4. Review P1 settled by D6:
  the frozen header (G17) marks `design.md` as not maintained.
- **G9** `.scratch/design.md`: §5 ticket mapping corrected. Review P5 settled
  by D6 (G17).
- **G10** `.scratch/design.md`: §7 "Left to ticket time" deleted; every item is
  settled in code.
- **G11** `.scratch/design.md`: compose service list adds `airflow-init`,
  `airflow-dag-processor`, `anomaly-detection`. Review S5 settled by D6 (G17):
  the spec's Deployment list is the one maintained copy.
- **G12** `.scratch/factorypulse/spec.md`: Deployment list adds
  `anomaly-detection`, `airflow-init`, `airflow-dag-processor`, per D4.
- **G13** `.scratch/factorypulse/spec.md`: rebuild note deleted, per D4.
- **G14** `.scratch/repo-release/spec.md`: glossary and ADRs listed where they
  live (`CONTEXT.md`, `docs/adr/`), per D2.
- **G15** `.scratch/repo-release/spec.md`: the "internal notes file" exclusion
  dropped, per D2. D5 makes the inclusion explicit.
- **G16** `.scratch/repo-release/spec.md`: "replaces `spec1.md`" note deleted,
  per D2.
- **G17** `.scratch/design.md`: frozen header, per D6 step 2. Review P2, S3
  and S4 settled by it; the threshold rule stays in closed ticket 08, per D10.
- **G18** `.scratch/factorypulse/spec.md`: header pointer to `design.md` marks
  it frozen working material whose decisions live in the spec and tickets, per
  D8.
- **G19** `.scratch/factorypulse/spec.md`: Testing Decisions gain an
  Orchestration bullet (the DAG file loads, both DAGs expose the expected task
  chain), added from `design.md` §6, per D9. The wording follows D11. Review
  P7.
- **G20** `docs/agents/gotchas/dbt.md`: the `--indirect-selection cautious`
  rule is its own entry, detected by
  `test_weekly_dbt_step_builds_only_the_weekly_grain`. The README index names
  it. Review S8.
- `CONTEXT.md`: every term checked against the code; unchanged.

## Log

2026-11-10 · garden · e29fc95 · G1-G16 · -
2026-11-10 · review · 104c62c · block (P1) · .scratch/garden/01-2026-11-10/review.md
2026-11-10 · triage · - · record backfilled; D5, D6, D7 decided; P6 settled · .scratch/garden/01-2026-11-10/review.md
2026-11-10 · triage · - · renamed to garden 01; D6 replaced: retire design.md · .scratch/garden/01-2026-11-10/review.md
2026-11-10 · regarden · - · fixed P3; P1, P2, P4, P5, S2-S5 settled by D6 (G17); D8-D10 asked · .scratch/garden/01-2026-11-10/review.md
2026-11-10 · rereview · - · block (P7) · fixed P3; settled P1, P2, P4-P6, S1-S5 · .scratch/garden/01-2026-11-10/review.md
2026-11-10 · regarden · - · fixed P7 (D11), S6, S7, S8 · .scratch/garden/01-2026-11-10/review.md
2026-11-10 · rereview · - · pass; S9 open (minor, triage) · fixed P7, S6, S7, S8 · .scratch/garden/01-2026-11-10/review.md
2026-11-10 · triage · - · fixed S9 · .scratch/garden/01-2026-11-10/review.md
