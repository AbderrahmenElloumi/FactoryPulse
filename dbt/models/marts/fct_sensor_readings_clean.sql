-- Cleaned sensor readings: one row per event, typed and deduplicated.
--
-- This is the only model that touches the raw lake. Everything downstream
-- reads this table, so the contract's string timestamp and stringly-typed
-- JSON values become real types exactly once.
--
{%- set lake_root = var('lake_root', 's3a://' ~ env_var('MINIO_BUCKET', 'factorypulse') ~ '/delta') -%}
{%- set raw_events_path = var('raw_sensor_events_path', lake_root ~ '/raw_sensor_events') -%}
{%- set raw_events = ref('raw_sensor_events_fixture') if target.name == 'fixture' else 'delta.`' ~ raw_events_path ~ '`' -%}

{{ config(
    materialized='table',
    file_format='delta',
    location_root=lake_root
) }}

with typed as (

    select
        event_id,
        -- The contract's canonical ts is ISO-8601 UTC with a trailing 'Z'.
        -- The Python validator normalizes that same 'Z' before its calendar
        -- check (see docs/agents/gotchas/spark.md); Spark needs the same
        -- normalization before it will cast the string to a timestamp.
        cast(regexp_replace(ts, 'Z$', '') as timestamp) as event_ts,
        site_id,
        machine_id,
        sensor_type,
        cast(value as double) as value,
        unit,
        status
    -- No null filter, on purpose. Both ingestion paths write only rows the
    -- contract validator accepted, and the validator rejects a null in every
    -- contract field, so a null here means the ingestion boundary broke. The
    -- row is let through and the not_null tests in schema.yml fail the build
    -- on it: a tripwire, not silent data loss. Filtering a column would drop
    -- the row unseen and leave that column's not_null test unable to fail.
    from {{ raw_events }}

),

-- The lake is append-only from two directions (streaming + the batch MERGE),
-- so a replayed Kafka offset or an overlapping backfill can leave the same
-- event_id behind twice. Keep the newest version of each event, drop the rest.
--
-- A tie on event_ts is broken arbitrarily, on purpose. The real duplicate is a
-- streaming replay: the same event_id with the same ts and the same payload,
-- so either copy is the right one. The quality gate (ticket 07) asserts what
-- matters instead of which copy wins: event_id is unique here, every event_id
-- comes from the raw lake, and there are no more rows than raw distinct events.
deduplicated as (

    select
        *,
        row_number() over (partition by event_id order by event_ts desc) as _recency_rank
    from typed

)

select
    event_id,
    event_ts,
    site_id,
    machine_id,
    sensor_type,
    value,
    unit,
    status
from deduplicated
where _recency_rank = 1
