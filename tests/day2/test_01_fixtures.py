"""
Day 2, topic 1: fixtures.

A fixture is a function that pytest runs for you before a test. You ask
for one by writing its name as a test parameter, and pytest passes in
whatever the fixture returned. Fixtures used here:

    client             - tests/conftest.py       (in-process TestClient)
    auth_headers       - tests/day2/conftest.py  (builds the identity header)
    employee_a_ticket  - tests/day2/conftest.py  (A's ticket from data/tickets.json)
    employee_b_ticket  - tests/day2/conftest.py  (B's ticket from data/tickets.json)
"""

from tests.day2.day2_data import EMPLOYEE_A, EMPLOYEE_B


def test_employee_a_retrieves_own_ticket(client, auth_headers, employee_a_ticket):
    # Arrange: the ticket ID and its owner both come from the prepared data.
    ticket_id = employee_a_ticket["ticket_id"]
    expected_owner = employee_a_ticket["employee_id"]
    assert expected_owner == EMPLOYEE_A  # sanity check on the data itself

    # Act: Employee A asks for the ticket.
    response = client.get(f"/tickets/{ticket_id}", headers=auth_headers(EMPLOYEE_A))

    # Assert: allowed, the right ticket came back, and it belongs to A.
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == ticket_id
    assert body["employee_id"] == expected_owner


def test_employee_b_retrieves_own_ticket(client, auth_headers, employee_b_ticket):
    # Arrange: the ticket ID and its owner both come from the prepared data.
    ticket_id = employee_b_ticket["ticket_id"]
    expected_owner = employee_b_ticket["employee_id"]
    assert expected_owner == EMPLOYEE_B  # sanity check on the data itself

    # Act: Employee B asks for the ticket.
    response = client.get(f"/tickets/{ticket_id}", headers=auth_headers(EMPLOYEE_B))

    # Assert: allowed, the right ticket came back, and it belongs to B.
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == ticket_id
    assert body["employee_id"] == expected_owner
