# Day 2 Instructor Map

Prepared on 2026-10-11 and re-verified on 2026-10-14 (branch `main`,
HEAD `0bd7faf`, working tree clean). `0bd7faf` committed the Day 1 docs
(`docs/day1-local-map.md`, `docs/day1-curl-commands.md`), this map,
and the `.training/` line in `.gitignore`. `app/`, `data/`, `schemas/`,
`tests/` and `pyproject.toml` are unchanged since `276db27`.
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

## 2. Baseline result (verified 2026-10-11 and 2026-10-14, this machine)

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

## 7. TEST-ONLY pytest option `--day2-fault` (updated 2026-10-14)

It injects a known defect into the app **for one pytest run only**, so
students can watch unchanged tests fail for the right reason. Nothing is
marked `xfail`.

| Value | Where it is injected | Effect on the real endpoint |
| --- | --- | --- |
| `none` (default) | nothing | the real application |
| `ownership` | `app.rules.employee_owns_ticket` replaced with `lambda ticket, employee_id: True` | cross-employee `GET /tickets/{id}` returns **200 + the foreign ticket** instead of 403 |
| `missing-status` | `app.data.load_tickets` and `app.data.load_service_status` return copies without `status` | ticket and VPN-status responses are **200 with no `status` field** |
| `wrong-status-type` | the same loaders return copies with `"status": 1` | ticket and VPN-status responses are **200 with `"status": 1`** |

The earlier name `ownership-bypass` was replaced by `ownership`. It is now
rejected with `invalid choice: 'ownership-bypass'`, and so is any other
unknown value.

### Isolation and safety

- **Test-only.** Everything lives in the root [`conftest.py`](../conftest.py),
  which only pytest loads. `python -m uvicorn app.main:app` never imports
  it, so a normal application run can never have a fault switched on.
- **Equivalent of an isolated instance.** The app has no factory function,
  so the tests cannot create a second app object. Instead, the autouse
  fixture `day2_fault` uses `monkeypatch.setattr` to swap one function
  inside the app's modules for the duration of **one test**. monkeypatch
  restores the original during teardown, even when the test fails. This
  works because `app/main.py` calls `rules.employee_owns_ticket(...)` and
  `data.load_tickets()` through the module at request time.
  Limitation: the patch covers the whole pytest process while that test
  runs. That is fine for normal pytest and for pytest-xdist, which uses
  separate processes, but it would not be safe for tests running in
  threads.
- **Real endpoint, real response.** Tests still call the actual route
  through `TestClient`. Nothing in a test builds or edits a response.
- **Authentication untouched.** `get_current_employee` is never patched.
  `test_identity_is_still_required_under_any_fault` proves this: it
  passes under `--day2-fault=ownership`.
- **Persistent data untouched.** The faulty loaders return modified
  *copies*. `git diff -- app data` is empty after every fault run.
- **Expected values are independent of the app.** `day2_data.py` and the
  `prepared_tickets` fixture read `data/*.json` directly, not through
  `app/data.py`. A loader fault therefore cannot change what the tests
  expect.

### Why the option is registered at the root

pytest only honours `pytest_addoption` in conftests it loads at startup.
Those are the root conftest and the conftests in, or above, the paths on
the command line. If the option lived only in `tests/day2/conftest.py`,
then `python -m pytest tests/test_tickets.py --day2-fault=ownership`
would fail with `unrecognized arguments`. The root conftest is always
loaded, so Day 1-only runs, full-suite runs and `--help` all see it.

### Verified fault cycle (2026-10-14, full suite; ownership rows re-verified 2026-10-17)

| Run | Result | Tests that fail (and why) |
| --- | --- | --- |
| baseline | **31 passed** | none |
| `--day2-fault=ownership` | **8 failed, 23 passed** | Day 1 `test_get_other_employees_ticket_returns_403`; test_02 `[employee-a-requests-employee-b-ticket]` and `[employee-b-requests-employee-a-ticket]`; test_03 all 4 cross-employee cases; test_04 `[error-403-foreign-ticket]`. All fail with `assert 200 == 403` |
| baseline again | **31 passed** | none |
| `--day2-fault=missing-status` | **7 failed, 24 passed** | test_04 `[ticket-employee-a-own]`, `[ticket-employee-b-own]`, `[service-status]` (`'status' is a required property`); Day 1 `test_ticket_matches_schema` and `test_vpn_status_has_defined_status_and_update_time`; test_02 both own-ticket cases (body differs from prepared record) |
| baseline again | **31 passed** | none |
| `--day2-fault=wrong-status-type` | **7 failed, 24 passed** | the same 7 tests (`1 is not of type 'string'`, `1 is not one of [...]`) |
| baseline again | **31 passed** | none |

