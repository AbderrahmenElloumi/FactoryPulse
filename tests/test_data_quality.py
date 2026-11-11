"""Table-level quality checks (ticket 07): the quality seam and its report.

``quality.check_table`` reads one lake table through ``factorypulse.lake``,
runs its named checks, and returns a ``QualityReport`` naming every check
that failed. A local directory of Delta tables stands in for the lake, so
every behaviour here runs without MinIO.

Two runners sit behind the seam. A substitute runner tests the mapping from
check outcomes to the report without Great Expectations; the real Great
Expectations runner proves that known-bad data fails the named check and that
good data passes.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from deltalake import write_deltalake

from factorypulse import quality
from factorypulse.quality.__main__ import main
from factorypulse.quality.expectations import Outcome

RAW = "raw_sensor_events"
FCT = "fct_sensor_readings_clean"
DIM = "dim_machine"
HOURLY = "mrt_machine_hourly"
WEEKLY = "mrt_machine_weekly"

M1, S1 = "site-a-machine-01", "site-a"
M2, S2 = "site-b-machine-01", "site-b"
READINGS = [
    ("temperature", 61.5, "celsius"),
    ("vibration", 3.25, "g_pp"),
    ("pressure", 101.0, "psi"),
    ("humidity", 40.0, "percent"),
]


def _event_id(n):
    return f"00000000-0000-4000-8000-{n:012d}"


def _raw_rows():
    rows = []
    for m, (machine, site) in enumerate([(M1, S1), (M2, S2)]):
        for s, (sensor, value, unit) in enumerate(READINGS):
            rows.append(
                {
                    "event_id": _event_id(m * 10 + s),
                    "ts": f"2026-10-05T10:{m}{s}:00.000Z",
                    "site_id": site,
                    "machine_id": machine,
                    "sensor_type": sensor,
                    "value": value,
                    "unit": unit,
                    "status": "warning" if (m, s) == (1, 1) else "nominal",
                }
            )
    # A streaming replay: the same event twice, byte for byte.
    rows.append(dict(rows[0]))
    return rows


def _fct_rows():
    rows = []
    for row in _raw_rows()[:-1]:
        clean = {k: v for k, v in row.items() if k != "ts"}
        clean["event_ts"] = pd.Timestamp(row["ts"])
        rows.append(clean)
    return rows


def _dim_rows():
    return [
        {
            "machine_id": machine,
            "site_id": site,
            "first_seen_at": pd.Timestamp("2026-10-05T10:00:00Z"),
            "last_seen_at": pd.Timestamp("2026-10-05T10:13:00Z"),
            "reading_count": 4,
            "sensor_type_count": 4,
        }
        for machine, site in [(M1, S1), (M2, S2)]
    ]


def _stats():
    return {
        "temperature_avg": 61.5,
        "temperature_max": 61.5,
        "vibration_avg": 3.25,
        "vibration_max": 3.25,
        "pressure_avg": 101.0,
        "pressure_max": 101.0,
        "humidity_avg": 40.0,
        "humidity_max": 40.0,
    }


def _hourly_rows():
    return [
        {
            "machine_hour_key": f"{machine}|2026-10-05T10",
            "machine_id": machine,
            "site_id": site,
            "hour_start": pd.Timestamp("2026-10-05T10:00:00Z"),
            "reading_count": 4,
            "nominal_count": nominal,
            "warning_count": 4 - nominal,
            "critical_count": 0,
            **_stats(),
        }
        for machine, site, nominal in [(M1, S1, 4), (M2, S2, 3)]
    ]


def _weekly_rows():
    return [
        {
            "machine_week_key": f"{machine}|2026-10-05",
            "machine_id": machine,
            "site_id": site,
            "iso_year": 2026,
            "iso_week": 41,
            "week_start": pd.Timestamp("2026-10-05T00:00:00Z"),
            "reading_count": 4,
            "nominal_count": nominal,
            "warning_count": 4 - nominal,
            "critical_count": 0,
            **_stats(),
        }
        for machine, site, nominal in [(M1, S1, 4), (M2, S2, 3)]
    ]


def _good_rows():
    return {
        RAW: _raw_rows(),
        FCT: _fct_rows(),
        DIM: _dim_rows(),
        HOURLY: _hourly_rows(),
        WEEKLY: _weekly_rows(),
    }


def _write_lake(root, rows_by_table):
    for name, rows in rows_by_table.items():
        write_deltalake(str(root / name), pd.DataFrame(rows))
    return str(root)


@pytest.fixture
def good_lake(tmp_path):
    return _write_lake(tmp_path, _good_rows())


class _ScriptedRunner:
    """Substitute runner: reports every check passed except the named ones."""

    def __init__(self, failing=(), omitted=()):
        self.failing = set(failing)
        self.omitted = set(omitted)
        self.calls = []

    def __call__(self, table, frame, checks):
        self.calls.append((table, [check.name for check in checks]))
        return [
            Outcome(check.name, check.name not in self.failing, f"why {check.name}")
            for check in checks
            if check.name not in self.omitted
        ]


# --- report mapping (substitute runner, no Great Expectations) -------------


def test_report_passes_when_every_check_passes(good_lake):
    runner = _ScriptedRunner()

    report = quality.check_table(RAW, root=good_lake, runner=runner)

    assert report.table == RAW
    assert report.passed
    assert report.failed == ()
    assert runner.calls[0][0] == RAW
    assert "status is a contract status" in runner.calls[0][1]


def test_report_names_every_failed_check_in_definition_order(good_lake):
    runner = _ScriptedRunner(failing={"status is a contract status", "unit is never null"})

    report = quality.check_table(RAW, root=good_lake, runner=runner)

    assert not report.passed
    assert report.failed == ("unit is never null", "status is a contract status")
    assert report.details["status is a contract status"] == "why status is a contract status"


def test_check_the_runner_returned_no_result_for_counts_as_failed(good_lake):
    # A check that silently did not run must not read as a pass.
    runner = _ScriptedRunner(omitted={"event_id is never null"})

    report = quality.check_table(RAW, root=good_lake, runner=runner)

    assert report.failed == ("event_id is never null",)
    assert "no result" in report.details["event_id is never null"]


def test_table_that_has_not_been_built_fails_a_named_check_without_running(tmp_path):
    runner = _ScriptedRunner()

    report = quality.check_table(RAW, root=str(tmp_path), runner=runner)

    assert report.failed == ("raw_sensor_events is built",)
    assert "has not been built" in report.details["raw_sensor_events is built"]
    assert runner.calls == []


def test_table_without_a_declared_column_fails_a_named_check(tmp_path):
    rows = [{k: v for k, v in row.items() if k != "unit"} for row in _raw_rows()]
    root = _write_lake(tmp_path, {RAW: rows})

    report = quality.check_table(RAW, root=root, runner=_ScriptedRunner())

    assert report.failed == ("raw_sensor_events stores every declared column",)
    assert "unit" in report.details["raw_sensor_events stores every declared column"]


def test_table_with_no_checks_is_rejected(good_lake):
    with pytest.raises(ValueError, match="mrt_anomaly_scores"):
        quality.check_table("mrt_anomaly_scores", root=good_lake, runner=_ScriptedRunner())


def test_run_all_reports_each_table_in_the_order_given(good_lake):
    reports = quality.run_all([RAW, RAW], root=good_lake, runner=_ScriptedRunner())

    assert [report.table for report in reports] == [RAW, RAW]
    assert all(report.passed for report in reports)


def test_report_mapping_works_without_great_expectations_installed(good_lake):
    # None in sys.modules makes any import of great_expectations raise.
    probe = (
        "import sys\n"
        "sys.modules['great_expectations'] = None\n"
        "from factorypulse import quality\n"
        "from factorypulse.quality.expectations import Outcome\n"
        "runner = lambda table, frame, checks: [Outcome(c.name, True) for c in checks]\n"
        f"report = quality.check_table({RAW!r}, root={good_lake!r}, runner=runner)\n"
        "assert report.passed and report.checked > 0, report\n"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


# --- Great Expectations runner: known-bad data fails, good data passes -----

# The quality image always has it; a host venv without it still runs the
# report-mapping tests above.
needs_ge = pytest.mark.skipif(
    importlib.util.find_spec("great_expectations") is None,
    reason="great_expectations is not installed",
)


def _with(table, mutate):
    """The good lake's rows, with one table changed by ``mutate(rows)``."""
    rows = _good_rows()
    mutate(rows[table])
    return rows


