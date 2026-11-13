# FactoryPulse: IoT Predictive Maintenance Pipeline

Status: `ready-for-agent`

Module design was worked out in [`../design.md`](../design.md), frozen working
material; its decisions live in this spec and the tickets. The repository and release work lives in its own
feature directory, [`../repo-release/spec.md`](../repo-release/spec.md).

## Problem Statement

As an engineering student in my final year, I need a portfolio project that demonstrates I can build production-shaped data systems end-to-end. I already know Spark, Kafka, Python, SQL, and Docker, but I have no public artifact proving I can apply them together, and I haven't worked with the lakehouse, transformation, orchestration, data-quality, and streaming-analysis technologies that employers currently demand and will demand in the future. I also have a strict zero budget: I will not be charged by any cloud provider, now or later.

## Solution

Build **FactoryPulse**, a local-first, end-to-end IoT predictive maintenance pipeline that runs entirely in Docker on a laptop for `$0`. A Python simulator emits smart-factory sensor readings (temperature, vibration, pressure, humidity) into Kafka. A hybrid Spark pipeline (structured streaming for real-time + batch for historical) ingests events into a Delta Lake backed by MinIO (S3-compatible object storage). dbt transforms the raw lake into clean analytics tables. Airflow orchestrates the batch jobs. Great Expectations enforces data quality at ingestion and after transformation. A PySpark ML step scores anomalies on vibration/temperature. A Streamlit app lets anyone query the lake and visualize machine health. Everything is containerized and started with one command, and the repository is fully documented for interviewers.

## User Stories

### Simulator (Phase 1)

1. As an engineer, I want a Python simulator that emits realistic machine sensor readings, so that I have a reproducible data source without buying hardware.
2. As an engineer, I want readings for temperature, vibration, pressure, and humidity, so that the dataset supports a predictive-maintenance narrative.
3. As an engineer, I want each reading attributed to a specific `machine_id`, `site_id`, and sensor, so that readings are traceable to a machine.
4. As an engineer, I want the simulator to accept a target records-per-day, so that I can control data volume (default 10K/day).
5. As an engineer, I want deterministic reproduction via a random seed, so that tests and demos are repeatable.
6. As an engineer, I want occasional anomalous readings injected (spikes/drift), so that the anomaly detector has signal to find.
7. As an engineer, I want the simulator to publish directly to a Kafka topic, so that the pipeline is streaming-first from the source.
8. As an engineer, I want each event to carry a unique `event_id` and a UTC timestamp with millisecond precision, so that downstream deduplication and time-window analytics work.

### Ingestion (Phase 2)

9. As an engineer, I want a Spark structured-streaming job that consumes the Kafka topic, so that events flow into the lake in near real time.
10. As an engineer, I want a Spark batch job that can reprocess/backfill historical events, so that the pipeline supports both real-time and batch paradigms.
11. As an engineer, I want both paths to write to the same Delta Lake, so that streaming and batch results stay consistent.

### Lakehouse (Phase 3)

12. As an engineer, I want raw sensor events stored as a Delta table on MinIO, so that the data is versioned, time-travelable, and queryable.
13. As an engineer, I want the lake to support SQL reads through Spark, so that I can demonstrate lakehouse querying.
14. As an engineer, I want MinIO configured S3-compatibly, so that the object-storage skills transfer directly to production AWS environments.

### Transformation (Phase 4)

15. As an engineer, I want dbt SQL models that turn raw events into clean analytics tables (per-machine hourly aggregates, filtered nominal readings), so that the transformation logic is versioned and testable. The trailing baseline that anomaly scoring compares against is computed by the anomaly scoring job, not by dbt.
16. As an engineer, I want dbt to target the Delta lake, so that models run against the same storage used by Spark.

### Orchestration (Phase 5)

17. As an engineer, I want Airflow DAGs that schedule the batch and weekly-aggregation jobs, so that the pipeline runs on its own.

### Data quality (Phase 6)

18. As an engineer, I want Great Expectations suites that validate schema, value ranges, and missingness at ingestion and after transformation, so that bad data is caught and reported.
19. As an engineer, I want quality checks wired into the orchestrated pipeline, so that failures surface as pipeline events.

### Anomaly detection (Phase 7)

20. As an engineer, I want a PySpark ML job that scores anomalies on vibration and temperature windows, so that the pipeline demonstrates predictive-maintenance value.
21. As an engineer, I want anomaly scores joined into an analytics table, so that dashboards can show "machines at risk".

### Dashboard (Phase 8)

22. As an engineer, I want a Streamlit app that reads the lake and shows machine health KPIs, hourly temperature and vibration trends, and anomaly flags, so that interviewers can see results without running SQL.
23. As an engineer, I want the dashboard to run locally with one command, so that demos are low-friction.

