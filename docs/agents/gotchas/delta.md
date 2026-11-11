# Delta gotchas

- **Write a Delta table through `common.merge_into_delta`, not a hand-written
  MERGE.** Delta rejects a source that repeats a key, and overlapping backfill
  snapshots repeat keys as a rule; the helper drops duplicates first.
  Detect: `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`.
- **A source column the existing table lacks is dropped without a warning.**
  The CREATE keeps the old schema and the MERGE drops the column (Delta 3.2.1),
  so a column added to `ANOMALY_SCORE_COLUMNS` never reaches an existing
  `mrt_anomaly_scores`. Rebuild the table, or check the schema in the write.
  Detect: the column is missing when the table is read back; no error is raised.
- **A fake of Delta in a test must enforce Delta's rules, not a dict's.** A
  fake that folds rows into `{key: row}` deduplicates by itself, so a test
  passes with the production fix deleted. Prove a merge test by deleting the
  production line it claims to prove. Detect:
  `test_merge_into_delta_accepts_a_duplicated_source_key_already_in_the_target`.
