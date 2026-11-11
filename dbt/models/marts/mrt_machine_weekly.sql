-- Weekly per-machine aggregates: a real second grain over the hourly mart.
--
-- One row per machine per ISO week. The week starts on Monday 00:00 UTC
-- (`date_trunc('week', ...)`), and `iso_year`/`iso_week` carry the ISO-8601
-- labels, so the year boundary is correct even when 1 January falls in the
-- previous ISO year.
--
-- Rolling up from `mrt_machine_hourly` (rather than re-reading the raw lake)
-- keeps one aggregation path: the weekly mart inherits the hourly mart's
-- deduplication and per-sensor pivoting. Averages are the mean of the hourly
-- averages; maxima are the maximum over the week.
--
-- machine_week_key is the surrogate key: Spark has no enforced primary key,
-- so uniqueness is asserted on this deterministic column instead of on the
-- (machine_id, week_start) pair. The model is materialized as a table, so a
-- re-run replaces the same machine-week rows rather than appending.
--
-- The weekly DAG builds this model alone (`--select tag:weekly`, ticket 06),
-- and every dbt run starts from an empty session catalog, so a `ref()` to a
-- table the run did not build resolves to nothing. The hourly mart is read
-- from its lake location instead; the `ref()` inside the path keeps the
-- lineage, so a full build still orders the hourly mart first.
--
{%- set lake_root = var('lake_root', 's3a://' ~ env_var('MINIO_BUCKET', 'factorypulse') ~ '/delta') -%}

{{ config(
    materialized='table',
    file_format='delta',
    location_root=lake_root,
    tags=['weekly']
) }}

with readings as (

    select
        machine_id,
        site_id,
        date_trunc('week', hour_start) as week_start,
        reading_count,
        nominal_count,
        warning_count,
        critical_count,
        temperature_avg,
        temperature_max,
        vibration_avg,
        vibration_max,
        pressure_avg,
        pressure_max,
        humidity_avg,
        humidity_max
    from delta.`{{ lake_root }}/{{ ref('mrt_machine_hourly').identifier }}`

),

weekly as (

    select
        machine_id,
        week_start,
        min(site_id) as site_id,
        sum(reading_count) as reading_count,
        sum(nominal_count) as nominal_count,
        sum(warning_count) as warning_count,
        sum(critical_count) as critical_count,
        round(avg(temperature_avg), 4) as temperature_avg,
        max(temperature_max) as temperature_max,
        round(avg(vibration_avg), 4) as vibration_avg,
        max(vibration_max) as vibration_max,
        round(avg(pressure_avg), 4) as pressure_avg,
        max(pressure_max) as pressure_max,
        round(avg(humidity_avg), 4) as humidity_avg,
        max(humidity_max) as humidity_max
    from readings
    group by machine_id, week_start

)

select
    concat(machine_id, '@', date_format(week_start, 'yyyy-MM-dd')) as machine_week_key,
    machine_id,
    site_id,
    -- The Thursday inside the week always sits in the ISO week-year, so this
    -- is the ISO-8601 year even when the Monday falls in the previous year.
    year(date_add(week_start, 3)) as iso_year,
    weekofyear(week_start) as iso_week,
    week_start,
    reading_count,
    nominal_count,
    warning_count,
    critical_count,
    temperature_avg,
    temperature_max,
    vibration_avg,
    vibration_max,
    pressure_avg,
    pressure_max,
    humidity_avg,
    humidity_max
from weekly
