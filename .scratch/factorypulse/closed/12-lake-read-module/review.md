---
ticket: .scratch/factorypulse/closed/12-lake-read-module/ticket.md
verdict: pass
---

# Review: ticket 12 — Lake read module

**Final verdict:** pass, on the second re-review of `3343083` (range `776099f..3343083`, a test-only fix round). Production code is unchanged since `15acab1`, so the first review's live MinIO check still holds.

**Standards:** no hard violations. The `TABLE_COLUMNS` lock `major` is fixed. Environment handling and test-helper judgement calls stay open as `minor` (S1-S8).

**Spec:** all five checklist items hold. Both propagation `major` findings (a non-`TableNotFoundError` failure, then a plain `DeltaError`) are fixed. Endpoint, credential and lock-strength edge cases stay open as `minor` (P1-P6).

## Open findings

- **S1 · minor · 2026-11-07** — open, no ticket. `lake.py` and `spark/common.py` both read `MINIO_ENDPOINT`, with different defaults: `localhost:9000` (`src/factorypulse/lake.py:28`) and `minio:9000` (`spark/common.py:60`). Make the two defaults deliberate, or say why they differ.
- **S2 · minor · 2026-11-07** — open, no ticket. `lake.py` reads `os.environ` directly (`src/factorypulse/lake.py:28,40,94`), while its neighbours take an injected mapping (`analytics.lake_root(env)`, `spark_conf(env)`). An `env` parameter would match and cut `monkeypatch` from the tests.
- **S3 · minor · 2026-11-07** — open, no ticket. `LakeTableMissing.uri` and `LakeColumnsMissing.uri` (`src/factorypulse/lake.py:57-60,66-71`): `CONTEXT.md` calls this a **Lake Path**, and `analytics.py` uses `*_path`. Consider `path`.
- **S4 · minor · 2026-11-07** — open, no ticket. The local versus object-store decision is made by string prefix twice (`src/factorypulse/lake.py:96-99`). Fine at this size.
- **S5 · minor · 2026-11-07** — open, no ticket. `_UnreachableDeltaTable` has the same shape as `_RecordingDeltaTable`, and its test patches `deltalake.DeltaTable` inline instead of through a fixture (`tests/test_lake.py:206-221` against `:169-189`). One stand-in that takes the exception to raise would serve both.
- **S6 · minor · 2026-11-07** — open, no ticket. `test_model_sql_column_lists_match_the_column_contracts` asserts three things (every model has declared columns, no key is unregistered, each declared column is in the model SQL); its name says only the last (`tests/test_dbt_project.py:117`). "Column contracts" also overloads the glossary's **Event Contract**.
- **S7 · minor · 2026-11-07** — open, no ticket. The Delta log layout is written inline: `tmp_path / "dim_machine" / "_delta_log" / "00000000000000000000.json"` (`tests/test_lake.py:245`). A `_first_commit(table_dir)` helper would name it.
- **S8 · minor · 2026-11-07** — open, no ticket. `from deltalake.exceptions import DeltaError` is a local import (`tests/test_lake.py:241`) in a module that already imports `deltalake` at the top (`:15`). The deferred-import reason applies to `lake.py`, not to the tests.
- **P1 · minor · 2026-11-07** — open, no ticket. An endpoint with a scheme (`http://minio:9000`) parses its host as `http`, skips the rewrite and yields `http://http://...` (`src/factorypulse/lake.py:28-29`). The docstring and compose say `host:port`; a guard or a clear error would make the misconfiguration obvious.
- **P2 · minor · 2026-11-07** — open, no ticket. Only `true` (any case) turns on `MINIO_SECURE`; `1` and `yes` mean plain HTTP (`src/factorypulse/lake.py:40`). Matches `.env.example`.
- **P3 · minor · 2026-11-07** — open, no ticket. Missing credentials become `""` without a warning (`src/factorypulse/lake.py:43-44`); the failure surfaces later as a privileges `OSError`.
- **P4 · minor · 2026-11-07** — open, no ticket. The registry lock is one-directional: it checks that each declared column appears in the model SQL, not that every selected column is declared (`tests/test_dbt_project.py:127-130`). A declared tuple that drops a selected column passes. The key checks compare `TABLE_COLUMNS` with the registry, not with the dbt models, so a Spark-written table's columns get no SQL check.
- **P5 · minor · 2026-11-07** — open, no ticket. The same loop passes without checking anything if `ANALYTICS_MODELS` is empty (`tests/test_dbt_project.py:127`).
- **P6 · minor · 2026-11-07** — open, no ticket. `pytest.raises(DeltaError)` has no `match` (`tests/test_lake.py:248`), so an unrelated `DeltaError` from the fixture setup would satisfy it. `match="Kernel error"` would pin the cause.

## Coverage

Checklist item to test (`tests/test_lake.py` unless named):

| Checklist item | Tests |
| --- | --- |
| 1. Declared columns in declared order | `test_read_table_returns_declared_columns_in_declared_order`, `test_raw_lake_reads_as_the_event_contract_fields`; `tests/test_dbt_project.py::test_model_sql_column_lists_match_the_column_contracts` |
| 2. Table not built raises a named, catchable error | `test_table_that_has_not_been_built_raises_a_named_error`, `test_directory_without_a_delta_log_counts_as_not_built`; contrast `test_built_table_with_no_rows_reads_as_empty_frame_not_an_error` |
| 3. Environment in one place, container versus host | `test_container_reaches_storage_by_service_name`, `test_host_process_reaches_the_service_name_on_localhost` (port carry-over), `test_host_process_keeps_an_endpoint_that_is_not_the_service_name`, `test_host_process_defaults_to_localhost_when_no_endpoint_is_set`, `test_secure_storage_uses_https_and_refuses_plain_http`, `test_default_source_is_the_object_store_lake_with_storage_options` |
| 4. Local Delta directory as the source | every fixture read above; `test_local_directory_source_gets_no_storage_options` |
| 5. Import without the Delta reader | `test_module_imports_where_the_delta_reader_is_not_installed` |

Rejection branches and error paths:

- Undeclared name raises `ValueError` before any read: `test_table_without_declared_columns_is_rejected_before_any_read`.
- `TableNotFoundError` becomes `LakeTableMissing`: the two not-built tests above.
- An `OSError` (credentials, bucket, network) propagates: `test_read_failure_other_than_a_missing_table_propagates`.
- A plain `DeltaError` from a built table (corrupt log, unsupported reader version) propagates: `test_built_table_that_cannot_be_read_is_not_reported_as_not_built[_corrupt_the_log]`, `[_require_an_unsupported_reader]`.
- `s3a://` becomes `s3://` with storage options: `test_default_source_is_the_object_store_lake_with_storage_options`.
- `TABLE_COLUMNS` covers every dbt model and holds no unregistered key: `tests/test_dbt_project.py::test_model_sql_column_lists_match_the_column_contracts`.

Live check at `15acab1`, against a throwaway MinIO from a host process: the endpoint rewrite, a declared-column read and `LakeTableMissing` on S3 all held; wrong credentials, a missing bucket and an unreachable port each raised `OSError`. Host suite at `3343083`: 165 passed, 2 skipped.
