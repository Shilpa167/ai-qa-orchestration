# Day 4 Notes: AI Response Evaluation, Part 2

Built 2026-10-18 on top of Days 1–3. `app/`, `data/` and the Day 3 lab
(`day3_lab/`) are unchanged. All earlier tests still pass.

## 1. What Day 4 adds, and why

Day 3 scored responses by hand. Day 4 asks: **can an LLM judge help, and
how far can we trust it?**

| Activity | Command | Question it answers |
| --- | --- | --- |
| Judge fixed responses | `judge` | What does an LLM judge say about eight known responses? |
| Calibrate | `calibrate` | Does the judge agree with **confirmed** human labels? |
| Compare prompts | `compare` | Does prompt B produce better answers than prompt A? |
| Repeat | `repeat` | How much do results vary when the same request is repeated? |
| Human review | `review-fixed`, `review-generated` | What does a person decide? (Only humans create labels.) |

Key ideas:

- A **judge score is a machine assessment**, never a human label.
- **PASS/FAIL is computed in code** from the four scores and critical
  violations. The judge is never asked for a verdict, and a threshold it
  chooses is never accepted.
- The eight **proposed labels** in `datasets/day4/human_labels.json` are
  trainer suggestions. They stay **unconfirmed** until a named person
  records a review.
- **Every run is new evidence** in its own folder. Nothing is overwritten.

## 2. Setup (existing environment)

From the project root:

**macOS / Linux**
```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"          # replay and tests
python -m pip install -e ".[dev,live]"     # adds the OpenAI SDK for live mode
```

**Windows PowerShell**
```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pip install -e ".[dev,live]"
```

Re-running the install once makes the new `training_day4` package
importable from anywhere. Commands also work from the project root without
it.

## 3. Configuration for live mode

| Variable | Required | Meaning |
| --- | --- | --- |
| `OPENAI_API_KEY` | live only | Your API key. **Keep it in your terminal environment, never in Git.** |
| `OPENAI_MODEL` | live only | The model that generates responses (and judges, unless the next one is set) |
| `OPENAI_JUDGE_MODEL` | optional | A separate judge model. If unset, `OPENAI_MODEL` is used, and the report says so |

No model name is built in. Use a model your account can access that
supports Structured Outputs; the judge uses them. The project does **not**
read `.env` files, so set the variables in the terminal.

**macOS / Linux**
```bash
export OPENAI_API_KEY='<your key>'
export OPENAI_MODEL='<model id>'
export OPENAI_JUDGE_MODEL='<model id>'     # optional
```

**Windows PowerShell**
```powershell
$env:OPENAI_API_KEY = '<your key>'
$env:OPENAI_MODEL = '<model id>'
$env:OPENAI_JUDGE_MODEL = '<model id>'     # optional
```

Use single quotes and nothing else inside them. A stray quote character
inside the key caused the Day 3 `invalid_api_key` error.

## 4. Commands

Every command that can call the API needs an explicit `--mode`. There is no
default. `--cases` accepts `all` or individual IDs, for example
`--cases D4-01 D4-06`.

| Command | What it does | Calls the API? |
| --- | --- | --- |
| `python -m training_day4 --help` | Lists commands | no |
| `python -m training_day4 validate` | Checks data, labels, references, prompts, schemas and fixtures; counts confirmed vs proposed labels | no |
| `python -m training_day4 show-case --case D4-02` | Shows one case, its fixed response, rubric, proposed label and confirmed reviews | no |
| `python -m training_day4 access-check --mode live` | **Billable** preflight: one tiny call per distinct model | **yes** |
| `python -m training_day4 judge --mode replay --cases all` | Judges the fixed responses with authored fixtures | no |
| `python -m training_day4 judge --mode live --cases all` | Judges the fixed responses: 8 judge calls | **yes** |
| `python -m training_day4 calibrate --run latest-fixed` | Compares the newest fixed-response judge run with confirmed labels | no |
| `python -m training_day4 calibrate --run <RUN_ID>` | Same, for an explicit run | no |
| `python -m training_day4 compare --mode replay --cases all` | Prompt A vs B with authored fixtures | no |
| `python -m training_day4 compare --mode live --cases all` | Prompt A vs B: normally 16 generation + 16 judge calls | **yes** |
| `python -m training_day4 repeat --mode replay --prompt B --cases D4-01 D4-06 D4-08 --runs 3` | Repeat workflow with authored variants | no |
| `python -m training_day4 repeat --mode live --prompt B --cases D4-01 D4-06 D4-08 --runs 3` | Normally 9 generation + 9 judge calls (`--prompt A` also works) | **yes** |
| `python -m training_day4 summary` | Which activities ran, live and replay listed separately | no |
| `python -m training_day4 review-fixed ...` | Records **your** review of one fixed response (section 6) | no |
| `python -m training_day4 review-generated ...` | Records **your** review of one generated response (section 7) | no |

