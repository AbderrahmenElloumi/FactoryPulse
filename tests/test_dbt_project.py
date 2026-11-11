"""Lock the dbt analytics layer (ticket 05) on the host.

dbt needs a JVM and a Spark session, so the models themselves only ever run
in their container (``scripts/dbt.sh``). What these tests lock is everything
that run depends on: the model set and the lake location each model writes
to, the schema.yml assertions (their accepted values come from the event
contract, never from a second copy), the dbt vars shared with
``factorypulse.analytics``, and the fixture seed — every row of which must
satisfy the same contract validator the ingestion boundary uses.

Text assertions on the SQL/YAML are deliberate: the artifacts are the
deliverable (they are what dbt reads), and PyYAML is not a host dependency.
They are written as canonical snippets built from the contract constants, so
they fail loudly when a model, a path, or an accepted value drifts.
"""

import csv
import re
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import jinja2
import pytest

from factorypulse import analytics
from factorypulse.contract import ALLOWED_UNITS, EVENT_FIELDS, SENSOR_TYPES, STATUSES
from factorypulse.validator import validate_event
from spark.common import lake_paths

REPO = Path(__file__).resolve().parents[1]
DBT = REPO / "dbt"
MODEL_DIR = DBT / "models" / "marts"
SEED_DIR = DBT / "seeds"
DBT_TEST_DIR = DBT / "tests"

RAW_FIXTURE = SEED_DIR / "raw_sensor_events_fixture.csv"
EXPECTED_FIXTURE = SEED_DIR / "expected_mrt_machine_hourly.csv"
EXPECTED_WEEKLY_FIXTURE = SEED_DIR / "expected_mrt_machine_weekly.csv"


def _readings_fixture_rows():
    """The fixture events, with ``value`` parsed the way Spark's JSON reader
    would parse it (a real number, not the CSV's text)."""
    with RAW_FIXTURE.open(newline="", encoding="utf-8") as handle:
        return [
            dict(row, value=float(row["value"])) for row in csv.DictReader(handle)
        ]


def _iso_week_start(ts):
    """The Monday of the ISO week a fixture timestamp falls into."""
    day = date.fromisoformat(ts[:10])
    return day - timedelta(days=day.weekday())


# --- the model set ---------------------------------------------------------


def test_every_analytics_model_has_a_sql_file():
    for model in analytics.ANALYTICS_MODELS:
        assert (MODEL_DIR / f"{model}.sql").is_file(), f"missing model {model}"


def test_models_are_pure_sql_queries_and_nothing_else():
    # "Models are pure SQL": every model is a query in a .sql file, and no
    # Python model sneaks in as a second, differently-tested code path.
    assert list(MODEL_DIR.glob("*.py")) == []
    for model in analytics.ANALYTICS_MODELS:
        text = (MODEL_DIR / f"{model}.sql").read_text(encoding="utf-8")
        assert re.search(r"^\s*select\b", text, re.IGNORECASE | re.MULTILINE)


def test_models_materialize_as_delta_tables_under_the_lake_root():
    # Each model materializes as a Delta table under the lake root. dbt-spark's
    # `location_root` config appends the model identifier itself, so the table
    # lands at <lake_root>/<model> — one directory per table, never a shared
    # dir (Delta tables must not nest).
    for model in analytics.ANALYTICS_MODELS:
        text = (MODEL_DIR / f"{model}.sql").read_text(encoding="utf-8")
        assert "file_format='delta'" in text
        assert "location_root=lake_root" in text
        # No hardcoded path anywhere: the bucket is spelled once, in the var
        # default that factorypulse.analytics also owns.
        assert text.count("'s3a://'") == 1


def test_models_take_their_lake_root_from_the_shared_dbt_var():
    # The path is never hardcoded: dbt reads the same var name as
    # factorypulse.analytics.LAKE_ROOT_VAR, defaulting to the pipeline bucket.
    for model in analytics.ANALYTICS_MODELS:
        text = (MODEL_DIR / f"{model}.sql").read_text(encoding="utf-8")
        assert f"var('{analytics.LAKE_ROOT_VAR}'" in text
        assert "env_var('MINIO_BUCKET', 'factorypulse')" in text


