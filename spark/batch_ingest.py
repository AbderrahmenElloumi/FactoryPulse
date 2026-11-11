"""Batch ingest: reprocess a historical JSONL snapshot into the raw Delta lake (ticket 04).

The batch half of the tracer bullet. Reads the producer's deterministic
JSONL snapshot from MinIO, validates it against the contract, and MERGEs it
into the *same* Delta table the streamer writes — by ``event_id``, so a
backfill is idempotent and the two paradigms converge on one logical lake
without duplicates.

Run via the compose ``batch-ingest`` service (``spark-submit``).
"""

import os
import sys

# See streaming_ingest.py: inside the container the shared module is `common`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyspark.sql import functions as F  # type: ignore[import-not-found]  # container only

from common import (
    EVENT_SCHEMA_SPEC,
    build_spark,
    lake_paths,
    merge_into_delta,
    to_struct_type,
    validation_errors_udf,
)


def main() -> None:
    env = dict(os.environ)
    spark = build_spark(env, "factorypulse-batch")
    paths = lake_paths(env)
    errors_udf = validation_errors_udf()

    source = spark.read.format("json").schema(to_struct_type()).load(
        f"{paths['backfill']}/*.jsonl"
    )
    checked = source.withColumn(
        "_validation_errors", errors_udf(F.struct(*[F.col(name) for name in EVENT_SCHEMA_SPEC]))
    )
    valid = checked.where(F.size(F.col("_validation_errors")) == 0).select(*EVENT_SCHEMA_SPEC)
    n_valid = valid.count()
    n_invalid = checked.count() - n_valid

    merge_into_delta(spark, valid, paths["raw"], keys=("event_id",))

    print(
        f"batch: merged {n_valid} valid events into {paths['raw']}; "
        f"{n_invalid} invalid skipped"
    )


if __name__ == "__main__":
    main()