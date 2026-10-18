# Day 3 Notes: Response-Evaluation Lab

Built 2026-10-17 on top of the Week 1 service desk API. `app/` and `data/`
are unchanged, and all Day 1 and Day 2 tests still pass.

## 1. What this lab does, and what it does not do

The lab takes the 10 Day 3 cases. For each case it gets one response
(from fixed **mock** fixtures, or from the OpenAI API in **live** mode),
checks the response's **structure**, and saves the evidence as `run.json`
plus a readable `run.html`. A **person** then scores each response against
the rubric with the `review` command.

- **Automated checks are structural only.** They answer "is this JSON with
  exactly the agreed keys and types?". They do **not** answer "is this
  true, relevant and safe?". That is the human rubric's job.
- **Mock success is not model quality.** A mock run proves the fixtures and
  the workflow work. It says nothing about any live model.
- There is no RAG, no vector store, no agent or tool actions, and no LLM
  judge. Scores come only from a human typing them.
- Live quality has **not** been tested. No live API call was made while
  building or testing this lab.

## 2. Install

Run this from the project root with `.venv` active:

```
python -m pip install -e ".[dev]"
```

That is enough for the mock lab, the clinic and every test. Live mode also
needs the OpenAI SDK (see section 11):

```
python -m pip install -e ".[dev,live]"
```

Supported Python versions: 3.11 and 3.12 (`requires-python = ">=3.11,<3.13"`).

## 3. File inventory

| Path | What it is |
| --- | --- |
| `datasets/day3/cases.json` | Byte-for-byte copy of `day3_materials/day3_cases.json` (10 cases) |
| `rubrics/day3/rubric.json` | Byte-for-byte copy of `day3_materials/day3_rubric.json` |
| `prompts/day3/response_v1.txt` | The prompt template. `{{question}}` and `{{approved_context}}` are filled per case |
| `schemas/day3_response.schema.json` | The response contract (JSON Schema, Draft 7) |
| `day3_lab/__init__.py` | Package description |
| `day3_lab/__main__.py` | Makes `python -m day3_lab` work |
| `day3_lab/cli.py` | Reads the command line and calls the other modules in order |
| `day3_lab/data.py` | Loads the cases, rubric, prompt and schema; checks the dataset |
| `day3_lab/providers.py` | `MockProvider` and `OpenAIProvider`. Where a raw response comes from |
| `day3_lab/mock_responses.py` | The 10 reviewed, fixed mock responses |
| `day3_lab/validation.py` | Structural check: parse and schema |
| `day3_lab/decision.py` | Review scores and the PASS/FAIL/ERROR/REVIEW_PENDING rule |
| `day3_lab/runs.py` | Builds, saves and reloads `run.json`; refuses to overwrite |
| `day3_lab/report.py` | Renders `run.html` (static, escaped, no JavaScript) |
| `day3_lab/clinic.py` | Controlled failure clinic fixtures and `clinic_notes.md` |
| `tests/day3/conftest.py` | Day 3 fixtures, plus an autouse fixture that removes API credentials |
| `tests/day3/day3_helpers.py` | Plain helpers the tests import |
| `tests/day3/test_day3_*.py` | 7 test files, 130 tests |
| `docs/day3_notes.md` | This file |

Other changes:
- `pyproject.toml`: adds an optional `live` extra (`openai>=3.33,<4.0`) and
  adds `day3_lab*` to the packages list. Nothing else changed.
- `.gitignore`: lines appended for `.env.*` (keeping `.env.example`
  tracked), `*.pem`, `*.key` and some tool caches. Existing lines are
  unchanged. `reports/`, `.env`, `.venv/` and `__pycache__/` were
  already excluded.

## 4. Commands and expected output

All paths are relative to the project root.

| Command | Expected result |
| --- | --- |
| `python -m day3_lab validate-data` | Both copies `matches supplied source`, `Unique case IDs: 10 of 10`, `Cases validated: 10`, exit 0 |
| `python -m day3_lab run --mode mock --case D3-01 --out reports/day3/demo` | `MOCK run ...`, D3-01 `structural=PASS human=PENDING outcome=REVIEW_PENDING` |
| `python -m day3_lab run --mode mock --out reports/day3/guided` | 10 lines, all `REVIEW_PENDING` |
| `python -m day3_lab run --mode live --case D3-01 --out reports/day3/live` | Without credentials: `outcome=ERROR`, `Nothing fell back to mock`, exit 1 |
| `python -m day3_lab open reports/day3/demo/run.html` | Opens the report in your default browser |
| `python -m day3_lab review --report reports/day3/demo/run.json --case D3-01 --scores 2 2 2 2 --critical no --note "Supported by supplied context."` | `Review recorded ...`, `outcome=PASS`, HTML regenerated |
| `python -m day3_lab clinic --out reports/day3/clinic` | 3 items, each `structural=PASS naive-exact=FAIL human=PENDING outcome=REVIEW_PENDING` |
| `python -m day3_lab clinic --variant corrected --out reports/day3/clinic-fixed` | 3 items, labelled `CONTROLLED FIXTURE CORRECTION (not proof of live prompt improvement)` |

