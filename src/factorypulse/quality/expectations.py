"""The named quality checks of every checked lake table (ticket 07).

A check is plain data: a human-readable name, the Great Expectations
expectation class that decides it, and that expectation's arguments. Nothing
here imports Great Expectations, so the report mapping is testable without it.

Every allowed value, unit and range comes from ``factorypulse.contract``
(ADR 0001): no check spells a status, a unit or a bound of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Tuple

from factorypulse import analytics, contract


@dataclass(frozen=True)
class Check:
    """One named, falsifiable assertion about a table."""

    name: str
    expectation: str
    kwargs: Mapping[str, Any] = field(default_factory=dict)
    # (column, value): the check applies only to rows where column == value.
    where: Optional[Tuple[str, Any]] = None


@dataclass(frozen=True)
class Outcome:
    """A runner's verdict on one check, with the evidence behind a failure."""

    check: str
    success: bool
    detail: str = ""


# Reads a lake table by name; raises the lake read module's named errors.
Reader = Callable[[str], Any]


def _not_null(columns) -> Tuple[Check, ...]:
    return tuple(
        Check(f"{column} is never null", "ExpectColumnValuesToNotBeNull", {"column": column})
        for column in columns
    )


def _at_least_one_row() -> Check:
    return Check("has at least one row", "ExpectTableRowCountToBeBetween", {"min_value": 1})


def _event_vocabulary() -> Tuple[Check, ...]:
    """Allowed values, unit agreement and operating ranges of a reading."""
    checks = [
        Check(
            "sensor_type is a contract sensor type",
            "ExpectColumnValuesToBeInSet",
            {"column": "sensor_type", "value_set": list(contract.SENSOR_TYPES)},
        ),
        Check(
            "unit is a contract unit",
            "ExpectColumnValuesToBeInSet",
            {"column": "unit", "value_set": sorted(contract.ALLOWED_UNITS)},
        ),
        Check(
            "status is a contract status",
            "ExpectColumnValuesToBeInSet",
            {"column": "status", "value_set": list(contract.STATUSES)},
        ),
        Check(
            "unit matches its sensor_type",
            "ExpectColumnPairValuesToBeInSet",
            {
                "column_A": "sensor_type",
                "column_B": "unit",
                "value_pairs_set": sorted(contract.SENSOR_UNITS.items()),
            },
        ),
    ]
    for sensor, (low, high) in contract.SENSOR_RANGES.items():
        checks.append(
            Check(
                f"{sensor} value is within {low:g} to {high:g}",
                "ExpectColumnValuesToBeBetween",
                {"column": "value", "min_value": low, "max_value": high},
                where=("sensor_type", sensor),
            )
        )
    return tuple(checks)


def _raw_checks(read: Reader) -> Tuple[Check, ...]:
    raw = read(analytics.RAW_EVENTS_TABLE)
    # The site each machine first reports from, the way dim_machine picks it
    # (min(site_id)). A reading from any other site means the machine reports
    # from two sites, which dim_machine's group by would hide.
    machine_site = raw.groupby("machine_id")["site_id"].min()
    return (
        _at_least_one_row(),
        *_not_null(contract.EVENT_FIELDS),
        *_event_vocabulary(),
        Check(
            "each machine reports from one site",
            "ExpectColumnPairValuesToBeInSet",
            {
                "column_A": "machine_id",
                "column_B": "site_id",
                "value_pairs_set": sorted(machine_site.items()),
            },
        ),
    )