def _set(index, **changes):
    def mutate(rows):
        rows[index].update(changes)

    return mutate


def _append(row_factory):
    def mutate(rows):
        rows.append(row_factory(rows))

    return mutate


@needs_ge
def test_good_raw_lake_passes_every_check(good_lake):
    report = quality.check_table(RAW, root=good_lake)

    assert report.passed, report.details
    assert report.checked >= 17


RAW_BAD = {
    "null unit": (_set(2, unit=None), "unit is never null"),
    "null machine_id": (_set(3, machine_id=None), "machine_id is never null"),
    "unknown status": (_set(1, status="degraded"), "status is a contract status"),
    "unknown sensor": (_set(1, sensor_type="torque"), "sensor_type is a contract sensor type"),
    "unknown unit": (_set(1, unit="kelvin"), "unit is a contract unit"),
    "unit of another sensor": (_set(0, unit="psi"), "unit matches its sensor_type"),
    "temperature above range": (_set(0, value=150.5), "temperature value is within -40 to 150"),
    "vibration below range": (_set(1, value=-0.1), "vibration value is within 0 to 20"),
    "pressure above range": (_set(2, value=200.01), "pressure value is within 0 to 200"),
    "humidity above range": (_set(3, value=100.5), "humidity value is within 0 to 100"),
    "machine at two sites": (
        _append(lambda rows: {**rows[0], "event_id": _event_id(99), "site_id": S2}),
        "each machine reports from one site",
    ),
}