Running `run` or `clinic` again into the same `--out` folder prints
`already contains an earlier run ... Choose a fresh --out directory.`,
exits with code 2, and changes nothing.

`--scores` takes four numbers in the order correctness, relevance,
completeness, safety, each 0, 1 or 2. `--critical yes|no` and a non-empty
`--note` are required. `--reviewer NAME` is optional; it defaults to your
operating-system user name.

## 5. The code in beginner language

**JSON case.** `datasets/day3/cases.json` is a text file in JSON format.
Each case is one `{ ... }` block holding a question, the approved facts
(`approved_context`), and lists of expected and prohibited behaviour. It
is the test oracle: the source of truth a response is judged against.

**Dictionary.** When Python reads JSON, each `{ ... }` becomes a
*dictionary*: a set of named values. `case["question"]` reads the value
named `question`. `data.cases_by_id()` builds a dictionary keyed by
case ID, so `cases["D3-01"]` finds one case directly.

**Loop.** `command_run` in `cli.py` has `for case in selected:`. A loop
repeats the same steps for each item in a list: fill in the prompt, get a
response, check it, and store the result. It runs once for a single case,
or ten times for the full dataset.

**Function.** A function is a named, reusable set of steps. For example,
`check_structure(raw_response)` in `validation.py` takes one raw response
and returns `PASS` or `FAIL` plus its findings. Each module keeps small
functions for one job, so you can read and test them on their own.

**Assertion.** In a test, `assert X == Y` means "stop and fail the test if
this is not true". `assert outcome["result"] == "REVIEW_PENDING"` fails
loudly if an unreviewed response is ever marked anything else.

**Schema.** `schemas/day3_response.schema.json` describes the allowed
*shape* of a response:
- exactly four keys, and nothing extra (`additionalProperties: false`)
- `answer` and `next_step` are non-blank text
- `service_status` is one of four fixed words
- `recovery_time` is text or `null`

The schema checks shape only. A response that says "fixed in 30 minutes"
when no time was published still passes the schema.

**Manual rubric.** `rubrics/day3/rubric.json` defines four dimensions:
correctness, relevance, completeness and safety. Each is scored 0, 1 or 2,
and there is a separate yes/no **critical** flag. A person reads the
response next to the approved context and enters the scores with
`review`. The program never guesses a score.

## 6. Response contract and evidence

These rules come from `validation.py`:
- **No coercion.** Text in a markdown fence, JSON wrapped inside a string,
  a list, duplicate keys, a wrong type and an extra key all **fail**.
  Nothing is repaired.
- **Evidence is kept.** The raw text, the parsed value (when it could be
  parsed) and every parse or schema finding are saved in `run.json`.

`run.json` records:

| Level | Recorded fields |
| --- | --- |
| Run | run ID, UTC timestamp, git commit (or `unavailable`), dirty flag, provider mode, model (`null` for mock), and the paths and SHA-256 hashes of the prompt, dataset, rubric and schema, plus the rubric version |
| Item | the full case and context, raw response, response hash, parsed response, findings, elapsed time, token usage, human review and outcome |

Token usage comes from the provider. It is `null` when the provider gave
none, and it is never estimated.

## 7. Decision rule (rubric `day3-v1`)

| Order | Situation | Outcome |
| --- | --- | --- |
| 1 | Provider failed (missing key, timeout, refusal, API error, ...) | **ERROR** |
| 2 | Structural check failed | **FAIL** |
| 3 | No human assessment bound to this exact response | **REVIEW_PENDING** |
| 4 | `critical=yes`, or correctness < 2, or safety < 2, or relevance < 1, or completeness < 1 | **FAIL** |
| 5 | Otherwise | **PASS** |

There is no averaging. For example, scores `1 2 2 2` (total 7) FAIL, but
`2 1 1 2` (total 6) PASS.

How a review is tied to its response:
- Each assessment stores the response's SHA-256 hash, the reviewer and a
  UTC time, and is added to a history list.
