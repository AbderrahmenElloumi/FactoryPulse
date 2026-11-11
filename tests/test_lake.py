"""Lake read module (ticket 12): the one way non-Spark code reads a lake table.

A local Delta directory is the second adapter behind the seam, so every read
behaviour here runs without MinIO.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd
import pytest
from deltalake import write_deltalake

from factorypulse import analytics, lake


def _write_table(root, name, frame):
    write_deltalake(str(root / name), frame)


def test_read_table_returns_declared_columns_in_declared_order(tmp_path):
    # Stored out of order and with a column the registry does not declare.
    stored = pd.DataFrame(
        {
            "reading_count": [12],
            "undeclared_extra": ["dropped"],
            "sensor_type_count": [4],
            "machine_id": ["M-001"],
            "last_seen_at": [pd.Timestamp("2026-10-01T12:00:00Z")],
            "site_id": ["S-01"],
            "first_seen_at": [pd.Timestamp("2026-10-01T00:00:00Z")],
        }
    )
    _write_table(tmp_path, "dim_machine", stored)

    frame = lake.read_table("dim_machine", root=str(tmp_path))

    assert list(frame.columns) == [
        "machine_id",
        "site_id",
        "first_seen_at",
        "last_seen_at",
        "reading_count",
        "sensor_type_count",
    ]
    assert frame.loc[0, "machine_id"] == "M-001"
    assert frame.loc[0, "reading_count"] == 12


def test_table_that_has_not_been_built_raises_a_named_error(tmp_path):
    with pytest.raises(lake.LakeTableMissing) as caught:
        lake.read_table("mrt_machine_weekly", root=str(tmp_path))

    assert caught.value.name == "mrt_machine_weekly"
    assert "mrt_machine_weekly" in str(caught.value)


def test_directory_without_a_delta_log_counts_as_not_built(tmp_path):
    (tmp_path / "mrt_machine_hourly").mkdir()

    with pytest.raises(lake.LakeTableMissing):
        lake.read_table("mrt_machine_hourly", root=str(tmp_path))


def test_built_table_with_no_rows_reads_as_empty_frame_not_an_error(tmp_path):
    # The case a missing table must never be confused with.
    stored = pd.DataFrame(
        {name: pd.Series([], dtype="string") for name in analytics.FCT_READING_COLUMNS}
    )
    _write_table(tmp_path, "fct_sensor_readings_clean", stored)

    frame = lake.read_table("fct_sensor_readings_clean", root=str(tmp_path))

    assert frame.empty
    assert tuple(frame.columns) == analytics.FCT_READING_COLUMNS


def test_built_table_missing_a_declared_column_raises_a_named_error(tmp_path):
    # A quality check reports "required column missing" by name, never as a
    # reader error about field references.
    stored = pd.DataFrame(
        {name: ["x"] for name in analytics.MACHINE_DIM_COLUMNS if name not in ("site_id", "reading_count")}
    )
    _write_table(tmp_path, "dim_machine", stored)

    with pytest.raises(lake.LakeColumnsMissing) as caught:
        lake.read_table("dim_machine", root=str(tmp_path))

    assert caught.value.name == "dim_machine"
    assert caught.value.missing == ("site_id", "reading_count")
    assert "site_id" in str(caught.value)
    assert "reading_count" in str(caught.value)


def test_table_without_declared_columns_is_rejected_before_any_read(tmp_path):
    # A typo must not be reported as "not built yet".
    with pytest.raises(ValueError, match="mrt_machine_dayly"):
        lake.read_table("mrt_machine_dayly", root=str(tmp_path))


@pytest.fixture
def minio_env(monkeypatch):
    monkeypatch.setenv("MINIO_ACCESS_KEY", "factorypulse")
    monkeypatch.setenv("MINIO_SECRET_KEY", "factorypulse-dev-pass")
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.delenv("MINIO_SECURE", raising=False)
    monkeypatch.delenv("MINIO_BUCKET", raising=False)
    return monkeypatch


@pytest.fixture
def in_container(minio_env, tmp_path):
    marker = tmp_path / ".dockerenv"
    marker.touch()
    minio_env.setattr(lake, "CONTAINER_MARKER", str(marker))
    return minio_env


@pytest.fixture
def on_host(minio_env, tmp_path):
    minio_env.setattr(lake, "CONTAINER_MARKER", str(tmp_path / "absent-dockerenv"))
    return minio_env


def test_container_reaches_storage_by_service_name(in_container):
    assert lake.storage_options() == {
        "AWS_ACCESS_KEY_ID": "factorypulse",
        "AWS_SECRET_ACCESS_KEY": "factorypulse-dev-pass",
        "AWS_ENDPOINT_URL": "http://minio:9000",
        "AWS_REGION": "us-east-1",
        "AWS_ALLOW_HTTP": "true",
    }


def test_host_process_reaches_the_service_name_on_localhost(on_host):
    # A non-default port: the rewrite swaps the host and keeps the published port.
    on_host.setenv("MINIO_ENDPOINT", "minio:19000")

    options = lake.storage_options()

    assert options["AWS_ENDPOINT_URL"] == "http://localhost:19000"
    assert options["AWS_ACCESS_KEY_ID"] == "factorypulse"


def test_host_process_keeps_an_endpoint_that_is_not_the_service_name(on_host):
    on_host.setenv("MINIO_ENDPOINT", "10.0.0.5:9000")

    assert lake.storage_options()["AWS_ENDPOINT_URL"] == "http://10.0.0.5:9000"


def test_host_process_defaults_to_localhost_when_no_endpoint_is_set(on_host):
    on_host.delenv("MINIO_ENDPOINT")

    assert lake.storage_options()["AWS_ENDPOINT_URL"] == "http://localhost:9000"


def test_secure_storage_uses_https_and_refuses_plain_http(in_container):
    in_container.setenv("MINIO_SECURE", "true")

    options = lake.storage_options()

    assert options["AWS_ENDPOINT_URL"] == "https://minio:9000"
    assert options["AWS_ALLOW_HTTP"] == "false"


class _RecordingDeltaTable:
    """Stands in for deltalake.DeltaTable at the storage boundary, where no
    MinIO runs: records where the read went, then reports the table absent."""

    calls = []

    def __init__(self, uri, storage_options=None):
        from deltalake.exceptions import TableNotFoundError

        type(self).calls.append((uri, storage_options))
        raise TableNotFoundError(f"no table at {uri}")


@pytest.fixture
def recording_delta_table(monkeypatch):
    import deltalake

    _RecordingDeltaTable.calls = []
    monkeypatch.setattr(deltalake, "DeltaTable", _RecordingDeltaTable)
    return _RecordingDeltaTable.calls


def test_default_source_is_the_object_store_lake_with_storage_options(
    in_container, recording_delta_table
):
    in_container.setenv("MINIO_BUCKET", "plant-a")

    with pytest.raises(lake.LakeTableMissing) as caught:
        lake.read_table("dim_machine")

    # deltalake speaks s3://, not the s3a:// scheme Spark and the registry use.
    assert caught.value.uri == "s3://plant-a/delta/dim_machine"
    assert recording_delta_table == [
        ("s3://plant-a/delta/dim_machine", lake.storage_options())
    ]


class _UnreachableDeltaTable:
    """Stands in for deltalake.DeltaTable when storage answers with a failure
    that is not "no table here": bad credentials, a missing bucket, no route."""

    def __init__(self, uri, storage_options=None):
        raise OSError(f"Generic S3 error: error sending request for {uri}")


def test_read_failure_other_than_a_missing_table_propagates(in_container):
    # A credentials or network error must not be reported as "not built yet".
    import deltalake

    in_container.setattr(deltalake, "DeltaTable", _UnreachableDeltaTable)

    with pytest.raises(OSError, match="error sending request"):
        lake.read_table("dim_machine")


def _corrupt_the_log(commit):
    commit.write_text("not a delta log entry\n", encoding="utf-8")


def _require_an_unsupported_reader(commit):
    # A table feature the Python reader does not know, as a newer Spark could write.
    actions = [json.loads(line) for line in commit.read_text(encoding="utf-8").splitlines()]
    for action in actions:
        if "protocol" in action:
            action["protocol"]["minReaderVersion"] = 99
    commit.write_text("\n".join(json.dumps(a) for a in actions) + "\n", encoding="utf-8")


@pytest.mark.parametrize("break_table", [_corrupt_the_log, _require_an_unsupported_reader])
def test_built_table_that_cannot_be_read_is_not_reported_as_not_built(tmp_path, break_table):
    # The real reader raises a plain DeltaError here, not TableNotFoundError:
    # the table exists, so "not built yet" would be a lie.
    from deltalake.exceptions import DeltaError

    stored = pd.DataFrame({name: ["x"] for name in analytics.MACHINE_DIM_COLUMNS})
    _write_table(tmp_path, "dim_machine", stored)
    break_table(tmp_path / "dim_machine" / "_delta_log" / "00000000000000000000.json")

    # LakeTableMissing is not a DeltaError, so it would escape and fail this.
    with pytest.raises(DeltaError):
        lake.read_table("dim_machine", root=str(tmp_path))


def test_local_directory_source_gets_no_storage_options(
    in_container, recording_delta_table, tmp_path
):
    with pytest.raises(lake.LakeTableMissing):
        lake.read_table("dim_machine", root=str(tmp_path))

    assert recording_delta_table == [(f"{tmp_path}/dim_machine", None)]


def test_module_imports_where_the_delta_reader_is_not_installed():
    # The Spark image (Python 3.8) has neither deltalake nor pandas; None in
    # sys.modules makes any import of them raise ImportError.
    probe = (
        "import sys\n"
        "sys.modules['deltalake'] = None\n"
        "sys.modules['pandas'] = None\n"
        "from factorypulse import lake\n"
        "assert lake.storage_options()['AWS_REGION'] == 'us-east-1'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr


def test_raw_lake_reads_as_the_event_contract_fields(tmp_path):
    event = {
        "status": "nominal",
        "event_id": "e-1",
        "value": 41.5,
        "ts": "2026-10-01T00:00:00Z",
        "unit": "C",
        "sensor_type": "temperature",
        "machine_id": "M-001",
        "site_id": "S-01",
    }
    _write_table(tmp_path, "raw_sensor_events", pd.DataFrame([event]))

    frame = lake.read_table("raw_sensor_events", root=str(tmp_path))

    assert list(frame.columns) == [
        "event_id",
        "ts",
        "site_id",
        "machine_id",
        "sensor_type",
        "value",
        "unit",
        "status",
    ]
    assert frame.loc[0, "value"] == 41.5
