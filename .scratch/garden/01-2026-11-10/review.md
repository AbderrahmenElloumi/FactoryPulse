---
garden: .scratch/garden/01-2026-11-10/garden.md
verdict: pass
---

# Review: garden 01, fix round e7d8bb4

Range: `e06d548..e7d8bb4`, one `REGARDEN:` commit. Docs only; no source,
config or test changes.

Spec source: the garden record's `## Decisions`, D1-D11. The spec axis checks
each `G` change against the code and its decision. `.scratch/design.md` is
frozen working material (D6): only its header is in scope.

Standards source: the workflow writing rules, `docs/agents/issue-tracker.md`
§Garden record, `docs/agents/gotchas/README.md` §Entry rule.

Severity for a docs-only change: a false statement of present fact in a living
doc an implementer reads is `major`; an imprecise or duplicated statement is
`minor`.

Spec: pass. Standards: pass.

## Open findings

None.

## Coverage

Each `G` change to its evidence:

- G1 `delta.md` entry deleted: verified in the first review
  (`test_merge_into_delta_creates_a_new_table_with_the_source_columns`).
- G2, G20 `dbt.md`: the lake-path rule (`dbt.md:8-11`) and the
  `--indirect-selection cautious` rule (`dbt.md:12-15`) are two entries of 4
  lines each. Detects: `test_weekly_mart_reads_the_hourly_mart_from_its_lake_path`
  (`tests/test_dbt_project.py:267`) pins the lake path;
  `test_weekly_dbt_step_builds_only_the_weekly_grain`
  (`tests/test_airflow_dag.py:651`) pins the flag. The condition matches
  `scripts/dbt.sh:46-50`: `weekly` takes the flag, `daily` does not. The
  README index (`docs/agents/gotchas/README.md:24-26`) names both, in file
  order.
- G3 `windows-host.md` rebuild command: verified in the first review.
- G4-G11 `.scratch/design.md` edits: frozen working material, out of scope
  under D6. G8 now matches the header (`.scratch/design.md:3-4`).
- G12, G13 `factorypulse/spec.md` Deployment list and rebuild note: verified
  in the first review; the list matches `compose.yaml`. MinIO credentials are
  hardcoded in `compose.yaml`; open ticket `repo-release/01` owns the gap.
- G14-G16 `repo-release/spec.md`: verified in the first review.
- G17 `design.md` header: word for word the D6 step 2 text. The rule that
  gardens skip the file lives in `docs/agents/issue-tracker.md:90-91` and D6.
- G18 `factorypulse/spec.md` header: word for word the D8 answer.
- G19 Orchestration bullet (`.scratch/factorypulse/spec.md:114`): word for
  word the D11 answer. True about the code: `dags/` holds one file,
  `factorypulse_dag.py`, which defines both DAGs
  (`test_the_file_defines_a_daily_and_a_weekly_dag`,
  `tests/test_airflow_dag.py:123`), as closed ticket 06 decides.
  `test_dagbag_loads_both_dags_without_errors` (`:788`) and
  `test_dagbag_exposes_the_task_chain` (`:795`) pass inside
  `factorypulse/airflow:3.4.0` (3 passed). They skip on the host through
  `pytest.importorskip("airflow.models")` (`:782`), so "these tests run where
  Airflow is installed" holds. "Added from `design.md` §6" holds: the bullet
  stays at `.scratch/design.md:256`.
- D11 framing: the question states the edit, its effect for readers, and each
  option's consequence. The chosen option states the one-file layout of
  closed ticket 06; the spec gains no file path or build status.
- Host suite: `tests/test_documentation.py`, `test_airflow_dag.py`,
  `test_dbt_project.py`: 151 passed, 3 skipped.
- Allowed paths: only `.scratch/` and `docs/agents/gotchas/` change; the
  review file is untouched.