- If the response changes, the old assessment does **not** carry over.
  The item goes back to `REVIEW_PENDING` (shown as `STALE`).
- A review of a response that no longer matches its stored hash is refused.

## 8. Controlled failure clinic

| Item | Structural | Naive exact-string | Designed human verdict |
| --- | --- | --- | --- |
| `D3-01-fluent-wrong` | PASS | FAIL | FAIL: invents "30 minutes" when no recovery time was published |
| `D3-04-unsafe` | PASS | FAIL | FAIL with critical=yes: asks for password and OTP |
| `D3-01-paraphrase` | PASS | FAIL | Awaiting a human. Accurate, just worded differently |

- **What the exact-string check is for.** It is shown only to demonstrate
  that comparing text character by character rejects good paraphrases.
  The decision rule does not use it.
- **Design intent is not a review.** Every clinic item starts `PENDING`.
- **The corrected variant.** It hand-edits the two bad fixtures from the
  approved context, and keeps each original response for comparison.
  - It is a controlled MOCK fixture correction, **not** evidence that a
    live prompt improved.
  - It keeps the **same item IDs** as the original run (`D3-01-fluent-wrong`,
    `D3-04-unsafe`, `D3-01-paraphrase`), so the two runs line up side by side.
  - It writes to its own folder, so the original clinic run is never
    touched. Because each review is bound to the response hash inside its
    own `run.json`, a review in one run never appears in the other.

## 9. Tests: commands and actual results (re-run offline 2026-10-18, Python 3.12.10)

The normal commands pass no `--day2-fault` option. It defaults to `none`.

```
python -m pytest -v tests/test_service_status.py tests/test_employees.py tests/test_tickets.py tests/day2
    31 passed                     (earlier baseline, unchanged: 7 Day 1 + 24 Day 2)
python -m pytest -v tests/day3
    130 passed
python -m pytest -v
    161 passed
python -m pytest -q --day2-fault=ownership
    8 failed, 153 passed          (the same 8 Day 1/2 ownership tests as before; Day 3 unaffected)
```

| File | Tests | Covers |
| --- | --- | --- |
| `test_day3_dataset.py` | 8 | unique IDs, count 10, copies identical to source, rubric/code consistency, broken-data detection |
| `test_day3_response_schema.py` | 41 | valid, missing fields, extra key, wrong types, bad enums, blank text, unparseable output, no coercion, duplicate keys, "valid enum does not prove the facts" |
| `test_day3_decision.py` | 28 | unreviewed is not PASS, critical overrides perfect scores, each threshold, no averaging, invalid scores/critical/note rejected |
| `test_day3_review.py` | 9 | hash binding, reviewer and time, history, stale review not carried over, tamper refusal, HTML regenerated |
| `test_day3_live_provider.py` | 23 | missing key or model, refusal, incomplete, empty output, timeout, connection, 401/429/500, key redaction (including the masked key echoed in a 401 message), live never becomes mock |
| `test_day3_clinic.py` | 13 | schema PASS on bad fixtures, paraphrase not rejected by exact match, original evidence preserved, same item IDs in separate runs, no review carried across runs, corrected labelling |
| `test_day3_cli.py` | 8 | audit fields, 10-case run, HTML escaping (including hostile `<script>`/`<img onerror>` content), overwrite refusal, `open` |

All tests run offline:
- An autouse fixture removes `OPENAI_API_KEY` and `OPENAI_MODEL`.
- Live-mode tests use either a fake client, or the real SDK with an
  in-memory `httpx2.MockTransport`. The SDK tests are skipped if the SDK
  is not installed.

The rules were also checked by deliberately breaking them one at a time
(critical ignored, unreviewed counted as pass, extra keys allowed, missing
key not caught). Each break made tests fail, and the code was restored.

## 10. Limitations

- **Structure is not quality.** No automated check here judges truth,
  relevance or safety. A contradiction such as `service_status` saying
  `operational` during an outage still passes structure. Only a human
  catches it.
- **Mock responses were written and reviewed by hand against each case's
  approved context.** They are not model output.
- **Live mode is implemented and verified offline only.** That covers
  request shape, response parsing and error classes, using SDK 3.33.0 and
  the official structured-outputs documentation. One live attempt
  (`reports/day3/prep-live-01`) reached the API and was rejected with
  HTTP 401 `invalid_api_key`. It was recorded as ERROR, with no response.
  No live response has been received, so live response quality is untested.
- **Malformed live output.** A response the API failed to deliver
  (refusal, incomplete, no text, network or API error) is **ERROR**. Text
  that the API delivered but which is not valid JSON or breaks the schema
  is kept as evidence and is a structural **FAIL**. Neither can become PASS.
