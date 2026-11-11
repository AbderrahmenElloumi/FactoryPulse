# Spark gotchas

- **Code that runs in the Spark image must run on Python 3.8.** The image
  (`apache/spark:3.5.4`) has Python 3.8; host tests run on 3.14 and miss it.
  No module-level PEP 585 generics or `|` unions: `from __future__ import
  annotations` defers only annotations. Detect: `TypeError: 'type' object is
  not subscriptable` at import.
- **`datetime.fromisoformat` in the Spark image rejects a trailing `Z`.**
  Python 3.8 parses a numeric offset such as `+00:00`, not `Z`. Detect:
  `ValueError: Invalid isoformat string`.
- **The Spark image has only a `python3` binary.** A script that calls
  `python` fails there. Detect: `python: command not found`.
- **Connector jars arrive on the submit command line, never through
  `spark.jars.packages`.** The in-process PySpark driver ignores that config.
  Use `spark-submit --packages`, or `PYSPARK_SUBMIT_ARGS` for an in-process
  session (dbt). Detect: `Failed to find data source: kafka`.
- **Spark 3.5.4 has no `yearofweek()`.** Use `year(date_add(week_start, 3))`:
  the Thursday of an ISO week is always in its ISO year. `weekofyear()`
  exists and is ISO-8601. Detect: `UNRESOLVED_ROUTINE` on `yearofweek`.
- **A Spark job needs 45–60 s to boot its JVM**, even with the warm Ivy
  cache, and the streamer's first micro-batch comes after that. Size any
  timeout that waits on a Spark job for it. Detect: `subprocess.TimeoutExpired`
  (`timed out after`) on a wait shorter than the boot.