def test_fct_model_reads_the_raw_lake_table_ingestion_writes(env):
    text = (MODEL_DIR / f"{analytics.FCT_SENSOR_READINGS_CLEAN}.sql").read_text(encoding="utf-8")
    # Default raw path is <lake_root>/raw_sensor_events — the same table
    # spark.common's lake_paths() points ingestion at.
    assert f"var('{analytics.RAW_EVENTS_VAR}'" in text
    assert f"lake_root ~ '/{analytics.RAW_EVENTS_TABLE}'" in text


def test_fct_model_switches_to_the_fixture_seed_in_fixture_mode():
    # The fixture run must not touch the lake: the target name is the only
    # switch, so nothing in the model body has to change between the two runs.
    text = (MODEL_DIR / f"{analytics.FCT_SENSOR_READINGS_CLEAN}.sql").read_text(encoding="utf-8")
    assert "target.name == 'fixture'" in text
    assert "ref('raw_sensor_events_fixture')" in text


# --- paths -----------------------------------------------------------------


def test_model_sql_column_lists_match_the_column_contracts():
    # The lake read module reads through TABLE_COLUMNS, so this lock reads it
    # too: a registered model with no declared columns fails here, not later as
    # a ValueError from lake.read_table.
    missing = set(analytics.ANALYTICS_MODELS) - set(analytics.TABLE_COLUMNS)
    assert not missing, f"registered models with no declared columns: {sorted(missing)}"
    # And the other way: a key for a removed or misspelled table is not a table.
    known = set(analytics.REGISTERED_TABLES) | {analytics.RAW_EVENTS_TABLE}
    leftover = set(analytics.TABLE_COLUMNS) - known
    assert not leftover, f"declared columns for unregistered tables: {sorted(leftover)}"
    for model in analytics.ANALYTICS_MODELS:
        text = (MODEL_DIR / f"{model}.sql").read_text(encoding="utf-8")
        for column in analytics.TABLE_COLUMNS[model]:
            assert column in text, f"{model}.sql is missing column {column}"


def test_analytics_paths_live_in_the_raw_lake_bucket(env):
    raw = lake_paths(env)["raw"]
    bucket_root = raw.rsplit("/", 1)[0]  # s3a://factorypulse/delta
    for model in analytics.ANALYTICS_MODELS:
        assert analytics.analytics_path(env, model) == f"{bucket_root}/{model}"


def test_raw_events_path_reuses_the_spark_lake_path(env):
    # Both stages must agree on where the raw events are: ingestion writes
    # spark.common's path, the dbt models read analytics' path.
    assert analytics.raw_events_path(env) == lake_paths(env)["raw"]


def test_analytics_path_rejects_unknown_models(env):
    with pytest.raises(ValueError):
        analytics.analytics_path(env, "fct_sensor_readings")


def test_analytics_path_resolves_the_spark_written_anomaly_table(env):
    assert analytics.analytics_path(env, analytics.MRT_ANOMALY_SCORES) == (
        f"{analytics.lake_root(env)}/{analytics.MRT_ANOMALY_SCORES}"
    )


# --- the fixture seed ------------------------------------------------------


def test_fixture_seed_header_matches_the_event_contract():
    with RAW_FIXTURE.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == list(EVENT_FIELDS)


def test_fixture_seed_rows_are_contract_conforming():
    # The fixture is only meaningful if it is the same shape as the raw lake;
    # it is validated with the shared validator, not a bespoke check.
    for row in _readings_fixture_rows():
        assert validate_event(row) == [], f"fixture row {row['event_id']} is off-contract"


def test_fixture_seed_repeats_an_event_id_to_exercise_deduplication():
    rows = _readings_fixture_rows()
    event_ids = [row["event_id"] for row in rows]
    assert len(set(event_ids)) < len(event_ids)


