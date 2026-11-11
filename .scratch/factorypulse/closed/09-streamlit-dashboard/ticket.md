# 09: Streamlit dashboard

**What to build:** the visual layer — a local Streamlit app reading the lake, showing machine-health KPIs, temperature/vibration trends, and an at-risk machines list driven by anomaly scores.

**Blocked by:** 08 Anomaly detection; 12 Lake read module.

Status: `closed`

- [x] Starting the app locally serves a dashboard that reads the lake.
- [x] It shows machine-health KPIs, temperature/vibration trends, and an at-risk machines list driven by anomaly scores.
- [x] It runs with one command and renders without a Spark process running.

## Current state

Decisions later tickets depend on:

- The app runs as the `streamlit` compose service, on its own Python image
  (no JVM). `docker compose up -d streamlit` starts MinIO and the app, and
  serves it on http://localhost:8501. The service has no profile.
- The dashboard reads `dim_machine`, `mrt_machine_hourly` and
  `mrt_anomaly_scores` through `lake.read_table`. A table that is not built,
  or that lacks a declared column, shows as one error naming it.
- The machine-health functions in `analytics.py` take frames and never import
  pandas, because the Spark image imports that module.
- A machine's health status is its `machine_status` in its latest scored
  window. A scored window has an anomaly score on at least one sensor type.
  A window with too few baseline windows has no score, so its nominal status
  is ignored. A machine whose latest window has no score keeps the health
  status of its last scored window.
- An at-risk machine is one whose health status is not nominal. The list
  shows the worst health status first. A status outside `contract.STATUSES`
  raises `ValueError`.
- The KPIs count machines tracked, machines by health status, and machines
  with no scored window. A machine with no scored window is in no health
  status count.
- The trends plot the hourly average of temperature and vibration per
  machine.

## Log

2026-11-10 · triage · - · design gaps recorded from garden review P6 · .scratch/garden/01-2026-11-10/review.md
2026-11-10 · impl · d311568 · all items done · -
2026-11-10 · review · 05af0b8 · block (P1) · .scratch/factorypulse/closed/09-streamlit-dashboard/review.md
2026-11-10 · fix · d5f6458 · fixed P1, S3 · .scratch/factorypulse/closed/09-streamlit-dashboard/review.md
2026-11-10 · rereview · - · pass · fixed P1; S3 rename fixed, its glossary question stays open · P2, P3, P4, S1, S2, S3 open, no ticket · .scratch/factorypulse/closed/09-streamlit-dashboard/review.md
