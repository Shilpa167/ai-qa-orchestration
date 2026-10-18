"""
Plain helper functions for the Day 3 tests (not a test file, not a conftest),
so test files can import them, following the tests/day2/day2_data.py pattern.
"""

import json

from day3_lab import runs


def read_run(path) -> dict:
    return runs.load_run(path)


def write_run(path, run: dict) -> None:
    """Simulate someone editing run.json by hand (used to test tamper detection)."""
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")
