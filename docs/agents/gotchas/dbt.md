# dbt gotchas

- **Every word of `DBT_ARGS` must be one shell word.** The dbt service's
  compose `command:` passes `$$DBT_ARGS` unquoted, so the shell splits it.
  Spell `--vars` as JSON (`--vars {"lake_root":"/tmp/fp-fixture"}`), never as
  YAML with spaces. Detect: `Error: Invalid value for '--vars': String
  '{lake_root:' is not valid YAML`.
- **Every dbt run starts from an empty session catalog.** A model built alone
  cannot `ref()` a table the run did not build, and `dbt test` alone finds no
  tables. Read the other table from its lake path. Detect:
  `test_weekly_mart_reads_the_hourly_mart_from_its_lake_path`.
- **Add `--indirect-selection cautious` when a selected test reads a model
  the run does not build.** dbt's default (`eager`) selects every test of a
  selected model, so that test reads a table missing from the session
  catalog. Detect: `test_weekly_dbt_step_builds_only_the_weekly_grain`.
- **A `session` seed cannot hold a NULL string.** dbt-spark binds every seed
  value as `'{value}'`, so an empty CSV cell becomes the text `'None'`. A
  `double` column casts it to NULL; a `string` column keeps `'None'`, which
  passes `not_null`. Detect: `Failure in test accepted_values_` on a column
  whose `not_null` test passes.
- **Render a dbt macro on the host from its `{% macro %}` block only.** dbt
  never renders the text around a macro; plain `jinja2` renders the whole
  file, so a header comment that calls the macro fails first. `jinja2` is not
  a declared dependency: it arrives through `streamlit`. Detect:
  `UndefinedError: 'floats_match' is undefined`.
- **A text lock on a SQL macro does not prove its NULL branches.** A rewrite
  can keep every locked substring and still turn a one-sided NULL into NULL,
  which `where not (...)` drops. Run the rendered SQL on sqlite with edge
  rows. Detect: `test_floats_match_reports_drift_and_one_sided_null`.
