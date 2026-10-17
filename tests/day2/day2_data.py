"""
Shared Day 2 test data and documented API contract values.

This is a plain helper module (not a test file and not a conftest), so
test files can import from it.

Expected values are read straight from the prepared JSON files in data/,
NOT through app/data.py. That keeps the test's "source of truth"
independent of the application code, so a --day2-fault injected into the
app's loaders can never quietly change what the tests expect.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

DEMO_HEADER_NAME = "X-Demo-Employee-ID"

EMPLOYEE_A = "EMP001"
EMPLOYEE_B = "EMP002"
MISSING_TICKET_ID = "TCK-9999"

# Documented error bodies (docs/business_rules.md, app/main.py).
FORBIDDEN_BODY = {"detail": "You may not view another employee's ticket."}
NOT_FOUND_BODY = {"detail": f"Ticket not found: {MISSING_TICKET_ID}"}
MISSING_HEADER_BODY = {"detail": f"Missing required header: {DEMO_HEADER_NAME}"}

# Ticket fields whose values must never appear in a denied response.
PROTECTED_TICKET_FIELDS = ("subject", "description", "employee_id", "created_at", "updated_at")


def read_prepared_json(filename: str):
    """Read one prepared data file directly from disk."""
    with open(DATA_DIR / filename, "r", encoding="utf-8") as file:
        return json.load(file)


def tickets_owned_by(tickets: list[dict], employee_id: str) -> list[dict]:
    """Return every prepared ticket whose owner is employee_id."""
    return [ticket for ticket in tickets if ticket["employee_id"] == employee_id]


def first_ticket_owned_by(tickets: list[dict], employee_id: str) -> dict:
    """Return the first prepared ticket whose owner is employee_id."""
    owned = tickets_owned_by(tickets, employee_id)
    if not owned:
        raise LookupError(f"No ticket owned by {employee_id} in data/tickets.json")
    return owned[0]


TICKETS = read_prepared_json("tickets.json")

# One prepared ticket for each of Employee A and Employee B.
TICKET_OF_A = first_ticket_owned_by(TICKETS, EMPLOYEE_A)
TICKET_OF_B = first_ticket_owned_by(TICKETS, EMPLOYEE_B)
