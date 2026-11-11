"""Shared wiring for the Spark jobs (ticket 04).

Every Spark app in this directory builds on these helpers. The seam is the
same as everywhere else in FactoryPulse: the event contract. The *pure*
data below (the schema mirror, the Spark config, the lake layout, the jar
coordinates) is locked by host tests in ``tests/test_spark_common.py``;
PySpark is only imported inside the functions the containers call, so
nothing here needs a JVM on the host.
"""

from __future__ import annotations  # PEP 563: the spark image runs Python 3.8

from typing import Mapping, Sequence

from factorypulse.contract import EVENT_FIELDS

# --- Spark package coordinates -------------------------------------------
# Resolved by Spark into the Ivy cache baked into the image (see
# docker/spark.Dockerfile — keep the two lists identical). delta-spark 3.2.x
# is the line built against the Spark 3.5 runtime this repo uses.
PACKAGES = (
    "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4",
    "io.delta:delta-spark_2.12:3.2.1",
    "org.apache.hadoop:hadoop-aws:3.3.4",
    "com.amazonaws:aws-java-sdk-bundle:1.12.780",
)
PACKAGES_CSV = ",".join(PACKAGES)

# --- Event schema mirror of the contract ---------------------------------
# Keys + order must track factorypulse.contract.EVENT_FIELDS (~ a test in
# test_spark_common.py enforces it); kinds must map in to_struct_type().
EVENT_SCHEMA_SPEC = {
    "event_id": "string",
    "ts": "string",
    "site_id": "string",
    "machine_id": "string",
    "sensor_type": "string",
    "value": "double",
    "unit": "string",
    "status": "string",
}

# Both ingestion paths target the same lake table: this IS the "streaming
# and batch writes land in the same logical lake" guarantee.
STREAMING_TABLE_NAME = "raw_sensor_events"
BATCH_TABLE_NAME = "raw_sensor_events"


class MergeKeyError(ValueError):
    """Raised when a merge cannot run because its key columns are absent."""


def spark_conf(env: Mapping[str, str]) -> dict[str, str]:
    """Hadoop/S3a/Delta Spark config derived from the pipeline env vars.

    ``MINIO_ENDPOINT`` is expected as ``host:port`` without a scheme (the
    compose services set ``minio:9000``); credentials are the dev ones from
    compose.yaml — swap them for any non-local use.
    """
    endpoint = env.get("MINIO_ENDPOINT", "minio:9000")
    return {
        # Delta SQL runtime.
        "spark.sql.extensions": "io.delta.sql.DeltaSparkSessionExtension",
        "spark.sql.catalog.spark_catalog": "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        # The contract's timestamps are UTC; hour buckets (the dbt hourly mart,
        # and every window downstream of it) must be UTC hours regardless of
        # the container's local timezone.
        "spark.sql.session.timeZone": "UTC",
        # Any managed table a job creates (dbt's seed tables, for instance) lands
        # in a writable path — $PWD is not guaranteed writable in every image.
        "spark.sql.warehouse.dir": "/tmp/spark-warehouse",
        # S3a → MinIO (S3-compatible, path-style, plain HTTP on the compose net).
        "spark.hadoop.fs.s3a.endpoint": f"http://{endpoint}",
        "spark.hadoop.fs.s3a.access.key": env.get("MINIO_ACCESS_KEY", ""),
        "spark.hadoop.fs.s3a.secret.key": env.get("MINIO_SECRET_KEY", ""),
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
        "spark.hadoop.fs.s3a.aws.credentials.provider": (
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider"
        ),
        # Delta's default S3 log store wants DynamoDB for cross-driver locks;
        # local MinIO has none, so local[*] jobs use the lock-free single-driver
        # store or every write blocks on a lock acquire.
        "spark.delta.logStore.class": (
            "org.apache.spark.sql.delta.storage.S3SingleDriverLogStore"
        ),
    }