@needs_ge
@pytest.mark.parametrize("mutate, check", RAW_BAD.values(), ids=RAW_BAD.keys())
def test_known_bad_raw_row_fails_the_named_check(tmp_path, mutate, check):
    root = _write_lake(tmp_path, _with(RAW, mutate))

    report = quality.check_table(RAW, root=root)

    assert check in report.failed, report.failed
    assert report.details[check]


@needs_ge
def test_empty_raw_lake_fails_the_row_count_check(tmp_path):
    empty = pd.DataFrame({k: pd.Series([], dtype="string") for k in _raw_rows()[0]})
    empty["value"] = empty["value"].astype("float64")
    write_deltalake(str(tmp_path / RAW), empty)

    report = quality.check_table(RAW, root=str(tmp_path))

    assert report.failed == ("has at least one row",)


@needs_ge
@pytest.mark.parametrize("table", [FCT, DIM, HOURLY, WEEKLY])
def test_good_dbt_table_passes_every_check(good_lake, table):
    report = quality.check_table(table, root=good_lake)

    assert report.passed, report.details
    assert report.checked >= 5


def _replayed(rows):
    rows.append(dict(rows[0]))


def _drop_machine(machine):
    def mutate(rows):
        rows[:] = [row for row in rows if row["machine_id"] != machine]

    return mutate


# What the dbt tests cannot catch: uniqueness and relationships asserted
# against the raw lake and the clean fact, not against a table derived from
# the one under test (ticket 05 review, findings 1 and 2).
DBT_BAD = {
    "fct duplicate event": (FCT, _replayed, "event_id is unique"),
    "fct event not in raw": (
        FCT,
        _set(0, event_id=_event_id(77)),
        "every event_id is in raw_sensor_events",
    ),
    "fct more rows than raw events": (
        FCT,
        _append(lambda rows: {**rows[0], "event_id": _event_id(0).replace("4000", "4001")}),
        "has no more rows than raw_sensor_events has events",
    ),
    "fct null unit": (FCT, _set(2, unit=None), "unit is never null"),
    "fct null event_ts": (FCT, _set(2, event_ts=None), "event_ts is never null"),
    "fct unknown status": (FCT, _set(1, status="degraded"), "status is a contract status"),
    "fct unit of another sensor": (FCT, _set(3, unit="celsius"), "unit matches its sensor_type"),
    "fct humidity above range": (FCT, _set(3, value=100.5), "humidity value is within 0 to 100"),
    "dim lost a machine": (DIM, _drop_machine(M2), "machine_id values match fct_sensor_readings_clean"),
    "dim invented a machine": (
        DIM,
        _append(lambda rows: {**rows[0], "machine_id": "site-a-machine-09"}),
        "machine_id values match fct_sensor_readings_clean",
    ),
    "dim miscounted readings": (
        DIM,
        _set(0, reading_count=5),
        "reading_count sums to the fct_sensor_readings_clean row count",
    ),
    "dim sensor_type_count beyond contract": (
        DIM,
        _set(0, sensor_type_count=5),
        "sensor_type_count is within 1 to 4",
    ),
    "dim null site_id": (DIM, _set(1, site_id=None), "site_id is never null"),
    "hourly lost a machine": (
        HOURLY,
        _drop_machine(M1),
        "machine_id values match fct_sensor_readings_clean",
    ),
    "hourly miscounted readings": (
        HOURLY,
        _set(1, reading_count=3),
        "reading_count sums to the fct_sensor_readings_clean row count",
    ),
    "hourly temperature_max above range": (
        HOURLY,
        _set(0, temperature_max=151.0),
        "temperature_max is within -40 to 150",
    ),
    "hourly null hour_start": (HOURLY, _set(0, hour_start=None), "hour_start is never null"),
    "weekly miscounted readings": (
        WEEKLY,
        _set(0, reading_count=8),
        "reading_count sums to the fct_sensor_readings_clean row count",
    ),
    "weekly vibration_avg below range": (
        WEEKLY,
        _set(1, vibration_avg=-1.0),
        "vibration_avg is within 0 to 20",
    ),
    "weekly null machine_week_key": (
        WEEKLY,
        _set(1, machine_week_key=None),
        "machine_week_key is never null",
    ),
}


