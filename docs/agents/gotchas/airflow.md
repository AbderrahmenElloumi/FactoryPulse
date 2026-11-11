# Airflow gotchas

- **This is Airflow 3, not Airflow 2.** The UI is `airflow api-server`, DAG
  parsing is `airflow dag-processor`. Import `airflow.sdk.DAG` and
  `airflow.providers.standard.operators.bash.BashOperator`. An Airflow 2
  import still loads and only warns. Detect: `DeprecatedImportWarning`, or
  ``Command `airflow webserver` has been removed``.
- **In a test, read `dagbag.dags[dag_id]`, not `DagBag.get_dag`.** `get_dag`
  queries the metadata database, which a test does not create. Detect:
  `(sqlite3.OperationalError) no such table: dag`.
- **On a Linux host the scheduler needs `group_add` with the Docker socket's
  group id.** On Docker Desktop the socket is `root:root 660` and the
  `airflow` user is in group `0`; on Linux the socket belongs to the `docker`
  group. Detect: `permission denied while trying to connect to the Docker
  daemon socket`.
- **Do not parse `airflow` CLI output in a script.** Warnings land on stdout
  and break `-o plain`. Read the `dag_run` and `task_instance` tables of
  `/opt/airflow/airflow.db` instead. Detect: `Could not import graphviz` in
  the parsed output.