def test_fixture_seed_spans_more_than_one_machine_hour_and_site():
    rows = _readings_fixture_rows()
    assert len({(row["machine_id"], row["ts"][:13]) for row in rows}) >= 4
    assert len({row["site_id"] for row in rows}) == 2


def test_expected_hourly_fixture_header_is_the_model_column_contract():
    with EXPECTED_FIXTURE.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == list(analytics.MACHINE_HOURLY_COLUMNS)


def test_expected_hourly_fixture_covers_every_machine_hour_of_the_seed():
    # The dbt fixture assertion compares model output to this seed with a
    # FULL OUTER JOIN, so a missing expected row is reported as a fixture
    # failure rather than silently passing.
    with EXPECTED_FIXTURE.open(newline="", encoding="utf-8") as handle:
        keys = {row["machine_hour_key"] for row in csv.DictReader(handle)}
    expected_keys = {
        # ts[:13] is "YYYY-MM-DDTHH"; the model's key spells the hour with a space.
        f"{row['machine_id']}@{row['ts'][:13].replace('T', ' ')}:00:00"
        for row in _readings_fixture_rows()
    }
    assert keys == expected_keys


# --- the weekly mart -------------------------------------------------------


def test_weekly_mart_is_registered_with_its_iso_week_columns():
    assert analytics.MRT_MACHINE_WEEKLY in analytics.ANALYTICS_MODELS
    assert analytics.MACHINE_WEEKLY_COLUMNS[0] == "machine_week_key"
    for column in ("machine_id", "site_id", "iso_year", "iso_week", "week_start"):
        assert column in analytics.MACHINE_WEEKLY_COLUMNS


def test_weekly_mart_rolls_up_from_the_hourly_mart():
    text = (MODEL_DIR / f"{analytics.MRT_MACHINE_WEEKLY}.sql").read_text(encoding="utf-8")
    assert f"ref('{analytics.MRT_MACHINE_HOURLY}')" in text
    assert "date_trunc('week', hour_start)" in text
    assert "year(date_add(week_start, 3)) as iso_year" in text
    assert "weekofyear(week_start)" in text
    assert "group by machine_id, week_start" in text
    assert "sum(reading_count)" in text
    assert "sum(critical_count)" in text


def test_weekly_mart_key_is_deterministic():
    # A stable surrogate key plus table materialization means a re-run replaces
    # the same machine-week rows instead of adding a second copy.
    text = (MODEL_DIR / f"{analytics.MRT_MACHINE_WEEKLY}.sql").read_text(encoding="utf-8")
    assert "concat(machine_id, '@', date_format(week_start" in text
    assert "materialized='table'" in text
    assert "file_format='delta'" in text
    assert "insert into" not in text.lower()
    assert "merge into" not in text.lower()


# The `weekly` tag in a model's config(), in either quote style and with any
# spacing, alone or among other tags: dbt reads every one of these the same way.
WEEKLY_TAG = re.compile(r"""\btags\s*=\s*\[[^\]]*['"]weekly['"][^\]]*\]""")


@pytest.mark.parametrize(
    "config",
    ["tags=['weekly']", 'tags=["weekly"]', "tags = [ 'weekly' ]", "tags=['mart', \"weekly\"]"],
)
def test_the_weekly_tag_is_found_in_every_spelling_dbt_accepts(config):
    assert WEEKLY_TAG.search(f"{{{{ config(materialized='table', {config}) }}}}")


@pytest.mark.parametrize("config", ["tags=['daily']", "tags=['weekly_report']", "alias='weekly'"])
def test_a_model_without_the_weekly_tag_is_not_weekly(config):
    assert not WEEKLY_TAG.search(f"{{{{ config(materialized='table', {config}) }}}}")


def test_the_weekly_grain_is_the_models_tagged_weekly():
    # The weekly DAG builds `tag:weekly` and the daily DAG excludes it, so the
    # tag decides which DAG advances a model. The registry names the same set.
    tagged = tuple(
        model
        for model in analytics.ANALYTICS_MODELS
        if WEEKLY_TAG.search((MODEL_DIR / f"{model}.sql").read_text(encoding="utf-8"))
    )
    assert tagged == analytics.WEEKLY_MODELS == (analytics.MRT_MACHINE_WEEKLY,)
    assert analytics.DAILY_MODELS == tuple(
        model for model in analytics.ANALYTICS_MODELS if model not in analytics.WEEKLY_MODELS
    )