### Delivery and DevOps (Phase 9)

24. As an engineer, I want the whole stack behind a single `docker compose up`, so that anyone can run the platform on a laptop with zero cloud spend.
25. As an engineer, I want a README with an architecture diagram, tech-stack rationale, and setup guide, so that a recruiter or interviewer understands the project in 10 minutes.
26. As an engineer, I want the repo private on GitHub initially, with the ability to make it public later, so that I control when it's seen.

## Implementation Decisions

- **Scope:** one event per sensor reading (a machine with N sensors emits N events per sampling interval). Running at 10K events/day keeps the dataset ~150 MB/month.
- **Event contract (single seam across all stages):**

```json
{
  "event_id": "uuid",
  "ts": "ISO8601 UTC, ms precision",
  "site_id": "string",
  "machine_id": "string",
  "sensor_type": "temperature|vibration|pressure|humidity",
  "value": "float",
  "unit": "celsius|g_pp|psi|percent",
  "status": "nominal|warning|critical"
}
```

- **Simulator:** Python, configurable records-per-day and seed, anomaly injection as occasional spikes/drift above normal ranges. Publishes JSON events to the `sensor-events` Kafka topic.
- **Kafka:** single-node Kafka in KRaft mode (no external ZooKeeper) via the `apache/kafka` image; the `sensor-events` topic is created by an init job on startup.
- **Spark:** spark-structured-streaming consumer writes `raw_sensor_events` Delta table; a batch job supports backfill. Both write through the same Delta path.
- **Object storage / lakehouse:** MinIO runs in Docker; Delta tables live under an S3a bucket (`factorypulse/`) using `hadoop-aws` + MinIO credentials. Resumé-relevant claim: "S3-compatible data lake". Small data means near-zero disk use.
- **Transformation:** dbt-spark configured with the Delta file format, targeting the same lake, models authored in SQL. Models: `dim_machine`, `fct_sensor_readings_clean`, `mrt_machine_hourly`, plus `mrt_machine_weekly` (machine × ISO week, rolled up from the hourly mart). "Weekly aggregation" in the orchestration story means the weekly mart, not a weekly re-run of the hourly mart.
- **Orchestration:** Airflow (LocalExecutor + SQLite metadata DB) in Docker, running a daily DAG (batch ingest, dbt run, quality checks) and a weekly DAG (weekly mart, quality checks). Airflow is a pure orchestrator: tasks are shell invocations of the existing compose services, so every task is reproducible by hand and the DAG owns no logic the command line lacks.
- **Data quality:** Great Expectations (version 1.x) suites over a pandas datasource, reading the Delta tables through the same `deltalake` path the dashboard uses, run in a lightweight container rather than the Spark one. Coverage is table-level (the table is built and stores every declared column, row count, the fact agrees with the raw lake, and dim_machine and both marts agree with the fact) and column-level (required columns never null, value ranges, allowed values, unique event_id, unit-to-sensor and machine-to-site agreement). Checks run at ingestion and post-dbt and produce a report naming every failed check. Row-level validation at the ingestion boundary remains the event contract's job.
- **Anomaly detection:** pure scoring functions classify each sensor's z-score into the contract's status vocabulary, and a machine's status is the worst status among its sensors; the PySpark job does the windowing and writes the result idempotently to `mrt_anomaly_scores`, keyed on machine, window, and sensor type. Each row carries the baseline mean, standard deviation, and count of the window it scores.
- **Dashboard:** Streamlit reads lake data through the shared lake read module, which owns the MinIO endpoint and credentials and raises a named error for a table that has not been built rather than rendering an empty chart; KPIs and trends are pure functions over frames, plotted with Plotly, no Spark needed at runtime. The app runs as a compose service.
- **Deployment:** single `compose.yaml` with services: kafka (KRaft, single node — no ZooKeeper), minio, minio-init, kafka-init (idempotent init jobs create the bucket and topic), producer, streamer, batch-ingest, dbt, query, query-analytics, anomaly-detection, airflow-init, airflow-webserver, airflow-scheduler, airflow-dag-processor, quality, streamlit. MinIO credentials come from the environment, templated in `.env.example` and interpolated by compose.
- **Repository:** two repositories, per [`../repo-release/spec.md`](../repo-release/spec.md): a private development repository and a public release repository fed by squashed commits. README with architecture diagram + setup + stack rationale. Resume frame: "IoT Predictive Maintenance Pipeline".

## Testing Decisions

