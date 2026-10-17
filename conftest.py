"""
Project-wide pytest hooks for the Northstar Services API test suite.

TEST-ONLY fault injection: --day2-fault
=======================================
Faults exist only inside a pytest run. This file is never imported by
uvicorn, so `python -m uvicorn app.main:app` always runs the real app.

Values:
    none               (default) the real application, unchanged
    ownership          the ownership rule (BR02) always says "yes", so
                       employees can read each other's tickets
    missing-status     ticket and VPN-status responses lose their "status" field
    wrong-status-type  ticket and VPN-status "status" becomes a number (1),
                       not a string

How the isolation works:
- There is no app factory, so the tests share the one `app` object from
  app/main.py. Instead of a second app, `monkeypatch` swaps ONE function
  inside the app's modules for the length of a single test, then puts the
  original back automatically, even if the test fails.
- Authentication (the X-Demo-Employee-ID check) is never touched.
- data/*.json is never written. The fault versions return modified
  COPIES of what was read from disk.

The option is registered here at the project root, not in
tests/day2/conftest.py. pytest only reads options from conftest files it
loads at startup, and this root file is always loaded. That means
Day 1-only runs work too:

    python -m pytest tests/test_tickets.py --day2-fault=ownership
"""

import pytest

from app import data, rules

DAY2_FAULTS = ("none", "ownership", "missing-status", "wrong-status-type")


def pytest_addoption(parser):
    parser.addoption(
        "--day2-fault",
        action="store",
        default="none",
        choices=DAY2_FAULTS,
        help="TEST-ONLY: inject a known defect into the app for this pytest run (default: none).",
    )


def pytest_report_header(config):
    """Show the active fault at the top of every run, so it is never a surprise."""
    return f"day2-fault: {config.getoption('--day2-fault')}"


def remove_status(record: dict) -> dict:
    """Return a copy of record without its "status" field."""
    return {key: value for key, value in record.items() if key != "status"}


def make_status_a_number(record: dict) -> dict:
    """Return a copy of record whose "status" is the number 1 instead of a string."""
    return {**record, "status": 1}


def patch_status_field(monkeypatch, change):
    """Make the app's ticket and VPN-status loaders return changed copies.

    This sits in the app's own response-generation path. app/main.py calls
    data.load_tickets() and data.load_service_status(), so every response
    built from them carries the fault, while the files on disk stay unchanged.
    """
    real_load_tickets = data.load_tickets
    real_load_service_status = data.load_service_status

    monkeypatch.setattr(data, "load_tickets", lambda: [change(ticket) for ticket in real_load_tickets()])
    monkeypatch.setattr(data, "load_service_status", lambda: change(real_load_service_status()))


@pytest.fixture(autouse=True)
def day2_fault(request, monkeypatch):
    """Apply the selected TEST-ONLY fault for one test, then undo it.

    autouse=True means every test gets this fixture without asking for it.
    With the default --day2-fault=none it does nothing at all.
    """
    fault = request.config.getoption("--day2-fault")

    if fault == "ownership":
        # BR02 enforcement lives in app/rules.py: employee_owns_ticket().
        # Replace it with a version that always answers True.
        monkeypatch.setattr(rules, "employee_owns_ticket", lambda ticket, employee_id: True)
    elif fault == "missing-status":
        patch_status_field(monkeypatch, remove_status)
    elif fault == "wrong-status-type":
        patch_status_field(monkeypatch, make_status_a_number)

    # Everything after `yield` runs after the test. monkeypatch restores the
    # real functions on its own; nothing else needs cleaning up.
    yield fault