def test_weekly_mart_reads_the_hourly_mart_from_its_lake_path():
    # Each dbt run starts from an empty session catalog, so a weekly-only run
    # cannot resolve `ref()` to a table it did not build. Reading the hourly
    # mart by its lake location lets the weekly DAG build the weekly mart
    # alone; `ref()` inside the path keeps the dbt lineage.
    text = (MODEL_DIR / f"{analytics.MRT_MACHINE_WEEKLY}.sql").read_text(encoding="utf-8")
    assert (
        f"from delta.`{{{{ lake_root }}}}/{{{{ ref('{analytics.MRT_MACHINE_HOURLY}').identifier }}}}`"
        in text
    )


def test_expected_weekly_fixture_header_is_the_model_column_contract():
    with EXPECTED_WEEKLY_FIXTURE.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle)) == list(analytics.MACHINE_WEEKLY_COLUMNS)


def test_expected_weekly_fixture_covers_every_machine_week_of_the_seed():
    with EXPECTED_WEEKLY_FIXTURE.open(newline="", encoding="utf-8") as handle:
        keys = {row["machine_week_key"] for row in csv.DictReader(handle)}
    expected_keys = {
        f"{row['machine_id']}@{_iso_week_start(row['ts']).isoformat()}"
        for row in _readings_fixture_rows()
    }
    assert keys == expected_keys


def test_weekly_fixture_assertion_compares_the_model_to_the_expected_seed():
    assertions = sorted(DBT_TEST_DIR.glob("*.sql"))
    text = "\n".join(path.read_text(encoding="utf-8") for path in assertions)
    assert f"ref('{analytics.MRT_MACHINE_WEEKLY}')" in text
    assert "ref('expected_mrt_machine_weekly')" in text
    assert "full outer join" in text.lower()
    assert "target.name == 'fixture'" in text


# --- dbt tests (schema.yml + the fixture assertion) ------------------------


def _declared_tests(text):
    """Read ``(model, column, test)`` triples out of schema.yml by indentation.

    A real YAML parser would be a host dependency for one file; the layout is
    fixed by dbt convention (models at indent 2, columns at 6, tests at 10), so
    a small scanner is enough — and if the layout drifts it finds nothing and
    the assertions below fail loudly.
    """
    triples = set()
    model = column = None
    for line in text.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped.startswith("- name:") and indent == 2:
            model, column = stripped.split(":", 1)[1].strip(), None
        elif stripped.startswith("- name:") and indent == 6:
            column = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- ") and indent == 10 and model and column:
            triples.add((model, column, stripped[2:].strip().rstrip(":")))
    return triples


def test_schema_yml_declares_a_primary_key_per_model():
    declared = _declared_tests((MODEL_DIR / "schema.yml").read_text(encoding="utf-8"))
    assert ("dim_machine", "machine_id", "unique") in declared
    assert ("fct_sensor_readings_clean", "event_id", "unique") in declared
    assert ("mrt_machine_hourly", "machine_hour_key", "unique") in declared
    assert ("mrt_machine_weekly", "machine_week_key", "unique") in declared


def test_schema_yml_asserts_not_null_on_every_model():
    declared = _declared_tests((MODEL_DIR / "schema.yml").read_text(encoding="utf-8"))
    for model in analytics.ANALYTICS_MODELS:
        columns = {column for (m, column, test) in declared if m == model and test == "not_null"}
        assert columns, f"{model} declares no not_null test"


def test_every_event_contract_column_of_the_clean_fact_asserts_not_null():
    # The ingestion boundary rejects a null in any contract field, so every
    # contract column of the clean fact carries not_null. accepted_values alone
    # is not enough: dbt's accepted_values passes NULL.
    declared = _declared_tests((MODEL_DIR / "schema.yml").read_text(encoding="utf-8"))
    asserted = {
        column
        for (model, column, test) in declared
        if model == analytics.FCT_SENSOR_READINGS_CLEAN and test == "not_null"
    }
    missing = set(analytics.FCT_READING_COLUMNS) - asserted
    assert not missing, f"contract columns without not_null: {sorted(missing)}"