- **What makes a good test here:** validate external, observable behavior at stage boundaries, not internal implementation. The single seam is the **event contract** above — every stage either produces or consumes it, so tests assert that the contract holds at each boundary.
- **Development workflow (TDD):** pure components (simulator generator, contract validator, aggregation logic, anomaly scorer) are built test-first — failing test, then implementation, then refactor — using the event contract as the shared fixture. The seam is the integration contract across stages; TDD drives how each component is written. Parameters such as the Baseline's length and the z-score thresholds come from the module under test, never from literals in tests.
- **Simulator:** pytest asserts emitted events validate against the contract (schema, ranges, units, valid status), that a fixed seed reproduces identical output, and that injected anomalies are present in expected proportions.
- **Contract validation util:** a shared validator used by tests and by the streaming/ingestion boundary; tested once against representative rows (valid, out-of-range, null field, bad unit, bad status).
- **dbt models:** dbt tests (not null, unique, accepted values) plus fixture-driven model tests for `mrt_machine_hourly` aggregations.
- **Great Expectations suites:** the expectations themselves double as living tests run inside the pipeline.
- **Anomaly detector:** pure scoring functions tested directly at the threshold boundaries, with seeded fixtures asserting that typical machines score low and injected anomalies score high; the Spark job is asserted through the table it writes, not through its internals.
- **Lake read module:** a fixture Delta table written to a local path is the second adapter, so `read_table` returns the declared columns and a missing table raises a named error rather than an empty frame. The seam is real because two things sit behind it.
- **Quality checks:** a fixture table containing one known-bad row fails with a named check; a clean table passes; the mapping from the checker's result to the report is tested against a substitute runner, so the report shape is verified without the checker installed.
- **Analytics registry:** the existing test locking the Python registry against the dbt models extends to every new mart, so a model and its declared columns cannot drift apart silently.
- **Orchestration:** the DAG file loads without errors and both DAGs expose the expected task chain; these tests run where Airflow is installed.
- **Prior art:** the contract, validator, simulator, Spark common layer, and dbt project suites already establish the pattern — assert observable behaviour at a stage boundary using the event contract as the shared fixture. Repository-wide invariant tests that read files and assert consistency (the dbt-model lock, the schema-sync test) are the model for anything that spans two representations of one fact.

## Out of Scope

- Real IoT hardware, firmware, or MQTT/broker protocols beyond Kafka.
- Any paid cloud service (S3/GCS/Azure, Athena/BigQuery, managed Airflow, Managed Spark). MinIO + local Docker only.
- Production observability (Prometheus/Grafana), multi-user auth, or a full CI/CD pipeline beyond a basic build check.
- ML model training/retraining, model registry, or tuning beyond a baseline anomaly score.
- Alerting/paging (SNS, PagerDuty), mobile apps, or a public API.
- Data volumes above ~100K events/day.

## Future Improvements (Roadmap)

Recorded as aspirational work to pick up once the current scope is implemented, tested, and demoed end to end. Not ordered; survey only. Each item will be scoped and ticketed via `/to-tickets` when the core project is complete.

- **MQTT / broker protocols:** ingest from real IoT hardware and edge devices by supporting MQTT alongside Kafka.
- **CI/CD:** a real CI pipeline (lint, unit tests, container image build) with delivery to a target environment once one exists.
- **Production observability:** Prometheus + Grafana dashboards for throughput, latency, and pipeline health; structured logging.
- **Alerting:** notify a human when a data-quality check fails or a machine crosses an anomaly threshold (email/webhook/incident tool).
- **Scale data volume:** raise throughput well past the current ~100K events/day cap and prove the design holds.
- **Cloud friendliness:** re-target the lake and compute to a real cloud provider once a budget exists; the MinIO/S3a-compatible path keeps that door open.
- **Scalability & distributability:** move from single-host compose toward distributed/clustered execution (a reason to revisit Kubernetes).
- **Security:** authentication and authorization, secrets management, encryption in transit and at rest, dependency and container scanning.
- **Better anomaly detection:** move beyond the baseline z-score toward stronger methods (e.g., Isolation Forest, autoencoder), with a model registry and retraining.

Items already named in Out of Scope remain out of scope for this build; this section is simply the record of where the project goes next.

## Further Notes

- **Build order** (mirrors the user stories): 1) simulator + contract, 2) Kafka + Spark streaming to Delta, 3) MinIO + lake layer, 4) dbt, 5) Airflow, 6) Great Expectations, 7) anomaly detection, 8) Streamlit, 9) Docker Compose + README. Each phase is independently demoable.
- **Cost rule:** no service runs that can't be torn down for free; every data artifact stays under ~1 GB on disk.
- The `$0`, local-first constraint is deliberate and worth stating in the README: it demonstrates containerization skill rather than "clicked a cloud console".
