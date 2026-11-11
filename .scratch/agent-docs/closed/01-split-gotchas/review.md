---
ticket: .scratch/agent-docs/closed/01-split-gotchas/ticket.md
verdict: pass
---

# Review: ticket 01 — Split and verify the gotchas

**Final verdict:** pass, on the re-review of `261830a` (range `bff8579..261830a`).

**Standards:** every entry in the touched area files has a rule, a reason and a detect part that the named image prints or the named test checks; all entries fit 5 lines and 80 columns.

**Spec:** every checklist item is met; two `minor` outcome questions stay open for triage.

## Open findings

- **P1 · minor · 2026-11-09** — triaged 2026-11-09: keep the entry. Ticket 08's documentation pass rewrites it around the silent column drop, a lasting trap no test catches. The `CREATE TABLE … LOCATION` entry (`docs/agents/gotchas/delta.md:7-10`) is kept although the ticket's delete criterion applies: the fact is in the comment at `spark/common.py:178-180`, the only `CREATE TABLE` site is inside `merge_into_delta`, and `test_merge_into_delta_creates_a_new_table_with_the_source_columns` pins the column list. Ticket 08's open checkbox (`.scratch/factorypulse/issues/08-anomaly-detection.md:38`) edits this entry, so triage decides between deleting it (and amending ticket 08) and recording a lasting reason to keep it.
- **P2 · minor · 2026-11-09** — open, no ticket. The Kafka artifact name entry is deleted on `test_jar_packages_cover_kafka_delta_and_s3` (`tests/test_spark_common.py:100`), which reads `spark/common.py::PACKAGES_CSV`. No runtime path uses that constant; the live lists are `compose.yaml:40` and `docker/spark.Dockerfile:18`, and no test reads them. Restore the entry in `spark.md` with the Ivy error as its detect, or point the test at the live lists.

## Coverage

Doc ticket: no behaviour to test. Checklist item to proof:

| Checklist item | Proof |
| --- | --- |
| `gotchas/` holds `README.md` (entry rule, then index) and the area files; no file for an empty area | `docs/agents/gotchas/README.md:5-31`; six area files, no `quality.md` |
| Every old entry checked, one outcome each | Commit message of `f6a800c`; detect strings checked in `factorypulse/airflow:3.4.0`, `factorypulse/spark:3.5-dbt` (dbt 1.8.7), `apache/spark:3.5.4` and `minio/minio:RELEASE.2025-04-22T22-12-26Z`; named tests exist; P1, P2 open |
| Ticket-specific is not a reason to delete | Kept entries carry no ticket number or story |
| Verification habit deleted | Absent from `docs/agents/gotchas/` |
| Commit message lists each outcome | `git show -s f6a800c` |
| References checked | `dbt/profiles.yml:17` reference removed; `scripts/dbt-entrypoint.sh:8` and `dbt/models/marts/fct_sensor_readings_clean.sql:23` name `spark.md` |
| `docs/agents/gotchas.md` deleted | `git show --stat f6a800c` |
| `AGENTS.md` points to `README.md` only | `AGENTS.md:21` |

Host suite: `.venv/Scripts/python.exe -m pytest -q` gives 358 passed, 19 skipped.