def test_clean_fact_filters_no_null_the_schema_asserts_against():
    # One opinion on nulls, not two. Both ingestion paths write only rows the
    # contract validator accepted, and it rejects a null in every field, so a
    # null in the raw lake means the boundary broke. The model lets such a row
    # through and the not_null tests above fail the build on it; a WHERE
    # filter on the same column would drop the row silently and leave its
    # not_null test unable to fail.
    text = (MODEL_DIR / f"{analytics.FCT_SENSOR_READINGS_CLEAN}.sql").read_text(encoding="utf-8")
    sql = "\n".join(line.split("--")[0] for line in text.splitlines())
    filtered = re.findall(r"(\w+)\s+is\s+not\s+null", sql, re.IGNORECASE)
    assert filtered == [], f"null filters that hide a not_null failure: {filtered}"


def test_schema_yml_asserts_accepted_values_on_the_contract_enums():
    text = (MODEL_DIR / "schema.yml").read_text(encoding="utf-8")
    declared = _declared_tests(text)
    assert ("fct_sensor_readings_clean", "sensor_type", "accepted_values") in declared
    assert ("fct_sensor_readings_clean", "status", "accepted_values") in declared
    assert ("fct_sensor_readings_clean", "unit", "accepted_values") in declared
    # The accepted lists are the contract's enums, spelled once, canonically.
    assert "values: [" + ", ".join(SENSOR_TYPES) + "]" in text
    assert "values: [" + ", ".join(STATUSES) + "]" in text
    assert "values: [" + ", ".join(sorted(ALLOWED_UNITS)) + "]" in text


def test_schema_yml_relates_the_marts_to_the_machine_dimension():
    text = (MODEL_DIR / "schema.yml").read_text(encoding="utf-8")
    declared = _declared_tests(text)
    assert any(test == "relationships" for (_, _, test) in declared)
    assert f"to: ref('{analytics.DIM_MACHINE}')" in text
    assert "field: machine_id" in text


def test_hourly_fixture_assertion_compares_the_model_to_the_expected_seed():
    assertions = sorted(DBT_TEST_DIR.glob("*.sql"))
    assert assertions, "the fixture-based hourly assertion is missing"
    text = "\n".join(path.read_text(encoding="utf-8") for path in assertions)
    assert f"ref('{analytics.MRT_MACHINE_HOURLY}')" in text
    assert "ref('expected_mrt_machine_hourly')" in text
    assert "full outer join" in text.lower()
    # Only meaningful against the fixture: the real lake has real numbers.
    assert "target.name == 'fixture'" in text


FIXTURE_ASSERTIONS = {
    "assert_mrt_machine_hourly_matches_expected_fixture.sql": analytics.MACHINE_HOURLY_COLUMNS,
    "assert_mrt_machine_weekly_matches_expected_fixture.sql": analytics.MACHINE_WEEKLY_COLUMNS,
}


def _floats_match_reports(actual, expected):
    """Say whether ``floats_match`` reports one actual/expected row pair.

    The macro is plain Jinja, so it is rendered here and run on sqlite in the
    same ``where not (...)`` shape the fixture assertions use. Like dbt, only
    the ``{% macro %}`` block is loaded; the header comment around it is never
    rendered. ``coalesce``, ``abs`` and three-valued ``and``/``or``/``not``
    behave the same in sqlite and Spark SQL, so a condition that drops a row
    here drops it in the dbt build too.
    """
    text = (DBT / "macros" / "floats_match.sql").read_text(encoding="utf-8")
    block = re.search(r"{% macro floats_match\(.*?{%- endmacro %}", text, re.DOTALL)
    assert block, "floats_match.sql defines no floats_match macro"
    condition = str(jinja2.Environment().from_string(block.group(0)).module.floats_match(list(actual)))
    side = "select " + ", ".join(f"? as {column}" for column in actual)
    query = f"select 1 from ({side}) as actual, ({side}) as expected where not ({condition})"
    with closing(sqlite3.connect(":memory:")) as db:
        return bool(db.execute(query, [*actual.values(), *expected.values()]).fetchall())


