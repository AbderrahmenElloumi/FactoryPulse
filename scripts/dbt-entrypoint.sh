#!/usr/bin/env bash
# dbt runtime wiring inside the pipeline container (ticket 05).
#
# dbt-spark's `session` method builds the SparkSession in-process, which
# leaves two things the dbt profile cannot express:
#
#   1. The connector jars. Every in-process PySpark driver in this repo
#      ignores `spark.jars.packages` (see docs/agents/gotchas/spark.md), so
#      the jars must arrive on the PySpark submit command line — that is what
#      PYSPARK_SUBMIT_ARGS is for. The Ivy cache baked into the image
#      resolves them offline.
#   2. Spark's own configuration. The session reads
#      $SPARK_CONF_DIR/spark-defaults.conf when the JVM starts, so the conf
#      dict every Spark job already shares (spark/common.py::spark_conf) is
#      rendered to that file here rather than duplicated in the dbt profile.
#
# Usage: scripts/dbt-entrypoint.sh <dbt args...>   (driven by scripts/dbt.sh)
set -euo pipefail

conf_dir="${SPARK_CONF_DIR:-/tmp/spark-conf}"
mkdir -p "$conf_dir" /tmp/spark-warehouse

DBT_SPARK_CONF_DIR="$conf_dir" python3 - <<'PY'
import os
import sys

sys.path.insert(0, "/opt/app")  # the mounted spark/ directory (spark/common.py)
from common import spark_conf

target = os.path.join(os.environ["DBT_SPARK_CONF_DIR"], "spark-defaults.conf")
conf = spark_conf(dict(os.environ))
with open(target, "w") as handle:
    for key in sorted(conf):
        handle.write("{} {}\n".format(key, conf[key]))
print("dbt: rendered {} ({} keys)".format(target, len(conf)))
PY

export SPARK_CONF_DIR="$conf_dir"
export PYSPARK_SUBMIT_ARGS="--packages ${SPARK_JAR_PACKAGES} pyspark-shell"

# dbt-spark's session method turns on Hive support, and Derby writes its
# metastore (metastore_db/, derby.log) into the CURRENT DIRECTORY. The project
# directory is a bind mount from the host, so running in place would persist a
# session catalog into the repo and make every run depend on the last one: a
# stale entry pinning a table to a different location fails the next run with
# DELTA_TABLE_LOCATION_MISMATCH. Run from a throwaway copy instead, and link the
# artifacts worth reading (compiled SQL, run results, dbt log) back to the
# mounted project.
rm -rf /tmp/dbt-project
cp -r /opt/dbt /tmp/dbt-project
rm -rf /tmp/dbt-project/target /tmp/dbt-project/logs \
       /tmp/dbt-project/metastore_db /tmp/dbt-project/derby.log
mkdir -p /opt/dbt/target /opt/dbt/logs
ln -s /opt/dbt/target /tmp/dbt-project/target
ln -s /opt/dbt/logs /tmp/dbt-project/logs

cd /tmp/dbt-project
exec dbt "$@"
