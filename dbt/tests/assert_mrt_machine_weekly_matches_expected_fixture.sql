-- Fixture assertion for the weekly mart: every machine-week the fixture
-- produces must equal the hand-computed expectation, and neither side may
-- have a machine-week the other lacks.
--
-- A singular test fails by returning rows, so an empty result is a pass. It
-- only runs against the `fixture` target: the real lake holds real numbers,
-- and comparing those to a fixture would be meaningless. Run it with
-- `scripts/dbt.sh fixture`.
--
{{ config(enabled=(target.name == 'fixture')) }}

with actual as (

    select
        machine_week_key,
        machine_id,
        site_id,
        cast(iso_year as int) as iso_year,
        cast(iso_week as int) as iso_week,
        date_format(week_start, 'yyyy-MM-dd HH:mm:ss') as week_start,
        cast(reading_count as bigint) as reading_count,
        cast(nominal_count as bigint) as nominal_count,
        cast(warning_count as bigint) as warning_count,
        cast(critical_count as bigint) as critical_count,
        cast(temperature_avg as double) as temperature_avg,
        cast(temperature_max as double) as temperature_max,
        cast(vibration_avg as double) as vibration_avg,
        cast(vibration_max as double) as vibration_max,
        cast(pressure_avg as double) as pressure_avg,
        cast(pressure_max as double) as pressure_max,
        cast(humidity_avg as double) as humidity_avg,
        cast(humidity_max as double) as humidity_max
    from {{ ref('mrt_machine_weekly') }}

),

expected as (

    select
        machine_week_key,
        machine_id,
        site_id,
        cast(iso_year as int) as iso_year,
        cast(iso_week as int) as iso_week,
        week_start,
        cast(reading_count as bigint) as reading_count,
        cast(nominal_count as bigint) as nominal_count,
        cast(warning_count as bigint) as warning_count,
        cast(critical_count as bigint) as critical_count,
        cast(temperature_avg as double) as temperature_avg,
        cast(temperature_max as double) as temperature_max,
        cast(vibration_avg as double) as vibration_avg,
        cast(vibration_max as double) as vibration_max,
        cast(pressure_avg as double) as pressure_avg,
        cast(pressure_max as double) as pressure_max,
        cast(humidity_avg as double) as humidity_avg,
        cast(humidity_max as double) as humidity_max
    from {{ ref('expected_mrt_machine_weekly') }}

)

select
    coalesce(actual.machine_week_key, expected.machine_week_key) as machine_week_key,
    actual.machine_id as actual_machine_id,
    expected.machine_id as expected_machine_id,
    actual.reading_count as actual_reading_count,
    expected.reading_count as expected_reading_count
from actual
full outer join expected
    on actual.machine_week_key = expected.machine_week_key
where not (
    actual.machine_id <=> expected.machine_id
    and actual.site_id <=> expected.site_id
    and actual.iso_year <=> expected.iso_year
    and actual.iso_week <=> expected.iso_week
    and actual.week_start <=> expected.week_start
    and actual.reading_count <=> expected.reading_count
    and actual.nominal_count <=> expected.nominal_count
    and actual.warning_count <=> expected.warning_count
    and actual.critical_count <=> expected.critical_count
    -- Per-sensor statistics are floats: compared with a tolerance, and
    -- "both null" (no reading for that sensor in that week) counts as equal.
    and {{ floats_match([
        'temperature_avg', 'temperature_max',
        'vibration_avg', 'vibration_max',
        'pressure_avg', 'pressure_max',
        'humidity_avg', 'humidity_max',
    ]) }}
)
