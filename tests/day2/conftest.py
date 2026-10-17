"""
Day 2 fixtures, layered on top of the shared `client` fixture in
tests/conftest.py (pytest makes parent fixtures available here
automatically, so `client` is reused, not redefined).

Expected ticket owners come from the prepared data file
data/tickets.json, never from the API response being tested.

The --day2-fault option is NOT registered here. It lives in the
project-root conftest.py so that it works for every pytest run.
"""

import pytest

from tests.day2.day2_data import (
    DEMO_HEADER_NAME,
    EMPLOYEE_A,
    EMPLOYEE_B,
    first_ticket_owned_by,
    read_prepared_json,
)


@pytest.fixture()
def auth_headers():
    """Return a helper that builds the demo identity header for one employee.

    Usage: client.get("/employees/me", headers=auth_headers("EMP001"))

    This is a training identity header, not real authentication.
    """

    def make_headers(employee_id: str) -> dict:
        return {DEMO_HEADER_NAME: employee_id}

    return make_headers


@pytest.fixture()
def prepared_tickets() -> list[dict]:
    """All tickets exactly as stored in data/tickets.json (the source of truth).

    Read straight from the file, not through app/data.py, so an injected
    --day2-fault in the app can never change the expected values.
    """
    return read_prepared_json("tickets.json")


@pytest.fixture()
def employee_a_ticket(prepared_tickets) -> dict:
    """A ticket that Employee A (EMP001) owns, according to the prepared data."""
    return first_ticket_owned_by(prepared_tickets, EMPLOYEE_A)


@pytest.fixture()
def employee_b_ticket(prepared_tickets) -> dict:
    """A ticket that Employee B (EMP002) owns, according to the prepared data."""
    return first_ticket_owned_by(prepared_tickets, EMPLOYEE_B)
