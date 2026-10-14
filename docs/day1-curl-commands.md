# Day 1 curl Commands

Six requests against the local training server at
`http://127.0.0.1:8123`. Employee A (`EMP001`, Dana Whitfield) is the
caller for every profile and ticket scenario. Ownership comes from
[`data/tickets.json`](../data/tickets.json): A owns `TCK-1001`,
Employee B (`EMP002`) owns `TCK-1002`, and `TCK-9999` does not exist.
See [`day1-local-map.md`](day1-local-map.md) for the full map.

**Before you start:** in a separate terminal, start the server and
leave it running:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8123 --reload
```

## Verification status

| Platform | Status |
| --- | --- |
| Windows PowerShell, `C:\WINDOWS\system32\curl.exe` 8.21.0 | **Verified 2026-10-04.** All six statuses observed. |
| Git Bash curl 8.7.1 (`-K` config files) | **Verified 2026-10-04.** All six statuses observed. |
| macOS `curl` | **Unverified** (no Mac available). The commands use only standard curl flags. |

## Flags and headers used

| Piece | Meaning |
| --- | --- |
| `curl.exe` | In PowerShell, always type `.exe`. Windows PowerShell 5.1 has a `curl` alias for `Invoke-WebRequest`, which takes different flags. |
| `-i` | Include the response status line and headers in the output, so you can *see* `HTTP/1.1 403 Forbidden`. |
| `-s` | Silent: hide the progress meter. |
| `-H "X-Demo-Employee-ID: EMP001"` | The training identity header. The API treats the caller as EMP001. It is **not** authentication: there is no secret, and anyone can type any ID. |
| `-w "\nHTTP_STATUS=%{http_code}\n"` | Print the status code on its own line at the end. |
| `-K <file>` | Read all of the above from a config file in `.training/day1/`. |

No cookies, tokens, passwords or `.env` values are involved. The
starter needs none.

## 1. Health: expect 200

Route `GET /health` is public, so no header is sent.

```powershell
curl.exe -i -s http://127.0.0.1:8123/health
```
```bash
curl -i -s http://127.0.0.1:8123/health
```
Observed: `200 OK`, `{"status":"ok","service":"northstar-it-service-desk"}`

## 2. Employee A profile: expect 200

Route `GET /employees/me` returns whoever the header names.

```powershell
curl.exe -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/employees/me
```
```bash
curl -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/employees/me
```
Observed: `200 OK`, the EMP001 / Dana Whitfield object.

## 3. VPN status: expect 200

Route `GET /services/vpn/status` is public. The header is sent so the
request matches the other Employee A requests, but the route ignores it.

```powershell
curl.exe -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/services/vpn/status
```
```bash
curl -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/services/vpn/status
```
Observed: `200 OK`, `"status":"operational"`, `"updated_at":"2026-09-25T08:00:00Z"`.

## 4. Own ticket: expect 200

Route `GET /tickets/TCK-1001`. `data/tickets.json` lists EMP001 as the owner.

```powershell
curl.exe -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/tickets/TCK-1001
```
```bash
curl -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/tickets/TCK-1001
```
Observed: `200 OK`, the TCK-1001 ticket with `"employee_id":"EMP001"`.

## 5. Another employee's ticket: expect 403

Route `GET /tickets/TCK-1002`. The ticket exists but is owned by EMP002, so A is refused (BR02).

```powershell
curl.exe -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/tickets/TCK-1002
```
```bash
curl -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/tickets/TCK-1002
```
Observed: `403 Forbidden`, `{"detail":"You may not view another employee's ticket."}`

## 6. Missing ticket: expect 404

Route `GET /tickets/TCK-9999`. The ID is well-formed but absent, so the
404 check runs before the ownership check (BR03).

```powershell
curl.exe -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/tickets/TCK-9999
```
```bash
curl -i -s -H "X-Demo-Employee-ID: EMP001" http://127.0.0.1:8123/tickets/TCK-9999
```
Observed: `404 Not Found`, `{"detail":"Ticket not found: TCK-9999"}`

## Same requests from the config files

Run these from the project root. The files live in `.training/day1/`
and are git-ignored.

```powershell
curl.exe -K .training/day1/01-health.curl
curl.exe -K .training/day1/02-profile.curl
curl.exe -K .training/day1/03-vpn.curl
curl.exe -K .training/day1/04-own-ticket.curl
curl.exe -K .training/day1/05-other-ticket.curl
curl.exe -K .training/day1/06-missing-ticket.curl
```

On macOS, use `curl` instead of `curl.exe`.

## Summary

| # | Scenario | Expected (starter) | Observed | Match |
| --- | --- | --- | --- | --- |
| 1 | Health | 200 | 200 | ✅ |
| 2 | Profile (A) | 200 | 200 | ✅ |
| 3 | VPN | 200 | 200 | ✅ |
| 4 | Own ticket (A → TCK-1001) | 200 | 200 | ✅ |
| 5 | Other ticket (A → TCK-1002) | 403 | 403 | ✅ |
| 6 | Missing ticket (A → TCK-9999) | 404 | 404 | ✅ |

No contract discrepancies were found. Extra check: omitting the header
on `/employees/me` returns `400` with `{"detail":"Missing required header: X-Demo-Employee-ID"}`.
