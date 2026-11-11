"""Anomaly scoring job (ticket 08): the predictive-maintenance core.

Reads the hourly mart and scores the hourly average of every scored sensor
(``anomaly_core.SCORED_SENSORS``: temperature and vibration) against the same
machine's trailing baseline: the hourly windows of the previous
``BASELINE_HOURS`` hours, never the scored window itself. The z-score, the
sensor status and the machine status (the worst sensor of the window) come
from ``factorypulse.anomaly_core``; this job owns only the windowing.

The result is merged into ``mrt_anomaly_scores``, keyed on machine, window
and sensor, through ``common.merge_into_delta``, the idempotent write raw
ingestion uses too: re-running over the same hours updates rows in place.

Run via the compose ``anomaly-detection`` service. ``--lake-root`` points the
job at another lake with the same layout, such as a local fixture lake.
"""

from __future__ import annotations  # PEP 563: the spark image runs Python 3.8

import argparse
import os
import sys
from typing import Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import build_spark, merge_into_delta
from factorypulse.analytics import (
    ANOMALY_SCORE_COLUMNS,
    ANOMALY_SCORE_KEYS,
    MRT_ANOMALY_SCORES,
    MRT_MACHINE_HOURLY,
    analytics_path,
)
from factorypulse.anomaly_core import (
    BASELINE_HOURS,
    SCORED_SENSORS,
    classify,
    machine_status,
    z_score,
)

# The scored windows are the hourly mart's windows.
WINDOW_SECONDS = 3600


def compute_anomaly_scores(hourly_df):
    """Score every scored sensor of every machine-hour of ``hourly_df``.

    Returns a frame with exactly ``ANOMALY_SCORE_COLUMNS``. An hour without a
    reading of a sensor has nothing to score and gets no row for it.
    """
    from pyspark.sql import functions as F  # type: ignore[import-not-found]  # container only
    from pyspark.sql import types as T  # type: ignore[import-not-found]
    from pyspark.sql.window import Window  # type: ignore[import-not-found]

    readings = None
    for sensor in SCORED_SENSORS:
        frame = hourly_df.select(
            "machine_id",
            "site_id",
            F.col("hour_start").alias("window_start"),
            F.lit(sensor).alias("sensor_type"),
            F.col(f"{sensor}_avg").cast("double").alias("value"),
        )
        readings = frame if readings is None else readings.unionByName(frame)
    # A NaN average would poison every baseline window that holds it.
    readings = readings.where(
        F.col("value").isNotNull() & ~F.isnan("value")
    ).withColumn(
        "_epoch", F.col("window_start").cast("long")
    )

    # A time range, not a row count: a machine that was down for a day starts
    # again with no baseline instead of comparing against last week.
    baseline = (
        Window.partitionBy("machine_id", "sensor_type")
        .orderBy("_epoch")
        .rangeBetween(-BASELINE_HOURS * WINDOW_SECONDS, -1)
    )
    z_score_udf = F.udf(z_score, T.DoubleType())
    classify_udf = F.udf(classify, T.StringType())
    machine_status_udf = F.udf(machine_status, T.StringType())

    scored = (
        readings.withColumn("baseline_mean", F.avg("value").over(baseline))
        .withColumn("baseline_stddev", F.stddev_samp("value").over(baseline))
        .withColumn("baseline_count", F.count("value").over(baseline))
        .withColumn(
            "z_score",
            z_score_udf("value", "baseline_mean", "baseline_stddev", "baseline_count"),
        )
        .withColumn("sensor_status", classify_udf("z_score"))
        .withColumn(
            "window_end",
            (F.col("_epoch") + WINDOW_SECONDS).cast("timestamp"),
        )
    )
    machine_window = Window.partitionBy("machine_id", "window_start")
    return scored.withColumn(
        "machine_status",
        machine_status_udf(F.collect_list("sensor_status").over(machine_window)),
    ).select(*ANOMALY_SCORE_COLUMNS)


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--lake-root",
        default=None,
        help="lake to read and write (default: the MinIO lake from the environment)",
    )
    args = parser.parse_args(argv)

    env = dict(os.environ)
    spark = build_spark(env, "factorypulse-anomaly-detection")
    hourly = spark.read.format("delta").load(
        analytics_path(env, MRT_MACHINE_HOURLY, root=args.lake_root)
    )
    scores = compute_anomaly_scores(hourly)
    target = analytics_path(env, MRT_ANOMALY_SCORES, root=args.lake_root)
    merged = merge_into_delta(spark, scores, target, keys=ANOMALY_SCORE_KEYS)
    print(f"anomaly: merged {merged} scores into {target}")
    spark.stop()


if __name__ == "__main__":
    main()
