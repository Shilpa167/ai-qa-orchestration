"""
Structural validation of one raw response.

"Structural" means two questions only:
  1. Parse: is the raw text one JSON object?
  2. Schema: does it have exactly the agreed keys, with the agreed types?

It does NOT check whether the answer is true, relevant or safe. A response
can pass here and still invent a recovery time or ask for a password.
A valid service_status value does not prove it matches the supplied facts.
Those questions are for the human rubric.

Nothing here repairs a bad response. No quotes are stripped, no text is
trimmed and no type is converted: invalid output stays invalid and every
problem is kept as evidence.
"""

import json
from functools import lru_cache

import jsonschema

from day3_lab.data import RESPONSE_SCHEMA_PATH, load_json

PASS = "PASS"
FAIL = "FAIL"
NOT_RUN = "NOT_RUN"

# Keywords the local schema uses that are not needed by, or may not be
# supported by, the provider's strict structured-output mode. The local
# schema stays the authority. The provider copy is only a hint to the model.
_PROVIDER_UNSUPPORTED = ("$schema", "title", "description", "minLength", "pattern")


@lru_cache(maxsize=1)
def load_response_schema() -> dict:
    schema = load_json(RESPONSE_SCHEMA_PATH)
    jsonschema.Draft7Validator.check_schema(schema)
    return schema


def provider_schema() -> dict:
    """A copy of the response schema without keywords strict structured outputs may reject."""

    def strip(node):
        if isinstance(node, dict):
            return {key: strip(value) for key, value in node.items() if key not in _PROVIDER_UNSUPPORTED}
        return node

    return strip(load_response_schema())


class _DuplicateKeys(ValueError):
    pass


def _no_duplicate_keys(pairs):
    keys = [key for key, _ in pairs]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise _DuplicateKeys(f"duplicate keys {duplicates}")
    return dict(pairs)


def _no_special_numbers(name):
    raise ValueError(f"{name} is not valid JSON")


def check_structure(raw_response) -> dict:
    """Parse and schema-check one raw response.

    Returns a dictionary:
        status:   PASS or FAIL
        parsed:   the decoded JSON value, or None if it could not be decoded
        findings: a list of {stage, path, message}; empty when status is PASS
    """
    if not isinstance(raw_response, str):
        return {
            "status": FAIL,
            "parsed": None,
            "findings": [{"stage": "parse", "path": "", "message": f"raw response must be text, got {type(raw_response).__name__}"}],
        }

    try:
        parsed = json.loads(raw_response, object_pairs_hook=_no_duplicate_keys, parse_constant=_no_special_numbers)
    except (ValueError, _DuplicateKeys) as error:
        return {
            "status": FAIL,
            "parsed": None,
            "findings": [{"stage": "parse", "path": "", "message": str(error)}],
        }

    validator = jsonschema.Draft7Validator(load_response_schema())
    findings = []
    for error in validator.iter_errors(parsed):
        path = "/".join(str(part) for part in error.absolute_path) or "<whole response>"
        findings.append({"stage": "schema", "path": path, "message": error.message})
    findings.sort(key=lambda finding: (finding["path"], finding["message"]))

    return {"status": FAIL if findings else PASS, "parsed": parsed, "findings": findings}