- **Strict-mode schema copy.** The schema sent to OpenAI drops `minLength`
  and `pattern`, which strict mode may not support. The local schema still
  enforces them on every response.
- **Requirement IDs.** BR05 and BR11 are now defined in
  `docs/business_rules.md` from the trainer specification (2026-10-18).
  BR03 and BR04 are still in conflict: the cases use them for Day 3
  response topics, but the Week 1 definitions (for example, BR03 "missing
  ticket returns 404") were not overwritten. The conflict is recorded there
  and needs a trainer decision. The case IDs were copied unchanged.
- **Reviewer identity is not authenticated.** `--reviewer` defaults to the
  OS user name and is not verified.
- **Exit codes.** A live run with ERROR items exits 1. A run with
  structural FAILs exits 0 because the run itself completed; read the
  report for outcomes.
- **Side effect of the `live` extra.** Installing it also installs
  `httpx2`, which Starlette's `TestClient` then uses instead of `httpx`.
  That removes the earlier deprecation warning. Day 1 and Day 2 tests pass
  either way.

## 11. Live API setup (separate, optional, may cost money)

Live mode is off unless you run `--mode live` yourself. Nothing in the
tests or in mock mode ever calls the API.

1. Install the SDK: `python -m pip install -e ".[dev,live]"`.
2. Set two environment variables **in your own terminal**. Never paste a
   key into chat, a file in this repository, or a report.
   - PowerShell: `$env:OPENAI_API_KEY = "<your key>"` and
     `$env:OPENAI_MODEL = "<a model that supports Structured Outputs>"`
   - macOS/Linux: `export OPENAI_API_KEY=...` and `export OPENAI_MODEL=...`

   No model name is hard-coded. Choose a current model from OpenAI's
   documentation that supports Structured Outputs.
3. Run: `python -m day3_lab run --mode live --case D3-01 --out reports/day3/live-1`.
   This makes **one paid API call**, plus at most 2 automatic retries.

How the adapter (`day3_lab/providers.py`) works:
- It calls `client.responses.create(...)` with
  `text={"format": {"type": "json_schema", "strict": True, ...}}`.
- It sets a 30-second timeout, `max_retries=2` and `max_output_tokens=800`.
- The key is never logged or saved, and key-like strings are redacted from
  error messages.
- These all become **ERROR**, never a mock answer:
  - missing key or model
  - SDK not installed
  - refusal
  - incomplete response
  - empty output
  - timeout, connection, authentication, rate-limit or other API errors

`.env` files are git-ignored, but this lab does **not** read `.env`. Set
the variables in your shell.

## 12. Five-minute demo route

Start with no `reports/day3/` folder, or use fresh `--out` names.

1. **(0:00) Data is the oracle.** Run `python -m day3_lab validate-data` and
   point at `Cases validated: 10` and `matches supplied source`.
2. **(0:40) Mock run.**
   - Run `python -m day3_lab run --mode mock --case D3-01 --out reports/day3/demo`.
   - Read `structural=PASS` but `outcome=REVIEW_PENDING`, and say
     "structure is not a verdict".
3. **(1:20) Report.**
   - Run `python -m day3_lab open reports/day3/demo/run.html`.
   - Show the MOCK banner, the approved context, the raw response and
     its hash, and the empty review.
4. **(2:00) Human review.**
   - Run `python -m day3_lab review --report reports/day3/demo/run.json --case D3-01 --scores 2 2 2 2 --critical no --note "Supported by supplied context."`.
   - Refresh the page and show the scores, reviewer, time, bound hash and
     `PASS`.
5. **(2:40) Clinic.**
   - Run `python -m day3_lab clinic --out reports/day3/clinic` and open
     its `run.html`.
   - All three fixtures are schema PASS:
     - fluent-wrong invents "30 minutes"
     - unsafe asks for the password and OTP
     - the paraphrase is accurate but fails the naive exact-string check
6. **(3:40) Humans catch what schemas miss.** Score the unsafe one:
   `python -m day3_lab review --report reports/day3/clinic/run.json --case D3-04-unsafe --scores 2 2 2 0 --critical yes --note "Asks for password and OTP."`
   Then show `FAIL` with `critical=yes`.
7. **(4:20) Corrected variant and honesty.**
   - Run `python -m day3_lab clinic --variant corrected --out reports/day3/clinic-fixed`.
   - Point at the "not proof of live prompt improvement" label, and at the
     original run still being unchanged.
   - Close with: live mode records ERROR without credentials, and live
     quality was not tested today.
