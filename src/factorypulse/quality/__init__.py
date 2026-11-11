"""Table-level quality seam (ticket 07): named checks over lake tables.

``check_table(name)`` reads one table through ``factorypulse.lake``, runs its
checks (``quality.expectations``) through a runner, and returns a
``QualityReport`` naming every check that failed. The default runner is the
Great Expectations adapter (``quality.ge_runner``), imported only when a check
actually runs, so this module and the report mapping work without it.

Row-level validation at the ingestion boundary stays the event contract's
job (``factorypulse.validator``); these checks assert things about whole
tables as stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from factorypulse import analytics, lake
from factorypulse.quality.expectations import CHECKED_TABLES, Check, Outcome, checks_for

Runner = Callable[[str, Any, Sequence[Check]], Sequence[Outcome]]

# When each checked table is checked: the raw lake right after ingestion, the
# daily dbt tables right after the daily dbt build, and the weekly mart right
# after the weekly build. A stage holds only tables built together, because
# the mart checks compare a table with the fact it was built from.
STAGES: Mapping[str, Tuple[str, ...]] = {
    "ingestion": (analytics.RAW_EVENTS_TABLE,),
    "post-dbt": analytics.DAILY_MODELS,
    "weekly": analytics.WEEKLY_MODELS,
}


@dataclass(frozen=True)
class QualityReport:
    """The outcome of one table's checks, naming every check that failed."""

    table: str
    failed: Tuple[str, ...]
    details: Mapping[str, str] = field(default_factory=dict)
    checked: int = 0

    @property
    def passed(self) -> bool:
        return not self.failed


def _default_runner() -> Runner:
    from factorypulse.quality import ge_runner

    return ge_runner.run


def check_table(
    name: str, root: Optional[str] = None, runner: Optional[Runner] = None
) -> QualityReport:
    """Run the checks of table ``name`` and report every one that failed.

    ``root`` is the lake root ``lake.read_table`` reads from (default: the
    object-store lake). A table the checks need that is not built, or lacks
    a declared column, is a failed check, never a vacuous pass. Raises
    ``ValueError`` for a table with no checks.
    """
    frames: Dict[str, Any] = {}

    def read(table: str) -> Any:
        if table not in frames:
            frames[table] = lake.read_table(table, root=root)
        return frames[table]

    try:
        checks = checks_for(name, read)
        frame = read(name)
    except lake.LakeTableMissing as missing:
        return _unreadable(name, f"{missing.name} is built", str(missing))
    except lake.LakeColumnsMissing as lacking:
        return _unreadable(name, f"{lacking.name} stores every declared column", str(lacking))

    outcomes = {o.check: o for o in (runner or _default_runner())(name, frame, checks)}
    failed: List[str] = []
    details: Dict[str, str] = {}
    for check in checks:
        outcome = outcomes.get(check.name)
        if outcome is None:
            failed.append(check.name)
            details[check.name] = "the runner returned no result for this check"
        elif not outcome.success:
            failed.append(check.name)
            details[check.name] = outcome.detail
    return QualityReport(name, tuple(failed), details, len(checks))


def _unreadable(name: str, check: str, detail: str) -> QualityReport:
    return QualityReport(name, (check,), {check: detail}, 1)


def run_all(
    tables: Sequence[str], root: Optional[str] = None, runner: Optional[Runner] = None
) -> List[QualityReport]:
    """One report per table, in the order given."""
    return [check_table(name, root=root, runner=runner) for name in tables]


__all__ = ["CHECKED_TABLES", "STAGES", "QualityReport", "check_table", "run_all"]
