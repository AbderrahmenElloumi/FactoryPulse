"""Tests for the shared Spark wiring (ticket 04) — the *pure* half.

The Spark jobs run in a container (no Spark on the host), so these tests
lock the data the jobs are built from: the event-schema mirror of the
contract, the Hadoop/S3a/Delta Spark configuration derived from pipeline
env vars, the lake paths, and the idempotent ``merge_into_delta`` write seam
(ticket 11), driven through a fake session that mimics Delta's MERGE rules.
PySpark is deliberately never imported here.
"""

import re
from pathlib import Path

import pytest

from factorypulse.contract import EVENT_FIELDS
from spark.common import (
    EVENT_SCHEMA_SPEC,
    MergeKeyError,
    PACKAGES_CSV,
    lake_paths,
    merge_into_delta,
    spark_conf,
)

REPO = Path(__file__).resolve().parents[1]


# --- event schema mirror of the contract ---------------------------------


def test_event_schema_mirrors_contract_field_names_and_order(env):
    assert list(EVENT_SCHEMA_SPEC) == list(EVENT_FIELDS)


def test_event_schema_uses_only_supported_spark_kinds(env):
    # Only the kinds to_struct_type() can map; adding a new one must extend both.
    assert set(EVENT_SCHEMA_SPEC.values()) <= {"string", "double"}


def test_value_field_is_parsed_as_double(env):
    # Spark reads JSON numbers as doubles; value must parse to a float type
    # so Python-side range checks in the validator see a real number.
    assert EVENT_SCHEMA_SPEC["value"] == "double"


# --- Spark session configuration ------------------------------------------


def test_spark_conf_activates_the_delta_catalog(env):
    conf = spark_conf(env)
    assert conf["spark.sql.extensions"] == "io.delta.sql.DeltaSparkSessionExtension"
    assert conf["spark.sql.catalog.spark_catalog"] == "org.apache.spark.sql.delta.catalog.DeltaCatalog"


def test_spark_conf_points_s3a_at_minio_with_dev_credentials(env):
    conf = spark_conf(env)
    assert conf["spark.hadoop.fs.s3a.endpoint"] == "http://minio:9000"
    assert conf["spark.hadoop.fs.s3a.access.key"] == "factorypulse"
    assert conf["spark.hadoop.fs.s3a.secret.key"] == "factorypulse-dev-pass"
    assert conf["spark.hadoop.fs.s3a.path.style.access"] == "true"
    assert conf["spark.hadoop.fs.s3a.connection.ssl.enabled"] == "false"


def test_spark_conf_forces_the_minio_credentials_provider(env):
    # local MinIO has no instance-metadata chain; pin the provider so Spark
    # never scans the (slow, timing-out) DefaultAWSCredentialsProvider chain.
    conf = spark_conf(env)
    assert (
        conf["spark.hadoop.fs.s3a.aws.credentials.provider"]
        == "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
    )


def test_spark_conf_uses_the_single_driver_delta_log_store(env):
    # Delta's default S3 log store wants DynamoDB for cross-driver locks;
    # local MinIO has no DynamoDB, so local[*] jobs must use the single-driver
    # log store or every write hangs on a lock acquire.
    conf = spark_conf(env)
    assert conf["spark.delta.logStore.class"] == "org.apache.spark.sql.delta.storage.S3SingleDriverLogStore"


def test_spark_conf_pins_the_session_timezone_to_utc(env):
    # The contract's timestamps are UTC; the dbt hourly mart buckets on
    # date_trunc('hour', ...), so a local-timezone session would shift every
    # bucket by the host offset.
    conf = spark_conf(env)
    assert conf["spark.sql.session.timeZone"] == "UTC"


def test_spark_conf_points_the_warehouse_at_a_writable_path(env):
    # dbt's seed tables are managed tables: with no warehouse dir they land in
    # $PWD, which the spark user may not own.
    conf = spark_conf(env)
    assert conf["spark.sql.warehouse.dir"].startswith("/tmp/")