def lake_paths(env: Mapping[str, str]) -> dict[str, str]:
    """The s3a locations every job reads/writes, all under one bucket."""
    bucket = env.get("MINIO_BUCKET", "factorypulse")
    return {
        "raw": f"s3a://{bucket}/delta/{STREAMING_TABLE_NAME}",
        "invalid": f"s3a://{bucket}/delta/{STREAMING_TABLE_NAME}_invalid",
        "checkpoint": f"s3a://{bucket}/checkpoints/streaming_ingest",
        "backfill": f"s3a://{bucket}/backfill",
    }


def to_struct_type():
    """PySpark StructType mirroring the contract.

    Only ``string`` and ``double`` kinds are supported — a host test in
    test_spark_common.py guards that the spec stays within them, so landing
    a new field kind must extend this function too.
    """
    from pyspark.sql import types as T  # type: ignore[import-not-found]  # container only

    kind_to_type = {"string": T.StringType, "double": T.DoubleType}
    return T.StructType(
        [T.StructField(name, kind_to_type[kind](), nullable=True) for name, kind in EVENT_SCHEMA_SPEC.items()]
    )


def validation_errors_udf():
    """UDF returning the contract-validation errors for one parsed event row.

    Applies the shared validator (factorypulse.validator) at the ingestion
    boundary, so the raw lake only ever holds contract-conforming events.
    """
    from pyspark.sql import functions as F  # type: ignore[import-not-found]
    from pyspark.sql.types import ArrayType, StringType  # type: ignore[import-not-found]

    from factorypulse.validator import validate_event

    def _errors(row):
        if row is None:
            return ["event: expected a dict, got null"]
        return validate_event(row.asDict())

    return F.udf(_errors, ArrayType(StringType()))


def build_spark(env: Mapping[str, str], app_name: str):
    """A local[*] SparkSession (Delta catalog + S3a/MinIO).

    The connector jars are provided on the spark-submit CLI (--packages)
    by the compose services — setting spark.jars.packages from the session
    builder is silently ignored by the in-process PySpark driver, so the
    Kafka source provider only registers when the jars come in that way.
    """
    from pyspark.sql import SparkSession  # type: ignore[import-not-found]  # container only

    builder = SparkSession.builder.appName(app_name).master("local[*]")
    for key, value in spark_conf(env).items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


def merge_into_delta(spark, source_df, path: str, keys: Sequence[str]) -> int:
    """Idempotent upsert into a Delta table, keyed on ``keys``.

    The one implementation of the "re-running must not duplicate" guarantee:
    raw ingestion and the anomaly write both call this, so a replay converges
    instead of appending a second copy of every row. Creates the table with the
    source's columns if it is the first thing to land (so batch can precede
    streaming on a fresh bucket), then MERGEs on every key column.

    A source frame missing a key column is a programming error, not something
    Delta should silently mishandle, so it raises :class:`MergeKeyError` before
    any SQL runs. A source frame containing the same key twice (overlapping
    backfill snapshots are the normal case) is collapsed to one row per key:
    Delta rejects a MERGE whose source matches one target row more than once.

    Returns the number of rows the MERGE inserted or updated, read from the
    MERGE's own metrics, so a caller can log it without recomputing the source.
    """
    table = path.rstrip("/").rsplit("/", 1)[-1]
    keys = tuple(keys)
    if not keys:
        raise MergeKeyError(f"merging into {path} needs at least one key column")

    missing = [key for key in keys if key not in source_df.columns]
    if missing:
        raise MergeKeyError(
            f"cannot merge into {path}: source frame {source_df.columns} "
            f"is missing key column(s) {missing}"
        )

    # The column list gives a fresh location its schema: without it Delta
    # creates a table with no columns, and the MERGE cannot resolve its keys.
    # A table already at the location keeps its own.
    columns = ", ".join(f"`{name}` {kind}" for name, kind in source_df.dtypes)
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {table} ({columns}) USING delta LOCATION '{path}'"
    )
    source_df.dropDuplicates(list(keys)).createOrReplaceTempView("_merge_source")
    predicate = " AND ".join(f"t.{key} = s.{key}" for key in keys)
    metrics = spark.sql(
        f"MERGE INTO {table} t USING _merge_source s "
        f"ON {predicate} "
        "WHEN MATCHED THEN UPDATE SET * "
        "WHEN NOT MATCHED THEN INSERT *"
    ).first()
    return int(metrics["num_affected_rows"])