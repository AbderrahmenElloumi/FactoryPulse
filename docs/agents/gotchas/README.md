# Gotchas

Read this index, then only the area files your change touches.

## Entry rule

- An entry is a lasting trap that is not obvious from the code. It has at
  most 5 lines: the **rule**, why, and how to detect it (the test name or the
  exact error string).
- No ticket numbers and no story in an entry.
- Do not add a trap that a test or a linter already reports with a clear
  failure.
- When a change removes the trap at its root, delete the entry in the same
  commit.
- Record a new trap in its area file, and list the file in this index if it
  is new.

## Index

- [spark.md](spark.md): the Spark image's Python 3.8, connector jars, Spark
  SQL functions missing on 3.5.4, JVM boot time.
- [delta.md](delta.md): MERGE through `merge_into_delta`, duplicate source
  keys, source columns dropped by the MERGE, fakes of Delta in tests.
- [dbt.md](dbt.md): `DBT_ARGS` word splitting, the empty session catalog,
  indirect test selection, NULL in `session` seeds, testing macros on the
  host.
- [docker.md](docker.md): compose anchors, `$$` and `${VAR:?}`
  interpolation, the `minio` image's missing tools.
- [airflow.md](airflow.md): Airflow 3 APIs, `DagBag` in tests, the Docker
  socket on Linux, scripting against the `airflow` CLI.
- [windows-host.md](windows-host.md): Git Bash path rewriting, CRLF from
  Python, a moved `.venv`.
