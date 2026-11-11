"""Structured Streaming ingest: Kafka ``sensor-events`` → raw Delta lake (ticket 04).

The streaming half of the tracer bullet. Consumes the simulator topic,
validates each event with the shared contract validator, and writes
contract-conforming events to the raw Delta table on MinIO. Events the
validator rejects go to a sibling ``*_invalid`` table so nothing is
silently dropped.

Run via the compose ``streamer`` service (``spark-submit``).
"""

import os
import sys

# The job scripts ship inside the container as plain files (mount ./spark →
# /opt/app), so the *shared* module is `common`, not `spark.common` (the
# latter only exists when the repo root is on sys.path, i.e. on the host).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyspark.sql import functions as F  # type: ignore[import-not-found]  # container only

from common import (
    EVENT_SCHEMA_SPEC,
    build_spark,
    lake_paths,
    to_struct_type,
    validation_errors_udf,
)


def main() -> None:
    env = dict(os.environ)
    spark = build_spark(env, "factorypulse-streamer")
    paths = lake_paths(env)
    errors_udf = validation_errors_udf()

    parsed = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", env.get("KAFKA_BOOTSTRAP", "kafka:9092"))
        .option("subscribe", env.get("KAFKA_TOPIC", "sensor-events"))
        .option("startingOffsets", "earliest")
        .load()
        .select(F.from_json(F.col("value").cast("string"), to_struct_type()).alias("e"))
        .select("e.*", errors_udf(F.col("e")).alias("_validation_errors"))
    )

    valid = parsed.where(F.size(F.col("_validation_errors")) == 0).select(*EVENT_SCHEMA_SPEC)
    invalid = parsed.where(F.size(F.col("_validation_errors")) > 0)

    valid.writeStream.format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", paths["checkpoint"]) \
        .start(paths["raw"])

    invalid.writeStream.format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", paths["checkpoint"] + "-invalid") \
        .start(paths["invalid"])

    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()