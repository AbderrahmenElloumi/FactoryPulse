# 07: Great Expectations data quality

**What to build:** data-quality guardrails — Great Expectations suites that validate raw ingestion and the dbt-clean tables (schema, value ranges, missingness, allowed status values), wired into the pipeline and producing reports that name failing checks.

**Blocked by:** 12 Lake read module; 13 dbt and test prefactoring.

Status: `closed`

- [x] GE suites validate the raw ingestion and the dbt-clean tables: schema, value ranges, missingness, allowed status values.
- [x] Validation runs as part of the pipeline and produces a report naming which checks failed.
- [x] Known-bad data fails the suite; good data passes.

## Current state

Decisions later tickets depend on:

- Every allowed value a check uses comes from `factorypulse.contract` (ADR 0001), and every column list from `factorypulse.analytics`.
- The checks run in their own Python image, not the Spark image (`test_quality_image_is_python_with_the_pinned_checker_not_spark`).
- A table that is not built, or that lacks a declared column, gives a failed named check: `<table> is built` or `<table> stores every declared column`. A check the runner returns no result for counts as failed. Nothing passes vacuously.
- The dbt `unique` and `relationships` tests cannot fail, because each model is grouped from the table it is tested against. The quality checks assert the property behind each one against a table the model is not derived from.
- The fact is compared with the raw lake through bounds and inclusion only, because the streamer keeps appending after the dbt build. The marts are compared with the fact. A stage holds only tables built together.

## Log

2026-09-10 · triage · 623463b · created · -
2026-09-23 · triage · 9c5cbd1 · ticket 05 review findings 1-6 parked here · -
2026-10-07 · impl · 855bc04 · two hand-written events run through the validator; no Great Expectations · -
2026-10-07 · triage · be98213 · closed with the criteria unmet · -
2026-10-13 · triage · da3af0b · reopened: no suite, no report, no pipeline stage · -
2026-10-13 · triage · 11bccc7 · ticket 05 findings 3-6 -> 13; blocked by 12 and 13 · -
2026-11-08 · impl · f66aee0 · quality gate over five tables, wired after ingestion and after dbt; host 239 passed, 2 skipped · -
2026-11-08 · review · 9ddce22 · pass · S1-S10, P2-P4 open, no ticket · P1 -> 06 · .scratch/factorypulse/closed/07-data-quality/review.md
2026-11-09 · impl · - · condensed and moved to closed/ by .scratch/agent-docs/issues/02-condense-closed-tickets.md · P1 fixed by ticket 06 · S8 merged into review 06 S-7 · .scratch/factorypulse/closed/07-data-quality/review.md
