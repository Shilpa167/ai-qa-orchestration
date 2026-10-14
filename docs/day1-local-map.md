# Day 1 Local Map

Prepared by inspecting this repository on 2026-10-04 (branch `main`,
commit `276db27`) and verifying locally on Windows 11 with the
project's `.venv` (Python 3.12.10, FastAPI 0.142.2, uvicorn 0.54.0,
pytest 8.4.2). Every path, ID and status below was read from the
files or observed in a live run. Nothing is carried over from older
lesson plans.

## 1. Project at a glance

| Item | Value | Where |
| --- | --- | --- |
| Framework | FastAPI (ASGI), served by uvicorn | [`pyproject.toml`](../pyproject.toml) |
| Entry point | `app.main:app` | [`app/main.py`](../app/main.py) line 13 |
| Python | `>=3.11,<3.13` (3.14 is rejected by pip) | `pyproject.toml` `requires-python` |
| Dependency file | `pyproject.toml` only (no `requirements.txt`) | `[project.dependencies]` + `[project.optional-dependencies].dev` |
| Dependency command | `python -m pip install -e ".[dev]"` | verified |
| Training server port | `8123` (passed to uvicorn, not hard-coded) | see [discrepancies](#7-discrepancies-and-notes) |
| Authentication | **None.** A demo identity header, `X-Demo-Employee-ID` | `app/main.py` lines 24–51 |
| Secrets / `.env` | None needed. Only `.env.example` exists (placeholder for later weeks) | project root |

## 2. File locations

| Path | What it is |
| --- | --- |
| [`app/main.py`](../app/main.py) | The 4 routes, plus the `get_current_employee` dependency (line 27) |
| [`app/rules.py`](../app/rules.py) | `find_employee_by_id` (11), `find_ticket_by_id` (19), `employee_owns_ticket` (27) |
| [`app/data.py`](../app/data.py) | Reads JSON from `data/` (`DATA_DIR`, line 13) |
| [`data/employees.json`](../data/employees.json) | 4 synthetic employees |
| [`data/tickets.json`](../data/tickets.json) | 6 synthetic tickets (each has an `employee_id` owner field) |
| [`data/service_status.json`](../data/service_status.json) | VPN status, returned unchanged |
| [`schemas/ticket.schema.json`](../schemas/ticket.schema.json) | Ticket JSON Schema (`ticket_id` must match `^TCK-[0-9]+$`) |
| [`docs/business_rules.md`](business_rules.md) | BR01–BR04 |
| [`docs/day1-curl-commands.md`](day1-curl-commands.md) | Expanded curl commands for today |
| `.training/day1/*.curl` | Local curl config files (git-ignored, not committed) |

### Day 1 test file paths

These are the tests that exist today. No Day 2 tests have been added.

| Test file | Tests |
| --- | --- |
| [`tests/conftest.py`](../tests/conftest.py) | `client` fixture → `TestClient(app)` |
| [`tests/test_service_status.py`](../tests/test_service_status.py) | `test_health_check_returns_ok` (10), `test_vpn_status_has_defined_status_and_update_time` (17) |
| [`tests/test_employees.py`](../tests/test_employees.py) | `test_get_my_profile_returns_known_employee` (10) |
| [`tests/test_tickets.py`](../tests/test_tickets.py) | `test_get_own_ticket_returns_200` (18), `test_get_other_employees_ticket_returns_403` (25), `test_ticket_matches_schema` (32), `test_missing_ticket_returns_404` (42) |

## 3. API routes

| Method | Route | Needs `X-Demo-Employee-ID`? | Handler |
| --- | --- | --- | --- |
| GET | `/health` | No (public) | `get_health`, line 55 |
| GET | `/employees/me` | Yes | `get_my_profile`, line 61 |
| GET | `/services/vpn/status` | No (public) | `get_vpn_status`, line 67 |
| GET | `/tickets/{ticket_id}` | Yes | `get_ticket`, line 77 |

Swagger UI is at `http://127.0.0.1:8123/docs` while the server is running.

## 4. Identity mechanism (not authentication)

`get_current_employee()` reads the `X-Demo-Employee-ID` header and
looks it up in `data/employees.json`. There is no password, token,
session or signature. Anyone can send any ID, so **this is a training
identity header, not production authentication**. Real systems derive
identity from a verified credential (a session, an OAuth/JWT token,
mTLS), never from a header the client chooses freely.

The order of checks in `GET /tickets/{id}` is: header present → known
employee (400 if not) → ticket exists (404 if not) → caller owns it
(403 if not) → 200.

## 5. Ownership table (read from `data/tickets.json`, not from API responses)

| Role | Employee ID | Name | Owns |
| --- | --- | --- | --- |
| **Employee A** | `EMP001` | Dana Whitfield | `TCK-1001` (open), `TCK-1005` (in_progress) |
| **Employee B** | `EMP002` | Marcus Lee | `TCK-1002` (resolved), `TCK-1006` (resolved) |
| — | `EMP003` | Priya Nair | `TCK-1003` |
| — | `EMP004` | Oliver Grant | `TCK-1004` |

Day 1 scenario IDs:

- A's own ticket: **`TCK-1001`**
- B's ticket (A must be refused): **`TCK-1002`**
- Missing ticket: **`TCK-9999`**. It matches the schema pattern
  `^TCK-[0-9]+$` and doesn't appear in `data/tickets.json`.

## 6. Actual response contracts (verified live on port 8123)

| Scenario | Request | Status | Body |
| --- | --- | --- | --- |
| Health | `GET /health` | 200 | `{"status":"ok","service":"northstar-it-service-desk"}` |
| Profile (A) | `GET /employees/me`, header `EMP001` | 200 | the EMP001 employee object |
| VPN | `GET /services/vpn/status` | 200 | `{"service":"vpn","status":"operational","updated_at":"2026-09-25T08:00:00Z","message":"..."}` |
| Own ticket | `GET /tickets/TCK-1001`, header `EMP001` | 200 | the TCK-1001 ticket object |
| Other's ticket | `GET /tickets/TCK-1002`, header `EMP001` | 403 | `{"detail":"You may not view another employee's ticket."}` |
| Missing ticket | `GET /tickets/TCK-9999`, header `EMP001` | 404 | `{"detail":"Ticket not found: TCK-9999"}` |
| No header | `GET /employees/me` | 400 | `{"detail":"Missing required header: X-Demo-Employee-ID"}` |
| Unknown ID | header `EMP999` | 400 | `{"detail":"Unknown demo employee id: EMP999"}` |

All errors use FastAPI's standard `{"detail": "<message>"}` shape with
`content-type: application/json`. The expected statuses from the
starter (200/200/200/200/403/404) **all match** what we observed.

## 7. Discrepancies and notes

- **Port:** `README.md` and `docs/day2-instructor-map.md` say
  `--port 8000`. The recorded Day 1 starter uses **8123**. The port is
  only a uvicorn command-line flag, so both work. These Day 1 materials
  use 8123, and the README has not been changed.
- **Python version:** the README says 3.11. This machine uses 3.12.10,
  which is allowed. Python 3.14 is rejected by `pip install`.
- **"Unknown employee" uses 400, not 401/403.** This is a deliberate
  training contract (BR01), not a bug. A real API would typically
  return 401 for a missing or invalid credential.
- **No contract mismatches** were found for the six Day 1 scenarios.

## 8. Exact commands

### Run the tests (no server needed)

```powershell
# Windows PowerShell, from the project root
.\.venv\Scripts\Activate.ps1
python -m pytest -v
```

```bash
# macOS
source .venv/bin/activate
python -m pytest -v
```

**pytest uses an in-process client, not a live server.**
`tests/conftest.py` builds `fastapi.testclient.TestClient(app)`, which
calls the ASGI app directly in memory. No test refers to `localhost`,
`127.0.0.1` or port 8123. The suite passes whether or not uvicorn is
running.

Result on 2026-10-04: **7 passed, 1 warning** (a harmless Starlette
deprecation notice about `httpx`).

### Run the local training server (needed only for curl and /docs)

Use a second terminal and keep it open:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8123 --reload
```

Stop it with `Ctrl+C`. To check whether something is already using
the port: `netstat -ano | findstr :8123` (Windows) or
`lsof -i :8123` (macOS).

### Run the curl practice files (server must be running)

```powershell
curl.exe -K .training/day1/01-health.curl
```

```bash
curl -K .training/day1/01-health.curl
```

See [`day1-curl-commands.md`](day1-curl-commands.md) for all six.
