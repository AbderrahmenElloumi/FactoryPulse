"""Great Expectations adapter for the quality seam (ticket 07).

Runs a table's checks as one Great Expectations 1.x suite over a pandas
dataframe in an ephemeral context, and maps each expectation result back to
the check that asked for it. Nothing is written to disk: no project
directory, no Data Docs. The report is ``quality.QualityReport``.
"""

from __future__ import annotations

import os
from typing import Any, Iterator, List, Sequence

from factorypulse.quality.expectations import Check, Outcome

# How many offending values a failure quotes as evidence.
SAMPLE = 5


def run(table: str, frame: Any, checks: Sequence[Check]) -> List[Outcome]:
    """One ``Outcome`` per check, decided by Great Expectations over ``frame``."""
    # Usage analytics would send events to Great Expectations' servers; a
    # local, $0 pipeline sends nothing anywhere.
    os.environ.setdefault("GX_ANALYTICS_ENABLED", "false")
    import great_expectations as gx
    import great_expectations.expectations as gxe
    from great_expectations.data_context.types.base import ProgressBarsConfig
    from great_expectations.expectations.row_conditions import Column

    context = gx.get_context(mode="ephemeral")
    context.variables.progress_bars = ProgressBarsConfig(globally=False)
    batch = (
        context.data_sources.add_pandas(name="lake")
        .add_dataframe_asset(name=table)
        .add_batch_definition_whole_dataframe("whole")
        .get_batch(batch_parameters={"dataframe": frame})
    )
    suite = gx.ExpectationSuite(
        name=table,
        expectations=[_expectation(gxe, Column, check) for check in checks],
    )
    result = batch.validate(context.suites.add(suite))
    # Results do not come back in suite order; the meta tag pairs them up.
    return [
        Outcome(
            check=item.expectation_config.meta["check"],
            success=bool(item.success),
            detail="" if item.success else _evidence(item),
        )
        for item in result.results
    ]


def _expectation(gxe: Any, column: Any, check: Check) -> Any:
    kwargs = dict(check.kwargs)
    if check.where is not None:
        name, value = check.where
        # A Column condition, not a string: string row conditions
        # (condition_parser="pandas") are deprecated since GX 1.9 and warn on
        # every expectation.
        kwargs["row_condition"] = column(name) == value
    return getattr(gxe, check.expectation)(**kwargs, meta={"check": check.name})


def _evidence(item: Any) -> str:
    """Why an expectation failed, in one line."""
    message = next(_exception_messages(item.exception_info), None)
    if message:
        return f"could not evaluate: {message}"
    result = item.result or {}
    if result.get("unexpected_count") is not None:
        sample = list(result.get("partial_unexpected_list") or [])[:SAMPLE]
        return f"{result['unexpected_count']} unexpected, e.g. {sample}"
    return f"observed {result.get('observed_value')}"


def _exception_messages(info: Any) -> Iterator[str]:
    """Exception messages anywhere in an expectation's exception info.

    A failed metric nests its exception one level down, keyed by metric id.
    A missing column arrives this way: ``validate`` returns ``success=False``
    instead of raising.
    """
    if not isinstance(info, dict):
        return
    if info.get("raised_exception") and info.get("exception_message"):
        yield info["exception_message"]
    for value in info.values():
        if isinstance(value, dict):
            yield from _exception_messages(value)