def _fct_checks(read: Reader) -> Tuple[Check, ...]:
    raw_events = read(analytics.RAW_EVENTS_TABLE)["event_id"].dropna().unique()
    # The raw lake may hold a replayed event twice; the fact keeps one row per
    # event, and which copy survives a same-ts replay is arbitrary (the copies
    # are identical). So the row count is bounded by the raw distinct events,
    # not compared with any particular copy. The raw lake only grows, so the
    # bound holds while the streamer keeps appending after the dbt build.
    return (
        _at_least_one_row(),
        Check(
            f"has no more rows than {analytics.RAW_EVENTS_TABLE} has events",
            "ExpectTableRowCountToBeBetween",
            {"max_value": len(raw_events)},
        ),
        *_not_null(analytics.FCT_READING_COLUMNS),
        Check("event_id is unique", "ExpectColumnValuesToBeUnique", {"column": "event_id"}),
        Check(
            f"every event_id is in {analytics.RAW_EVENTS_TABLE}",
            "ExpectColumnValuesToBeInSet",
            {"column": "event_id", "value_set": sorted(raw_events)},
        ),
        *_event_vocabulary(),
    )


def _against_the_fact(read: Reader) -> Tuple[Check, ...]:
    """A model built from the clean fact covers its machines and readings.

    The dbt ``relationships`` and ``unique`` tests on these models cannot fail:
    the model is grouped from the fact. These can: a model that drops or
    invents a machine, or loses or double-counts a reading, fails them.
    """
    fct = read(analytics.FCT_SENSOR_READINGS_CLEAN)
    source = analytics.FCT_SENSOR_READINGS_CLEAN
    return (
        Check(
            f"machine_id values match {source}",
            "ExpectColumnDistinctValuesToEqualSet",
            {"column": "machine_id", "value_set": sorted(fct["machine_id"].dropna().unique())},
        ),
        Check(
            f"reading_count sums to the {source} row count",
            "ExpectColumnSumToBeBetween",
            {"column": "reading_count", "min_value": len(fct), "max_value": len(fct)},
        ),
    )


def _dim_checks(read: Reader) -> Tuple[Check, ...]:
    return (
        _at_least_one_row(),
        *_not_null(analytics.MACHINE_DIM_COLUMNS),
        *_against_the_fact(read),
        Check(
            f"sensor_type_count is within 1 to {len(contract.SENSOR_TYPES)}",
            "ExpectColumnValuesToBeBetween",
            {"column": "sensor_type_count", "min_value": 1, "max_value": len(contract.SENSOR_TYPES)},
        ),
    )


def _mart_checks(columns: Tuple[str, ...]) -> Callable[[Reader], Tuple[Check, ...]]:
    # Per-sensor statistics are null for an hour or week without that sensor;
    # every other column is required.
    statistics = {
        f"{sensor}_{stat}": bounds
        for sensor, bounds in contract.SENSOR_RANGES.items()
        for stat in ("avg", "max")
    }

    def checks(read: Reader) -> Tuple[Check, ...]:
        return (
            _at_least_one_row(),
            *_not_null(column for column in columns if column not in statistics),
            *_against_the_fact(read),
            *(
                Check(
                    f"{column} is within {low:g} to {high:g}",
                    "ExpectColumnValuesToBeBetween",
                    {"column": column, "min_value": low, "max_value": high},
                )
                for column, (low, high) in statistics.items()
            ),
        )

    return checks


_DEFINITIONS: Mapping[str, Callable[[Reader], Tuple[Check, ...]]] = {
    analytics.RAW_EVENTS_TABLE: _raw_checks,
    analytics.DIM_MACHINE: _dim_checks,
    analytics.FCT_SENSOR_READINGS_CLEAN: _fct_checks,
    analytics.MRT_MACHINE_HOURLY: _mart_checks(analytics.MACHINE_HOURLY_COLUMNS),
    analytics.MRT_MACHINE_WEEKLY: _mart_checks(analytics.MACHINE_WEEKLY_COLUMNS),
}

CHECKED_TABLES: Tuple[str, ...] = tuple(_DEFINITIONS)


def checks_for(name: str, read: Reader) -> Tuple[Check, ...]:
    """The checks of table ``name``, in report order.

    ``read`` loads any lake table the checks compare against. Raises
    ``ValueError`` for a table with no checks.
    """
    if name not in _DEFINITIONS:
        raise ValueError(f"{name!r} has no quality checks: {CHECKED_TABLES}")
    return _DEFINITIONS[name](read)