Exit codes: 0 means success. 1 means the run finished but has errors (for
example, the replay repeat has one deliberate evaluation error). 2 means
the command could not run.

## 5. Replay vs live

**Replay** uses `datasets/day4/replay_fixtures.json`:
- Every response and judge output in it was **written by hand**.
- Replay needs no key and no network.
- It records **no latency and no token usage**; reports say
  "not measured (replay)", never zero.
- The replay judge looks up an authored output by the response text. It
  **never reads the labels**. Some authored judge outputs deliberately
  disagree with the proposals so that calibration has something to show
  (for example, an over-strict FAIL on the D4-06 paraphrase).
- One authored judge output for the repeat command is deliberately invalid,
  to show that malformed output becomes an **evaluation error**.
- Replay results, including any prompt "preference", reflect the authored
  fixtures. They demonstrate the workflow, not a model. Fixed fixtures
  cannot show live-model variation.

**Live** uses the OpenAI Responses API with the configured models:
- It records the returned model ID, latency and token usage when the API
  provides them.
- Only transient errors are retried: timeouts, connection errors, rate
  limits and HTTP 408/409/5xx. There are at most 3 attempts per call; the
  SDK's own retries are turned off so every attempt is counted.
- Malformed output and low scores are **never** retried.
- A live failure is recorded as an error and **never** switches to replay.
- The response generator receives only the prompt, the employee request
  and the approved context. The judge receives only an opaque response ID,
  the request, the context, the candidate response and the general rubric.
  It never sees labels, answer keys, the case ID or prompt A/B.

Live mode has **not** been run while building Day 4. No authorised live
test has been performed, so it is not known whether live access works with
your key and models.

## 6. Reviewing and confirming fixed-response labels

Use [`day4_review_worksheet.md`](day4_review_worksheet.md), or
`show-case`, to read each case. Then record **your own** decision on one
line:

```
python -m training_day4 review-fixed --case D4-02 --reviewer "<your name>" --scores 0 2 0 0 --critical none --reason "Invents a 30-minute recovery time; no status-page step."
```

- Scores go in the order correctness, relevance, completeness,
  safety_and_policy, each 0, 1 or 2.
- `--critical none`, or one or more of `SECRET_REQUEST`,
  `CROSS_USER_DISCLOSURE`, `UNVERIFIED_ACTION_CLAIM`,
  `UNSAFE_SECURITY_ADVICE`.
- To **confirm** a proposal, type its scores. To **correct** it, type
  different scores. Nothing is accepted automatically.
- The review is appended to `datasets/day4/confirmed_reviews.json` with your
  name, the time and hashes of the response, case context and rubric. The
  proposals file is never changed.
- If any of those change later, the review is **stale** and is not used.
- To change your mind, record a new review. The latest current one is used.
- Check progress with `python -m training_day4 validate` or `summary`.
- After confirming, run `judge` (if needed) and then
  `calibrate --run latest-fixed` to see real agreement figures.

## 7. Reviewing generated answers

Each `compare` or `repeat` run's `results.md` lists response IDs. Review one:

```
python -m training_day4 review-generated --run <RUN_ID> --response <RESPONSE_ID> --reviewer "<your name>" --scores 2 2 2 2 --critical none --reason "<why>"
```

- The review is saved to `reports/day4/<RUN_ID>/human_reviews.json`.
  `run.json` is not changed.
- Fixed-response labels are never reused for generated answers.
- A prompt comparison stays **provisional** until its generated answers
  have been reviewed by a human.

## 8. Reading the reports

Each run folder `reports/day4/<RUN_ID>/` contains:

- **`run.json`: the full evidence.**
  - Mode, timestamps, git commit and dirty flag.
  - Dataset, rubric, schema and prompt snapshots with hashes (prompt texts
    included).
  - Model configuration, settings and the A/B seed.
  - Every observation, with its opaque response ID, response text and hash,
    and per-call attempts, retries, latency, usage and errors.
  - The sanitised raw judge output and its validation errors, plus scores,
    reasons and the computed verdict.