**Does FastAPI catch the schema faults first? No.** Verified directly:
under both faults, `GET /tickets/TCK-1001` and `GET /services/vpn/status`
return **200** with the broken body (`status` absent or `1`). The routes
are annotated `-> dict` with no `response_model`, so FastAPI only checks
"is it a dict?", which it is. No validation was disabled. The app simply
has none for response shape, so the schema tests are the only thing
catching this defect.

## 8. Day 2 test layout (created 2026-10-14)

`tests/day2/` inherits the `client` fixture from `tests/conftest.py`
automatically.

| File | Role | Tests |
| --- | --- | --- |
| [`conftest.py`](../conftest.py) (project root) | TEST-ONLY `--day2-fault` option, report header, autouse `day2_fault` fixture | n/a |
| [`tests/day2/day2_data.py`](../tests/day2/day2_data.py) | Helper module: IDs A/B, `TCK-9999`, documented error bodies, protected fields, `tickets_owned_by`, `first_ticket_owned_by`. Reads `data/*.json` directly | n/a |
| [`tests/day2/schema_validation.py`](../tests/day2/schema_validation.py) | Reusable `load_schema`, `schema_errors`, `assert_matches_schema` (Draft 7 + FormatChecker) | n/a |
| [`tests/day2/conftest.py`](../tests/day2/conftest.py) | Fixtures `auth_headers`, `prepared_tickets`, `employee_a_ticket`, `employee_b_ticket` | n/a |
| [`tests/day2/test_01_fixtures.py`](../tests/day2/test_01_fixtures.py) | Fixtures: A and B each read their own ticket | 2 |
| [`tests/day2/test_02_parameterized.py`](../tests/day2/test_02_parameterized.py) | Parametrize: 5 ticket-access cases | 5 |
| [`tests/day2/test_03_ownership.py`](../tests/day2/test_03_ownership.py) | Ownership both directions (4) + identity guard (1) | 5 |
| [`tests/day2/test_04_schema.py`](../tests/day2/test_04_schema.py) | 7 API schema cases + 5 validator examples (not API cases) | 12 |
| [`schemas/employee.schema.json`](../schemas/employee.schema.json), [`service_status.schema.json`](../schemas/service_status.schema.json), [`error.schema.json`](../schemas/error.schema.json) | New contract files, alongside the existing `ticket.schema.json` | n/a |

Total: **24 Day 2 tests**, plus 7 Day 1 tests, makes **31**. Day 1 files
are unchanged. Constants are imported from `day2_data.py` rather than
from a conftest, because importing a conftest directly can load it twice.

### Lesson 1: fixtures (`test_01_fixtures.py`)

| Test | Caller | Ticket (from `data/tickets.json`) | Checks |
| --- | --- | --- | --- |
| `test_employee_a_retrieves_own_ticket` | `EMP001` | `TCK-1001` | 200, `ticket_id`, owner `EMP001` |
| `test_employee_b_retrieves_own_ticket` | `EMP002` | `TCK-1002` | 200, `ticket_id`, owner `EMP002` |

| Fixture | File | Returns | Depends on |
| --- | --- | --- | --- |
| `client` | `tests/conftest.py` (Day 1, reused) | `TestClient(app)`, in-process with no server | none |
| `auth_headers` | `tests/day2/conftest.py` | a function: `auth_headers("EMP001")` gives `{"X-Demo-Employee-ID": "EMP001"}` | none |
| `prepared_tickets` | `tests/day2/conftest.py` | `data/tickets.json` read directly from disk | none |
| `employee_a_ticket` / `employee_b_ticket` | `tests/day2/conftest.py` | first prepared ticket owned by `EMP001` / `EMP002` | `prepared_tickets` |
| `day2_fault` | `conftest.py` (root, autouse) | applies the selected fault; does nothing for `none` | `request`, `monkeypatch` |

Show the fixture order with `python -m pytest -q --setup-show tests/day2/test_01_fixtures.py`.