@needs_ge
@pytest.mark.parametrize("table, mutate, check", DBT_BAD.values(), ids=DBT_BAD.keys())
def test_known_bad_dbt_row_fails_the_named_check(tmp_path, table, mutate, check):
    root = _write_lake(tmp_path, _with(table, mutate))

    report = quality.check_table(table, root=root)

    assert check in report.failed, report.failed
    assert report.details[check]


@needs_ge
def test_failed_value_check_quotes_the_offending_values(tmp_path):
    root = _write_lake(tmp_path, _with(RAW, _set(1, status="degraded")))

    report = quality.check_table(RAW, root=root)

    assert report.details["status is a contract status"] == "1 unexpected, e.g. ['degraded']"


@needs_ge
def test_failed_table_level_check_quotes_the_observed_value(tmp_path):
    root = _write_lake(tmp_path, _with(DIM, _set(0, reading_count=5)))

    report = quality.check_table(DIM, root=root)

    assert report.details["reading_count sums to the fct_sensor_readings_clean row count"] == "observed 9"


@needs_ge
def test_check_that_cannot_be_evaluated_fails_with_the_reason():
    from factorypulse.quality import ge_runner
    from factorypulse.quality.expectations import Check

    check = Check("pressure is never null", "ExpectColumnValuesToNotBeNull", {"column": "pressure"})

    [outcome] = ge_runner.run(RAW, pd.DataFrame({"value": [1.0]}), [check])

    assert outcome == Outcome(
        "pressure is never null",
        False,
        'could not evaluate: Error: The column "pressure" in BatchData does not exist.',
    )


def test_dbt_table_whose_reference_is_not_built_fails_a_named_check(tmp_path):
    rows = _good_rows()
    del rows[RAW]
    root = _write_lake(tmp_path, rows)

    report = quality.check_table(FCT, root=root, runner=_ScriptedRunner())

    assert report.failed == ("raw_sensor_events is built",)


def test_stages_check_the_raw_lake_then_the_daily_models_then_the_weekly_mart():
    assert quality.STAGES == {
        "ingestion": ("raw_sensor_events",),
        "post-dbt": (
            "dim_machine",
            "fct_sensor_readings_clean",
            "mrt_machine_hourly",
        ),
        "weekly": ("mrt_machine_weekly",),
    }
    assert set(quality.CHECKED_TABLES) == {RAW, FCT, DIM, HOURLY, WEEKLY}


# --- command line: the path the pipeline and a human share ------------------


def _passing(table, frame, checks):
    return [Outcome(check.name, True) for check in checks]


def _failing_status(table, frame, checks):
    return [
        Outcome(check.name, check.name != "status is a contract status", "1 unexpected, e.g. ['degraded']")
        for check in checks
    ]


def test_cli_exits_zero_and_says_pass_when_every_check_passes(good_lake, capsys, monkeypatch):
    monkeypatch.setattr(quality, "_default_runner", lambda: _passing)

    code = main(["--root", good_lake, "--stage", "ingestion"])

    out = capsys.readouterr().out
    assert code == 0
    assert "PASS raw_sensor_events" in out
    assert "fct_sensor_readings_clean" not in out