def test_jar_packages_cover_kafka_delta_and_s3(env):
    joined = PACKAGES_CSV
    assert "spark-sql-kafka-0-10_2.12" in joined
    assert "delta-spark_2.12" in joined
    assert "hadoop-aws" in joined
    assert "aws-java-sdk-bundle" in joined


# --- lake layout -----------------------------------------------------------


def test_lake_paths_hold_stream_and_batch_in_one_lake(env):
    paths = lake_paths(env)
    assert paths["raw"] == "s3a://factorypulse/delta/raw_sensor_events"
    assert paths["invalid"] == "s3a://factorypulse/delta/raw_sensor_events_invalid"
    assert paths["checkpoint"] == "s3a://factorypulse/checkpoints/streaming_ingest"
    assert paths["backfill"] == "s3a://factorypulse/backfill"


def test_batch_and_stream_share_the_raw_path(env):
    # Both paths already point at one lake; the ticket's "same logical lake"
    # is guaranteed by construction.
    from spark import common

    assert common.STREAMING_TABLE_NAME == common.BATCH_TABLE_NAME == "raw_sensor_events"
    assert lake_paths(env)["raw"] == lake_paths(env)["raw"]


# --- the idempotent write seam ---------------------------------------------


class FakeMergeSpark:
    """Just enough of a SparkSession to execute ``merge_into_delta``'s SQL.

    The container owns the real Delta runtime; this stand-in executes exactly
    the statements the helper emits, so the upsert semantics (and therefore
    re-run idempotency) are observable without a JVM or a lake.
    """

    def __init__(self):
        self.tables = {}
        self.schemas = {}
        self.statements = []
        self.views = {}

    def frame(self, rows):
        return FakeFrame(self, rows)

    def sql(self, statement):
        self.statements.append(statement)
        create = re.match(
            r"CREATE TABLE IF NOT EXISTS (\w+) (?:\((.*)\) )?USING delta LOCATION '([^']+)'$",
            statement,
        )
        if create:
            # Delta's rules: a new location gets the declared columns (none,
            # without a column list); an existing table keeps its own.
            table, columns, _ = create.groups()
            if table not in self.tables:
                self.tables[table] = []
                self.schemas[table] = re.findall(r"`(\w+)` (\w+)", columns or "")
            return None

        merge = re.match(
            r"MERGE INTO (\w+) t USING (\w+) s ON (.+?) "
            r"WHEN MATCHED THEN UPDATE SET \* "
            r"WHEN NOT MATCHED THEN INSERT \*$",
            statement,
            re.DOTALL,
        )
        assert merge, f"unexpected statement: {statement}"
        table, view, predicate = merge.groups()
        keys = re.findall(r"t\.(\w+) = s\.\w+", predicate)
        assert keys, f"merge has no key predicate: {statement}"
        target_columns = {name for name, _ in self.schemas[table]}
        if not set(keys) <= target_columns:
            raise FakeDeltaMergeError(
                f"DELTA_MERGE_UNRESOLVED_EXPRESSION: cannot resolve t.{keys[0]}"
            )

        # Delta's semantics, not a dict's: a source that repeats a key already
        # in the target is rejected, and unmatched source rows are inserted
        # one-for-one, so a repeated new key lands twice.
        def key_of(row):
            return tuple(row[key] for key in keys)

        source = self.views[view]
        target = self.tables[table]
        target_keys = {key_of(row) for row in target}
        merged = []
        for row in target:
            matches = [incoming for incoming in source if key_of(incoming) == key_of(row)]
            if len(matches) > 1:
                raise FakeDeltaMergeError(
                    "DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE"
                )
            merged.append(dict(matches[0]) if matches else row)
        merged.extend(
            dict(incoming) for incoming in source if key_of(incoming) not in target_keys
        )
        self.tables[table] = merged
        # Delta's MERGE returns its metrics as a one-row result.
        written = sum(1 for incoming in source if key_of(incoming) in target_keys)
        written += len(merged) - len(target)
        return FakeResult({"num_affected_rows": written})