### Lesson 2: parametrize (`test_02_parameterized.py`)

| Case ID | Caller → ticket | Status | Body asserted | Overlap |
| --- | --- | --- | --- | --- |
| `employee-a-own-ticket` | EMP001 → TCK-1001 | 200 | equals the prepared record | **Overlap:** test_01 A; Day 1 `test_get_own_ticket_returns_200` |
| `employee-b-own-ticket` | EMP002 → TCK-1002 | 200 | equals the prepared record | **Overlap:** test_01 B |
| `employee-a-requests-employee-b-ticket` | EMP001 → TCK-1002 | 403 | documented 403 body + no leak | **New** |
| `employee-b-requests-employee-a-ticket` | EMP002 → TCK-1001 | 403 | documented 403 body + no leak | **Overlap:** Day 1 `test_get_other_employees_ticket_returns_403` |
| `employee-a-requests-missing-ticket` | EMP001 → TCK-9999 | 404 | `{"detail":"Ticket not found: TCK-9999"}` | **Overlap:** Day 1 `test_missing_ticket_returns_404` |

### Lesson 3: ownership (`test_03_ownership.py`)

**Where it is enforced:** `GET /tickets/{id}` in `app/main.py` checks, in
order, identity (400), existence (404), then ownership (403). Only the
last step decides ownership. It is the single line
`return ticket["employee_id"] == employee_id` in
`app/rules.py::employee_owns_ticket`.

| Case ID | Caller → ticket | Expected | Overlap |
| --- | --- | --- | --- |
| `employee-a-requests-TCK-1002-of-employee-b` | EMP001 → TCK-1002 | 403, exact body, no leak | **Overlap:** test_02 A→B |
| `employee-a-requests-TCK-1006-of-employee-b` | EMP001 → TCK-1006 | 403, exact body, no leak | **New** |
| `employee-b-requests-TCK-1001-of-employee-a` | EMP002 → TCK-1001 | 403, exact body, no leak | **Overlap:** Day 1 403 test, test_02 B→A |
| `employee-b-requests-TCK-1005-of-employee-a` | EMP002 → TCK-1005 | 403, exact body, no leak | **New** |
| `test_identity_is_still_required_under_any_fault` | none → TCK-1002 | 400, missing-header body | **New** (fault-safety guard) |

"No leak" means none of the foreign ticket's `subject`, `description`,
`employee_id`, `created_at` or `updated_at` values appears in the
response text.

**What the failure looks like:** under `--day2-fault=ownership`, each
cross-employee case fails at its first assertion with `assert 200 == 403`.
The real endpoint handed the other employee's ticket over. In beginner
terms, the "is this yours?" check was switched off, and the test noticed.

**Beginner explanation to read out:** think of the endpoint as a front
desk with three questions. "Who are you?" (no badge → 400). "Does that
ticket exist?" (no → 404). "Is it yours?" (no → 403). The fault replaces
only the third question with someone who always says "yes". So when
Employee A asks for Employee B's ticket, the desk hands it over with 200.
The test expected 403, so it fails with `assert 200 == 403`. That red
result is the test doing its job: it shows the test would catch anyone
who broke BR02. The guard test still passes, which shows the first
question ("who are you?") was never switched off.

Verified 2026-10-14 and re-verified 2026-10-17 with
`.venv\Scripts\python.exe` (Python 3.12.10): normal run 5 passed; under
`ownership` 4 failed (all cross-employee, `assert 200 == 403`) and 1
passed (the guard); normal run afterwards 5 passed. Full suite on
2026-10-17: 31 passed → 8 failed, 23 passed → 31 passed. `app/` and
`data/` were byte-for-byte identical before and after, and the test file
was not edited between runs.

### Lesson 4: schema (`test_04_schema.py`)

Keywords explained in the file: `"type": "object"` (must be a dict),
`"properties"` (rules per field), `"required"` (fields that must be
present), `"type": "string"` (must be text). Every API case checks the
**status first** and the schema second.

