"""
Reusable JSON Schema validation for the Day 2 tests.

The schemas live in schemas/ at the project root. They are the project's
written contract for what each response must look like:

    schemas/employee.schema.json        GET /employees/me
    schemas/ticket.schema.json          GET /tickets/{ticket_id}
    schemas/service_status.schema.json  GET /services/vpn/status
    schemas/error.schema.json           any 400 / 403 / 404 error body

Usage in a test:

    assert_matches_schema(response.json(), "ticket.schema.json")
"""

import json
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def load_schema(filename: str) -> dict:
    """Read one schema file and check that the schema itself is valid."""
    with open(SCHEMA_DIR / filename, "r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    jsonschema.Draft7Validator.check_schema(schema)
    return schema


def schema_errors(instance, filename: str) -> list[str]:
    """Return every way `instance` breaks the schema, as readable lines.

    An empty list means the instance is valid. FormatChecker makes
    "format": "date-time" a real check (needs rfc3339-validator, see
    pyproject.toml).
    """
    validator = jsonschema.Draft7Validator(load_schema(filename), format_checker=jsonschema.FormatChecker())
    errors = []
    for error in validator.iter_errors(instance):
        location = "/".join(str(part) for part in error.path) or "<whole object>"
        errors.append(f"{location}: {error.message}")
    return sorted(errors)


def assert_matches_schema(instance, filename: str) -> None:
    """Fail the test with a list of every schema violation, if there are any."""
    errors = schema_errors(instance, filename)
    assert errors == [], f"Response does not match {filename}:\n  " + "\n  ".join(errors)