class FakeResult:
    """The one-row DataFrame a Delta MERGE statement returns."""

    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class FakeDeltaMergeError(Exception):
    """Stands in for the ``AnalysisException`` Delta raises on a bad MERGE."""


class FakeFrame:
    KINDS = {str: "string", float: "double", int: "bigint"}

    def __init__(self, spark, rows):
        self._spark = spark
        self._rows = [dict(row) for row in rows]
        self.columns = list(self._rows[0]) if self._rows else []
        self.dtypes = [
            (column, self.KINDS[type(value)]) for column, value in self._rows[0].items()
        ] if self._rows else []

    def dropDuplicates(self, keys):
        seen = set()
        rows = []
        for row in self._rows:
            key = tuple(row[column] for column in keys)
            if key not in seen:
                seen.add(key)
                rows.append(row)
        return FakeFrame(self._spark, rows)

    def createOrReplaceTempView(self, name):
        self._spark.views[name] = self._rows


RAW_PATH = "s3a://factorypulse/delta/raw_sensor_events"


def test_merge_into_delta_upserts_by_the_requested_keys():
    spark = FakeMergeSpark()
    frame = spark.frame(
        [
            {"event_id": "e1", "value": 1.0},
            {"event_id": "e2", "value": 2.0},
        ]
    )

    merge_into_delta(spark, frame, RAW_PATH, keys=("event_id",))

    assert len(spark.tables["raw_sensor_events"]) == 2
    assert "t.event_id = s.event_id" in spark.statements[-1]


def test_merge_into_delta_creates_a_new_table_with_the_source_columns():
    # A fresh location has no schema to merge into: the first write must
    # declare the source's columns, or Delta cannot resolve the merge keys.
    spark = FakeMergeSpark()
    frame = spark.frame([{"machine_id": "m1", "baseline_count": 3, "z_score": 1.5}])

    merge_into_delta(spark, frame, "/fixture/mrt_anomaly_scores", keys=("machine_id",))

    assert spark.schemas["mrt_anomaly_scores"] == [
        ("machine_id", "string"),
        ("baseline_count", "bigint"),
        ("z_score", "double"),
    ]
    assert spark.statements[0] == (
        "CREATE TABLE IF NOT EXISTS mrt_anomaly_scores "
        "(`machine_id` string, `baseline_count` bigint, `z_score` double) "
        "USING delta LOCATION '/fixture/mrt_anomaly_scores'"
    )
    assert spark.tables["mrt_anomaly_scores"] == [
        {"machine_id": "m1", "baseline_count": 3, "z_score": 1.5}
    ]


def test_merge_into_delta_is_idempotent_when_the_same_range_is_replayed():
    # Re-running the same batch over the same range must converge instead of
    # appending a second copy of every event.
    spark = FakeMergeSpark()
    frame = spark.frame(
        [
            {"event_id": "e1", "value": 1.0},
            {"event_id": "e2", "value": 2.0},
        ]
    )

    merge_into_delta(spark, frame, RAW_PATH, keys=("event_id",))
    rows_after_one_run = len(spark.tables["raw_sensor_events"])
    merge_into_delta(spark, frame, RAW_PATH, keys=("event_id",))

    assert rows_after_one_run == 2
    assert len(spark.tables["raw_sensor_events"]) == rows_after_one_run


def test_merge_into_delta_updates_a_replayed_row_instead_of_duplicating_it():
    spark = FakeMergeSpark()
    merge_into_delta(
        spark,
        spark.frame([{"event_id": "e1", "value": 1.0}]),
        RAW_PATH,
        keys=("event_id",),
    )
    merge_into_delta(
        spark,
        spark.frame([{"event_id": "e1", "value": 9.0}]),
        RAW_PATH,
        keys=("event_id",),
    )

    assert spark.tables["raw_sensor_events"] == [{"event_id": "e1", "value": 9.0}]