def test_cli_exits_nonzero_and_names_each_failed_check(good_lake, capsys, monkeypatch):
    monkeypatch.setattr(quality, "_default_runner", lambda: _failing_status)

    code = main(["--root", good_lake, "--tables", RAW, DIM])

    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL raw_sensor_events" in out
    assert "FAIL dim_machine" not in out
    assert "status is a contract status: 1 unexpected, e.g. ['degraded']" in out
    assert "PASS dim_machine" in out


def test_cli_without_a_selection_checks_every_stage_in_pipeline_order(good_lake, capsys, monkeypatch):
    monkeypatch.setattr(quality, "_default_runner", lambda: _passing)

    assert main(["--root", good_lake]) == 0

    lines = [line.split()[1] for line in capsys.readouterr().out.splitlines() if line.startswith("PASS")]
    assert lines == [RAW, DIM, FCT, HOURLY, WEEKLY]


def test_cli_fails_when_a_table_is_not_built(tmp_path, capsys):
    code = main(["--root", str(tmp_path), "--stage", "ingestion"])

    assert code == 1
    assert "raw_sensor_events is built" in capsys.readouterr().out


def test_cli_rejects_a_table_with_no_checks(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--tables", "mrt_anomaly_scores"])

    assert caught.value.code == 2
    assert "mrt_anomaly_scores" in capsys.readouterr().err



# --- pipeline wiring: the quality service and the drivers that run it -------

ROOT = Path(__file__).resolve().parent.parent


def _compose_service(name):
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    match = re.search(rf"^  {name}:\n((?:    .*\n|\n)+)", text, re.MULTILINE)
    assert match, f"compose.yaml has no {name} service"
    return match.group(1)


def test_quality_service_runs_the_cli_in_its_own_light_image():
    service = _compose_service("quality")

    assert "dockerfile: docker/quality.Dockerfile" in service
    assert "./src:/opt/src" in service
    assert "MINIO_ENDPOINT: minio:9000" in service
    assert "MINIO_BUCKET: factorypulse" in service
    assert 'profiles: ["lake-jobs"]' in service
    assert "minio: { condition: service_healthy }" in service


def test_quality_image_is_python_with_the_pinned_checker_not_spark():
    dockerfile = (ROOT / "docker" / "quality.Dockerfile").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-quality.txt").read_text(encoding="utf-8")

    assert re.search(r"^FROM python:3\.12", dockerfile, re.MULTILINE)
    assert "requirements-quality.txt" in dockerfile
    assert "GX_ANALYTICS_ENABLED=false" in dockerfile
    assert '"-m", "factorypulse.quality"' in dockerfile
    assert re.search(r"^great_expectations==1\.\d+\.\d+$", requirements, re.MULTILINE)
    assert re.search(r"^deltalake==\d", requirements, re.MULTILINE)
    # deltalake 1.x does not depend on pyarrow, but its to_pandas needs it.
    assert re.search(r"^pyarrow==\d", requirements, re.MULTILINE)


def _function_body(script, name):
    """The body of a shell function, one-line (`f() { ...; }`) or block form."""
    text = (ROOT / "scripts" / script).read_text(encoding="utf-8")
    match = re.search(rf"^{name}\(\)\s*\{{(.*?)^\}}", text, re.MULTILINE | re.DOTALL)
    one_line = re.search(rf"^{name}\(\)\s*\{{(.*)\}}\s*$", text, re.MULTILINE)
    found = one_line or match
    assert found, f"scripts/{script} has no {name}()"
    return found.group(1)


@pytest.mark.parametrize("stage", ["ingestion", "post-dbt"])
def test_quality_driver_runs_one_stage_through_the_service(stage):
    text = (ROOT / "scripts" / "quality.sh").read_text(encoding="utf-8")

    # run_job (scripts/job.sh) is `docker compose run --rm` that owns its
    # container; tests/test_airflow_dag.py drives it against a fake docker.
    assert 'run_job quality -- "$@"' in text
    assert re.search(rf"^\s*{re.escape(stage)}\)", text, re.MULTILINE)


def test_dbt_lake_build_is_followed_by_the_post_dbt_checks():
    body = _function_body("dbt.sh", "run")

    assert body.index('dbt_run "build --target lake"') < body.index("scripts/quality.sh post-dbt")


def test_lake_demo_checks_the_raw_lake_after_ingesting():
    body = _function_body("lake.sh", "demo")

    assert body.rindex("batch") < body.index("scripts/quality.sh ingestion")