- **`results.md`: a readable summary.** It has counts, per-case tables,
  judge reasons, the compare preference or repeat statistics, and the review
  instructions.

Notes:
- `calibrate` writes its own folder. It references its source run by ID and
  hash and never edits it.
- `latest-fixed` uses only the newest fixed-response judge run. If that run
  is unfinished, unreadable or tied with another, it refuses rather than
  using an older run.
- `reports/` is git-ignored.

## 9. Preserving sanitised evidence in Git

Reports are ignored by default. To keep **selected** evidence, force-add
specific files only, for example a judge run's results and a calibration's
results:

```
git add -f reports/day4/<judge-fixed-run-id>/results.md reports/day4/<calibrate-run-id>/results.md
```

Check a file before adding it. Reports never contain the API key, but look
anyway. **Never force-add the whole `reports/` folder.**

## 10. Business-rule references

`validate` checks that every case's requirement IDs are defined in
`docs/business_rules.md`. On 2026-10-18:
- BR05, BR06 and BR11 match the Day 4 meanings. BR06 was added from the
  trainer-provided specification; nothing was renumbered.
- BR02 is compatible but narrower (tickets only).
- **BR03 and BR04 conflict**: their Week 1 meanings differ from the Day 4
  meanings. They were reported in `business_rules.md` and not changed. This
  needs a trainer decision.

## 11. Dataset limitations

- These are **eight fixed-response examples, not eight independent
  scenarios**.
- D4-01 and D4-02 share one input. D4-06 and D4-07 share one input. Reports
  label them as separately identified but dependent observations.
- The development/holdout split supports classroom discipline only. Do not
  tune prompts against holdout results.
- No statistical independence or production reliability is claimed. The
  broader Week 2 target is at least 15 genuinely human-labelled responses;
  this dataset does not meet it, and examples were not duplicated to pretend
  otherwise.

## 12. Tests (actual results, 2026-10-18, Python 3.12.10, offline)

```
python -m pytest -v                       226 passed  (7 Day 1 + 24 Day 2 + 130 Day 3 + 65 Day 4)
python -m pytest -v tests/day4            65 passed
python -m training_day4 validate          VALID; 8 proposed (unconfirmed), 0 confirmed
python -m day3_lab validate-data          Cases validated: 10
```

| File | Tests | Covers |
| --- | --- | --- |
| `test_day4_data.py` | 7 | supplied cases preserved, references defined, proposed labels never treated as confirmed |
| `test_day4_judge.py` | 24 | judge and generator inputs exclude labels/answer keys/prompt labels, invalid judge output is an error, critical violations override perfect scores, PASS rule |
| `test_day4_live.py` | 13 | missing credentials never fall back to replay, bounded retries for transient errors only, no retry on low scores or malformed output, judge-model configuration, access check, network guard |
| `test_day4_runs.py` | 10 | no overwrites, repeat keeps every result and error, strict `latest-fixed`, calibration with 0 confirmed labels and missing results, summary |
| `test_day4_reviews.py` | 11 | explicit named reviews, proposal untouched, stale detection (response, rubric), generated reviews bound to run and response, judge never creates reviews |

Offline protection is in `tests/day4/conftest.py`:
- It clears `OPENAI_API_KEY`, `OPENAI_MODEL` and `OPENAI_JUDGE_MODEL`.
- It blocks every non-loopback connection and DNS lookup.
- It redirects reports and confirmed reviews to temporary copies.
- Live behaviour is tested only with a fake SDK client.
- Day 3's protection is unchanged.

Six safeguards were also broken on purpose, one at a time, to confirm the
tests catch them. Every break failed tests, and the code was restored.

## 13. What remains incomplete

- **Human review:** 0 of 8 fixed-response labels are confirmed. No generated
  answer has been reviewed. Day 4 learning activities are **not** complete.
- **Live mode:** never run. `access-check --mode live` is the first billable
  step, and it is the trainer's decision to run it.
- **Calibration:** only replay calibration exists. It is a workflow
  demonstration, not validation of a judge.
- **Business rules:** BR03 and BR04 still conflict with their Week 1
  meanings.
- **Dataset size:** eight examples are well below the Week 2 target of 15+
  genuinely human-labelled responses.
