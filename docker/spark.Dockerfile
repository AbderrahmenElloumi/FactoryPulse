# FactoryPulse Spark runtime — apache/spark 3.5.4 plus the exact connector
# jars the Phase-2 jobs need, pre-fetched into the image's Ivy cache so a
# fresh `docker compose up` boots without hitting Maven Central again.
#
# Keep SPARK_JAR_PACKAGES in sync with spark/common.py::PACKAGES.
FROM apache/spark:3.5.4

# delta python wrapper for the batch MERGE (no deps: the image already
# bundles the matching pyspark; the jar itself comes via spark.jars.packages).
# apache/spark exposes Python as `python3`, only — there is no `python` alias.
USER root
RUN python3 -m pip install --no-cache-dir --no-deps delta-spark==3.2.1 && \
    # The spark user's $HOME (/home/spark) doesn't exist in the base image;
    # Ivy needs a writable cache at $HOME/.ivy2, so create it here.
    mkdir -p /home/spark/.ivy2/cache && chown -R spark:spark /home/spark
USER spark

ARG SPARK_JAR_PACKAGES="org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4,io.delta:delta-spark_2.12:3.2.1,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.780"

# Warm the Ivy cache so a fresh `docker compose up` boots without hitting
# Maven Central. Guarded: a flaky Maven hit must not hard-fail the build —
# a missing jar is simply re-resolved at submit time.
RUN /opt/spark/bin/spark-shell --master "local[1]" \
    --packages "$SPARK_JAR_PACKAGES" \
    -e 'spark.range(1).count()' || true

# Optional analytics layer (ticket 05): dbt-spark runs Spark in-process, so
# it needs exactly the Java, PySpark and warmed Ivy cache this image already
# has — building it from the same Dockerfile (compose passes
# INSTALL_DBT=true for the `dbt` service) keeps one Spark runtime instead of
# two. This layer sits after the Ivy warm so both images share it.
USER root
ARG INSTALL_DBT=false
# Both pins are explicit on purpose: dbt-spark 1.8.0 only asks for
# `dbt-core~=1.8.0`, which the resolver on Python 3.8 satisfied with the
# pre-release 1.9.0-b2 — an adapter/core pair dbt itself then reports as
# incompatible. 1.8.7 is the newest core with a Python 3.8 wheel.
RUN if [ "$INSTALL_DBT" = "true" ]; then \
      python3 -m pip install --no-cache-dir "dbt-core==1.8.7" "dbt-spark[session]==1.8.0"; \
    fi
USER spark

CMD ["/bin/bash"]