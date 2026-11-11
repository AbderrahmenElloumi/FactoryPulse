"""Query the dbt analytics layer with Spark SQL (ticket 05).

Proves the marts are queryable *the same way as the raw lake*: every table
``factorypulse.analytics`` registers is read straight off the lake with
``spark.read.format("delta").load(path)`` — no dbt, no metastore, no
session. Run via the compose ``query-analytics`` service (``spark-submit``),
or through ``scripts/dbt.sh query``.
"""

import os
import sys

# See streaming_ingest.py: inside the container the shared module is `common`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyspark.sql import functions as F  # type: ignore[import-not-found]  # container only

from common import build_spark
from factorypulse.analytics import (
    ANALYTICS_MODELS,
    DIM_MACHINE,
    MRT_MACHINE_HOURLY,
    analytics_path,
)


def main() -> None:
    env = dict(os.environ)
    spark = build_spark(env, "factorypulse-query-analytics")

    for model in ANALYTICS_MODELS:
        path = analytics_path(env, model)
        df = spark.read.format("delta").load(path)
        df.createOrReplaceTempView(model)
        print(f"== {model} ({path}) ==")
        df.show(10, truncate=False)

    print("== machines at risk (share of critical readings, hourly mart) ==")
    spark.sql(
        "select machine_id, "
        "       sum(reading_count) as readings, "
        "       sum(critical_count) as critical, "
        "       round(100.0 * sum(critical_count) / sum(reading_count), 2) as critical_pct "
        f"from {MRT_MACHINE_HOURLY} "
        "group by machine_id order by critical_pct desc, machine_id"
    ).show(20, truncate=False)

    print("== busiest machine-hours in the mart ==")
    spark.sql(
        "select machine_hour_key, reading_count, nominal_count, warning_count, critical_count "
        f"from {MRT_MACHINE_HOURLY} order by reading_count desc, machine_hour_key"
    ).show(10, truncate=False)

    print("== machine dimension ==")
    spark.table(DIM_MACHINE).agg(
        F.count("*").alias("machines"),
        F.countDistinct("site_id").alias("sites"),
        F.sum("reading_count").alias("readings"),
    ).show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
