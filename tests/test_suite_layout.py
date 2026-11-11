"""Lock the shape of the host test suite itself (ticket 13).

Fixtures that more than one module needs live in ``tests/conftest.py``, where
pytest shares them with every module. A copy in a test module drifts from the
others the first time one of them changes.
"""

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def test_pipeline_env_fixture_is_defined_once_in_conftest():
    defining = sorted(
        path.name
        for path in TESTS.glob("*.py")
        if re.search(r"^def env\(", path.read_text(encoding="utf-8"), re.MULTILINE)
    )
    assert defining == ["conftest.py"]
