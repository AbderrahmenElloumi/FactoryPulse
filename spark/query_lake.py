"""Query the raw Delta lake with Spark SQL (ticket 04).

Proves the lake is queryable: reads the raw table and prints a summary plus
the sensor/status mixes and the machines with critical events. Run via the
compose ``query`` service (``spark-submit``).
"""

import os
import sys

# See streaming_ingest.py: inside the container the shared module is `common`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyspark.sql import functions as F  # type: ignore[import-not-found]  # container only

from common import build_spark, lake_paths


def main() -> None:
    env = dict(os.environ)
    spark = build_spark(env, "factorypulse-query")
    path = lake_paths(env)["raw"]

    df = spark.read.format("delta").load(path)
    df.createOrReplaceTempView("raw_sensor_events")

    df.agg(
        F.count("*").alias("total_events"),
        F.countDistinct("event_id").alias("distinct_events"),
        F.countDistinct("machine_id").alias("distinct_machines"),
        F.countDistinct("site_id").alias("distinct_sites"),
        F.min("ts").alias("first_ts"),
        F.max("ts").alias("last_ts"),
    ).show(truncate=False, vertical=True)

    print("sensor mix:")
    df.groupBy("sensor_type").count().orderBy("sensor_type").show(truncate=False)

    print("status mix:")
    df.groupBy("status").count().orderBy("status").show(truncate=False)

    print("machines with critical events (anomaly candidates):")
    (
        df.where(F.col("status") == "critical")
        .select("machine_id")
        .distinct()
        .orderBy("machine_id")
        .show(truncate=False, n=20)
    )

    spark.stop()


if __name__ == "__main__":
    main()