@pytest.mark.parametrize(
    ("actual", "expected", "reported"),
    [
        (1.0, 1.0, False),
        (1.0, 1.00005, False),  # rounding, within the 0.0001 default tolerance
        (1.0, 1.001, True),  # drift beyond the tolerance
        (None, None, False),  # no reading for the sensor on either side
        (None, 1.0, True),  # the mart dropped a statistic the seed expects
        (1.0, None, True),  # the mart invented a statistic the seed lacks
    ],
)
def test_floats_match_reports_drift_and_one_sided_null(actual, expected, reported):
    # A one-sided null must be reported: without the coalesce the condition
    # is null, and `where not (null)` drops the row instead of reporting it.
    assert _floats_match_reports({"v": actual}, {"v": expected}) is reported


def test_floats_match_requires_every_column_to_match():
    # The per-column conditions are joined with `and`: a mismatch in any one
    # column, here the last, reports the row.
    assert _floats_match_reports({"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 2.0}) is False
    assert _floats_match_reports({"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 3.0}) is True
    assert _floats_match_reports({"a": 1.0, "b": 2.0}, {"a": 1.0, "b": None}) is True


def test_fixture_assertions_compare_every_sensor_statistic_through_the_macro():
    for name, columns in FIXTURE_ASSERTIONS.items():
        text = (DBT_TEST_DIR / name).read_text(encoding="utf-8")
        # The comparison is spelled once, in the macro; no inline copy remains.
        assert "abs(" not in text, f"{name} still compares floats inline"
        call = re.search(r"floats_match\(\s*\[([^\]]*)\]", text)
        assert call, f"{name} does not call floats_match"
        compared = re.findall(r"'(\w+)'", call.group(1))
        # Every float statistic in the mart's column contract is compared, so a
        # new sensor statistic cannot slip past the fixture unchecked.
        statistics = [c for c in columns if c.endswith(("_avg", "_max"))]
        assert compared == statistics, f"{name} compares {compared}"


def test_singular_assertions_exist_only_for_fixture_runs():
    for path in DBT_TEST_DIR.glob("*.sql"):
        text = path.read_text(encoding="utf-8")
        assert "target.name == 'fixture'" in text, f"{path.name} runs against the real lake"


# --- dbt project + profile -------------------------------------------------


def test_dbt_project_declares_the_project_and_delta_materialization():
    text = (DBT / "dbt_project.yml").read_text(encoding="utf-8")
    assert "name: factorypulse" in text
    assert "profile: factorypulse" in text
    assert "+materialized: table" in text
    assert "+file_format: delta" in text


def test_profiles_define_lake_and_fixture_session_targets():
    text = (DBT / "profiles.yml").read_text(encoding="utf-8")
    assert "lake:" in text and "fixture:" in text
    # Counted on live values only: the comments explain `method: session`.
    values = [line.split("#")[0].strip() for line in text.splitlines()]
    assert values.count("method: session") == 2, values
    # The fixture target is offline: it must not reach MinIO.
    assert "s3a://" not in text


def test_dbt_project_uses_the_default_model_seed_and_test_paths():
    text = (DBT / "dbt_project.yml").read_text(encoding="utf-8")
    assert 'model-paths: ["models"]' in text
    assert 'seed-paths: ["seeds"]' in text
    assert 'test-paths: ["tests"]' in text


def test_query_job_reads_the_analytics_paths_shared_module():
    # "Output tables are queryable the same way as the raw lake": the
    # verification job goes through the same path helper as every other stage.
    text = (REPO / "spark" / "query_analytics.py").read_text(encoding="utf-8")
    assert "from factorypulse.analytics import" in text
    assert "ANALYTICS_MODELS" in text
    assert "analytics_path" in text