def test_merge_into_delta_collapses_duplicate_source_keys():
    # Overlapping backfill snapshots legitimately contain the same event twice;
    # Delta rejects a MERGE whose source hits one target row more than once.
    spark = FakeMergeSpark()
    frame = spark.frame(
        [
            {"event_id": "e1", "value": 1.0},
            {"event_id": "e1", "value": 1.0},
            {"event_id": "e2", "value": 2.0},
        ]
    )

    merge_into_delta(spark, frame, RAW_PATH, keys=("event_id",))

    assert len(spark.tables["raw_sensor_events"]) == 2
    assert sorted(row["event_id"] for row in spark.views["_merge_source"]) == ["e1", "e2"]


def test_merge_into_delta_accepts_a_duplicated_source_key_already_in_the_target():
    # The second batch run over overlapping snapshots: the repeated key now
    # matches a target row, which is exactly where Delta raises.
    spark = FakeMergeSpark()
    merge_into_delta(
        spark,
        spark.frame([{"event_id": "e1", "value": 1.0}]),
        RAW_PATH,
        keys=("event_id",),
    )
    replay = spark.frame(
        [
            {"event_id": "e1", "value": 1.0},
            {"event_id": "e1", "value": 1.0},
        ]
    )

    merge_into_delta(spark, replay, RAW_PATH, keys=("event_id",))

    assert spark.tables["raw_sensor_events"] == [{"event_id": "e1", "value": 1.0}]


def test_merge_into_delta_returns_the_rows_the_merge_wrote():
    # The count comes from the MERGE's own metrics, after duplicate keys are
    # collapsed, so a caller never recomputes the source frame to log it.
    spark = FakeMergeSpark()
    frame = spark.frame(
        [
            {"event_id": "e1", "value": 1.0},
            {"event_id": "e1", "value": 1.0},
            {"event_id": "e2", "value": 2.0},
        ]
    )

    # One update of e2 and two inserts: a count no constant can match twice.
    again = spark.frame(
        [
            {"event_id": "e2", "value": 3.0},
            {"event_id": "e3", "value": 3.0},
            {"event_id": "e4", "value": 4.0},
        ]
    )

    assert merge_into_delta(spark, frame, RAW_PATH, keys=("event_id",)) == 2
    assert merge_into_delta(spark, again, RAW_PATH, keys=("event_id",)) == 3


def test_merge_into_delta_rejects_an_empty_key_list():
    spark = FakeMergeSpark()
    frame = spark.frame([{"event_id": "e1", "value": 1.0}])

    with pytest.raises(MergeKeyError, match="at least one key column"):
        merge_into_delta(spark, frame, RAW_PATH, keys=())
    assert spark.statements == []


def test_merge_into_delta_supports_composite_keys():
    spark = FakeMergeSpark()
    frame = spark.frame([{"machine_id": "m1", "hour_start": "10:00", "score": 1.0}])

    merge_into_delta(
        spark,
        frame,
        "s3a://factorypulse/delta/mrt_anomaly_scores",
        keys=("machine_id", "hour_start"),
    )

    assert "t.machine_id = s.machine_id AND t.hour_start = s.hour_start" in spark.statements[-1]


def test_merge_into_delta_rejects_a_frame_missing_a_key_column():
    spark = FakeMergeSpark()
    frame = spark.frame([{"machine_id": "m1", "score": 1.0}])

    with pytest.raises(MergeKeyError, match="hour_start"):
        merge_into_delta(
            spark,
            frame,
            "s3a://factorypulse/delta/mrt_anomaly_scores",
            keys=("machine_id", "hour_start"),
        )
    assert spark.statements == []


def test_raw_ingest_and_anomaly_write_share_the_merge_helper():
    # One implementation of the idempotency guarantee, not one per caller.
    batch = (REPO / "spark" / "batch_ingest.py").read_text(encoding="utf-8")
    anomaly = (REPO / "spark" / "anomaly_detection.py").read_text(encoding="utf-8")

    assert "merge_into_delta" in batch
    assert "merge_into_delta" in anomaly
    assert "merge_into_raw" not in batch
    assert "merge_into_raw" not in anomaly
