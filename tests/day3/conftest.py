"""
Day 3 fixtures.

Fixtures in tests/day2/conftest.py are NOT visible here: pytest only shares
a conftest's fixtures with tests in the same folder or below it, and
tests/day3/ is a sibling of tests/day2/. So Day 3 defines what it needs.

Every Day 3 test is offline. The autouse `no_live_credentials` fixture
removes OPENAI_API_KEY and OPENAI_MODEL for each test, so even a machine
with a real key set cannot make a paid call from the test suite.
"""

import pytest

from day3_lab import cli, data


@pytest.fixture(autouse=True)
def no_live_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)


@pytest.fixture(scope="session")
def cases_document() -> dict:
    """The Day 3 cases exactly as stored in datasets/day3/cases.json."""
    return data.load_cases()


@pytest.fixture(scope="session")
def rubric() -> dict:
    """The Day 3 rubric exactly as stored in rubrics/day3/rubric.json."""
    return data.load_rubric()


@pytest.fixture()
def run_cli(capsys):
    """Run the CLI in-process. Returns (exit code, stdout, stderr)."""

    def run(*argv):
        code = cli.main([str(arg) for arg in argv])
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return run


@pytest.fixture()
def mock_run(run_cli, tmp_path):
    """A fresh one-case MOCK run of D3-01 in a temporary folder. Returns the run.json path."""
    out = tmp_path / "demo"
    code, _, _ = run_cli("run", "--mode", "mock", "--case", "D3-01", "--out", out)
    assert code == 0
    return out / "run.json"