| API case ID | Request | Status | Schema | Overlap |
| --- | --- | --- | --- | --- |
| `employee-profile` | EMP001 → `/employees/me` | 200 | employee | Day 1 profile test (schema is new) |
| `ticket-employee-a-own` | EMP001 → TCK-1001 | 200 | ticket | Day 1 `test_ticket_matches_schema` |
| `ticket-employee-b-own` | EMP002 → TCK-1002 | 200 | ticket | test_01 B (schema is new) |
| `service-status` | `/services/vpn/status` | 200 | service_status | Day 1 VPN test (schema is new) |
| `error-403-foreign-ticket` | EMP001 → TCK-1002 | 403 | error | test_02 / test_03 A→B |
| `error-404-missing-ticket` | EMP001 → TCK-9999 | 404 | error | Day 1 404 test, test_02 |
| `error-400-missing-header` | none → `/employees/me` | 400 | error | **New request** |

The **5 validator examples** in `TestValidatorExamplesNotApiCases` check
plain dictionaries against the ticket schema: valid, missing `required`
field, wrong `string` type, not an `object`, and `jsonschema.validate`
raising. They are teaching aids and are **not counted as API cases**.

Verified per-file cycle: baseline 12 passed → `missing-status` 3 failed
(both tickets + VPN status) → `wrong-status-type` 3 failed (same) →
baseline 12 passed.

### Unique-case count (do not inflate)

| | Tests run | Distinct API request scenarios |
| --- | --- | --- |
| Day 1 | 7 | 6 (health, VPN, profile, A own, B→A, missing). The schema test reuses A own |
| + test_01 | +2 | +1 (B own) |
| + test_02 | +5 | +1 (A→B) |
| + test_03 | +5 | +3 (A→TCK-1006, B→TCK-1005, no-header ticket request) |
| + test_04 | +12 (7 API + 5 examples) | +1 (no-header profile request) |
| **Total** | **31** | **12 distinct scenarios** |

Report Day 2 as **+6 new scenarios**, with many earlier scenarios
re-checked more strongly (full body, no-leak, schema). Do not report it
as "+24 tests".

### Commands (with `.venv` active, from the project root)

```
python -m pytest -v                                                # Day 1 + Day 2: 31 passed
python -m pytest -v tests/day2                                     # Day 2 only: 24 passed
python -m pytest -v tests/test_service_status.py tests/test_employees.py tests/test_tickets.py   # Day 1 only: 7 passed
python -m pytest -v tests/day2/test_01_fixtures.py                 # 2 passed
python -m pytest -v tests/day2/test_02_parameterized.py            # 5 passed
python -m pytest -v tests/day2/test_03_ownership.py                # 5 passed
python -m pytest -v tests/day2/test_03_ownership.py --day2-fault=ownership   # 4 failed, 1 passed
python -m pytest -v tests/day2/test_04_schema.py                   # 12 passed
python -m pytest -v tests/day2/test_04_schema.py --day2-fault=missing-status      # 3 failed, 9 passed
python -m pytest -v tests/day2/test_04_schema.py --day2-fault=wrong-status-type   # 3 failed, 9 passed
python -m pytest -q --day2-fault=ownership                         # full suite: 8 failed, 23 passed
python -m pytest --help                                            # lists --day2-fault and its choices
```

## 9. Request flow (unchanged)

1. A test sends `GET /tickets/TCK-1001` with `X-Demo-Employee-ID: EMP001`.
2. `get_current_employee` resolves EMP001, or stops with 400.
3. `get_ticket` loads `tickets.json` and finds `TCK-1001`, or stops with 404.
4. `rules.employee_owns_ticket` compares owners, and stops with 403 on a mismatch.
5. Otherwise the ticket is returned with status 200.

## 10. Open items

- **No blockers.** Isolated fault injection works in this architecture
  via monkeypatch, with no persistent toggle and no app code changes.
- **Dependency change:** `pyproject.toml` `dev` extra gained
  `rfc3339-validator>=0.1.4,<1.0`. `jsonschema` was already declared.
  Without this package, `"format": "date-time"` was silently ignored.
  Students must re-run `python -m pip install -e ".[dev]"`.
- Day 1 `test_ticket_matches_schema` still calls `jsonschema.validate`
  without a FormatChecker, so it does not check date-time formats. Left
  as-is because Day 1 files are not edited. Day 2's helper does check them.
- Cosmetic: `tests/test_tickets.py` is missing one blank line before
  `test_missing_ticket_returns_404` (PEP 8). Left as-is.
- `README.md` says Python 3.11 and port 8000. Course materials use
  3.12 and 8123. The README was not changed.
- Not committed yet: `conftest.py`, `tests/day2/`, three new
  `schemas/*.json`, `pyproject.toml`, this map.
