-- Hourly per-machine aggregates: the mart the dashboard, the anomaly scorer
-- and the data-quality checks read.
--
-- One row per machine per UTC hour. Sensor statistics are pivoted into fixed
-- columns (an average per sensor type) rather than left long, so a KPI query
-- reads one row instead of self-joining four. A machine-hour is a real grain
-- even when a machine only reported some of its sensors, hence the nullable
-- per-sensor columns and the always-present counts.
--
-- machine_hour_key is the surrogate key: Spark has no enforced primary key,
-- so uniqueness is asserted on this column instead of on the (machine_id,
-- hour_start) pair.
--
{%- set lake_root = var('lake_root', 's3a://' ~ env_var('MINIO_BUCKET', 'factorypulse') ~ '/delta') -%}

{{ config(
    materialized='table',
    file_format='delta',
    location_root=lake_root
) }}

with readings as (

    select
        machine_id,
        site_id,
        sensor_type,
        value,
        status,
        date_trunc('hour', event_ts) as hour_start
    from {{ ref('fct_sensor_readings_clean') }}

),

hourly as (

    select
        machine_id,
        hour_start,
        min(site_id) as site_id,
        count(*) as reading_count,
        sum(case when status = 'nominal' then 1 else 0 end) as nominal_count,
        sum(case when status = 'warning' then 1 else 0 end) as warning_count,
        sum(case when status = 'critical' then 1 else 0 end) as critical_count,
        round(avg(case when sensor_type = 'temperature' then value end), 4) as temperature_avg,
        round(max(case when sensor_type = 'temperature' then value end), 4) as temperature_max,
        round(avg(case when sensor_type = 'vibration' then value end), 4) as vibration_avg,
        round(max(case when sensor_type = 'vibration' then value end), 4) as vibration_max,
        round(avg(case when sensor_type = 'pressure' then value end), 4) as pressure_avg,
        round(max(case when sensor_type = 'pressure' then value end), 4) as pressure_max,
        round(avg(case when sensor_type = 'humidity' then value end), 4) as humidity_avg,
        round(max(case when sensor_type = 'humidity' then value end), 4) as humidity_max
    from readings
    group by machine_id, hour_start

)

select
    concat(machine_id, '@', date_format(hour_start, 'yyyy-MM-dd HH:00:00')) as machine_hour_key,
    machine_id,
    site_id,
    hour_start,
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
from hourly
