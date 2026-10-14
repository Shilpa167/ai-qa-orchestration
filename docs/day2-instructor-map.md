# Day 2 Instructor Map

Prepared by re-inspecting the repository on 2026-10-11 (branch `main`,
HEAD `276db27`). Since that commit, the only working-tree changes are
uncommitted Day 1 additions: `docs/day1-local-map.md`,
`docs/day1-curl-commands.md`, and a `.training/` line in `.gitignore`.
`app/`, `data/`, `schemas/` and `tests/` are unchanged since `276db27`.
Every path, ID and status below was read from the current files or from
a live run. [`day1-local-map.md`](day1-local-map.md) was checked against
the code and is still accurate.

## 1. Day 1 baseline: explicit test paths

These files make up the Day 1 baseline. **They stay where they are and
must not be moved or edited by Day 2 work.**

| Path | Tests |
| --- | --- |
| [`tests/conftest.py`](../tests/conftest.py) | fixture `client`, which returns `TestClient(app)` |
| [`tests/test_service_status.py`](../tests/test_service_status.py) | `test_health_check_returns_ok`, `test_vpn_status_has_defined_status_and_update_time` |
| [`tests/test_employees.py`](../tests/test_employees.py) | `test_get_my_profile_returns_known_employee` |
| [`tests/test_tickets.py`](../tests/test_tickets.py) | `test_get_own_ticket_returns_200`, `test_get_other_employees_ticket_returns_403`, `test_ticket_matches_schema`, `test_missing_ticket_returns_404` |

**Command that runs only the Day 1 baseline** (same on Windows and
macOS, with `.venv` active, from the project root):

```
python -m pytest -v tests/test_service_status.py tests/test_employees.py tests/test_tickets.py
```

Once `tests/day2/` exists, plain `python -m pytest -v` will run Day 1
**and** Day 2 together, because `testpaths = ["tests"]` is set in
`pyproject.toml`. Use the explicit-path command above when you want the
Day 1 baseline alone.

## 2. Baseline result (verified 2026-10-11, this machine)

```
Python 3.12.10, pytest 8.4.2, plugins: anyio-4.15.1
tests/test_service_status.py::test_health_check_returns_ok PASSED
tests/test_service_status.py::test_vpn_status_has_defined_status_and_update_time PASSED
tests/test_employees.py::test_get_my_profile_returns_known_employee PASSED
tests/test_tickets.py::test_get_own_ticket_returns_200 PASSED
tests/test_tickets.py::test_get_other_employees_ticket_returns_403 PASSED
tests/test_tickets.py::test_ticket_matches_schema PASSED
tests/test_tickets.py::test_missing_ticket_returns_404 PASSED
======================== 7 passed, 1 warning ========================
```

- There were no errors to investigate and no tests were modified.
- The one warning is a Starlette `StarletteDeprecationWarning` about
  `httpx` vs `httpx2`, raised from the installed FastAPI package and
  not from project code. It is harmless and should not be suppressed
  during the lesson.
- The only pytest plugin installed in this `.venv` is `anyio`, which
  comes in as a FastAPI dependency. The `pytest-html`,
  `pytest-json-report` and `pytest-metadata` plugins named in an
  earlier version of this map are **not** installed here. A student's
  fresh `pip install -e ".[dev]"` matches this machine.

## 3. Application facts

| Item | Value |
| --- | --- |
| Framework / entry point | FastAPI, `app.main:app` |
| Python | `>=3.11,<3.13` (this machine uses 3.12.10; 3.14 is rejected by pip) |
| Dependencies | `pyproject.toml` only. Install with `python -m pip install -e ".[dev]"` |
| Test deps | `pytest>=8.0,<9.0`; runtime deps include `httpx` (needed by TestClient) and `jsonschema` |
| pytest config | `[tool.pytest.ini_options]` in `pyproject.toml`: `pythonpath = ["."]`, `testpaths = ["tests"]`. The rootdir is the project root |
| Data | `data/employees.json`, `data/tickets.json`, `data/service_status.json`, read fresh on every request by `app/data.py` |
| Schema | `schemas/ticket.schema.json` (`additionalProperties: false`, `status` ∈ `open`/`in_progress`/`resolved`) |

