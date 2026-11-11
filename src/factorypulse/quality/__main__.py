"""Quality gate command line (ticket 07).

    python -m factorypulse.quality                      every checked table
    python -m factorypulse.quality --stage ingestion    the raw lake
    python -m factorypulse.quality --stage post-dbt     the daily dbt models
    python -m factorypulse.quality --stage weekly       the weekly mart
    python -m factorypulse.quality --tables dim_machine

Prints one line per table, then one indented line per failed check with its
evidence, and exits 1 if any check failed. The pipeline and a human run the
same command (``docker compose run --rm quality ...``).
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from factorypulse import quality


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m factorypulse.quality",
        description="Run the named quality checks over lake tables.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--stage", choices=sorted(quality.STAGES))
    selection.add_argument("--tables", nargs="+", choices=quality.CHECKED_TABLES, metavar="TABLE")
    parser.add_argument(
        "--root", help="lake root holding the Delta tables (default: the object-store lake)"
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.tables:
        tables: List[str] = list(args.tables)
    elif args.stage:
        tables = list(quality.STAGES[args.stage])
    else:
        tables = [table for stage in quality.STAGES.values() for table in stage]

    reports = quality.run_all(tables, root=args.root)
    for report in reports:
        verdict = "PASS" if report.passed else "FAIL"
        print(f"{verdict} {report.table} ({report.checked} checks, {len(report.failed)} failed)")
        for check in report.failed:
            print(f"  - {check}: {report.details.get(check, '')}")
    return 0 if all(report.passed for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
