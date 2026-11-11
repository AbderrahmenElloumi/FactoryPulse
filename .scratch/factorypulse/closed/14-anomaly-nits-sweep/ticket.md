# 14: Anomaly nits sweep

**What to build:** the minor findings from the ticket 08 review that were deferred. Each one is small, and nothing here changes what a contract-valid lake scores. Source: `.scratch/factorypulse/closed/08-anomaly-detection/review.md`.

**Blocked by:** 08 Anomaly detection.

Status: `closed`

- [x] A NaN mean or standard deviation gives no score, not a NaN that is classified as nominal. Today `src/factorypulse/anomaly_core.py` `z_score` lets NaN past `stddev <= 0.0`. The job also drops a NaN hourly average, not only a null one (`spark/anomaly_detection.py`, the `isNotNull` filter). Ingestion cannot produce a NaN today, because `validator.py` rejects it, so this guard is defensive. Each branch has a test.
- [x] The score table's key columns live next to its other columns: move `ANOMALY_SCORE_KEYS` from `spark/anomaly_detection.py` to `src/factorypulse/analytics.py`, and update the imports in the tests.
- [x] `tests/test_anomaly_core.py` imports `NOMINAL`, `WARNING` and `CRITICAL` from `anomaly_core` instead of unpacking `STATUSES` again. A test pins that `STATUSES` is in severity order, mildest first, because `machine_status` depends on that order.
- [x] The job's closing log line counts the merged rows without running the whole UDF pipeline a second time. Today `scores.count()` runs after the merge and counts the rows before `dropDuplicates`.
- [x] The bar for "known-normal machines score low" is written down: over the known-normal windows, the critical count is at most the 99.9% Poisson quantile of the expected chance count, derived from `Z_CRITICAL` and each row's count of baseline windows. Say so in the test.
- [x] `MIN_BASELINE_WINDOWS` is checked against a second fixture seed, so the value of 12 is shown not to be luck of seed 8. The labelled-fixture tests pass on both seeds.
- [x] The opt-in note in `tests/test_anomaly_detection.py` gives the real run time (about 45 s, not "about two minutes").

## Current state

Decisions later tickets depend on:

- `merge_into_delta` returns the rows its MERGE inserted or updated, read from the MERGE's own metrics. A job logs that number instead of counting its source frame.
- "Score low" is a chance bar, not "never critical". Over the known-normal windows (the normal machines' windows, and the spiked machines' windows before the spike), the critical count is at most the 99.9% Poisson quantile of the expected chance count. Each row adds twice the upper tail of Student's t with n - 1 degrees of freedom beyond `Z_CRITICAL / sqrt(1 + 1/n)`, where n is the row's count of baseline windows. The bar moves with `Z_CRITICAL` and `MIN_BASELINE_WINDOWS`, so the test hardcodes no threshold. The test helpers need no `scipy`.
- The labelled-fixture tests run on seeds 8 and 2026. The fixture's hourly mart is written with pyarrow, so a NaN average stays NaN instead of null.
- `MIN_BASELINE_WINDOWS = 12` is a design choice. `test_a_thinner_baseline_calls_more_normal_readings_critical` pins its rationale; the fixture cannot tell 12 from 4.

## Log

2026-11-08 · triage · 76af654 · created from review 08 findings S2, S3, S5, S7, P3, P4, P5 · .scratch/factorypulse/closed/08-anomaly-detection/review.md
2026-11-10 · impl · ede5f07 · blocked on the second-seed item; other items done · -
2026-11-10 · review · f6d2d29 · block (P1) · .scratch/factorypulse/closed/14-anomaly-nits-sweep/review.md
2026-11-10 · triage · 24ba338 · bar for "score low" decided; closed-form tail; fix all minors; contract item 5 corrected: stale bar; P2 fixed in Current state · .scratch/factorypulse/closed/14-anomaly-nits-sweep/review.md
2026-11-10 · fix · 0cebba5 · fixed P1, P3, S1, S2, S3, S4, S5, S6 · .scratch/factorypulse/closed/14-anomaly-nits-sweep/review.md
2026-11-10 · rereview · - · pass · fixed P1, P3, S1, S2, S3, S4, S5, S6 · S7, S8, P4 open, no ticket · .scratch/factorypulse/closed/14-anomaly-nits-sweep/review.md