### Identity mechanism (not authentication)

`get_current_employee()` in [`app/main.py`](../app/main.py) (lines 27–51)
reads the `X-Demo-Employee-ID` header and looks it up in
`data/employees.json`. There is no password, token or session. It is
a **training identity header**: anyone can send any ID. Make this clear
to students.

Check order for `GET /tickets/{id}`: header present (400) → known
employee (400) → ticket exists (404) → caller owns ticket (403) → 200.

The ownership decision lives in exactly one function:
`rules.employee_owns_ticket(ticket, employee_id)` in
[`app/rules.py`](../app/rules.py) line 27. `app/main.py` calls it as
`rules.employee_owns_ticket(...)`, a module-attribute lookup at request
time, so a test can safely replace it with `monkeypatch.setattr` (see
section 7).

### Routes and fields

| Route | Header | Response fields |
| --- | --- | --- |
| `GET /health` | none | `status`, `service` |
| `GET /employees/me` | required | `employee_id`, `full_name`, `department`, `email` |
| `GET /services/vpn/status` | none | `service`, `status`, `updated_at`, `message` |
| `GET /tickets/{ticket_id}` | required | `ticket_id`, `employee_id`, `subject`, `description`, `status`, `created_at`, `updated_at` |

Errors always use `{"detail": "<message>"}`.

## 4. Employees and ticket ownership (from `data/*.json`)

| Employee ID | Name | Department | Tickets owned |
| --- | --- | --- | --- |
| `EMP001` (Employee A) | Dana Whitfield | Finance | `TCK-1001` (open), `TCK-1005` (in_progress) |
| `EMP002` (Employee B) | Marcus Lee | Sales | `TCK-1002` (resolved), `TCK-1006` (resolved) |
| `EMP003` | Priya Nair | Engineering | `TCK-1003` (in_progress) |
| `EMP004` | Oliver Grant | Human Resources | `TCK-1004` (open) |

Well-formed missing ticket ID: `TCK-9999`. Unknown employee ID: `EMP999`.

## 5. Documented status-code expectations (all verified live on Day 1)

| Route | Condition | Status | Body |
| --- | --- | --- | --- |
| `GET /health` | always | 200 | `{"status":"ok","service":"northstar-it-service-desk"}` |
| `GET /employees/me` | header missing | 400 | `{"detail":"Missing required header: X-Demo-Employee-ID"}` |
| `GET /employees/me` | header unknown | 400 | `{"detail":"Unknown demo employee id: <value>"}` |
| `GET /employees/me` | header valid | 200 | employee object |
| `GET /services/vpn/status` | always | 200 | `data/service_status.json` unchanged |
| `GET /tickets/{id}` | header missing/unknown | 400 | as above |
| `GET /tickets/{id}` | not found | 404 | `{"detail":"Ticket not found: <id>"}` |
| `GET /tickets/{id}` | other owner | 403 | `{"detail":"You may not view another employee's ticket."}` |
| `GET /tickets/{id}` | own ticket | 200 | ticket object |

An unknown employee returns 400, not 401. That is the documented
training contract (BR01), not a defect.

## 6. Do the tests need a server?

**No. The tests use an in-process client.** `tests/conftest.py` builds
`fastapi.testclient.TestClient(app)`, which calls the ASGI app in
memory. Nothing in `tests/` or `app/` refers to `localhost`,
`127.0.0.1` or a port. pytest passes with no server running, and Day 2
tests should keep using the `client` fixture.

A server is needed only for manual curl or Swagger demos. Run it in a
separate terminal:

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8123 --reload
```

macOS:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8123 --reload
```

Then open `http://127.0.0.1:8123/docs`. The bare `/` returns 404 by
design because no root route exists. `README.md` still shows port 8000.
Both ports work, but course materials use 8123.

## 7. Planned pytest option `--day2-fault` (not implemented yet)

To be added during the **ownership lesson**. Its purpose is to inject a
known defect so students can see their ownership tests fail for the
right reason.

**Planned contract**

| Value | Effect |
| --- | --- |
| `none` (default) | No fault; the app behaves normally |
| `ownership-bypass` (proposed) | `rules.employee_owns_ticket` always returns `True`, so cross-employee requests return 200 instead of 403 |

