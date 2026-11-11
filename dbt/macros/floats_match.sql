-- Compare float columns of two joined relations, for the fixture assertions.
--
-- Renders one condition per column, joined with `and`: the two values agree
-- within `tolerance`, or both are null. Both-null counts as a match because a
-- per-sensor statistic is null when the machine reported no reading for that
-- sensor in the period, and the expected seed spells that as an empty cell.
-- The coalesce also makes a one-sided null a definite mismatch: a bare
-- `abs(null - x) <= tolerance` is null, and `where not (...)` would then drop
-- the row instead of reporting it.
--
-- Usage: `and {{ floats_match(['temperature_avg', 'temperature_max']) }}`
{% macro floats_match(columns, actual='actual', expected='expected', tolerance=0.0001) -%}
    {%- for column in columns %}
    coalesce(
        abs({{ actual }}.{{ column }} - {{ expected }}.{{ column }}) <= {{ tolerance }},
        {{ actual }}.{{ column }} is null and {{ expected }}.{{ column }} is null
    ){% if not loop.last %} and{% endif %}
    {%- endfor %}
{%- endmacro %}
