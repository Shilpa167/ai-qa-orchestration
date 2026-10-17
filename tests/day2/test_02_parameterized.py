"""
Day 2, topic 2: parametrize.

Parametrize lets ONE test function run several times with different data.

    @pytest.mark.parametrize("caller, ticket_id", [case1, case2, ...])
    def test_something(client, caller, ticket_id): ...

- The first argument is a string of names, separated by commas. Each name
  becomes a parameter of the test function, just like a fixture.
- The second argument is a list of cases. Each case supplies one value
  for each name, in the same order.
- pytest.param(..., id="...") gives a case a readable name. pytest shows
  it in square brackets, e.g.
  test_ticket_access[employee-a-requests-employee-b-ticket].
- Fixtures (client, auth_headers) and parameters can be mixed freely in
  the same test function.

Every expected value comes from the prepared data (day2_data.py reads
data/tickets.json) or from the documented API contract, never from the
response under test.
"""

import pytest

from tests.day2.day2_data import (
    EMPLOYEE_A,
    EMPLOYEE_B,
    MISSING_TICKET_ID,
    TICKET_OF_A,
    TICKET_OF_B,
)

FORBIDDEN = {"detail": "You may not view another employee's ticket."}
NOT_FOUND = {"detail": f"Ticket not found: {MISSING_TICKET_ID}"}

# Columns: who calls, which ticket, expected status, expected JSON body,
# and (for denials) the foreign ticket whose data must not leak.
CASES = [
    pytest.param(
        EMPLOYEE_A, TICKET_OF_A["ticket_id"], 200, TICKET_OF_A, None,
        id="employee-a-own-ticket",  # overlap: test_01 (A own ticket)
    ),
    pytest.param(
        EMPLOYEE_B, TICKET_OF_B["ticket_id"], 200, TICKET_OF_B, None,
        id="employee-b-own-ticket",  # overlap: test_01 (B own ticket)
    ),
    pytest.param(
        EMPLOYEE_A, TICKET_OF_B["ticket_id"], 403, FORBIDDEN, TICKET_OF_B,
        id="employee-a-requests-employee-b-ticket",
    ),
    pytest.param(
        EMPLOYEE_B, TICKET_OF_A["ticket_id"], 403, FORBIDDEN, TICKET_OF_A,
        id="employee-b-requests-employee-a-ticket",  # overlap: Day 1 403 test
    ),
    pytest.param(
        EMPLOYEE_A, MISSING_TICKET_ID, 404, NOT_FOUND, None,
        id="employee-a-requests-missing-ticket",  # overlap: Day 1 404 test
    ),
]


@pytest.mark.parametrize(
    "caller, ticket_id, expected_status, expected_body, foreign_ticket",
    CASES,
)
def test_ticket_access(client, auth_headers, caller, ticket_id, expected_status, expected_body, foreign_ticket):
    # Arrange: nothing extra. The case row already holds the inputs and expectations.

    # Act
    response = client.get(f"/tickets/{ticket_id}", headers=auth_headers(caller))

    # Assert: exact status and exact body from the contract or prepared data.
    assert response.status_code == expected_status
    assert response.json() == expected_body

    # Assert: a denial must not reveal any of the foreign ticket's contents.
    if foreign_ticket is not None:
        for field in ("subject", "description", "employee_id", "created_at", "updated_at"):
            assert foreign_ticket[field] not in response.text
