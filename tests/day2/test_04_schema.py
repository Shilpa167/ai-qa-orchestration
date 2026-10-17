"""
Day 2, topic 4: JSON Schema validation.

A JSON Schema is a JSON file that describes what valid data looks like.
The four keywords used most in schemas/*.json:

    "type": "object"   the value must be a JSON object { ... }, i.e. a
                       Python dict
    "properties": {}   lists each field the object may have, and the rule
                       for each one, e.g. "status": {"type": "string"}
    "required": [...]  fields that MUST be present. A missing one is an error
    "type": "string"   the value must be text. 1, true or null are rejected

Order matters: check the HTTP status FIRST, then the schema. If a ticket
request unexpectedly returned a 403, validating the error body against
the ticket schema would give a confusing failure. The status assert
explains the real problem straight away.

TEST-ONLY faults for this lesson (see the root conftest.py):

    python -m pytest -v tests/day2/test_04_schema.py --day2-fault=missing-status
    python -m pytest -v tests/day2/test_04_schema.py --day2-fault=wrong-status-type

Each fault changes the app's own data loaders, so the real endpoint
produces a bad response. The tests below do not edit any response.
"""

import jsonschema
import pytest

from tests.day2.day2_data import EMPLOYEE_A, EMPLOYEE_B, MISSING_TICKET_ID, TICKET_OF_A, TICKET_OF_B
from tests.day2.schema_validation import assert_matches_schema, load_schema, schema_errors

# ---------------------------------------------------------------------------
# API cases: real requests to the real endpoints. These are the counted cases.
# Columns: path, caller (None = no identity header), expected status, schema.
# ---------------------------------------------------------------------------
API_CASES = [
    pytest.param("/employees/me", EMPLOYEE_A, 200, "employee.schema.json", id="employee-profile"),
    pytest.param(f"/tickets/{TICKET_OF_A['ticket_id']}", EMPLOYEE_A, 200, "ticket.schema.json", id="ticket-employee-a-own"),
    pytest.param(f"/tickets/{TICKET_OF_B['ticket_id']}", EMPLOYEE_B, 200, "ticket.schema.json", id="ticket-employee-b-own"),
    pytest.param("/services/vpn/status", None, 200, "service_status.schema.json", id="service-status"),
    pytest.param(f"/tickets/{TICKET_OF_B['ticket_id']}", EMPLOYEE_A, 403, "error.schema.json", id="error-403-foreign-ticket"),
    pytest.param(f"/tickets/{MISSING_TICKET_ID}", EMPLOYEE_A, 404, "error.schema.json", id="error-404-missing-ticket"),
    pytest.param("/employees/me", None, 400, "error.schema.json", id="error-400-missing-header"),
]


@pytest.mark.parametrize("path, caller, expected_status, schema_file", API_CASES)
def test_api_response_matches_schema(client, auth_headers, path, caller, expected_status, schema_file):
    # Arrange
    headers = auth_headers(caller) if caller else {}

    # Act
    response = client.get(path, headers=headers)

    # Assert: status first...
    assert response.status_code == expected_status
    # ...then the shape of the body: required fields, types, allowed values.
    assert_matches_schema(response.json(), schema_file)


# ---------------------------------------------------------------------------
# Beginner validator examples. These check plain dictionaries, NOT API
# responses, so they are not counted as API cases. They show what each
# keyword rejects, using the real ticket schema.
# ---------------------------------------------------------------------------
class TestValidatorExamplesNotApiCases:
    def valid_ticket(self) -> dict:
        return dict(TICKET_OF_A)  # a copy of a prepared ticket, known to be valid

    def test_example_valid_ticket_has_no_errors(self):
        assert schema_errors(self.valid_ticket(), "ticket.schema.json") == []

    def test_example_required_rejects_missing_field(self):
        ticket = self.valid_ticket()
        del ticket["status"]

        assert schema_errors(ticket, "ticket.schema.json") == ["<whole object>: 'status' is a required property"]

    def test_example_string_type_rejects_a_number(self):
        ticket = {**self.valid_ticket(), "status": 1}

        errors = schema_errors(ticket, "ticket.schema.json")

        assert "status: 1 is not of type 'string'" in errors

    def test_example_object_type_rejects_a_list(self):
        # A list containing a ticket is not itself a ticket.
        errors = schema_errors([self.valid_ticket()], "ticket.schema.json")

        assert len(errors) == 1
        assert errors[0].endswith("is not of type 'object'")

    def test_example_validate_raises_on_bad_data(self):
        # jsonschema.validate() is the one-line version: it raises instead of listing.
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance={"status": 1}, schema=load_schema("ticket.schema.json"))
