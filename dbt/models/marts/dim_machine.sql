-- Machine dimension: one row per machine that has reported an event.
--
-- The event contract carries machine_id/site_id on every reading and nothing
-- else about a machine, so the dimension is derived from observed traffic:
-- where it reports from, when it was first and last seen, and how much it
-- reports. Downstream joins (anomaly scores, dashboard KPIs) hang off this.
--
{%- set lake_root = var('lake_root', 's3a://' ~ env_var('MINIO_BUCKET', 'factorypulse') ~ '/delta') -%}

{{ config(
    materialized='table',
    file_format='delta',
    location_root=lake_root
) }}

select
    machine_id,
    min(site_id) as site_id,
    min(event_ts) as first_seen_at,
    max(event_ts) as last_seen_at,
    count(*) as reading_count,
    count(distinct sensor_type) as sensor_type_count
from {{ ref('fct_sensor_readings_clean') }}
group by machine_id