Final value names will be confirmed in that lesson. Unknown values
should be rejected by `choices=[...]`, never silently ignored.

**Where it will be registered:** in a new **project-root
`conftest.py`** (next to `pyproject.toml`) via `pytest_addoption`. It
will **not** go only in `tests/day2/conftest.py`.

Why: pytest only honours `pytest_addoption` in conftests it loads at
startup. Those are the root conftest and the conftests in, or above,
the paths given on the command line. If the option lived only in
`tests/day2/conftest.py`, then
`python -m pytest tests/test_tickets.py --day2-fault=ownership-bypass`
would fail with `unrecognized arguments`, and the option would not
appear in `python -m pytest --help` for a Day 1-only run. A root
conftest is always loaded because it sits in the rootdir, so these
commands all work:

```
python -m pytest --help                     # shows --day2-fault
python -m pytest -v                         # full suite, fault = none
python -m pytest -v --day2-fault=ownership-bypass
python -m pytest -v tests/test_tickets.py --day2-fault=ownership-bypass
```

An alternative with the same effect is a plugin module loaded early
through `addopts = "-p <module>"` in `pyproject.toml`. The root conftest
is simpler for beginners and is the recommended choice.

**How the fault will be applied:** an autouse fixture reads
`request.config.getoption("--day2-fault")` and, only when the value is
not `none`, calls `monkeypatch.setattr(rules, "employee_owns_ticket",
...)`. `monkeypatch` undoes the patch after each test, so no fault can
leak into the next test or the next run. No app code changes are
needed. The default `none` keeps the 7-test baseline green.

Expected demo: with `--day2-fault=ownership-bypass`,
`test_get_other_employees_ticket_returns_403` (Day 1) and any Day 2
ownership tests should fail with `assert 200 == 403`. Everything else
should still pass.

## 8. Proposed Day 2 test layout (no files created yet)

New files go in `tests/day2/`. Per the course instructions, no empty
placeholder files are created ahead of the lesson. `tests/day2/`
inherits the `client` fixture from `tests/conftest.py` automatically.

| File | Purpose |
| --- | --- |
| `conftest.py` (project root) | `--day2-fault` option and the fault-applying fixture (section 7). This is the only Day 2 file outside `tests/day2/` |
| `tests/day2/conftest.py` | Day-2-only helpers, e.g. an `auth_headers(employee_id)` fixture returning `{"X-Demo-Employee-ID": employee_id}`. No `pytest_addoption` here |
| `tests/day2/test_01_fixtures.py` | Introduce fixtures by reusing `client` and `auth_headers` for profile and VPN checks |
| `tests/day2/test_02_parameterized.py` | `@pytest.mark.parametrize` over the section 4 ownership table: every employee reads their own ticket → 200 |
| `tests/day2/test_03_ownership.py` | Cross-owner pairs → 403, missing/unknown header → 400, `TCK-9999` → 404. This is the lesson that introduces `--day2-fault` |
| `tests/day2/test_04_schema.py` | Schema-validate every ticket; add one negative case (bad `status`) expecting `ValidationError` |

Day 2 must not re-add `test_missing_ticket_returns_404` as if it were
new. It is already part of the Day 1 baseline.

## 9. Request flow (unchanged)

1. A test sends `GET /tickets/TCK-1001` with `X-Demo-Employee-ID: EMP001`.
2. `get_current_employee` resolves EMP001, or stops with 400.
3. `get_ticket` loads `tickets.json` and finds `TCK-1001`, or stops with 404.
4. `rules.employee_owns_ticket` compares owners, and stops with 403 on a mismatch.
5. Otherwise the ticket is returned with status 200.

## 10. Open items

- **No blockers.** The baseline passes from the project `.venv` with no
  changes.
- Cosmetic: `tests/test_tickets.py` is missing one blank line before
  `test_missing_ticket_returns_404` (PEP 8). It was left as-is because
  the baseline files are not to be edited.
- `README.md` says Python 3.11 and port 8000. Course materials use
  3.12 (allowed) and 8123. The README was not changed.
- `.gitignore` (`.training/` line) and the two Day 1 docs are still
  uncommitted, as requested.
