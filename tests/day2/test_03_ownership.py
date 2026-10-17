"""
Day 2, topic 3: ownership (BR02), with a TEST-ONLY fault to prove the
tests can catch a broken rule.

Where ownership is enforced
---------------------------
GET /tickets/{ticket_id} in app/main.py runs these checks in order:
    1. get_current_employee()      who is asking? (missing/unknown -> 400)
    2. rules.find_ticket_by_id()   does the ticket exist? (no -> 404)
    3. rules.employee_owns_ticket() is it theirs? (no -> 403)   <- BR02
Only step 3 decides ownership. It is one line in app/rules.py:
    return ticket["employee_id"] == employee_id

Seeing the tests catch a defect
-------------------------------
    python -m pytest -v tests/day2/test_03_ownership.py --day2-fault=ownership

replaces step 3, for that pytest run only, with a version that always
returns True. The request still goes through the real endpoint, but now
it returns 200 with the other employee's ticket. The cross-employee tests
below then FAIL with `assert 200 == 403`. That failure is the point: it
proves the tests would notice if someone broke BR02. The tests are not
changed and are not marked xfail. Run without the option and they pass
again.
"""

import pytest

from tests.day2.day2_data import (
    EMPLOYEE_A,
    EMPLOYEE_B,
    FORBIDDEN_BODY,
    MISSING_HEADER_BODY,
    PROTECTED_TICKET_FIELDS,
    TICKETS,
    tickets_owned_by,
)

# Both directions, for every ticket the other employee owns in data/tickets.json.
CROSS_EMPLOYEE_CASES = [
    pytest.param(EMPLOYEE_A, ticket, id=f"employee-a-requests-{ticket['ticket_id']}-of-employee-b")
    for ticket in tickets_owned_by(TICKETS, EMPLOYEE_B)
] + [
    pytest.param(EMPLOYEE_B, ticket, id=f"employee-b-requests-{ticket['ticket_id']}-of-employee-a")
    for ticket in tickets_owned_by(TICKETS, EMPLOYEE_A)
]


@pytest.mark.parametrize("caller, foreign_ticket", CROSS_EMPLOYEE_CASES)
def test_cross_employee_ticket_access_is_denied(client, auth_headers, caller, foreign_ticket):
    # Arrange: the ticket and its real owner come from data/tickets.json.
    ticket_id = foreign_ticket["ticket_id"]
    assert foreign_ticket["employee_id"] != caller  # sanity check: really someone else's

    # Act: call the real endpoint as the wrong employee.
    response = client.get(f"/tickets/{ticket_id}", headers=auth_headers(caller))

    # Assert: the documented denial, exactly.
    assert response.status_code == 403
    assert response.json() == FORBIDDEN_BODY

    # Assert: none of the protected ticket's contents leaked into the response.
    for field in PROTECTED_TICKET_FIELDS:
        assert foreign_ticket[field] not in response.text, f"denied response leaked {field}"


def test_identity_is_still_required_under_any_fault(client, employee_b_ticket):
    # Guard test: the ownership fault must not switch off the identity check.
    # It passes in normal runs AND under --day2-fault=ownership.

    # Arrange
    ticket_id = employee_b_ticket["ticket_id"]

    # Act: no X-Demo-Employee-ID header at all.
    response = client.get(f"/tickets/{ticket_id}")

    # Assert
    assert response.status_code == 400
    assert response.json() == MISSING_HEADER_BODY
